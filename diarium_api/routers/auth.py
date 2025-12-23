"""
Auth Router
============

Endpoints for authentication (login, logout, MFA).
- /diarium/login - Hybrid login (rule-based + AI verification)
- /diarium/logout - Click profile, scroll bottom, click logout
- /diarium/mfa - Handle MFA verification
"""

import asyncio
import subprocess
import time
from datetime import datetime
from fastapi import APIRouter

from ..config import Config, LoginScreenElements, HomeScreenElements, logger
from ..models import (
    StandardResponse, StatusCode, 
    LoginRequest, MFARequest,
    create_response
)
from ..adb_utils import (
    get_current_device,
    adb_launch_app, adb_force_stop_app, adb_clear_app_data,
    adb_tap, adb_long_tap, adb_scroll_to_bottom,
    adb_input_text, adb_dump_ui, clear_and_input_field,
    is_on_login_screen, is_logged_in, has_beranda_menu,
    handle_dialogs_and_permissions
)
from ..ai_agent import run_phone_agent, parse_status_response

router = APIRouter()


# =============================================================================
# LOGIN ENDPOINTS
# =============================================================================

@router.post("/diarium/prepare-login", response_model=StandardResponse, tags=["🔐 Auth"])
async def prepare_login():
    """
    🧹 Prepare for Login
    
    Clear app data dan launch fresh, handle semua permission dan onboarding:
    1. Notifikasi -> Allow
    2. Location -> While using the app
    3. Welcome screen -> Skip
    4. Feature explanation -> Get Started
    5. Return saat sudah di halaman login
    """
    hit_time = datetime.now()
    device_id = get_current_device()
    
    logger.info(f"[prepare-login] Started - device: {device_id}")
    
    if not device_id:
        logger.error("[prepare-login] No device connected")
        return create_response(
            success=False,
            status=StatusCode.DEVICE_NOT_FOUND,
            message="No device connected",
            data=None,
            hit_time=hit_time
        )
    
    steps_log = []
    
    try:
        # Step 1: Clear app data
        steps_log.append("Clearing app data...")
        logger.info("[prepare-login] Step 1: Clearing app data")
        adb_clear_app_data(Config.DIARIUM_PACKAGE)
        await asyncio.sleep(1)
        
        # Step 2: Launch app
        steps_log.append("Launching app...")
        logger.info("[prepare-login] Step 2: Launching app")
        adb_launch_app(Config.DIARIUM_PACKAGE)
        await asyncio.sleep(3)
        
        # Step 3: Use AI to handle all permissions and onboarding
        steps_log.append("Handling permissions and onboarding with AI...")
        logger.info("[prepare-login] Step 3: AI handling permissions and onboarding")
        
        ai_task = """
Kamu baru saja membuka aplikasi Diarium yang fresh (data sudah di-clear).
Lakukan langkah-langkah berikut secara berurutan:

1. Jika muncul permission dialog untuk NOTIFIKASI:
   - Klik tombol "Allow" atau "Izinkan"

2. Jika muncul permission dialog untuk LOKASI (Device location):
   - Klik tombol "While using the app" atau "Saat menggunakan aplikasi"

3. Jika muncul WELCOME SCREEN dengan gambar dan tulisan:
   - Cari dan klik tombol "Skip" di pojok kanan atas

4. Jika muncul layar PENJELASAN FITUR:
   - Klik tombol "Get Started" atau "Mulai"

5. Ulangi langkah 1-4 sampai kamu melihat HALAMAN LOGIN dengan:
   - Field "NIK TelkomGroup"
   - Field "Password"  
   - Tombol "Masuk"

Setelah sampai di halaman login, laporkan: STATUS:SUCCESS - Sudah di halaman login

Jika ada masalah, laporkan: STATUS:ERROR - [jelaskan masalahnya]
"""
        
        ai_success, ai_message = await run_phone_agent(ai_task)
        steps_log.append(f"AI result: {ai_message}")
        logger.info(f"[prepare-login] AI result: success={ai_success}, message={ai_message}")
        
        # Step 4: Verify we're on login screen
        await asyncio.sleep(1)
        on_login = is_on_login_screen()
        
        if on_login:
            steps_log.append("✅ Successfully reached login screen")
            duration = (datetime.now() - hit_time).total_seconds()
            logger.info(f"[prepare-login] ✅ Success - reached login screen in {duration:.2f}s")
            return create_response(
                success=True,
                status=StatusCode.SUCCESS,
                message="Ready for login - app prepared successfully",
                data={
                    "on_login_screen": True,
                    "steps": steps_log,
                    "ai_message": ai_message
                },
                hit_time=hit_time,
                device_id=device_id
            )
        else:
            steps_log.append("❌ Not on login screen yet")
            logger.warning(f"[prepare-login] ❌ Failed - not on login screen")
            return create_response(
                success=False,
                status=StatusCode.ERROR,
                message="Not on login screen - may need manual intervention",
                data={
                    "on_login_screen": False,
                    "steps": steps_log,
                    "ai_message": ai_message
                },
                hit_time=hit_time,
                device_id=device_id
            )
        
    except Exception as e:
        steps_log.append(f"Error: {str(e)}")
        logger.exception(f"[prepare-login] Exception: {str(e)}")
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=f"Error: {str(e)}",
            data={"steps": steps_log},
            hit_time=hit_time,
            device_id=device_id
        )


