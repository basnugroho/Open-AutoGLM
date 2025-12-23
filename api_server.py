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
Last Updated: December 23, 2025

Refactored Structure:
- diarium_api/config.py - Configuration and coordinates
- diarium_api/models.py - Pydantic models and enums
- diarium_api/adb_utils.py - ADB helper functions
- diarium_api/ai_agent.py - AI agent wrapper
- diarium_api/routers/device.py - Device endpoints
- diarium_api/routers/auth.py - Auth endpoints (login, logout, mfa)
- diarium_api/routers/actions.py - Action endpoints (checkin, checkout)
"""

import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add platform-tools to PATH
PLATFORM_TOOLS_PATH = "/Users/baskoronugroho/projects/platform-tools"
if PLATFORM_TOOLS_PATH not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{PLATFORM_TOOLS_PATH}:{os.environ.get('PATH', '')}"

# Import routers
from diarium_api.routers import device_router, auth_router, actions_router
from diarium_api.adb_utils import get_current_device


# =============================================================================
# APPLICATION LIFESPAN
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events"""
    # Startup
    print("\n" + "=" * 60)
    print("🚀 Diarium Automation API Starting...")
    print("=" * 60)
    
    # Check ADB connection
    device_id = get_current_device()
    if device_id:
        print(f"✅ Device connected: {device_id}")
    else:
        print("⚠️  No device connected. Please connect your Android device.")
    
    print("\n📚 API Documentation: http://localhost:8080/docs")
    print("=" * 60 + "\n")
    
    yield
    
    # Shutdown
    print("\n👋 Diarium Automation API Shutting down...")


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

app = FastAPI(
    title="Diarium Automation API",
    description="""
## 🤖 API untuk Otomasi Aplikasi Diarium

API ini menyediakan endpoint untuk mengotomasi berbagai aksi di aplikasi Diarium.

### 📱 Device Requirements
- Android device connected via USB
- USB Debugging enabled
- ADB Keyboard installed (for text input)

### 🔑 Available Endpoints

| Category | Endpoint | Description |
|----------|----------|-------------|
| 🏥 Health | GET `/` | Health check |
| 🔌 Device | GET `/diarium/devices` | List connected devices |
| 🔌 Device | POST `/diarium/setup-keyboard` | Setup ADB Keyboard |
| 🔐 Auth | POST `/diarium/prepare-login` | Clear & prepare for login |
| 🔐 Auth | POST `/diarium/login` | Login with NIK & password |
| 🔐 Auth | GET `/diarium/login-status` | Check login status |
| 🔐 Auth | POST `/diarium/logout` | Logout from app |
| 🔐 Auth | POST `/diarium/mfa` | Verify MFA code |
| 📍 Attendance | POST `/diarium/checkin` | Check-in attendance |
| 📍 Attendance | POST `/diarium/checkout` | Check-out attendance |
| 👤 User | GET `/diarium/whoami` | Get current user info |
| 📱 App | POST `/diarium/launch` | Launch app |
| 📱 App | POST `/diarium/stop` | Stop app |

### ⚡ Response Format

All endpoints return standardized JSON:

```json
{
    "success": true,
    "status": "SUCCESS",
    "message": "Operation completed",
    "data": {...},
    "metadata": {
        "hit_time": "2025-12-23T10:00:00",
        "response_time": "2025-12-23T10:00:05",
        "duration_seconds": 5.0,
        "device_id": "RR8T601DQLY"
    }
}
```
    """,
    version="2.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# INCLUDE ROUTERS
# =============================================================================

app.include_router(device_router)
app.include_router(auth_router)
app.include_router(actions_router)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8080,
        reload=True
    )
