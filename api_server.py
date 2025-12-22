#!/usr/bin/env python3
"""
Diarium Automation API Server

REST API untuk menjalankan otomasi Diarium dari web.
Endpoint utama: /diarium/checkout - untuk routine checkout harian

Usage:
    python api_server.py
    
Then access: http://localhost:8080/docs for Swagger UI
"""

import os
import subprocess
import asyncio
from typing import Optional
from datetime import datetime
from enum import Enum

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Diarium Automation API",
    description="API untuk otomasi app Diarium di HP Android",
    version="1.0.0"
)

# Enable CORS for web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== Configuration ==============

class Config:
    ZAI_API_KEY = os.getenv("zai_api_key", "")
    ZAI_BASE_URL = "https://api.z.ai/api/paas/v4"
    ZAI_MODEL = "autoglm-phone-multilingual"
    PYTHON_PATH = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python")
    MAIN_SCRIPT = os.path.join(os.path.dirname(__file__), "main.py")


# ============== Models ==============

class HealthStatus(str, Enum):
    SEHAT = "Sehat"
    KURANG_FIT = "Kurang Fit"
    SAKIT = "Sakit"


class LoginStatus(str, Enum):
    """Status login"""
    LOGGED_IN = "logged_in"
    NOT_LOGGED_IN = "not_logged_in"
    MFA_REQUIRED = "mfa_required"
    LOGIN_FAILED = "login_failed"


class DiariumLoginRequest(BaseModel):
    """Request untuk login Diarium"""
    nik: str = Field(..., description="NIK TelkomGroup", json_schema_extra={"example": "930436"})
    sso_password: str = Field(..., description="Password SSO", json_schema_extra={"example": "password123"})


class DiariumMFARequest(BaseModel):
    """Request untuk input MFA code"""
    mfa_code: str = Field(..., description="Kode MFA 6 digit", json_schema_extra={"example": "123456"})


class ProfileInfo(BaseModel):
    """Info profil user dari Diarium"""
    logged_in: bool
    nama: Optional[str] = None
    nik: Optional[str] = None
    perusahaan: Optional[str] = None
    divisi: Optional[str] = None
    posisi: Optional[str] = None
    telepon: Optional[str] = None
    tanggal_lahir: Optional[str] = None
    raw_data: Optional[str] = None


class LoginResult(BaseModel):
    """Response dari login"""
    success: bool
    status: LoginStatus
    message: str
    requires_mfa: bool = False
    timestamp: str


class DiariumCheckoutRequest(BaseModel):
    """Request untuk checkout routine Diarium"""
    nik: Optional[str] = Field(None, description="NIK TelkomGroup (opsional jika sudah login)")
    sso_password: Optional[str] = Field(None, description="Password SSO (opsional jika sudah login)")
    health_status: HealthStatus = Field(default=HealthStatus.SEHAT, description="Status kesehatan")
    complete_activities: bool = Field(default=True, description="Ubah semua aktivitas In Progress ke Done")


class TaskResult(BaseModel):
    """Response dari task automation"""
    success: bool
    message: str
    task_id: str
    timestamp: str
    details: Optional[dict] = None


class TaskStatus(BaseModel):
    """Status dari running task"""
    task_id: str
    status: str  # "running", "completed", "failed"
    message: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None


# ============== Task Storage ==============

# Simple in-memory storage for task status (use Redis/DB in production)
running_tasks: dict[str, TaskStatus] = {}

# Store pending MFA sessions
pending_mfa_sessions: dict[str, dict] = {}


# ============== Helper Functions ==============

def generate_task_id() -> str:
    """Generate unique task ID"""
    return f"task_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"


