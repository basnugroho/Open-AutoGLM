#!/usr/bin/env python3
"""
Diarium Automation API Server
=============================

REST API untuk otomasi aplikasi Diarium di HP Android.

Features:
- Hybrid approach: Rule-based input + AI verification
- Support onboarding, login, check-in, check-out, logout
- Standardized JSON response format
- Swagger UI documentation

Usage:
    python api_server.py
    # or
    uvicorn api_server:app --host 0.0.0.0 --port 8080
    
Then access: http://localhost:8080/docs for Swagger UI

Author: Baskoro Nugroho
Last Updated: December 22, 2025
"""

import os
import subprocess
import asyncio
import time
import xml.etree.ElementTree as ET
import re
from typing import Optional, Any
from datetime import datetime
from enum import Enum
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ============================================================================
# CONFIGURATION
# ============================================================================

# Add platform-tools to PATH at module level
PLATFORM_TOOLS_PATH = "/Users/baskoronugroho/projects/platform-tools"
if PLATFORM_TOOLS_PATH not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{PLATFORM_TOOLS_PATH}:{os.environ.get('PATH', '')}"


class Config:
    """API and ADB configuration"""
    ZAI_API_KEY = os.getenv("zai_api_key", "")
    ZAI_BASE_URL = "https://api.z.ai/api/paas/v4"
    ZAI_MODEL = "autoglm-phone-multilingual"
    PYTHON_PATH = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python")
    MAIN_SCRIPT = os.path.join(os.path.dirname(__file__), "main.py")
    PLATFORM_TOOLS = PLATFORM_TOOLS_PATH
    ADB_PATH = os.path.join(PLATFORM_TOOLS_PATH, "adb")


# ============================================================================
# UI ELEMENT COORDINATES (Samsung A13, 1080x2408)
# ============================================================================
# Detected via: adb shell uiautomator dump /sdcard/window_dump.xml
# Center calculated from bounds: ((x1+x2)/2, (y1+y2)/2)

class LoginScreenElements:
    """
    Koordinat elemen login screen Diarium.
    Device: Samsung A13 (1080x2408)
    
    Usage:
        adb_tap(*LoginScreenElements.NIK_INPUT)
    """
    # NIK TelkomGroup input: bounds="[45,1185][1035,1320]"
    NIK_INPUT = (540, 1252)
    
    # Password input: bounds="[45,1466][1035,1601]"
    PASSWORD_INPUT = (540, 1533)
    
    # Checkbox Syarat & Ketentuan: bounds="[45,1667][146,1769]"
    # Note: Use long-tap (150ms) for reliability
    CHECKBOX_TERMS = (95, 1718)
    
    # Tombol Masuk (Login): bounds="[45,1835][1035,1970]"
    LOGIN_BUTTON = (540, 1902)
    
    # Package name
    PACKAGE_NAME = "co.id.telkom.diarium.prod"


class HomeScreenElements:
    """Koordinat elemen home screen setelah login (TBD)"""
    pass


# ============================================================================
# APPLICATION LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for FastAPI app"""
    # Startup
    adb = Config.ADB_PATH
    print(f"🔌 Ensuring ADB server is running... (using {adb})")
    try:
        subprocess.run([adb, "start-server"], capture_output=True, timeout=10)
        result = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=10)
        devices = [line for line in result.stdout.split('\n') 
                   if line.strip() and not line.startswith('List') and 'device' in line.split()]
        if devices:
            print(f"✅ ADB ready with {len(devices)} device(s) connected")
        else:
            print("⚠️ No devices connected. Please connect your Android device.")
    except Exception as e:
        print(f"⚠️ ADB check failed: {e}")
    
    yield
    
    # Shutdown
    print("👋 Shutting down Diarium API Server...")


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Diarium Automation API",
    description="""
REST API untuk otomasi aplikasi Diarium di HP Android.

## Sections:
- **🔌 Device** - Cek device yang terhubung
- **🔐 Before Login** - Login, MFA, prepare login
- **👤 After Login** - Profile info, check-in
- **✅ After Check-In** - Checkout routine
- **🚪 Logout** - Logout dari app

## Architecture:
- **Hybrid Approach**: Rule-based input + AI verification
- **Fast Input**: Direct ADB commands for text input
- **Smart Verification**: AI for checkbox, buttons, and result checking
    """,
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class StatusCode(str, Enum):
    """Standard status codes for API responses"""
    SUCCESS = "success"
    ERROR = "error"
    LOGGED_IN = "logged_in"
    NOT_LOGGED_IN = "not_logged_in"
    MFA_REQUIRED = "mfa_required"
    LOGIN_FAILED = "login_failed"
    CHECKOUT_SUCCESS = "checkout_success"
    CHECKOUT_NOT_AVAILABLE = "checkout_not_available"
    CHECKOUT_ALREADY_DONE = "checkout_already_done"
    DEVICE_NOT_FOUND = "device_not_found"


class HealthStatus(str, Enum):
    """Health status options for check-in"""
    SEHAT = "Sehat"
    KURANG_FIT = "Kurang Fit"
    SAKIT = "Sakit"


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ResponseMetadata(BaseModel):
    """Metadata included in all API responses"""
    hit_time: str
    result_time: str
    duration_seconds: float
    device_id: Optional[str] = None


class StandardResponse(BaseModel):
    """
    Standard response format for all endpoints.
    
    Example:
        {
            "success": true,
            "status": "logged_in",
            "message": "Login successful",
            "data": {"username": "John"},
            "metadata": {...}
        }
    """
    success: bool
    status: str
    message: str
    data: Optional[dict] = None
    metadata: ResponseMetadata


class LoginRequest(BaseModel):
    """Request model for login endpoints"""
    nik: str = Field(..., description="NIK TelkomGroup")
    password: str = Field(..., description="Password SSO")


class MFARequest(BaseModel):
    """Request model for MFA submission"""
    mfa_code: str = Field(..., description="Kode MFA 6 digit")


class CheckoutRequest(BaseModel):
    """Request model for checkout"""
    health_status: HealthStatus = Field(default=HealthStatus.SEHAT, description="Status kesehatan")
    complete_activities: bool = Field(default=True, description="Selesaikan semua aktivitas In Progress")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_current_device() -> Optional[str]:
    """
    Get currently connected Android device ID.
    
    Returns:
        Device ID string (e.g., "RR8T601DQLY") or None if no device connected.
    """
    try:
        result = subprocess.run(
            [Config.ADB_PATH, "devices"],
            capture_output=True,
            text=True,
            timeout=10
        )
        devices = []
        for line in result.stdout.split('\n'):
            if line.strip() and not line.startswith('List') and 'device' in line.split():
                devices.append(line.split()[0])
        return devices[0] if devices else None
    except Exception:
        return None


