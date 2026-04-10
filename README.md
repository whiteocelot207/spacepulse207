# 🚀 spacepulse207

Automated **YouTube Shorts generator** menggunakan **Gemini AI + MoviePy + YouTube API**.

Pipeline:

```
idea_generator.py → script_formatter.py → video_renderer.py → youtube_uploader.py
   (Gemini API)        (Gemini API)          (MoviePy lokal)      (YouTube API)
```

Video dibuat **fully local** menggunakan **MoviePy** dengan animasi starfield, text, dan planet grafik.

Tidak perlu:

* Pexels
* ElevenLabs

Background music sudah tersedia di:

```
assets/audio/
```

---

# 🔐 Secrets yang Dibutuhkan (Hanya 3)

Pergi ke:

```
Repository → Settings → Secrets and variables → Actions → New repository secret
```

| Secret Name             | Isi                                             |
| ----------------------- | ----------------------------------------------- |
| `GEMINI_API_KEY`        | API key Google Gemini                           |
| `YOUTUBE_TOKEN`         | OAuth token JSON                                |
| `YOUTUBE_CLIENT_SECRET` | Isi file `client_secret.json` dari Google Cloud |

---

# 🎫 Step 1 — Dapatkan GEMINI_API_KEY

Buka:

```
https://aistudio.google.com/apikey
```

1. Klik **Create API Key**
2. Copy key
3. Simpan sebagai secret `GEMINI_API_KEY`

Gratis, tidak perlu kartu kredit.

---

# 🎬 Step 2 — Setup YouTube OAuth

## A. Buat Google Cloud Project

1. Buka

```
https://console.cloud.google.com
```

2. Buat project baru
3. Enable API:

```
YouTube Data API v3
YouTube Analytics API
```

4. Setup OAuth consent screen

```
APIs & Services → OAuth consent screen
```

* pilih **External**
* isi nama app
* Save

5. Buat credentials

```
APIs & Services → Credentials → Create Credentials → OAuth client ID
```

Pilih:

```
Application type: Desktop app
```

Download file JSON lalu rename menjadi:

```
client_secret.json
```

File ini akan digunakan sebagai secret:

```
YOUTUBE_CLIENT_SECRET
```

---

# 🔑 Generate Refresh Token (Jalankan Lokal Sekali)

Buat file (dan simpan di lokasi yang sama dengan file client_secret.json):

```
get_token.py
```

Contoh isi file:

```python
import json
import os
import sys
import subprocess


# =============================================================================
# AUTO-INSTALL DEPENDENCIES
# =============================================================================
REQUIRED_PACKAGES = {
    "google_auth_oauthlib": "google-auth-oauthlib",
    "google.oauth2":        "google-auth",
    "googleapiclient":      "google-api-python-client",
}

def check_and_install_dependencies():
    missing = []
    for import_name, package_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(package_name)

    if not missing:
        print("✅ Semua dependencies sudah tersedia\n")
        return

    print(f"📦 Dependencies belum ada: {', '.join(missing)}")
    print("⏳ Menginstall otomatis...\n")

    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", *missing
        ])
        print("\n✅ Install berhasil!\n")
    except subprocess.CalledProcessError:
        print("\n❌ Install gagal. Jalankan manual:")
        print(f"   pip install {' '.join(missing)}")
        sys.exit(1)

check_and_install_dependencies()


# =============================================================================
# MAIN — import setelah dependencies dipastikan ada
# =============================================================================
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

CLIENT_SECRET_FILE = "client_secret.json"


def main():
    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"❌ File {CLIENT_SECRET_FILE} tidak ditemukan!")
        print("   Download dari Google Cloud Console:")
        print("   APIs & Services → Credentials → OAuth 2.0 Client → Download JSON")
        print("   Letakkan file tersebut di folder yang sama dengan script ini")
        sys.exit(1)

    print("🔐 Membuka browser untuk OAuth login...")
    print("   Pastikan login dengan akun YouTube channel SpacePulse207\n")

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    credentials = flow.run_local_server(port=8080, prompt="consent")

    token_data = {
        "token":         credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri":     credentials.token_uri,
        "client_id":     credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes":        list(credentials.scopes),
    }

    output_file = "youtube_token_new.json"
    with open(output_file, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"\n✅ Token berhasil disimpan ke: {output_file}")
    print("\n📋 Isi token untuk GitHub Secret YOUTUBE_TOKEN:")
    print("─" * 50)
    print(json.dumps(token_data, indent=2))
    print("─" * 50)
    print("\n📌 Langkah selanjutnya:")
    print("   1. Copy seluruh JSON di atas")
    print("   2. Buka GitHub repo → Settings → Secrets and variables → Actions")
    print("   3. Klik YOUTUBE_TOKEN → Update secret → Paste → Save")
    print("\n⚠️  JANGAN commit file-file ini ke repo:")
    print(f"   - {output_file}")
    print(f"   - {CLIENT_SECRET_FILE}")


if __name__ == "__main__":
    main()
```