async def run_phone_agent(task: str, task_id: str) -> tuple[bool, str]:
    """
    Run the phone agent with given task.
    Returns (success, message)
    """
    cmd = [
        Config.PYTHON_PATH,
        Config.MAIN_SCRIPT,
        "--base-url", Config.ZAI_BASE_URL,
        "--model", Config.ZAI_MODEL,
        "--apikey", Config.ZAI_API_KEY,
        "--lang", "en",
        task
    ]
    
    try:
        # Run the command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.path.dirname(__file__)
        )
        
        stdout, stderr = await process.communicate()
        
        output = stdout.decode() if stdout else ""
        error = stderr.decode() if stderr else ""
        
        if process.returncode == 0:
            # Extract result message from output
            if "Task Completed:" in output:
                result_start = output.find("Task Completed:") + len("Task Completed:")
                result_end = output.find("==", result_start)
                message = output[result_start:result_end].strip() if result_end > result_start else "Task completed"
            else:
                message = "Task completed successfully"
            return True, message
        else:
            return False, f"Task failed: {error or output}"
            
    except Exception as e:
        return False, f"Error running task: {str(e)}"


async def execute_checkout_routine(
    request: DiariumCheckoutRequest,
    task_id: str
):
    """Execute the full checkout routine"""
    try:
        running_tasks[task_id].status = "running"
        
        # Build the task description
        task_parts = []
        
        # Step 1: Open Diarium and handle login if needed
        if request.nik and request.sso_password:
            task_parts.append(
                f"Open the Diarium app. If there is a login screen with 'NIK TelkomGroup' input field, "
                f"enter NIK: {request.nik}, then enter Password: {request.sso_password}, "
                f"then check/centang the Terms checkbox (Syarat Ketentuan), then click Masuk button. "
                f"Then wait for MFA code input. If already logged in, click Skip if available."
            )
        else:
            task_parts.append(
                "Open the Diarium app. If already logged in, click Skip if available."
            )
        
        # Execute login/open task
        success, message = await run_phone_agent(" ".join(task_parts), task_id)
        if not success:
            running_tasks[task_id].status = "failed"
            running_tasks[task_id].message = message
            running_tasks[task_id].completed_at = datetime.now().isoformat()
            return
        
        # Step 2: Complete activities if requested
        if request.complete_activities:
            activity_task = (
                "In the Diarium app: Click 'Lihat aktivitas' or 'Cek selengkapnya' to view activities. "
                "For each activity that shows 'In Progress' status, tap on the dropdown and change it to 'Done'. "
                "Do this for ALL in progress items. After all items are changed to Done, go back to the home screen (beranda)."
            )
            success, message = await run_phone_agent(activity_task, task_id)
            if not success:
                running_tasks[task_id].status = "failed"
                running_tasks[task_id].message = f"Failed to complete activities: {message}"
                running_tasks[task_id].completed_at = datetime.now().isoformat()
                return
        
        # Step 3: Perform checkout
        checkout_task = (
            f"In the Diarium app, click the 'Check-Out' button. "
            f"On the Check-Out screen, select '{request.health_status.value}' option, "
            f"then scroll down and click 'Simpan' button. "
            f"When confirmation dialog appears, click 'Check Out' to confirm."
        )
        success, message = await run_phone_agent(checkout_task, task_id)
        
        if success:
            running_tasks[task_id].status = "completed"
            running_tasks[task_id].message = f"Checkout completed successfully with status: {request.health_status.value}"
        else:
            running_tasks[task_id].status = "failed"
            running_tasks[task_id].message = f"Checkout failed: {message}"
        
        running_tasks[task_id].completed_at = datetime.now().isoformat()
        
    except Exception as e:
        running_tasks[task_id].status = "failed"
        running_tasks[task_id].message = str(e)
        running_tasks[task_id].completed_at = datetime.now().isoformat()