def create_response(
    success: bool,
    status: str,
    message: str,
    data: Optional[dict],
    hit_time: datetime,
    device_id: Optional[str] = None
) -> StandardResponse:
    """
    Create standardized API response with metadata.
    
    Args:
        success: Whether operation succeeded
        status: Status code (from StatusCode enum)
        message: Human-readable message
        data: Optional response data
        hit_time: Request timestamp
        device_id: Connected device ID
    
    Returns:
        StandardResponse object
    """
    result_time = datetime.now()
    duration = (result_time - hit_time).total_seconds()
    
    return StandardResponse(
        success=success,
        status=status,
        message=message,
        data=data,
        metadata=ResponseMetadata(
            hit_time=hit_time.isoformat(),
            result_time=result_time.isoformat(),
            duration_seconds=round(duration, 2),
            device_id=device_id
        )
    )


# ============================================================================
# AI AGENT RUNNER
# ============================================================================

async def run_phone_agent(task: str) -> tuple[bool, str]:
    """
    Run the AutoGLM phone agent with given task.
    
    This executes main.py as a subprocess with the ZAI API configuration.
    The agent uses vision AI to analyze screenshots and perform actions.
    
    Args:
        task: Natural language description of what to do
        
    Returns:
        Tuple of (success: bool, message: str)
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
    
    env = os.environ.copy()
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.path.dirname(__file__),
            env=env
        )
        
        stdout, stderr = await process.communicate()
        output = stdout.decode() if stdout else ""
        error = stderr.decode() if stderr else ""
        
        if process.returncode == 0:
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
        return False, f"Error: {str(e)}"


# ============================================================================
# ADB HELPER FUNCTIONS (Rule-Based)
# ============================================================================
# These functions provide direct ADB control without AI,
# used for fast and reliable input operations.

def adb_tap(x: int, y: int) -> bool:
    """
    Tap at specific screen coordinates.
    
    Args:
        x: X coordinate
        y: Y coordinate
        
    Returns:
        True if successful
    """
    try:
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "tap", str(x), str(y)],
            capture_output=True,
            timeout=5
        )
        return True
    except Exception:
        return False


def adb_long_tap(x: int, y: int, duration_ms: int = 150) -> bool:
    """
    Long tap at coordinates using swipe trick.
    
    More reliable for some UI elements like checkboxes that need
    sustained touch input. Uses swipe from point to same point with duration.
    
    Args:
        x: X coordinate
        y: Y coordinate
        duration_ms: Hold duration in milliseconds (default 150)
        
    Returns:
        True if successful
    """
    try:
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "touchscreen", "swipe", 
             str(x), str(y), str(x), str(y), str(duration_ms)],
            capture_output=True,
            timeout=5
        )
        return True
    except Exception:
        return False


def adb_input_text(text: str) -> bool:
    """
    Input text using direct ADB shell input.
    
    More reliable than broadcast method, works for all fields including
    password fields with security restrictions.
    
    Args:
        text: Text to input (no spaces or special chars)
        
    Returns:
        True if successful
    """
    try:
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "text", text],
            capture_output=True,
            timeout=10
        )
        return True
    except Exception:
        return False


def adb_input_text_broadcast(text: str) -> bool:
    """Input text using ADB Keyboard broadcast (requires ADB Keyboard as active IME)
    Note: May not work on password fields due to security restrictions"""
    try:
        result = subprocess.run(
            [Config.ADB_PATH, "shell", "am", "broadcast", 
             "-a", "ADB_INPUT_TEXT", 
             "--es", "msg", text],
            capture_output=True,
            text=True,
            timeout=10
        )
        return "Broadcast completed" in result.stdout
    except Exception:
        return False


def adb_clear_input_field() -> bool:
    """Clear input field using select all (Ctrl+A) + delete"""
    try:
        # Method 1: Use Ctrl+A to select all
        # KEYCODE_CTRL_LEFT = 113, KEYCODE_A = 29
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "keyevent", "--press", "113", "29"],
            capture_output=True,
            timeout=3
        )
        time.sleep(0.1)
        # Delete selected
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "keyevent", "67"],  # KEYCODE_DEL
            capture_output=True,
            timeout=2
        )
        return True
    except Exception:
        return False


def adb_clear_field_backup() -> bool:
    """Backup method: move to end and delete characters using shell loop (faster)"""
    try:
        # Move to end of field
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "keyevent", "123"],  # KEYCODE_MOVE_END
            capture_output=True,
            timeout=2
        )
        # Delete characters using shell loop (much faster than multiple subprocess calls)
        subprocess.run(
            [Config.ADB_PATH, "shell", 
             "for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do input keyevent 67; done"],
            capture_output=True,
            timeout=15
        )
        return True
    except Exception:
        return False


def adb_tap_and_clear_and_input(x: int, y: int, text: str) -> bool:
    """Tap field, clear existing content, then input new text - OPTIMIZED"""
    try:
        # Step 1: Tap the field to focus
        adb_tap(x, y)
        time.sleep(0.3)
        
        # Step 2: Clear with move-to-end + delete loop (proven to work)
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "keyevent", "123"],  # MOVE_END
            capture_output=True,
            timeout=2
        )
        subprocess.run(
            [Config.ADB_PATH, "shell", 
             "for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do input keyevent 67; done"],
            capture_output=True,
            timeout=10
        )
        time.sleep(0.1)
        
        # Step 3: Input new text
        adb_input_text(text)
        time.sleep(0.2)
        
        return True
    except Exception:
        return False


def adb_press_home() -> bool:
    """Press HOME button"""
    try:
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "keyevent", "3"],  # KEYCODE_HOME
            capture_output=True,
            timeout=3
        )
        return True
    except Exception:
        return False


def adb_press_back() -> bool:
    """Press BACK button"""
    try:
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "keyevent", "4"],  # KEYCODE_BACK
            capture_output=True,
            timeout=3
        )
        return True
    except Exception:
        return False


def adb_force_stop_app(package: str) -> bool:
    """Force stop an app"""
    try:
        subprocess.run(
            [Config.ADB_PATH, "shell", "am", "force-stop", package],
            capture_output=True,
            timeout=5
        )
        return True
    except Exception:
        return False


def adb_launch_app(package: str) -> bool:
    """Launch app using monkey command"""
    try:
        subprocess.run(
            [Config.ADB_PATH, "shell", "monkey", "-p", package, 
             "-c", "android.intent.category.LAUNCHER", "1"],
            capture_output=True,
            timeout=10
        )
        return True
    except Exception:
        return False


def adb_get_current_package() -> Optional[str]:
    """Get current foreground app package"""
    try:
        result = subprocess.run(
            [Config.ADB_PATH, "shell", "dumpsys", "window", "windows", 
             "|", "grep", "-E", "'mCurrentFocus|mFocusedApp'"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False
        )
        # Alternative approach
        result = subprocess.run(
            [Config.ADB_PATH, "shell", "dumpsys", "activity", "activities", 
             "|", "grep", "mResumedActivity"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip() if result.stdout else None
    except Exception:
        return None


def adb_dump_ui() -> Optional[str]:
    """Dump UI hierarchy and return as XML string"""
    try:
        subprocess.run(
            [Config.ADB_PATH, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"],
            capture_output=True,
            timeout=10
        )
        result = subprocess.run(
            [Config.ADB_PATH, "shell", "cat", "/sdcard/window_dump.xml"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout if result.stdout else None
    except Exception:
        return None


def find_element_by_content_desc(xml_str: str, content_desc: str) -> Optional[tuple[int, int]]:
    """Find element center coordinates by content-desc"""
    try:
        root = ET.fromstring(xml_str)
        for elem in root.iter('node'):
            if elem.get('content-desc') == content_desc:
                bounds = elem.get('bounds')
                # Parse bounds like "[45,1835][1035,1970]"
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    return ((x1 + x2) // 2, (y1 + y2) // 2)
        return None
    except Exception:
        return None


def find_element_by_text(xml_str: str, text: str) -> Optional[tuple[int, int]]:
    """Find element center coordinates by text"""
    try:
        root = ET.fromstring(xml_str)
        for elem in root.iter('node'):
            if text in (elem.get('text') or ''):
                bounds = elem.get('bounds')
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    return ((x1 + x2) // 2, (y1 + y2) // 2)
        return None
    except Exception:
        return None


def is_on_login_screen(xml_str: str) -> bool:
    """Check if currently on login screen"""
    try:
        root = ET.fromstring(xml_str)
        for elem in root.iter('node'):
            content_desc = elem.get('content-desc', '')
            if 'NIK TelkomGroup' in content_desc:
                return True
        return False
    except Exception:
        return False


def handle_dialogs_and_onboarding(xml_str: str) -> tuple[bool, str]:
    """
    Handle permission dialogs and onboarding screens.
    Returns (handled_something, description)
    """
    try:
        root = ET.fromstring(xml_str)
        
        for elem in root.iter('node'):
            content_desc = elem.get('content-desc', '')
            text = elem.get('text', '')
            resource_id = elem.get('resource-id', '')
            bounds = elem.get('bounds', '')
            
            # Handle "Skip" button (onboarding step 1)
            if content_desc == 'Skip' or text == 'Skip':
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                    return True, "Tapped Skip button"
            
            # Handle "Get Started" button (onboarding step 2)
            if content_desc == 'Get Started' or text == 'Get Started' or 'Get Started' in content_desc:
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                    return True, "Tapped Get Started button"
            
            # Handle "Mulai" button (Indonesian version of Get Started)
            if content_desc == 'Mulai' or text == 'Mulai':
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                    return True, "Tapped Mulai button"
            
            # Handle "Allow" for permissions
            if text in ['Allow', 'ALLOW', 'Izinkan', 'IZINKAN']:
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                    return True, f"Tapped {text} button"
            
            # Handle "While using the app" for location permission
            if 'While using' in text or 'Saat menggunakan' in text:
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                    return True, "Tapped 'While using the app'"
            
            # Handle "Only this time"
            if 'Only this time' in text or 'Hanya sekali ini' in text:
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                    return True, "Tapped 'Only this time'"
            
            # Handle common permission dialog resource IDs
            if 'permission' in resource_id.lower():
                if 'allow' in resource_id.lower():
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                        return True, "Tapped permission allow button"
        
        return False, "No dialogs found"
    except Exception as e:
        return False, f"Error: {str(e)}"


def dismiss_first_login_tutorial() -> tuple[bool, str]:
    """
    Dismiss first-time login tutorial overlay.
    User-discovered method: tap screen 5 times (anywhere), then tap OK button.
    Returns (success, description)
    """
    try:
        steps = []
        
        # Step 1: Tap center of screen 5 times to dismiss tutorial highlights
        center_x, center_y = 540, 1136  # Center of screen
        for i in range(5):
            adb_tap(center_x, center_y)
            steps.append(f"Tap {i+1}/5")
            time.sleep(0.4)
        
        time.sleep(0.5)
        
        # Step 2: Look for OK/Oke button and tap it
        xml_str = adb_dump_ui()
        if xml_str:
            root = ET.fromstring(xml_str)
            for elem in root.iter('node'):
                text = elem.get('text', '')
                content_desc = elem.get('content-desc', '')
                bounds = elem.get('bounds', '')
                
                # Look for OK button (various forms)
                if text.upper() in ['OK', 'OKE', 'OKAY', 'GOT IT', 'MENGERTI', 'DONE', 'SELESAI']:
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                        steps.append(f"Tapped {text} button")
                        return True, f"Tutorial dismissed: {', '.join(steps)}"
                
                # Also check content-desc
                if content_desc.upper() in ['OK', 'OKE', 'OKAY', 'GOT IT', 'MENGERTI']:
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                        steps.append(f"Tapped {content_desc} button")
                        return True, f"Tutorial dismissed: {', '.join(steps)}"
        
        # If no OK button found, try tapping common OK button locations
        # Typically centered at bottom of dialog
        adb_tap(540, 1800)  # Common location for dialog buttons
        steps.append("Tapped common OK location")
        
        return True, f"Tutorial dismiss attempted: {', '.join(steps)}"
    except Exception as e:
        return False, f"Error dismissing tutorial: {str(e)}"


def has_permission_dialog(xml_str: str) -> bool:
    """Check if there's a permission dialog on screen"""
    try:
        keywords = ['Izin', 'Permission', 'Izinkan', 'Allow', 'Deny', 'Tolak']
        root = ET.fromstring(xml_str)
        for elem in root.iter('node'):
            content_desc = elem.get('content-desc', '')
            text = elem.get('text', '')
            for kw in keywords:
                if kw.lower() in content_desc.lower() or kw.lower() in text.lower():
                    return True
        return False
    except Exception:
        return False


