"""
Actions Router
==============

Endpoints for attendance actions (check-in, check-out, whoami).
"""

import asyncio
from datetime import datetime
from fastapi import APIRouter

from ..config import Config, logger
from ..models import (
    StandardResponse, StatusCode,
    CheckInRequest, CheckoutRequest,
    create_response
)
from ..adb_utils import (
    get_current_device,
    adb_launch_app, adb_force_stop_app,
    is_logged_in, has_beranda_menu
)
from ..ai_agent import run_phone_agent, parse_status_response

router = APIRouter()


# =============================================================================
# CHECK-IN ENDPOINT
# =============================================================================

@router.post("/diarium/checkin", response_model=StandardResponse, tags=["📍 Attendance"])
async def check_in(request: CheckInRequest = None):
    """
    📍 Check-in Attendance
    
    Melakukan check-in kehadiran di Diarium.
    
    Prasyarat:
    - Sudah login ke aplikasi Diarium
    """
    hit_time = datetime.now()
    device_id = get_current_device()
    
    logger.info(f"[checkin] Started - device: {device_id}")
    
    if not device_id:
        logger.error("[checkin] No device connected")
        return create_response(
            success=False,
            status=StatusCode.DEVICE_NOT_FOUND,
            message="No device connected",
            data=None,
            hit_time=hit_time
        )
    
    try:
        # Check if logged in
        if not is_logged_in() and not has_beranda_menu():
            logger.warning("[checkin] Not logged in")
            return create_response(
                success=False,
                status=StatusCode.NOT_LOGGED_IN,
                message="Not logged in. Please login first.",
                data=None,
                hit_time=hit_time,
                device_id=device_id
            )
        
        # Build task prompt
        task = """
        Lakukan check-in kehadiran di aplikasi Diarium:
        
        1. Pastikan kamu di halaman Beranda
        2. Cari tombol "Check In" atau "Presensi Masuk" atau tombol hijau untuk masuk
        3. Klik tombol tersebut
        4. Jika muncul konfirmasi lokasi, klik OK/Confirm
        5. Jika muncul camera untuk selfie, ambil foto
        6. Tunggu konfirmasi check-in berhasil
        
        Jika check-in berhasil, laporkan STATUS:SUCCESS
        Jika gagal (sudah check-in, lokasi invalid, dll), laporkan STATUS:FAILED beserta alasannya
        """
        
        ai_success, ai_message = await run_phone_agent(task)
        logger.info(f"[checkin] AI result: success={ai_success}, message={ai_message}")
        
        status, _ = parse_status_response(ai_message)
        duration = (datetime.now() - hit_time).total_seconds()
        
        if status == "success" or ai_success:
            logger.info(f"[checkin] ✅ Success - duration: {duration:.2f}s")
        else:
            logger.warning(f"[checkin] ❌ Failed - duration: {duration:.2f}s, message: {ai_message}")
        
        return create_response(
            success=status == "success" or ai_success,
            status=StatusCode.SUCCESS if (status == "success" or ai_success) else StatusCode.ERROR,
            message=ai_message,
            data={"ai_success": ai_success, "ai_message": ai_message},
            hit_time=hit_time,
            device_id=device_id
        )
        
    except Exception as e:
        logger.exception(f"[checkin] Exception: {str(e)}")
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=f"Check-in error: {str(e)}",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )


# =============================================================================
# CHECK-OUT ENDPOINT
# =============================================================================