Jalankan:

```bash
python get_token.py
```

Browser akan terbuka.

Login dengan akun **YouTube channel** kamu dan klik **Authorize**.

Terminal akan menampilkan JSON.

Copy seluruh JSON tersebut dan simpan sebagai secret:

```
YOUTUBE_TOKEN
```
jika gagal dalam eksekusi file get_token.py (perlu depedanies), lakukan install terlebih dahulu :
```
pip install google-auth-oauthlib google-auth google-api-python-client
```

---

# 📄 Isi Secret YOUTUBE_CLIENT_SECRET

Buka file:

```
client_secret.json
```

Copy seluruh isi file lalu simpan sebagai secret:

```
YOUTUBE_CLIENT_SECRET
```

---

# ⚙️ Step 3 — Enable Repository Permissions

Workflow perlu permission untuk commit ke repo.

Buka:

```
Repository → Settings → Actions → General
```

Scroll ke **Workflow permissions**

Pilih:

```
Read and write permissions
```

Centang:

```
Allow GitHub Actions to create and approve pull requests
```

Klik **Save**.

---

# 🚀 Step 4 — Jalankan Manual untuk Test

Pergi ke tab:

```
Actions
```

Pilih workflow:

```
Generate Short Idea
```

Klik:

```
Run workflow
```

Jika berhasil, akan muncul:

* file baru di `scripts_output/`
* video MP4 di `videos_output/`
* commit otomatis
* video terupload ke YouTube

---

# ⏰ Jadwal Otomatis Upload

Workflow berjalan **5x sehari**.

| Cron (UTC)   | ET (EDT)    | WIB       |
| ------------ | ----------- | --------- |
| `7 11 * * *` | 07:07 AM ET | 18:07 WIB |
| `7 16 * * *` | 12:07 PM ET | 23:07 WIB |
| `7 21 * * *` | 05:07 PM ET | 04:07 WIB |
| `7 0 * * *`  | 08:07 PM ET | 07:07 WIB |
| `37 2 * * *` | 10:37 PM ET | 09:37 WIB |

Target audience: **United States timezone engagement**.

---

# 📊 Analytics & Learning

Setiap hari:

```
06:07 UTC (13:07 WIB)
```

Sistem akan:

* membaca performa video
* menganalisa analytics
* memperbaiki strategi topik

---

# ⚠️ Hal Penting

### Branch Protection

Jika repo menggunakan branch protection, workflow tidak bisa push.

Pastikan workflow bisa commit ke branch `main`.

---

### YouTube API Quota

Default quota:

```
10,000 unit / hari
```

Upload 1 video ≈ **1600 unit**

Jadi aman untuk:

```
5 video per hari
```

---

### Refresh Token

Refresh token **tidak kedaluwarsa** selama:

* project Google Cloud aktif
* token tidak di-revoke