def handle_permission_dialogs(xml_str: str) -> bool:
    """Handle permission dialogs by clicking Izinkan/Allow or Tutup/Close"""
    try:
        root = ET.fromstring(xml_str)
        
        # Look for Izinkan, Allow, or Tutup buttons
        for elem in root.iter('node'):
            content_desc = elem.get('content-desc', '')
            text = elem.get('text', '')
            
            # Click "Izinkan" or "Allow" for permissions
            if content_desc in ['Izinkan', 'Allow'] or text in ['Izinkan', 'Allow', 'ALLOW', 'IZINKAN']:
                bounds = elem.get('bounds')
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                    return True
            
            # Also handle "Tutup" (Close) button
            if content_desc == 'Tutup' or text in ['Tutup', 'TUTUP', 'Close', 'CLOSE']:
                bounds = elem.get('bounds')
                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                    return True
        
        return False
    except Exception:
        return False


def handle_system_permission_dialog() -> bool:
    """Handle Android system permission dialog (While using the app, etc.)"""
    try:
        xml_str = adb_dump_ui()
        if not xml_str:
            return False
        
        root = ET.fromstring(xml_str)
        
        # Look for system permission buttons
        for elem in root.iter('node'):
            resource_id = elem.get('resource-id', '')
            text = elem.get('text', '')
            
            # Android system permission dialog buttons
            if 'permission' in resource_id.lower():
                # Find "While using the app" or "Allow" button
                if 'allow' in text.lower() or 'while using' in text.lower() or 'saat menggunakan' in text.lower():
                    bounds = elem.get('bounds')
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                        return True
        
        return False
    except Exception:
        return False


