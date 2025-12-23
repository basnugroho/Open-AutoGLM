"""
Device Router
=============

Endpoints for device management and health checks.
"""

import subprocess
from datetime import datetime
from fastapi import APIRouter

from ..config import Config, logger
from ..models import StandardResponse, StatusCode, create_response
from ..adb_utils import get_current_device, get_all_devices

router = APIRouter()


@router.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "Diarium Automation API", "version": "2.1.0"}


@router.get("/diarium/devices", response_model=StandardResponse, tags=["🔌 Device"])
async def list_devices():
    """
    📱 List Connected Devices
    
    Menampilkan semua device Android yang terhubung via ADB.
    """
    hit_time = datetime.now()
    
    devices = get_all_devices()
    
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


@router.post("/diarium/setup-keyboard", response_model=StandardResponse, tags=["🔌 Device"])
async def setup_adb_keyboard():
    """
    ⌨️ Setup ADB Keyboard
    
    Aktifkan ADB Keyboard sebagai IME default.
    Dibutuhkan untuk input text yang reliable.
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
        # Get current IME
        result = subprocess.run(
            [Config.ADB_PATH, "shell", "settings", "get", "secure", "default_input_method"],
            capture_output=True,
            text=True,
            timeout=10
        )
        current_ime = result.stdout.strip()
        
        # Set ADB Keyboard
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
            message=f"Error: {str(e)}",
            data=None,
            hit_time=hit_time,
            device_id=device_id
        )
