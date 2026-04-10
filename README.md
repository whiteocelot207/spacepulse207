# 🚀 PabrikShort

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
from google_auth_oauthlib.flow import InstalledAppFlow
import json

CLIENT_SECRET_FILE = "client_secret.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def main():
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES
    )

    # membuka browser untuk login
    creds = flow.run_local_server(port=0)

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes)
    }

    print("\n=== YOUTUBE_TOKEN ===\n")
    print(json.dumps(token_data, indent=2))


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