def is_logged_in(xml_str: str) -> tuple[bool, Optional[str]]:
    """Check if already logged in, return (is_logged_in, username)"""
    try:
        root = ET.fromstring(xml_str)
        for elem in root.iter('node'):
            content_desc = elem.get('content-desc', '')
            # Look for greeting pattern
            if any(greeting in content_desc for greeting in ['Good Morning', 'Good Afternoon', 'Good Evening', 'Selamat Pagi', 'Selamat Siang', 'Selamat Sore', 'Selamat Malam']):
                # Extract username if possible
                return True, content_desc
        return False, None
    except Exception:
        return False, None


def parse_status_response(message: str) -> tuple[str, dict]:
    """Parse STATUS:XXX:key=value format from AI response"""
    result = {}
    status = "unknown"
    
    message_upper = message.upper()
    
    # Find STATUS: pattern
    if "STATUS:" in message_upper:
        # Extract status part
        parts = message.split("STATUS:")
        if len(parts) > 1:
            status_part = parts[1].strip().split()[0]  # Get first word after STATUS:
            status_parts = status_part.split(":")
            status = status_parts[0].lower()
            
            # Extract key=value pairs
            for part in status_parts[1:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    result[key.lower()] = value
    
    # Check for common patterns
    if "logged_in" in message_upper or "already logged in" in message_upper:
        status = "logged_in"
    elif "not_logged_in" in message_upper or "login screen" in message_upper:
        status = "not_logged_in"
    elif "mfa_required" in message_upper or "mfa" in message_upper.split():
        status = "mfa_required"
    elif "login_failed" in message_upper or "failed" in message_upper:
        status = "login_failed"
    elif "login_success" in message_upper or "success" in message_upper:
        status = "login_success"
    
    return status, result


# ============== SECTION 1: DEVICE ==============

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "Diarium Automation API", "version": "2.0.0"}


@app.post("/diarium/setup-keyboard", response_model=StandardResponse, tags=["🔌 Device"])
async def setup_adb_keyboard():
    """
    ⌨️ Setup ADB Keyboard
    
    Aktifkan ADB Keyboard sebagai IME default.
    WAJIB dijalankan sekali sebelum menggunakan /diarium/login-fast.
    
    Note: Setelah ini, keyboard di HP akan berubah jadi ADB Keyboard.
    Untuk kembali ke Samsung Keyboard, ganti manual di Settings > General Management > Keyboard.
    """
    hit_time = datetime.now()
    device_id = get_current_device()
    
    if not device_id:
        return create_response(
            success=False,
            status=StatusCode.DEVICE_NOT_FOUND,
            message="No device connected",
            data=None,
            hit_time=hit_time
        )
    
    try:
        # Check current IME
        result = subprocess.run(
            [Config.ADB_PATH, "shell", "settings", "get", "secure", "default_input_method"],
            capture_output=True,
            text=True,
            timeout=10
        )
        current_ime = result.stdout.strip()
        
        # Set ADB Keyboard as default
        subprocess.run(
            [Config.ADB_PATH, "shell", "ime", "set", "com.android.adbkeyboard/.AdbIME"],
            capture_output=True,
            timeout=10
        )
        
        # Verify
        result = subprocess.run(
            [Config.ADB_PATH, "shell", "settings", "get", "secure", "default_input_method"],
            capture_output=True,
            text=True,
            timeout=10
        )
        new_ime = result.stdout.strip()
        
        is_adb_keyboard = "adbkeyboard" in new_ime.lower()
        
        return create_response(
            success=is_adb_keyboard,
            status=StatusCode.SUCCESS if is_adb_keyboard else StatusCode.ERROR,
            message="ADB Keyboard activated" if is_adb_keyboard else "Failed to activate ADB Keyboard",
            data={
                "previous_ime": current_ime,
                "current_ime": new_ime,
                "is_adb_keyboard": is_adb_keyboard
            },
            hit_time=hit_time,
            device_id=device_id
        )
        
    except Exception as e:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=f"Error setting up keyboard: {str(e)}",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )


