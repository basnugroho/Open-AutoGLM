# Improvement Notes

## /diarium/login

### Issue: Welcome Screen After First Login
**Date:** 2025-12-23

Setelah login pertama kali (setelah `prepare-login` clear data), muncul welcome screen tambahan:
1. **"Dapatkan informasi terbaru"** - perlu di-dismiss
2. **Konfirmasi UU PDP** - perlu klik "Oke" untuk setuju

**Current behavior:** 
- Login berhasil tapi endpoint return `login_failed` karena detect masih ada dialog
- `is_on_login_screen()` return True karena belum sampai Beranda

**Proposed fix:**
- Setelah login sukses, handle welcome dialogs sebelum check `is_logged_in()`
- Atau gunakan AI untuk dismiss dialogs setelah klik Masuk
- Detect text "Dapatkan informasi" atau "UU PDP" sebagai indicator post-login dialog

### Flow yang benar:
```
Login Form → Klik Masuk → [Welcome Dialog: Dapatkan info] → [UU PDP Dialog] → Beranda
```

---

## /diarium/checkin

### Current Flow (2025-12-23)
Endpoint dimulai dari **Home Screen (Beranda)**:

1. Klik tombol **Check In** (di kanan atas)
2. Muncul halaman Check In, isi:
   - Pilih **Sehat**
   - Scroll ke bawah, terlihat peta
   - Klik **Perbarui** (refresh lokasi)
   - Scroll ke bawah, pilih **WFO**
   - **TUNGGU 2-3 detik** sampai muncul pilihan tambahan
   - Muncul pilihan: **Kantor Utama** atau **Perjalanan Dinas**
   - Untuk sekarang pilih **Perjalanan Dinas**
   - Scroll ke bawah, button **Simpan** enabled
   - Klik **Simpan**

### Notes:
- Button Simpan disabled sampai semua field terisi
- Perlu scroll untuk melihat semua options
- Lokasi perlu di-refresh dengan klik Perbarui

### TODO Improvements:

#### 1. Handle Non-Beranda State
User sudah login tapi mungkin tidak di halaman Beranda.
**Fix:** Di awal endpoint, klik menu **Beranda** dulu untuk memastikan posisi.

#### 2. Post-Simpan Flow
Setelah klik Simpan, flow belum selesai:
1. Muncul form → pilih **"Check In"**
2. Tunggu beberapa detik
3. Muncul tombol **"Selesai"** → klik
4. Muncul form dengan tulisan **"Deskripsi Aktivitas"**
5. Jika ada "Deskripsi Aktivitas" = **CHECK-IN BERHASIL**

```
Simpan → [Form: pilih Check In] → [Tunggu] → [Klik Selesai] → [Deskripsi Aktivitas] → DONE
```

---
