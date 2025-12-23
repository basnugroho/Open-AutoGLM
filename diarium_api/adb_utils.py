"""
ADB Utilities Module
====================

Direct ADB control functions for fast, reliable operations.
"""

import subprocess
import time
import re
import xml.etree.ElementTree as ET
from typing import Optional

from .config import Config


# ============================================================================
# BASIC ADB COMMANDS
# ============================================================================

def adb_tap(x: int, y: int) -> bool:
    """Tap at specific screen coordinates."""
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
    """Long tap using swipe trick (more reliable for checkboxes)."""
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


def adb_swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
    """Swipe from (x1,y1) to (x2,y2)."""
    try:
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "swipe", 
             str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
            capture_output=True,
            timeout=5
        )
        return True
    except Exception:
        return False


def adb_scroll_down(amount: int = 500) -> bool:
    """Scroll down on screen."""
    return adb_swipe(540, 1500, 540, 1500 - amount, 300)


def adb_scroll_to_bottom(times: int = 5) -> bool:
    """Scroll to bottom of screen by swiping multiple times."""
    for _ in range(times):
        adb_swipe(540, 1800, 540, 800, 200)
        time.sleep(0.3)
    return True


def adb_input_text(text: str) -> bool:
    """Input text using direct ADB shell input."""
    try:
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "text", text],
            capture_output=True,
            timeout=10
        )
        return True
    except Exception:
        return False


def adb_press_back() -> bool:
    """Press BACK button."""
    try:
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "keyevent", "4"],
            capture_output=True,
            timeout=3
        )
        return True
    except Exception:
        return False


def adb_press_home() -> bool:
    """Press HOME button."""
    try:
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "keyevent", "3"],
            capture_output=True,
            timeout=3
        )
        return True
    except Exception:
        return False


def adb_force_stop_app(package: str) -> bool:
    """Force stop an app."""
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
    """Launch app using monkey command."""
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


def adb_clear_app_data(package: str) -> bool:
    """Clear app data."""
    try:
        subprocess.run(
            [Config.ADB_PATH, "shell", "pm", "clear", package],
            capture_output=True,
            timeout=10
        )
        return True
    except Exception:
        return False


# ============================================================================
# UI DUMP & DETECTION
# ============================================================================

def adb_dump_ui() -> Optional[str]:
    """Dump UI hierarchy and return as XML string."""
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