@app.get("/diarium/devices", response_model=StandardResponse, tags=["🔌 Device"])
async def get_devices():
    """
    📱 Cek Available Devices
    
    Menampilkan semua device Android yang terhubung via ADB.
    Gunakan endpoint ini untuk memastikan device tersedia sebelum operasi lain.
    """
    hit_time = datetime.now()
    
    try:
        result = subprocess.run(
            [Config.ADB_PATH, "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        devices = []
        for line in result.stdout.split('\n'):
            # Skip header line and empty lines
            if line.startswith('List of devices') or not line.strip():
                continue
            # Check if line contains a device (has 'device' word after device ID)
            if ' device ' in line or line.strip().endswith('device'):
                parts = line.split()
                if len(parts) >= 2:
                    device_id = parts[0]
                    model = ""
                    for part in parts:
                        if part.startswith("model:"):
                            model = part.replace("model:", "")
                    devices.append({
                        "device_id": device_id,
                        "model": model,
                        "status": "connected"
                    })
        
        if devices:
            return create_response(
                success=True,
                status=StatusCode.SUCCESS,
                message=f"Found {len(devices)} device(s)",
                data={"devices": devices, "count": len(devices)},
                hit_time=hit_time,
                device_id=devices[0]["device_id"] if devices else None
            )
        else:
            return create_response(
                success=False,
                status=StatusCode.DEVICE_NOT_FOUND,
                message="No devices connected. Please connect your Android device via USB.",
                data={"devices": [], "count": 0},
                hit_time=hit_time
            )
            
    except Exception as e:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=f"Error checking devices: {str(e)}",
            data=None,
            hit_time=hit_time
        )


# ============== SECTION 2: BEFORE LOGIN ==============

@app.get("/diarium/login-status", response_model=StandardResponse, tags=["🔐 Before Login"])
async def check_login_status():
    """
    🔍 Cek Status Login
    
    Cek apakah user sudah login di app Diarium tanpa melakukan login.
    """
    hit_time = datetime.now()
    device_id = get_current_device()
    
    if not device_id:
        return create_response(
            success=False,
            status=StatusCode.DEVICE_NOT_FOUND,
            message="No device connected",
            data=None,
            hit_time=hit_time
        )
    
    if not Config.ZAI_API_KEY:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message="API key not configured",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    prompt = """Open the Diarium app. Look at the screen carefully.
If you see a greeting with username like 'Good Morning/Afternoon/Evening! [USERNAME]', report 'STATUS:LOGGED_IN:username=[USERNAME]'.
If you see a login screen with 'NIK TelkomGroup' input field, report 'STATUS:NOT_LOGGED_IN'.
If you see any popup or dialog, report what you see."""
    
    success, message = await run_phone_agent(prompt)
    
    if not success:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=message,
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    status, data = parse_status_response(message)
    
    return create_response(
        success=True,
        status=status,
        message=message,
        data=data if data else {"raw_response": message},
        hit_time=hit_time,
        device_id=device_id
    )


@app.post("/diarium/login", response_model=StandardResponse, tags=["🔐 Before Login"])
async def login(request: LoginRequest):
    """
    🔐 Login ke Diarium
    
    Login dengan NIK dan Password.
    - Jika sudah login, return status logged_in
    - Jika perlu MFA, return status mfa_required
    - Jika gagal, return status login_failed
    """
    hit_time = datetime.now()
    device_id = get_current_device()
    
    if not device_id:
        return create_response(
            success=False,
            status=StatusCode.DEVICE_NOT_FOUND,
            message="No device connected",
            data=None,
            hit_time=hit_time
        )
    
    if not Config.ZAI_API_KEY:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message="API key not configured",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    prompt = f"""Open the Diarium app. Look at the screen carefully.

If you see a greeting like 'Good Morning/Afternoon/Evening' with a username, 
the user is ALREADY LOGGED IN - report 'STATUS:ALREADY_LOGGED_IN'.

If you see a LOGIN screen with 'NIK TelkomGroup' input field:
1. Tap on the NIK TelkomGroup input field and enter: {request.nik}
2. Tap on the Password field and enter: {request.password}
3. Find and tap/check the checkbox for 'Syarat dan Ketentuan' (Terms and Conditions)
4. Tap the 'Masuk' (Login) button

After clicking Masuk, check what happens:
- If you see an MFA/OTP input screen, report 'STATUS:MFA_REQUIRED'
- If you see an error message about wrong credentials, report 'STATUS:LOGIN_FAILED:reason=[error message]'
- If login succeeds and you see the home screen with greeting, report 'STATUS:LOGIN_SUCCESS'"""
    
    success, message = await run_phone_agent(prompt)
    
    if not success:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=message,
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    status, data = parse_status_response(message)
    
    is_success = status in ["logged_in", "already_logged_in", "login_success"]
    requires_mfa = status == "mfa_required"
    
    return create_response(
        success=is_success,
        status=StatusCode.MFA_REQUIRED if requires_mfa else (StatusCode.LOGGED_IN if is_success else StatusCode.LOGIN_FAILED),
        message=message,
        data={
            "requires_mfa": requires_mfa,
            **data
        },
        hit_time=hit_time,
        device_id=device_id
    )


@app.post("/diarium/prepare-login", response_model=StandardResponse, tags=["🔐 Before Login"])
async def prepare_login():
    """
    🚀 Persiapan Login (Rule-Based)
    
    Navigasi ke login form Diarium. Handle:
    - Launch app
    - Skip onboarding
    - Handle permission dialogs
    - Sampai di login form
    
    Gunakan endpoint ini sebelum /diarium/login-fast jika app belum di login screen.
    """
    hit_time = datetime.now()
    device_id = get_current_device()
    
    if not device_id:
        return create_response(
            success=False,
            status=StatusCode.DEVICE_NOT_FOUND,
            message="No device connected",
            data=None,
            hit_time=hit_time
        )
    
    steps_log = []
    max_dialog_attempts = 10
    
    try:
        # Step 1: Launch Diarium app
        steps_log.append("Launching Diarium app...")
        adb_launch_app(LoginScreenElements.PACKAGE_NAME)
        time.sleep(2)
        
        # Step 2: Handle dialogs/onboarding until we reach login screen or are logged in
        for dialog_attempt in range(max_dialog_attempts):
            xml_str = adb_dump_ui()
            
            if not xml_str:
                steps_log.append(f"Attempt {dialog_attempt + 1}: Failed to read screen, retrying...")
                time.sleep(1)
                continue
            
            # Check if already logged in
            logged_in, username = is_logged_in(xml_str)
            if logged_in:
                return create_response(
                    success=True,
                    status=StatusCode.LOGGED_IN,
                    message=f"Already logged in: {username}",
                    data={"on_login_screen": False, "already_logged_in": True, "username": username, "steps": steps_log},
                    hit_time=hit_time,
                    device_id=device_id
                )
            
            # Check if on login screen
            if is_on_login_screen(xml_str):
                steps_log.append("Reached login screen!")
                return create_response(
                    success=True,
                    status=StatusCode.SUCCESS,
                    message="Ready for login - on login screen",
                    data={"on_login_screen": True, "already_logged_in": False, "steps": steps_log},
                    hit_time=hit_time,
                    device_id=device_id
                )
            
            # Check if we're on Android home (app might have closed)
            if 'com.sec.android.app.launcher' in xml_str or 'com.google.android.apps.nexuslauncher' in xml_str:
                steps_log.append("On Android home, launching Diarium again...")
                adb_launch_app(LoginScreenElements.PACKAGE_NAME)
                time.sleep(2)
                continue
            
            # Try to handle dialog/onboarding
            handled, desc = handle_dialogs_and_onboarding(xml_str)
            if handled:
                steps_log.append(f"Handled: {desc}")
                time.sleep(1)
            else:
                # No dialog found, try pressing back
                steps_log.append("No dialog found, pressing back...")
                adb_press_back()
                time.sleep(0.5)
        
        # Final check
        xml_str = adb_dump_ui()
        if xml_str:
            logged_in, username = is_logged_in(xml_str)
            if logged_in:
                return create_response(
                    success=True,
                    status=StatusCode.LOGGED_IN,
                    message=f"Already logged in: {username}",
                    data={"on_login_screen": False, "already_logged_in": True, "username": username, "steps": steps_log},
                    hit_time=hit_time,
                    device_id=device_id
                )
            
            if is_on_login_screen(xml_str):
                return create_response(
                    success=True,
                    status=StatusCode.SUCCESS,
                    message="Ready for login - on login screen",
                    data={"on_login_screen": True, "already_logged_in": False, "steps": steps_log},
                    hit_time=hit_time,
                    device_id=device_id
                )
        
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message="Could not navigate to login screen",
            data={"steps": steps_log},
            hit_time=hit_time,
            device_id=device_id
        )
        
    except Exception as e:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=f"Error: {str(e)}",
            data={"steps": steps_log},
            hit_time=hit_time,
            device_id=device_id
        )