@router.post("/diarium/login", response_model=StandardResponse, tags=["🔐 Auth"])
async def login_fast(request: LoginRequest):
    """
    🚀 Login Diarium (Full AI)
    
    Melakukan login menggunakan AI untuk:
    1. Input NIK dan Password
    2. Centang checkbox syarat & ketentuan
    3. Klik tombol Masuk
    4. Tunggu max 10 detik untuk verifikasi
    
    Jika dalam 10 detik tidak berhasil login (masih di halaman login),
    maka dianggap gagal dan user perlu mengulang dengan NIK/Password yang benar.
    """
    hit_time = datetime.now()
    device_id = get_current_device()
    
    logger.info(f"[login] Started - NIK: {request.nik}, device: {device_id}")
    
    if not device_id:
        logger.error("[login] No device connected")
        return create_response(
            success=False,
            status=StatusCode.DEVICE_NOT_FOUND,
            message="No device connected",
            data=None,
            hit_time=hit_time
        )
    
    steps_log = []
    
    try:
        # Step 1: Check if already logged in
        steps_log.append("Checking current state...")
        logger.info("[login] Step 1: Checking current state")
        if is_logged_in():
            steps_log.append("Already logged in!")
            logger.info("[login] Already logged in")
            return create_response(
                success=True,
                status=StatusCode.ALREADY_LOGGED_IN,
                message="Already logged in",
                data={"steps": steps_log, "beranda_available": has_beranda_menu()},
                hit_time=hit_time,
                device_id=device_id
            )
        
        # Step 2: Verify on login screen
        if not is_on_login_screen():
            steps_log.append("Not on login screen, launching app...")
            logger.info("[login] Not on login screen, launching app")
            adb_force_stop_app(Config.DIARIUM_PACKAGE)
            await asyncio.sleep(1)
            adb_launch_app(Config.DIARIUM_PACKAGE)
            await asyncio.sleep(3)
            
            if not is_on_login_screen():
                steps_log.append("Failed to reach login screen")
                logger.warning("[login] Failed to reach login screen")
                return create_response(
                    success=False,
                    status=StatusCode.ERROR,
                    message="Cannot reach login screen. Run /diarium/prepare-login first.",
                    data={"steps": steps_log},
                    hit_time=hit_time,
                    device_id=device_id
                )
        
        steps_log.append("On login screen, using AI for login...")
        logger.info("[login] Step 2: On login screen, using AI")
        
        # Step 3: Use AI to fill form and click login
        ai_task = f"""
Lakukan login ke aplikasi Diarium dengan langkah berikut:

1. Tap pada field NIK TelkomGroup (field input pertama)
2. Hapus semua text yang ada di field tersebut (select all lalu delete)
3. Ketik NIK: {request.nik}

4. Tap pada field Password (field input kedua) 
5. Hapus semua text yang ada di field tersebut (PENTING: select all lalu delete)
6. Ketik Password: {request.password}

7. Centang checkbox "Syarat & Ketentuan" jika belum tercentang

8. Klik tombol "Masuk" (tombol biru besar)

Setelah klik Masuk, JANGAN lakukan apa-apa lagi. Cukup laporkan bahwa sudah klik tombol Masuk.
"""
        
        ai_success, ai_message = await run_phone_agent(ai_task)
        steps_log.append(f"AI filled form and clicked Masuk: {ai_message}")
        logger.info(f"[login] AI result: success={ai_success}, message={ai_message}")
        
        # Step 4: Wait and check login result (max 10 seconds)
        steps_log.append("Waiting up to 10 seconds for login result...")
        logger.info("[login] Step 3: Waiting for login result (max 10s)")
        
        login_success = False
        max_wait = 10
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            await asyncio.sleep(1)
            
            # Check if we're still on login screen
            still_on_login = is_on_login_screen()
            
            if not still_on_login:
                # We left login screen - might be logged in or permission dialog
                beranda = has_beranda_menu()
                logged_in = is_logged_in()
                
                if beranda or logged_in:
                    login_success = True
                    steps_log.append(f"✅ Login successful after {int(time.time() - start_time)}s")
                    break
                else:
                    # Handle permission dialogs
                    steps_log.append("Left login screen, handling dialogs...")
                    await handle_dialogs_and_permissions(max_attempts=3)
                    await asyncio.sleep(1)
                    
                    if has_beranda_menu() or is_logged_in():
                        login_success = True
                        steps_log.append("✅ Login successful after handling dialogs")
                        break
        
        # Step 5: Return result
        duration = (datetime.now() - hit_time).total_seconds()
        if login_success:
            logger.info(f"[login] ✅ Success - NIK: {request.nik}, duration: {duration:.2f}s")
            return create_response(
                success=True,
                status=StatusCode.SUCCESS,
                message="Login successful",
                data={
                    "steps": steps_log,
                    "beranda_available": has_beranda_menu()
                },
                hit_time=hit_time,
                device_id=device_id
            )
        else:
            # Still on login screen after 10 seconds = login failed
            steps_log.append("❌ Still on login screen after 10 seconds - login failed")
            logger.warning(f"[login] ❌ Failed - NIK: {request.nik}, still on login screen after {duration:.2f}s")
            return create_response(
                success=False,
                status=StatusCode.LOGIN_FAILED,
                message="Login gagal - NIK atau Password tidak valid. Silakan periksa dan coba lagi.",
                data={
                    "steps": steps_log,
                    "error_type": "invalid_credentials",
                    "hint": "Pastikan NIK dan Password sudah benar. Toast error muncul sebentar lalu hilang."
                },
                hit_time=hit_time,
                device_id=device_id
            )
            
    except Exception as e:
        steps_log.append(f"Error: {str(e)}")
        logger.exception(f"[login] Exception: {str(e)}")
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=f"Login error: {str(e)}",
            data={"steps": steps_log},
            hit_time=hit_time,
            device_id=device_id
        )