# ============== API Endpoints ==============

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Diarium Automation API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Check if the system is ready"""
    # Check if ADB is available and device connected
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=10
        )
        devices = [line for line in result.stdout.split('\n') if '\tdevice' in line]
        
        return {
            "status": "healthy",
            "adb_available": True,
            "devices_connected": len(devices),
            "api_key_configured": bool(Config.ZAI_API_KEY)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.post("/diarium/checkout", response_model=TaskResult)
async def diarium_checkout_routine(
    request: DiariumCheckoutRequest,
    background_tasks: BackgroundTasks
):
    """
    🚀 Diarium Checkout Routine
    
    Menjalankan otomasi checkout Diarium:
    1. Buka app Diarium (login jika perlu)
    2. Ubah semua aktivitas "In Progress" ke "Done" (opsional)
    3. Klik Check-Out
    4. Pilih status kesehatan
    5. Simpan checkout
    
    Task berjalan di background. Gunakan /diarium/status/{task_id} untuk cek progress.
    """
    if not Config.ZAI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API key not configured. Set zai_api_key in .env file"
        )
    
    task_id = generate_task_id()
    
    # Initialize task status
    running_tasks[task_id] = TaskStatus(
        task_id=task_id,
        status="pending",
        started_at=datetime.now().isoformat()
    )
    
    # Run in background
    background_tasks.add_task(execute_checkout_routine, request, task_id)
    
    return TaskResult(
        success=True,
        message="Checkout routine started. Use /diarium/status/{task_id} to check progress.",
        task_id=task_id,
        timestamp=datetime.now().isoformat(),
        details={
            "health_status": request.health_status.value,
            "complete_activities": request.complete_activities,
            "has_credentials": bool(request.nik and request.sso_password)
        }
    )


@app.get("/diarium/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """
    Cek status task yang sedang berjalan
    """
    if task_id not in running_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return running_tasks[task_id]


@app.post("/diarium/quick-checkout", response_model=TaskResult)
async def quick_checkout(
    health_status: HealthStatus = HealthStatus.SEHAT,
    background_tasks: BackgroundTasks = None
):
    """
    ⚡ Quick Checkout (tanpa login, asumsi sudah login)
    
    Langsung checkout dengan status kesehatan yang dipilih.
    Tidak menjalankan step login dan complete activities.
    """
    if not Config.ZAI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API key not configured"
        )
    
    task_id = generate_task_id()
    
    task = (
        f"In the Diarium app, click the 'Check-Out' button on home screen. "
        f"On the Check-Out screen, select '{health_status.value}' option, "
        f"then scroll down and click 'Simpan' button. "
        f"When confirmation dialog appears, click 'Check Out' to confirm."
    )
    
    # For quick checkout, run synchronously (shorter task)
    success, message = await run_phone_agent(task, task_id)
    
    return TaskResult(
        success=success,
        message=message,
        task_id=task_id,
        timestamp=datetime.now().isoformat()
    )


@app.get("/diarium/tasks")
async def list_tasks():
    """
    List semua task yang pernah dijalankan
    """
    return {
        "tasks": list(running_tasks.values()),
        "total": len(running_tasks)
    }


@app.delete("/diarium/tasks")
async def clear_tasks():
    """
    Clear semua task history
    """
    running_tasks.clear()
    return {"message": "All tasks cleared"}


# ============== WHO AM I Endpoint ==============

@app.get("/diarium/whoami", response_model=ProfileInfo)
async def whoami():
    """
    👤 Who Am I - Cek profil user yang sedang login
    
    Flow:
    1. Buka app Diarium
    2. Cek apakah sudah login (ada nama user di home)
    3. Jika sudah login, klik profile dan ambil info:
       - Nama, NIK, Perusahaan, Divisi, Posisi, Telepon, Tanggal Lahir
    4. Jika belum login, return please login
    """
    if not Config.ZAI_API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured")
    
    task_id = generate_task_id()
    
    # First check if logged in by looking at home screen
    check_task = (
        "Open the Diarium app. Look at the screen carefully. "
        "If you see a greeting like 'Good Morning/Afternoon/Evening' with a user name (e.g., 'Good Afternoon! BASKORO'), "
        "then the user is LOGGED IN. Click on the profile icon or user name area at the top to open the profile page. "
        "Once on the profile page, read ALL the information you can see: "
        "nama (name), NIK, perusahaan (company), divisi (division), posisi (position), telepon (phone), tanggal lahir (birth date). "
        "Report all this information in your finish message. "
        "If you see a LOGIN screen with 'NIK TelkomGroup' input field, report 'NOT_LOGGED_IN' in your finish message."
    )
    
    success, message = await run_phone_agent(check_task, task_id)
    
    if not success:
        return ProfileInfo(logged_in=False, raw_data=f"Error: {message}")
    
    # Parse the response to extract profile info
    message_lower = message.lower()
    
    if "not_logged_in" in message_lower or "login screen" in message_lower or "nik telkomgroup" in message_lower:
        return ProfileInfo(
            logged_in=False,
            raw_data="Please login first using /diarium/login endpoint"
        )
    
    # Try to extract profile info from message
    profile = ProfileInfo(logged_in=True, raw_data=message)
    
    # Basic extraction (the AI response should contain this info)
    # In production, you'd want more robust parsing
    return profile


# ============== LOGIN Endpoint ==============

@app.post("/diarium/login", response_model=LoginResult)
async def login(request: DiariumLoginRequest):
    """
    🔐 Login ke Diarium
    
    Flow:
    1. Buka app Diarium
    2. Cek apakah sudah login - jika ya, return success
    3. Jika belum login:
       - Input NIK
       - Input Password
       - Centang Syarat Ketentuan
       - Klik Masuk
    4. Jika credentials salah, return error
    5. Jika perlu MFA, return mfa_required dan user harus hit /diarium/mfa
    """
    if not Config.ZAI_API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured")
    
    task_id = generate_task_id()
    
    # Check if already logged in, if not then login
    login_task = (
        f"Open the Diarium app. Look at the screen carefully. "
        f"If you see a greeting like 'Good Morning/Afternoon/Evening' with a user name, "
        f"then the user is ALREADY LOGGED IN - report 'ALREADY_LOGGED_IN' in your finish message. "
        f"If you see a LOGIN screen with 'NIK TelkomGroup' input field: "
        f"1. Tap on the NIK TelkomGroup input field and enter: {request.nik} "
        f"2. Tap on the Password field and enter: {request.sso_password} "
        f"3. Find and tap/check the checkbox for 'Syarat dan Ketentuan' (Terms and Conditions) "
        f"4. Tap the 'Masuk' (Login) button "
        f"After clicking Masuk, check what happens: "
        f"- If you see an MFA/OTP input screen, report 'MFA_REQUIRED' in your finish message "
        f"- If you see an error message about wrong credentials, report 'LOGIN_FAILED' in your finish message "
        f"- If login succeeds and you see the home screen with greeting, report 'LOGIN_SUCCESS' in your finish message"
    )
    
    success, message = await run_phone_agent(login_task, task_id)
    
    if not success:
        return LoginResult(
            success=False,
            status=LoginStatus.LOGIN_FAILED,
            message=f"Login process failed: {message}",
            requires_mfa=False,
            timestamp=datetime.now().isoformat()
        )
    
    message_lower = message.lower()
    
    # Check the result
    if "already_logged_in" in message_lower or "already logged in" in message_lower:
        return LoginResult(
            success=True,
            status=LoginStatus.LOGGED_IN,
            message="User is already logged in",
            requires_mfa=False,
            timestamp=datetime.now().isoformat()
        )
    
    if "mfa_required" in message_lower or "mfa" in message_lower or "otp" in message_lower:
        # Store session for MFA
        pending_mfa_sessions[request.nik] = {
            "nik": request.nik,
            "timestamp": datetime.now().isoformat()
        }
        return LoginResult(
            success=False,
            status=LoginStatus.MFA_REQUIRED,
            message="MFA code required. Please use /diarium/mfa endpoint to input the MFA code shown on your phone.",
            requires_mfa=True,
            timestamp=datetime.now().isoformat()
        )
    
    if "login_failed" in message_lower or "wrong" in message_lower or "invalid" in message_lower or "error" in message_lower:
        return LoginResult(
            success=False,
            status=LoginStatus.LOGIN_FAILED,
            message="Login failed. Please check your NIK and password.",
            requires_mfa=False,
            timestamp=datetime.now().isoformat()
        )
    
    if "login_success" in message_lower or "success" in message_lower or "home" in message_lower:
        return LoginResult(
            success=True,
            status=LoginStatus.LOGGED_IN,
            message="Login successful!",
            requires_mfa=False,
            timestamp=datetime.now().isoformat()
        )
    
    # Default - assume some issue
    return LoginResult(
        success=False,
        status=LoginStatus.LOGIN_FAILED,
        message=f"Unknown login result: {message}",
        requires_mfa=False,
        timestamp=datetime.now().isoformat()
    )


# ============== MFA Endpoint ==============

@app.post("/diarium/mfa", response_model=LoginResult)
async def submit_mfa(request: DiariumMFARequest):
    """
    🔑 Submit MFA Code
    
    Setelah login meminta MFA, gunakan endpoint ini untuk input kode MFA.
    
    Flow:
    1. Input kode MFA yang muncul di HP/authenticator
    2. Klik submit/verify
    3. Jika berhasil, return login success
    4. Jika gagal, return error
    """
    if not Config.ZAI_API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured")
    
    task_id = generate_task_id()
    
    # Input MFA code
    mfa_task = (
        f"On the Diarium app, you should be on the MFA/OTP verification screen. "
        f"Enter the MFA code: {request.mfa_code} into the input field. "
        f"Then tap the verify/submit/lanjutkan button. "
        f"After submitting: "
        f"- If you see the home screen with a greeting (Good Morning/Afternoon/Evening + username), report 'LOGIN_SUCCESS' "
        f"- If you see an error about invalid code, report 'MFA_FAILED' "
        f"- If you see another MFA prompt, report 'MFA_RETRY'"
    )
    
    success, message = await run_phone_agent(mfa_task, task_id)
    
    if not success:
        return LoginResult(
            success=False,
            status=LoginStatus.LOGIN_FAILED,
            message=f"MFA submission failed: {message}",
            requires_mfa=True,
            timestamp=datetime.now().isoformat()
        )
    
    message_lower = message.lower()
    
    if "login_success" in message_lower or "success" in message_lower or "home" in message_lower or "greeting" in message_lower:
        # Clear pending MFA session
        pending_mfa_sessions.clear()
        return LoginResult(
            success=True,
            status=LoginStatus.LOGGED_IN,
            message="MFA verified successfully! You are now logged in.",
            requires_mfa=False,
            timestamp=datetime.now().isoformat()
        )
    
    if "mfa_failed" in message_lower or "invalid" in message_lower or "wrong" in message_lower:
        return LoginResult(
            success=False,
            status=LoginStatus.MFA_REQUIRED,
            message="Invalid MFA code. Please try again with the correct code.",
            requires_mfa=True,
            timestamp=datetime.now().isoformat()
        )
    
    if "mfa_retry" in message_lower or "retry" in message_lower:
        return LoginResult(
            success=False,
            status=LoginStatus.MFA_REQUIRED,
            message="MFA verification needed again. Please submit a new code.",
            requires_mfa=True,
            timestamp=datetime.now().isoformat()
        )
    
    # Default
    return LoginResult(
        success=False,
        status=LoginStatus.LOGIN_FAILED,
        message=f"MFA result unclear: {message}",
        requires_mfa=True,
        timestamp=datetime.now().isoformat()
    )


@app.get("/diarium/login-status")
async def check_login_status():
    """
    🔍 Quick check apakah user sudah login
    
    Cek tanpa melakukan login - hanya melihat apakah ada greeting di home screen
    """
    if not Config.ZAI_API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured")
    
    task_id = generate_task_id()
    
    check_task = (
        "Open the Diarium app. Look at the screen. "
        "If you see a greeting with username like 'Good Afternoon! BASKORO', report 'LOGGED_IN'. "
        "If you see a login screen with NIK TelkomGroup input, report 'NOT_LOGGED_IN'."
    )
    
    success, message = await run_phone_agent(check_task, task_id)
    
    if not success:
        return {"logged_in": False, "error": message}
    
    message_lower = message.lower()
    
    if "logged_in" in message_lower and "not_logged_in" not in message_lower:
        return {"logged_in": True, "message": "User is logged in"}
    else:
        return {"logged_in": False, "message": "User is not logged in"}


# ============== Run Server ==============

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Diarium Automation API Server...")
    print("📖 Swagger UI: http://localhost:8080/docs")
    print("📖 ReDoc: http://localhost:8080/redoc")
    
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8080,
        reload=True
    )