@router.post("/diarium/checkout", response_model=StandardResponse, tags=["📍 Attendance"])
async def check_out(request: CheckoutRequest = None):
    """
    🏠 Check-out Attendance
    
    Melakukan check-out kehadiran di Diarium.
    
    Prasyarat:
    - Sudah login ke aplikasi Diarium
    - Sudah melakukan check-in sebelumnya
    """
    hit_time = datetime.now()
    device_id = get_current_device()
    
    logger.info(f"[checkout] Started - device: {device_id}")
    
    if not device_id:
        logger.error("[checkout] No device connected")
        return create_response(
            success=False,
            status=StatusCode.DEVICE_NOT_FOUND,
            message="No device connected",
            data=None,
            hit_time=hit_time
        )
    
    try:
        # Check if logged in
        if not is_logged_in() and not has_beranda_menu():
            logger.warning("[checkout] Not logged in")
            return create_response(
                success=False,
                status=StatusCode.NOT_LOGGED_IN,
                message="Not logged in. Please login first.",
                data=None,
                hit_time=hit_time,
                device_id=device_id
            )
        
        # Build task prompt
        task = """
        Lakukan check-out kehadiran di aplikasi Diarium:
        
        1. Pastikan kamu di halaman Beranda
        2. Cari tombol "Check Out" atau "Presensi Pulang" atau tombol untuk pulang
        3. Klik tombol tersebut
        4. Jika muncul konfirmasi lokasi, klik OK/Confirm
        5. Jika muncul camera untuk selfie, ambil foto
        6. Tunggu konfirmasi check-out berhasil
        
        Jika check-out berhasil, laporkan STATUS:SUCCESS
        Jika gagal (belum check-in, lokasi invalid, dll), laporkan STATUS:FAILED beserta alasannya
        """
        
        ai_success, ai_message = await run_phone_agent(task)
        logger.info(f"[checkout] AI result: success={ai_success}, message={ai_message}")
        
        status, _ = parse_status_response(ai_message)
        duration = (datetime.now() - hit_time).total_seconds()
        
        if status == "success" or ai_success:
            logger.info(f"[checkout] ✅ Success - duration: {duration:.2f}s")
        else:
            logger.warning(f"[checkout] ❌ Failed - duration: {duration:.2f}s, message: {ai_message}")
        
        return create_response(
            success=status == "success" or ai_success,
            status=StatusCode.SUCCESS if (status == "success" or ai_success) else StatusCode.ERROR,
            message=ai_message,
            data={"ai_success": ai_success, "ai_message": ai_message},
            hit_time=hit_time,
            device_id=device_id
        )
        
    except Exception as e:
        logger.exception(f"[checkout] Exception: {str(e)}")
        return create_response(
            success=False,
            status=StatusCode.ERROR,
            message=f"Check-out error: {str(e)}",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )


# =============================================================================
# WHOAMI ENDPOINT
# =============================================================================

@router.get("/diarium/whoami", response_model=StandardResponse, tags=["👤 User"])
async def whoami():
    """
    👤 Get Current User Info
    
    Ambil informasi user yang sedang login.
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
        # Check if logged in
        if not is_logged_in() and not has_beranda_menu():
            return create_response(
                success=False,
                status=StatusCode.NOT_LOGGED_IN,
                message="Not logged in",
                data=None,
                hit_time=hit_time,
                device_id=device_id
            )
        
        task = """
        Ambil informasi user yang sedang login:
        
        1. Klik menu Profil di bottom navigation
        2. Baca nama user yang tampil
        3. Baca NIK/NIP jika ada
        4. Baca unit kerja jika ada
        
        Laporkan informasi dalam format:
        NAME: [nama user]
        NIK: [nik/nip]
        UNIT: [unit kerja]
        """
        
        ai_success, ai_message = await run_phone_agent(task)
        
        # Parse user info from AI response
        user_info = {
            "name": None,
            "nik": None,
            "unit": None,
            "raw_response": ai_message
        }
        
        for line in ai_message.split("\n"):
            line = line.strip()
            if line.upper().startswith("NAME:"):
                user_info["name"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("NIK:"):
                user_info["nik"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("UNIT:"):
                user_info["unit"] = line.split(":", 1)[1].strip()
        
        return create_response(
            success=True,
            status=StatusCode.SUCCESS,
            message="User info retrieved",
            data={"user": user_info, "ai_success": ai_success},
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
# APP CONTROL ENDPOINTS
# =============================================================================

@router.post("/diarium/launch", response_model=StandardResponse, tags=["📱 App Control"])
async def launch_app():
    """
    🚀 Launch Diarium App
    
    Membuka aplikasi Diarium.
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
        adb_launch_app(Config.DIARIUM_PACKAGE)
        await asyncio.sleep(2)
        
        return create_response(
            success=True,
            status=StatusCode.SUCCESS,
            message="App launched",
            data={"package": Config.DIARIUM_PACKAGE},
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


@router.post("/diarium/stop", response_model=StandardResponse, tags=["📱 App Control"])
async def stop_app():
    """
    🛑 Stop Diarium App
    
    Force stop aplikasi Diarium.
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
        adb_force_stop_app(Config.DIARIUM_PACKAGE)
        
        return create_response(
            success=True,
            status=StatusCode.SUCCESS,
            message="App stopped",
            data={"package": Config.DIARIUM_PACKAGE},
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