@router.get("/diarium/login-status", response_model=StandardResponse, tags=["🔐 Auth"])
async def check_login_status():
    """
    👁️ Check Login Status
    
    Cek apakah saat ini sudah login atau masih di halaman login.
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
        on_login = is_on_login_screen()
        logged_in = is_logged_in()
        beranda = has_beranda_menu()
        
        if logged_in or beranda:
            status_msg = "Logged in"
            status_code = StatusCode.ALREADY_LOGGED_IN
        elif on_login:
            status_msg = "On login screen"
            status_code = StatusCode.NOT_LOGGED_IN
        else:
            status_msg = "Unknown state"
            status_code = StatusCode.ERROR
        
        return create_response(
            success=True,
            status=status_code,
            message=status_msg,
            data={
                "on_login_screen": on_login,
                "is_logged_in": logged_in,
                "beranda_available": beranda
            },
            hit_time=hit_time,
            device_id=device_id
        )
        
    except Exception as e:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=f"Error: {str(e)}",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )


# =============================================================================
# LOGOUT ENDPOINT
# =============================================================================

@router.post("/diarium/logout", response_model=StandardResponse, tags=["🔐 Auth"])
async def logout():
    """
    🚪 Logout Diarium
    
    Melakukan logout dengan flow:
    1. Klik menu Profil
    2. Scroll mentok ke bawah
    3. Klik tombol Keluar/Logout
    
    Flow selesai jika kembali ke halaman login.
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
        # Check if already on login screen
        if is_on_login_screen():
            steps_log.append("Already on login screen")
            return create_response(
                success=True,
                status=StatusCode.NOT_LOGGED_IN,
                message="Already logged out",
                data={"steps": steps_log, "on_login_screen": True},
                hit_time=hit_time,
                device_id=device_id
            )
        
        # Step 1: Click Profile menu
        steps_log.append("Clicking Profil menu...")
        adb_tap(*HomeScreenElements.MENU_PROFIL)
        await asyncio.sleep(2)
        
        # Step 2: Scroll to bottom
        steps_log.append("Scrolling to bottom...")
        adb_scroll_to_bottom(scroll_count=5)
        await asyncio.sleep(1)
        
        # Step 3: Look for and click Logout/Keluar button
        steps_log.append("Looking for Keluar/Logout button...")
        
        # Try to find logout button in UI dump
        ui_dump = adb_dump_ui()
        
        logout_clicked = False
        logout_keywords = ["keluar", "logout", "sign out", "log out"]
        
        for keyword in logout_keywords:
            if keyword.lower() in ui_dump.lower():
                steps_log.append(f"Found '{keyword}' in UI")
                # Use AI to click the logout button
                break
        
        # Use AI to find and click logout button
        steps_log.append("Using AI to click Keluar button...")
        ai_success, ai_message = await run_phone_agent(
            "Kamu sedang di halaman Profil. "
            "Scroll ke bawah jika perlu, lalu cari dan klik tombol 'Keluar' atau 'Logout'. "
            "Jika muncul konfirmasi, klik 'Ya' atau 'OK' untuk konfirmasi logout."
        )
        
        steps_log.append(f"AI result: {ai_message}")
        
        # Wait for logout process
        await asyncio.sleep(3)
        
        # Verify logout - check if back to login screen
        max_wait = 10  # seconds
        start_time = time.time()
        back_to_login = False
        
        while time.time() - start_time < max_wait:
            if is_on_login_screen():
                back_to_login = True
                break
            await asyncio.sleep(1)
        
        if back_to_login:
            steps_log.append("✅ Back to login screen - Logout successful!")
            return create_response(
                success=True,
                status=StatusCode.SUCCESS,
                message="Logout successful - back to login screen",
                data={"steps": steps_log, "on_login_screen": True},
                hit_time=hit_time,
                device_id=device_id
            )
        else:
            steps_log.append("❌ Not back to login screen")
            return create_response(
                success=False,
                status=StatusCode.ERROR,
                message="Logout may have failed - not on login screen",
                data={
                    "steps": steps_log,
                    "on_login_screen": False,
                    "ai_result": ai_message
                },
                hit_time=hit_time,
                device_id=device_id
            )
            
    except Exception as e:
        steps_log.append(f"Error: {str(e)}")
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=f"Logout error: {str(e)}",
            data={"steps": steps_log},
            hit_time=hit_time,
            device_id=device_id
        )


# =============================================================================
# MFA ENDPOINT
# =============================================================================

@router.post("/diarium/mfa", response_model=StandardResponse, tags=["🔐 Auth"])
async def verify_mfa(request: MFARequest):
    """
    🔒 Verify MFA Code
    
    Input kode MFA jika diminta setelah login.
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
        # Use AI to input MFA code
        task = f"""
        Input kode MFA berikut: {request.mfa_code}
        
        Langkah-langkah:
        1. Cari field input OTP/MFA
        2. Ketik kode: {request.mfa_code}
        3. Klik tombol Verify/Submit/OK
        4. Tunggu hasil verifikasi
        
        Jika berhasil, laporkan STATUS:SUCCESS
        Jika gagal, laporkan STATUS:FAILED
        """
        
        ai_success, ai_message = await run_phone_agent(task)
        
        status, _ = parse_status_response(ai_message)
        
        return create_response(
            success=status == "success" or status == "login_success",
            status=StatusCode.SUCCESS if status == "success" else StatusCode.MFA_REQUIRED,
            message=ai_message,
            data={"ai_success": ai_success, "ai_message": ai_message},
            hit_time=hit_time,
            device_id=device_id
        )
        
    except Exception as e:
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=f"MFA error: {str(e)}",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