@app.post("/diarium/login-fast", response_model=StandardResponse, tags=["🔐 Before Login"])
async def login_fast(request: LoginRequest):
    """
    ⚡ Login ke Diarium (Hybrid: Rule-Based + AI)
    
    Login dengan pendekatan hybrid yang optimal:
    - **Rule-Based**: Input NIK dan Password (cepat, ~5 detik)
    - **AI-Based**: Handle checkbox, tap Masuk, verifikasi hasil (~40 detik)
    
    **Total waktu**: ~45 detik (vs ~90 detik pure AI)
    
    **Alur:**
    1. Verifikasi di login screen
    2. Clear & input NIK (rule-based)
    3. Clear & input Password (rule-based)
    4. AI: Centang checkbox, tap Masuk, verify hasil
    
    **Prerequisite:** Sudah di login screen (gunakan `/diarium/prepare-login` jika app baru dibuka)
    """
    hit_time = datetime.now()
    device_id = get_current_device()
    
    if not device_id:
        return create_response(
            success=False,
            status=StatusCode.DEVICE_NOT_FOUND,
            message="No device connected",
            data=None,
            hit_time=hit_time
        )
    
    steps_log = []
    
    try:
        # Step 1: Verify we're on login screen
        steps_log.append("Checking current screen...")
        xml_str = adb_dump_ui()
        
        if not xml_str:
            return create_response(
                success=False,
                status=StatusCode.ERROR,
                message="Failed to read screen. Use /diarium/prepare-login first.",
                data={"steps": steps_log},
                hit_time=hit_time,
                device_id=device_id
            )
        
        # Check if already logged in
        logged_in, username = is_logged_in(xml_str)
        if logged_in:
            return create_response(
                success=True,
                status=StatusCode.LOGGED_IN,
                message=f"Already logged in: {username}",
                data={"username": username, "steps": steps_log},
                hit_time=hit_time,
                device_id=device_id
            )
        
        # Check if on login screen
        if not is_on_login_screen(xml_str):
            return create_response(
                success=False,
                status=StatusCode.ERROR,
                message="Not on login screen. Use /diarium/prepare-login first.",
                data={"steps": steps_log},
                hit_time=hit_time,
                device_id=device_id
            )
        
        steps_log.append("On login screen, proceeding...")
        
        # Step 2: Clear and input NIK
        steps_log.append(f"Inputting NIK: {request.nik}")
        adb_tap(LoginScreenElements.NIK_INPUT[0], LoginScreenElements.NIK_INPUT[1])
        time.sleep(0.3)
        subprocess.run([Config.ADB_PATH, "shell", "input", "keyevent", "123"], capture_output=True, timeout=2)
        subprocess.run(
            [Config.ADB_PATH, "shell", "for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do input keyevent 67; done"],
            capture_output=True, timeout=10
        )
        time.sleep(0.1)
        subprocess.run([Config.ADB_PATH, "shell", "input", "text", request.nik], capture_output=True, timeout=10)
        time.sleep(0.3)
        
        # Step 3: Clear and input Password
        steps_log.append("Inputting Password...")
        adb_tap(LoginScreenElements.PASSWORD_INPUT[0], LoginScreenElements.PASSWORD_INPUT[1])
        time.sleep(0.3)
        subprocess.run([Config.ADB_PATH, "shell", "input", "keyevent", "123"], capture_output=True, timeout=2)
        subprocess.run(
            [Config.ADB_PATH, "shell", "for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do input keyevent 67; done"],
            capture_output=True, timeout=10
        )
        time.sleep(0.1)
        subprocess.run([Config.ADB_PATH, "shell", "input", "text", request.password], capture_output=True, timeout=10)
        time.sleep(0.5)
        
        # Step 4: Use AI to complete login (checkbox, login button, verification)
        steps_log.append("Using AI to complete login...")
        
        ai_prompt = """Look at the current screen. NIK and Password fields are already filled.

Complete the login by doing these steps:
1. Find and tap/check the checkbox near 'Syarat Ketentuan' (Terms and Conditions) - it's usually a square box on the left
2. After checking the box, tap the 'Masuk' (Login) button
3. Wait for the login to complete

After login, check what happens:
- If you see a greeting like 'Selamat Pagi/Siang/Sore' with username, report 'STATUS:LOGIN_SUCCESS'
- If you see tutorial popup or overlay, dismiss it then report 'STATUS:LOGIN_SUCCESS'
- If you see MFA/OTP screen, report 'STATUS:MFA_REQUIRED'
- If you see error or still on login screen, report 'STATUS:LOGIN_FAILED'

Do NOT input NIK or Password - they are already filled."""
        
        success, ai_message = await run_phone_agent(ai_prompt)
        steps_log.append(f"AI result: {ai_message[:100]}...")
        
        # Step 5: Check final result
        steps_log.append("Checking result...")
        time.sleep(1)
        xml_str = adb_dump_ui()
        
        if not xml_str:
            return create_response(
                success=False,
                status=StatusCode.ERROR,
                message="Failed to read result screen",
                data={"steps": steps_log, "ai_message": ai_message},
                hit_time=hit_time,
                device_id=device_id
            )
        
        # Check if logged in
        logged_in, username = is_logged_in(xml_str)
        if logged_in:
            return create_response(
                success=True,
                status=StatusCode.LOGGED_IN,
                message=f"Login successful: {username}",
                data={"username": username, "steps": steps_log},
                hit_time=hit_time,
                device_id=device_id
            )
        
        # Check if MFA required
        if 'OTP' in xml_str or 'MFA' in xml_str or 'Verification' in xml_str or 'Kode' in xml_str:
            return create_response(
                success=True,
                status=StatusCode.MFA_REQUIRED,
                message="MFA/OTP verification required",
                data={"requires_mfa": True, "steps": steps_log},
                hit_time=hit_time,
                device_id=device_id
            )
        
        # Parse AI response for status
        status, _ = parse_status_response(ai_message)
        if status in ["login_success", "logged_in"]:
            return create_response(
                success=True,
                status=StatusCode.SUCCESS,
                message="Login completed (AI confirmed)",
                data={"steps": steps_log, "ai_message": ai_message},
                hit_time=hit_time,
                device_id=device_id
            )
        
        # Still on login screen = failed
        if is_on_login_screen(xml_str):
            return create_response(
                success=False,
                status=StatusCode.LOGIN_FAILED,
                message="Login failed - check credentials or checkbox",
                data={"steps": steps_log, "ai_message": ai_message},
                hit_time=hit_time,
                device_id=device_id
            )
        
        # Unknown state - might be success
        return create_response(
            success=True,
            status=StatusCode.SUCCESS,
            message="Login completed - please verify manually",
            data={"steps": steps_log, "ai_message": ai_message},
            hit_time=hit_time,
            device_id=device_id
        )
        
    except Exception as e:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=f"Error: {str(e)}",
            data={"steps": steps_log},
            hit_time=hit_time,
            device_id=device_id
        )


