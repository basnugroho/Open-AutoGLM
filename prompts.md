# Diarium Automation API - Documentation

REST API untuk otomasi aplikasi Diarium di Android.

**Last Updated:** December 22, 2025

---

## 🏗️ Architecture

### Hybrid Approach (Rule-Based + AI)

```
┌─────────────────────────────────────────────────────────────┐
│                    LOGIN FLOW (Hybrid)                       │
├─────────────────────────────────────────────────────────────┤
│  RULE-BASED (Fast ~5s)           AI-BASED (Smart ~40s)      │
│  ┌─────────────────────┐         ┌─────────────────────┐    │
│  │ 1. Tap NIK field    │         │ 1. Analyze screen   │    │
│  │ 2. Clear + Input    │   ──►   │ 2. Tap checkbox     │    │
│  │ 3. Tap Password     │         │ 3. Tap Login        │    │
│  │ 4. Clear + Input    │         │ 4. Verify success   │    │
│  └─────────────────────┘         │ 5. Handle tutorial  │    │
│                                   └─────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

**Why Hybrid?**
- **Rule-based for input**: Fast, reliable text input (~5 seconds)
- **AI for interaction**: Handles dynamic UI (checkbox, buttons, popups) (~40 seconds)
- **Total**: ~45 seconds vs ~90 seconds pure AI

---

## 📱 ENDPOINTS

### 🔐 Before Login

| Endpoint | Method | Description | Duration |
|----------|--------|-------------|----------|
| `/diarium/prepare-login` | POST | Navigate to login screen (handle onboarding) | ~25s |
| `/diarium/login-fast` | POST | Login with hybrid approach ⭐ | ~45s |
| `/diarium/login` | POST | Login with pure AI | ~90s |
| `/diarium/mfa` | POST | Submit MFA code | ~30s |

### ✅ After Login

| Endpoint | Method | Description | Duration |
|----------|--------|-------------|----------|
| `/diarium/login-status` | GET | Check if logged in | ~15s |
| `/diarium/check-in` | POST | Perform check-in | ~60s |
| `/diarium/activities` | GET | Get activities list | ~30s |

### 📦 After Check-In

| Endpoint | Method | Description | Duration |
|----------|--------|-------------|----------|
| `/diarium/check-out` | POST | Perform check-out | ~60s |

### 🚪 Logout

| Endpoint | Method | Description | Duration |
|----------|--------|-------------|----------|
| `/diarium/logout` | POST | Logout from app | ~30s |

### 📱 Device

| Endpoint | Method | Description | Duration |
|----------|--------|-------------|----------|
| `/diarium/devices` | GET | List connected devices | <1s |

---

## 📐 UI Element Coordinates

Device: **Samsung A13** (1080x2408 resolution)

### Login Screen

| Element | Bounds | Center (x, y) | Note |
|---------|--------|---------------|------|
| NIK Input | [45,1185][1035,1320] | **(540, 1252)** | |
| Password Input | [45,1466][1035,1601] | **(540, 1533)** | |
| Checkbox | [45,1667][146,1769] | **(95, 1718)** | Use long-tap (150ms) |
| Login Button | [45,1835][1035,1970] | **(540, 1902)** | |

### Detection Patterns

```python
# Login Screen Detection
content-desc contains "NIK TelkomGroup"

# Logged In Detection  
content-desc contains:
- "Good Morning" / "Good Afternoon" / "Good Evening"
- "Selamat Pagi" / "Selamat Siang" / "Selamat Sore" / "Selamat Malam"

# Onboarding Buttons
- "Skip" → tap to skip carousel
- "Get Started" → tap to enter login screen
- "Allow" → permission dialogs
```

---

## 🔧 Configuration

### Environment Variables (.env)

```bash
NIK=930436
SSO_PASS=your_password
zai_api_key=your_zhipu_api_key
```

### ADB Setup

```bash
# Path to platform-tools
PLATFORM_TOOLS=/Users/baskoronugroho/projects/platform-tools

# Set ADB Keyboard as IME (for text input)
adb shell ime set com.android.adbkeyboard/.AdbIME

# Package name
co.id.telkom.diarium.prod
```

---

## 📝 Code Structure

```
api_server.py
├── Configuration (Config, LoginScreenElements)
├── Request/Response Models (Pydantic)
├── Helper Functions
│   ├── ADB Commands (adb_tap, adb_input_text, etc.)
│   ├── UI Detection (is_logged_in, is_on_login_screen, etc.)
│   └── AI Runner (run_phone_agent)
└── Endpoints
    ├── Before Login (/prepare-login, /login-fast, /login, /mfa)
    ├── After Login (/login-status, /check-in, /activities)
    ├── After Check-In (/check-out)
    └── Logout (/logout)
```

---

## 🐛 Known Issues & Solutions

### ❌ Password field tidak terisi
**Cause:** ADB Keyboard broadcast tidak work untuk password field  
**Solution:** Gunakan `adb shell input text` langsung

### ❌ Checkbox tidak tercentang
**Cause:** Tap biasa terlalu cepat untuk element NAF (Not Accessible Focus)  
**Solution:** Gunakan long-tap dengan `adb shell input touchscreen swipe x y x y 150`

### ❌ Login button masih disabled setelah centang
**Cause:** Delay terlalu singkat setelah tap checkbox  
**Solution:** Tunggu 2 detik setelah checkbox di-tap

---

## 🚀 Usage Examples

### cURL

```bash
# Check devices
curl http://localhost:8080/diarium/devices

# Prepare login (from fresh app state)
curl -X POST http://localhost:8080/diarium/prepare-login

# Login (hybrid - recommended)
curl -X POST http://localhost:8080/diarium/login-fast \
  -H "Content-Type: application/json" \
  -d '{"nik":"930436","password":"YourPassword"}'

# Check-in
curl -X POST http://localhost:8080/diarium/check-in

# Check-out
curl -X POST http://localhost:8080/diarium/check-out

# Logout
curl -X POST http://localhost:8080/diarium/logout
```

### Python

```python
import requests

BASE_URL = "http://localhost:8080"

# Login
response = requests.post(f"{BASE_URL}/diarium/login-fast", json={
    "nik": "930436",
    "password": "YourPassword"
})
print(response.json())

# Check-in
response = requests.post(f"{BASE_URL}/diarium/check-in")
print(response.json())
```

---

## 📊 Response Format

All endpoints return standardized response:

```json
{
  "success": true,
  "status": "logged_in",
  "message": "Login successful: Good Evening!",
  "data": {
    "username": "Good Evening!",
    "steps": ["Step 1...", "Step 2..."]
  },
  "metadata": {
    "hit_time": "2025-12-22T23:54:10.826270",
    "result_time": "2025-12-22T23:54:57.340665",
    "duration_seconds": 46.51,
    "device_id": "RR8T601DQLY"
  }
}
```

### Status Codes

| Status | Description |
|--------|-------------|
| `success` | Operation completed successfully |
| `logged_in` | User is logged in |
| `login_failed` | Login failed |
| `mfa_required` | MFA verification needed |
| `checked_in` | Check-in successful |
| `checked_out` | Check-out successful |
| `device_not_found` | No Android device connected |
| `error` | General error |

