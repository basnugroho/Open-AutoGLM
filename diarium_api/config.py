"""
Configuration Module
====================

Contains all configuration, constants, and UI element coordinates.
"""

import os
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()

# Add platform-tools to PATH
PLATFORM_TOOLS_PATH = "/Users/baskoronugroho/projects/platform-tools"
if PLATFORM_TOOLS_PATH not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{PLATFORM_TOOLS_PATH}:{os.environ.get('PATH', '')}"


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

LOG_DIR = "/tmp/diarium_logs"
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logger(name: str = "diarium") -> logging.Logger:
    """
    Setup logger dengan file rotation.
    
    Log files:
    - /tmp/diarium_logs/diarium.log - Main log (rotates at 5MB, keeps 5 files)
    - /tmp/diarium_logs/diarium_YYYYMMDD.log - Daily log
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Rotating file handler (main log)
    main_log = os.path.join(LOG_DIR, "diarium.log")
    file_handler = RotatingFileHandler(
        main_log,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Daily log file
    today = datetime.now().strftime("%Y%m%d")
    daily_log = os.path.join(LOG_DIR, f"diarium_{today}.log")
    daily_handler = logging.FileHandler(daily_log)
    daily_handler.setLevel(logging.DEBUG)
    daily_handler.setFormatter(formatter)
    logger.addHandler(daily_handler)
    
    return logger

# Create default logger
logger = setup_logger()


class Config:
    """API and ADB configuration"""
    ZAI_API_KEY = os.getenv("zai_api_key", "")
    ZAI_BASE_URL = "https://api.z.ai/api/paas/v4"
    ZAI_MODEL = "autoglm-phone-multilingual"
    PYTHON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".venv", "bin", "python")
    MAIN_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
    PLATFORM_TOOLS = PLATFORM_TOOLS_PATH
    ADB_PATH = os.path.join(PLATFORM_TOOLS_PATH, "adb")
    DIARIUM_PACKAGE = "co.id.telkom.diarium.prod"


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
    """Koordinat elemen home screen setelah login"""
    # Bottom navigation
    MENU_BERANDA = (108, 2200)  # Approximate
    MENU_PROFIL = (972, 2200)   # Approximate (rightmost)