@app.post("/diarium/mfa", response_model=StandardResponse, tags=["🔐 Before Login"])
async def submit_mfa(request: MFARequest):
    """
    🔑 Submit MFA Code
    
    Input kode MFA setelah login meminta verifikasi.
    """
    hit_time = datetime.now()
    device_id = get_current_device()
    
    if not device_id:
        return create_response(
            success=False,
            status=StatusCode.DEVICE_NOT_FOUND,
            message="No device connected",
            data=None,
            hit_time=hit_time
        )
    
    if not Config.ZAI_API_KEY:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message="API key not configured",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    prompt = f"""On the Diarium app, you should be on the MFA/OTP verification screen.
Enter the MFA code: {request.mfa_code} into the input field.
Then tap the verify/submit/lanjutkan button.

After submitting:
- If you see the home screen with a greeting (Good Morning/Afternoon/Evening + username), report 'STATUS:MFA_SUCCESS'
- If you see an error about invalid code, report 'STATUS:MFA_FAILED:reason=Invalid code'
- If you see another MFA prompt, report 'STATUS:MFA_RETRY'"""
    
    success, message = await run_phone_agent(prompt)
    
    if not success:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=message,
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    status, data = parse_status_response(message)
    
    is_success = status in ["mfa_success", "success", "logged_in"]
    
    return create_response(
        success=is_success,
        status=StatusCode.LOGGED_IN if is_success else StatusCode.MFA_REQUIRED,
        message=message,
        data=data if data else {"raw_response": message},
        hit_time=hit_time,
        device_id=device_id
    )


# ============== SECTION 3: AFTER LOGIN ==============

