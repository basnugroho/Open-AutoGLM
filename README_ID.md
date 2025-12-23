# Open-AutoGLM - Panduan Bahasa Indonesia

<div align="center">
<img src=resources/logo.svg width="20%"/>
</div>

> Dokumentasi ini untuk penggunaan Open-AutoGLM dengan Diarium Automation API.

---

## Daftar Isi

- [Prasyarat](#prasyarat)
- [Koneksi Device](#koneksi-device)
- [Diarium Automation API](#diarium-automation-api)
- [Troubleshooting](#troubleshooting)

---

## Prasyarat

### 1. Python Environment

Python 3.10 atau lebih tinggi.

```bash
python --version
# Python 3.10+
```

### 2. ADB (Android Debug Bridge)

Download dari [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools).

```bash
# macOS - tambahkan ke PATH
export PATH=${PATH}:~/Downloads/platform-tools

# Atau simpan di lokasi proyek
export PATH=${PATH}:/Users/baskoronugroho/projects/platform-tools
```

### 3. Android Device

- Android 7.0+
- Developer Mode aktif
- USB Debugging aktif
- ADB Keyboard terinstall (untuk input text)

---

## Koneksi Device

### Koneksi via USB

```bash
# Hubungkan HP via kabel USB
adb devices -l

# Output:
# List of devices attached
# RR8T601DQLY    device usb:0-1 product:a13nnxx model:SM_A135F device:a13
```

### Koneksi via Wireless Debugging (Android 11+ - TANPA USB)

**Metode paling mudah untuk Android 11 ke atas - tidak perlu kabel USB sama sekali!**

#### Langkah-langkah:

1. **Aktifkan Wireless Debugging di HP:**
   - Settings > Developer Options > **Wireless debugging** → ON
   - Tap "Wireless debugging" untuk masuk ke detail

2. **Pair device (sekali saja):**
   - Di HP, tap **"Pair device with pairing code"**
   - Akan muncul: IP:Port dan Pairing Code (6 digit)
   ```bash
   # Di komputer, jalankan (ganti dengan IP:Port dan code dari HP)
   adb pair 192.168.1.100:37123 123456
   # Output: Successfully paired to 192.168.1.100:37123
   ```

3. **Connect ke device:**
   - Lihat IP:Port di bagian atas layar Wireless debugging (beda dari pairing port!)
   ```bash
   adb connect 192.168.1.100:45678
   # Output: connected to 192.168.1.100:45678
   
   adb devices -l
   # Output: 192.168.1.100:45678    device product:... model:...
   ```

#### Catatan Penting:
- ⚠️ Port **pairing** dan port **connect** BERBEDA! Perhatikan layar HP
- ✅ Setelah paired 1x, HP akan ingat komputer ini
- ✅ Next time cukup `adb connect` tanpa pair lagi
- ⚠️ Port bisa berubah setiap kali Wireless Debugging di-toggle

---

### Koneksi via WiFi dengan USB Setup (Android 7+)

```bash
# Pastikan HP dan komputer di WiFi yang sama
# Colok USB dulu, lalu:
adb tcpip 5555
adb connect 192.168.1.100:5555

# Cabut USB, koneksi tetap aktif
adb devices
```

---

### Koneksi via Mobile Hotspot

**Gunakan metode ini jika WiFi memiliki AP Isolation (umum di jaringan kantor/publik).**

#### Langkah-langkah:

1. **Aktifkan Mobile Hotspot di HP Android**
   - Buka Settings > Connections > Mobile Hotspot and Tethering
   - Aktifkan Mobile Hotspot

2. **Hubungkan komputer ke hotspot HP**
   - Pilih WiFi hotspot HP dari komputer

3. **Colok USB sementara untuk setup tcpip:**
   ```bash
   # Dengan USB terhubung, aktifkan mode tcpip
   adb tcpip 5555
   # Output: restarting in TCP mode port: 5555
   
   # Cek IP hotspot HP (biasanya 192.168.x.x atau 10.x.x.x)
   adb shell ip addr show swlan0 | grep "inet "
   # Contoh output: inet 10.131.227.123/24 brd 10.131.227.255 scope global swlan0
   ```

4. **Connect via WiFi dan cabut USB:**
   ```bash
   # Tunggu 2 detik lalu connect dengan IP hotspot
   adb connect 10.131.227.123:5555
   # Output: connected to 10.131.227.123:5555
   
   # Sekarang CABUT kabel USB
   
   # Verifikasi koneksi
   adb devices -l
   # Output: 10.131.227.123:5555    device product:a13nnxx model:SM_A135F device:a13
   ```

#### Keuntungan Metode Hotspot:
- ✅ Tidak ada masalah AP Isolation
- ✅ Bisa digunakan dimana saja tanpa akses router
- ✅ Koneksi langsung antara HP dan komputer
- ✅ Stabil untuk otomasi jangka panjang

---

## Diarium Automation API

### Menjalankan Server

```bash
cd /Users/baskoronugroho/projects/Open-AutoGLM
source .venv/bin/activate
python api_server.py 2>&1 | tee /tmp/api_server.log
```

Server berjalan di `http://localhost:8080`

### Dokumentasi API

Buka browser: http://localhost:8080/docs

### Endpoints Utama

| Endpoint | Method | Deskripsi |
|----------|--------|-----------|
| `/` | GET | Health check |
| `/diarium/devices` | GET | List device terhubung |
| `/diarium/prepare-login` | POST | Clear app data, handle permissions |
| `/diarium/login` | POST | Login dengan NIK & password |
| `/diarium/login-status` | GET | Cek status login |
| `/diarium/logout` | POST | Logout dari app |
| `/diarium/checkin` | POST | Check-in kehadiran |
| `/diarium/checkout` | POST | Check-out kehadiran |

### Contoh Penggunaan

#### 1. Cek Device
```bash
curl -s http://localhost:8080/diarium/devices | jq .
```

#### 2. Prepare Login (Clear App Data)
```bash
curl -s -X POST http://localhost:8080/diarium/prepare-login | jq .
```

#### 3. Login
```bash
curl -s -X POST http://localhost:8080/diarium/login \
  -H "Content-Type: application/json" \
  -d '{"nik": "930436", "password": "YourPassword"}' | jq .
```

#### 4. Cek Status Login
```bash
curl -s http://localhost:8080/diarium/login-status | jq .
```

#### 5. Logout
```bash
curl -s -X POST http://localhost:8080/diarium/logout | jq .
```

### Response Format

Semua endpoint mengembalikan format JSON standar:

```json
{
  "success": true,
  "status": "success",
  "message": "Operation completed",
  "data": { ... },
  "metadata": {
    "hit_time": "2025-12-23T01:00:00",
    "result_time": "2025-12-23T01:00:05",
    "duration_seconds": 5.0,
    "device_id": "10.131.227.123:5555"
  }
}
```

---

## Logging

Log tersimpan di `/tmp/diarium_logs/`:

| File | Deskripsi |
|------|-----------|
| `diarium.log` | Main log (rotates at 5MB, keeps 5 files) |
| `diarium_YYYYMMDD.log` | Daily log |

### Melihat Log

```bash
# Real-time monitoring
tail -f /tmp/diarium_logs/diarium.log

# Lihat log hari ini
cat /tmp/diarium_logs/diarium_$(date +%Y%m%d).log

# Search specific endpoint
grep "\[prepare-login\]" /tmp/diarium_logs/diarium.log
grep "\[login\]" /tmp/diarium_logs/diarium.log
grep "\[checkin\]" /tmp/diarium_logs/diarium.log
```

### Format Log

```
2025-12-23 08:30:20 | INFO     | diarium | [prepare-login] Started - device: 10.131.227.123:5555
2025-12-23 08:30:21 | INFO     | diarium | [prepare-login] Step 1: Clearing app data
2025-12-23 08:31:35 | INFO     | diarium | [prepare-login] ✅ Success - reached login screen in 74.74s
```

---

## Troubleshooting

### Device Tidak Terdeteksi

```bash
# Restart ADB server
adb kill-server
adb start-server
adb devices
```

### Koneksi WiFi Gagal "No route to host"

**Penyebab:** Router memiliki AP Isolation aktif.

**Solusi:** Gunakan metode Mobile Hotspot (lihat di atas).

### Login Gagal - Password Invalid

1. Pastikan NIK dan password benar
2. Coba clear app data dulu:
   ```bash
   curl -s -X POST http://localhost:8080/diarium/prepare-login | jq .
   ```
3. Lalu login ulang

### Koneksi WiFi Terputus

```bash
# Reconnect
adb connect 10.131.227.123:5555

# Jika gagal, colok USB lagi dan ulangi setup tcpip
adb tcpip 5555
adb connect <IP>:5555
```

### Melihat Log Server

```bash
# Real-time log
tail -f /tmp/api_server.log

# Atau lihat semua log
cat /tmp/api_server.log
```

---

## Struktur File

```
Open-AutoGLM/
├── api_server.py           # Main API server (streamlined)
├── diarium_api/            # Modular API package
│   ├── __init__.py
│   ├── config.py           # Configuration & coordinates
│   ├── models.py           # Pydantic models
│   ├── adb_utils.py        # ADB helper functions
│   ├── ai_agent.py         # AI agent wrapper
│   └── routers/
│       ├── __init__.py
│       ├── device.py       # Device endpoints
│       ├── auth.py         # Login/logout endpoints
│       └── actions.py      # Checkin/checkout endpoints
├── main.py                 # Original AutoGLM CLI
└── README_ID.md            # Dokumentasi ini
```

---

## Author

Baskoro Nugroho - December 2025