def find_element_by_text(xml_str: str, text: str, partial: bool = False) -> Optional[tuple[int, int]]:
    """Find element center coordinates by text."""
    try:
        root = ET.fromstring(xml_str)
        for elem in root.iter('node'):
            elem_text = elem.get('text', '')
            if partial:
                if text.lower() in elem_text.lower():
                    bounds = elem.get('bounds')
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        return ((x1 + x2) // 2, (y1 + y2) // 2)
            else:
                if elem_text == text:
                    bounds = elem.get('bounds')
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        return ((x1 + x2) // 2, (y1 + y2) // 2)
        return None
    except Exception:
        return None


def find_element_by_content_desc(xml_str: str, content_desc: str, partial: bool = False) -> Optional[tuple[int, int]]:
    """Find element center coordinates by content-desc."""
    try:
        root = ET.fromstring(xml_str)
        for elem in root.iter('node'):
            elem_desc = elem.get('content-desc', '')
            if partial:
                if content_desc.lower() in elem_desc.lower():
                    bounds = elem.get('bounds')
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        return ((x1 + x2) // 2, (y1 + y2) // 2)
            else:
                if elem_desc == content_desc:
                    bounds = elem.get('bounds')
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        return ((x1 + x2) // 2, (y1 + y2) // 2)
        return None
    except Exception:
        return None


# ============================================================================
# SCREEN STATE DETECTION
# ============================================================================

def is_on_login_screen(xml_str: str = None) -> bool:
    """Check if currently on login screen."""
    try:
        if xml_str is None:
            xml_str = adb_dump_ui()
        if not xml_str:
            return False
        return 'NIK TelkomGroup' in xml_str
    except Exception:
        return False


def is_logged_in(xml_str: str = None) -> bool:
    """Check if already logged in."""
    try:
        if xml_str is None:
            xml_str = adb_dump_ui()
        if not xml_str:
            return False
        greetings = ['Good Morning', 'Good Afternoon', 'Good Evening', 
                     'Selamat Pagi', 'Selamat Siang', 'Selamat Sore', 'Selamat Malam']
        for greeting in greetings:
            if greeting in xml_str:
                return True
        return False
    except Exception:
        return False


def has_beranda_menu(xml_str: str = None) -> bool:
    """Check if Beranda menu is visible (indicates successful login)."""
    try:
        if xml_str is None:
            xml_str = adb_dump_ui()
        if not xml_str:
            return False
        return 'Beranda' in xml_str
    except Exception:
        return False


def has_permission_dialog(xml_str: str = None) -> bool:
    """Check if there's a permission dialog on screen."""
    try:
        if xml_str is None:
            xml_str = adb_dump_ui()
        if not xml_str:
            return False
        keywords = ['Izinkan', 'Allow', 'While using', 'Saat menggunakan', 
                    'Only this time', 'Hanya sekali', 'permission']
        for kw in keywords:
            if kw.lower() in xml_str.lower():
                return True
        return False
    except Exception:
        return False


# ============================================================================
# DIALOG HANDLERS
# ============================================================================

def handle_permission_dialog(xml_str: str) -> tuple[bool, str]:
    """Handle permission dialogs by clicking Allow/While using/etc."""
    try:
        root = ET.fromstring(xml_str)
        
        # Priority order for permission buttons
        button_texts = [
            'While using the app', 'Saat menggunakan aplikasi',
            'Allow', 'ALLOW', 'Izinkan', 'IZINKAN',
            'Only this time', 'Hanya sekali ini'
        ]
        
        for elem in root.iter('node'):
            text = elem.get('text', '')
            content_desc = elem.get('content-desc', '')
            bounds = elem.get('bounds', '')
            
            for btn_text in button_texts:
                if btn_text.lower() in text.lower() or btn_text.lower() in content_desc.lower():
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                        return True, f"Tapped '{btn_text}'"
        
        return False, "No permission button found"
    except Exception as e:
        return False, f"Error: {str(e)}"


def handle_onboarding(xml_str: str) -> tuple[bool, str]:
    """Handle onboarding screens (Skip, Get Started, etc.)."""
    try:
        root = ET.fromstring(xml_str)
        
        onboarding_buttons = ['Skip', 'Get Started', 'Mulai', 'Lewati']
        
        for elem in root.iter('node'):
            text = elem.get('text', '')
            content_desc = elem.get('content-desc', '')
            bounds = elem.get('bounds', '')
            
            for btn_text in onboarding_buttons:
                if text == btn_text or content_desc == btn_text:
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        adb_tap((x1 + x2) // 2, (y1 + y2) // 2)
                        return True, f"Tapped '{btn_text}'"
        
        return False, "No onboarding button found"
    except Exception as e:
        return False, f"Error: {str(e)}"


async def handle_dialogs_and_permissions(max_attempts: int = 5) -> list[str]:
    """Handle multiple dialogs/permissions until stable screen."""
    import asyncio
    logs = []
    
    for i in range(max_attempts):
        await asyncio.sleep(1)
        xml_str = adb_dump_ui()
        if not xml_str:
            logs.append(f"Attempt {i+1}: Failed to dump UI")
            continue
        
        # Check for permission dialogs first
        if has_permission_dialog(xml_str):
            handled, msg = handle_permission_dialog(xml_str)
            logs.append(f"Attempt {i+1}: {msg}")
            if handled:
                continue
        
        # Check for onboarding
        handled, msg = handle_onboarding(xml_str)
        if handled:
            logs.append(f"Attempt {i+1}: {msg}")
            continue
        
        # If we reach here, no dialog was handled
        logs.append(f"Attempt {i+1}: No dialog found")
        break
    
    return logs


# ============================================================================
# INPUT HELPERS
# ============================================================================

def clear_and_input_field(text: str) -> bool:
    """Clear current field and input new text (assumes field is already focused)."""
    try:
        # Move to end and delete existing text
        subprocess.run(
            [Config.ADB_PATH, "shell", "input", "keyevent", "123"],
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
        
        # Input new text
        adb_input_text(text)
        time.sleep(0.2)
        
        return True
    except Exception:
        return False


# ============================================================================
# DEVICE HELPERS
# ============================================================================

def get_current_device() -> Optional[str]:
    """Get currently connected Android device ID."""
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


def get_all_devices() -> list[dict]:
    """Get all connected devices with details."""
    try:
        result = subprocess.run(
            [Config.ADB_PATH, "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        devices = []
        for line in result.stdout.split('\n'):
            if line.startswith('List of devices') or not line.strip():
                continue
            if ' device ' in line or line.strip().endswith('device'):
                parts = line.split()
                if len(parts) >= 2:
                    device_info = {
                        "device_id": parts[0],
                        "status": parts[1] if len(parts) > 1 else "unknown"
                    }
                    # Parse additional info
                    for part in parts[2:]:
                        if ':' in part:
                            key, value = part.split(':', 1)
                            device_info[key] = value
                    devices.append(device_info)
        
        return devices
    except Exception:
        return []