@app.get("/diarium/whoami", response_model=StandardResponse, tags=["👤 After Login"])
async def whoami():
    """
    👤 Who Am I - Get Profile Info
    
    Ambil informasi profil user yang sedang login:
    - Nama, NIK, Perusahaan, Divisi, Posisi, Telepon, Tanggal Lahir
    
    **Syarat:** User harus sudah login
    """
    hit_time = datetime.now()
    device_id = get_current_device()
    
    if not device_id:
        return create_response(
            success=False,
            status=StatusCode.DEVICE_NOT_FOUND,
            message="No device connected",
            data=None,
            hit_time=hit_time
        )
    
    if not Config.ZAI_API_KEY:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message="API key not configured",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    prompt = """In the Diarium app, you should be on the home screen.
First check: if you see a login screen with 'NIK TelkomGroup', report 'STATUS:NOT_LOGGED_IN' and stop.

If logged in, click on the profile icon or user avatar at the top of the screen to open the profile page.

Once on the profile page, read ALL the information you can see and report in this exact format:
PROFILE:
nama=[full name]
nik=[NIK number]
perusahaan=[company name]
divisi=[division]
posisi=[position/job title]
telepon=[phone number]
tanggal_lahir=[birth date]

If any field is not visible, use 'N/A' for that field.
After reading, go back to the home screen."""
    
    success, message = await run_phone_agent(prompt)
    
    if not success:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=message,
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    # Check if not logged in
    if "not_logged_in" in message.lower() or "nik telkomgroup" in message.lower():
        return create_response(
            success=False,
            status=StatusCode.NOT_LOGGED_IN,
            message="Please login first using /diarium/login endpoint",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    # Parse profile data
    profile_data = {
        "nama": None,
        "nik": None,
        "perusahaan": None,
        "divisi": None,
        "posisi": None,
        "telepon": None,
        "tanggal_lahir": None
    }
    
    # Try to extract profile fields from message
    for line in message.split('\n'):
        line = line.strip()
        for field in profile_data.keys():
            if line.lower().startswith(f"{field}="):
                value = line.split("=", 1)[1].strip()
                profile_data[field] = value if value and value.lower() != "n/a" else None
    
    profile_data["raw_response"] = message
    
    return create_response(
        success=True,
        status=StatusCode.LOGGED_IN,
        message="Profile retrieved successfully",
        data=profile_data,
        hit_time=hit_time,
        device_id=device_id
    )


# ============== SECTION 4: AFTER CHECK-IN ==============

@app.post("/diarium/checkout", response_model=StandardResponse, tags=["✅ After Check-In"])
async def checkout(request: CheckoutRequest):
    """
    ✅ Checkout Routine
    
    Melakukan checkout dari Diarium dengan langkah:
    1. Cek apakah tombol checkout tersedia
    2. Selesaikan semua aktivitas In Progress (opsional)
    3. Klik Check-Out, pilih status kesehatan, simpan
    
    **Syarat:** User harus sudah login dan sudah check-in
    
    **Return:**
    - checkout_success: Berhasil checkout
    - checkout_not_available: Belum check-in
    - checkout_already_done: Sudah checkout hari ini
    """
    hit_time = datetime.now()
    device_id = get_current_device()
    
    if not device_id:
        return create_response(
            success=False,
            status=StatusCode.DEVICE_NOT_FOUND,
            message="No device connected",
            data=None,
            hit_time=hit_time
        )
    
    if not Config.ZAI_API_KEY:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message="API key not configured",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    # Step 1: Check if checkout is available
    check_prompt = """In the Diarium app home screen, look for the Check-Out button/section.
If you see 'Check-Out' button with time (e.g., '17:22 WIB'), report 'CHECKOUT:AVAILABLE'.
If you see 'Check-In' button instead, report 'CHECKOUT:NOT_AVAILABLE:reason=Not checked in yet'.
If you see a message like 'Sudah checkout' or the checkout section shows completed status, report 'CHECKOUT:ALREADY_DONE'.
If you see a login screen, report 'STATUS:NOT_LOGGED_IN'."""
    
    success, message = await run_phone_agent(check_prompt)
    
    if not success:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=message,
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    message_lower = message.lower()
    
    # Check login status
    if "not_logged_in" in message_lower:
        return create_response(
            success=False,
            status=StatusCode.NOT_LOGGED_IN,
            message="Please login first",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    # Check if already done
    if "already_done" in message_lower or "sudah checkout" in message_lower:
        return create_response(
            success=True,
            status=StatusCode.CHECKOUT_ALREADY_DONE,
            message="Already checked out today",
            data={"already_checkout": True},
            hit_time=hit_time,
            device_id=device_id
        )
    
    # Check if not available
    if "not_available" in message_lower or "check-in" in message_lower:
        return create_response(
            success=False,
            status=StatusCode.CHECKOUT_NOT_AVAILABLE,
            message="Checkout not available. Please check-in first.",
            data={"reason": "Not checked in yet"},
            hit_time=hit_time,
            device_id=device_id
        )
    
    # Step 2: Complete activities if requested
    activities_completed = 0
    if request.complete_activities:
        activity_prompt = """In the Diarium app, click 'Lihat aktivitas' or 'Cek selengkapnya' to view activities.
For each activity that shows 'In Progress' status, tap on the dropdown and change it to 'Done'.
Do this for ALL in progress items.
After all items are changed to Done, report 'ACTIVITIES:COMPLETED:count=[number of items changed]'.
If no items need to be changed, report 'ACTIVITIES:NONE_PENDING'.
Then go back to the home screen."""
        
        success, act_message = await run_phone_agent(activity_prompt)
        if success:
            if "count=" in act_message.lower():
                try:
                    count_part = act_message.lower().split("count=")[1].split()[0]
                    activities_completed = int(''.join(filter(str.isdigit, count_part)))
                except:
                    pass
    
    # Step 3: Perform checkout
    checkout_prompt = f"""In the Diarium app, click the 'Check-Out' button.
On the Check-Out screen:
1. Select '{request.health_status.value}' option (look for Sehat/Kurang Fit/Sakit options)
2. Scroll down and click 'Simpan' button
3. When confirmation dialog appears, click 'Check Out' to confirm

After checkout:
- If successful and back to home screen, report 'CHECKOUT:SUCCESS:time=[checkout time shown]'
- If error occurs, report 'CHECKOUT:FAILED:reason=[error message]'"""
    
    success, checkout_message = await run_phone_agent(checkout_prompt)
    
    if not success:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=checkout_message,
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    checkout_lower = checkout_message.lower()
    
    if "success" in checkout_lower or "berhasil" in checkout_lower:
        return create_response(
            success=True,
            status=StatusCode.CHECKOUT_SUCCESS,
            message="Checkout completed successfully",
            data={
                "health_status": request.health_status.value,
                "activities_completed": activities_completed,
                "raw_response": checkout_message
            },
            hit_time=hit_time,
            device_id=device_id
        )
    else:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=f"Checkout may have failed: {checkout_message}",
            data={"raw_response": checkout_message},
            hit_time=hit_time,
            device_id=device_id
        )


# ============== SECTION 5: LOGOUT ==============

@app.post("/diarium/logout", response_model=StandardResponse, tags=["🚪 Logout"])
async def logout():
    """
    🚪 Logout dari Diarium
    
    Keluar dari akun Diarium yang sedang login.
    """
    hit_time = datetime.now()
    device_id = get_current_device()
    
    if not device_id:
        return create_response(
            success=False,
            status=StatusCode.DEVICE_NOT_FOUND,
            message="No device connected",
            data=None,
            hit_time=hit_time
        )
    
    if not Config.ZAI_API_KEY:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message="API key not configured",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    prompt = """In the Diarium app, click on the profile icon or menu (usually at bottom right or top).
Look for 'Logout' or 'Keluar' button and tap it.
If confirmation dialog appears, confirm the logout.
After logout, if you see the login screen with 'NIK TelkomGroup', report 'LOGOUT:SUCCESS'.
If logout failed or button not found, report 'LOGOUT:FAILED:reason=[what happened]'."""
    
    success, message = await run_phone_agent(prompt)
    
    if not success:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=message,
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
    
    message_lower = message.lower()
    
    if "success" in message_lower or "login screen" in message_lower or "nik telkomgroup" in message_lower:
        return create_response(
            success=True,
            status=StatusCode.NOT_LOGGED_IN,
            message="Logout successful",
            data={"logged_out": True},
            hit_time=hit_time,
            device_id=device_id
        )
    else:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=f"Logout may have failed: {message}",
            data={"raw_response": message},
            hit_time=hit_time,
            device_id=device_id
        )


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
