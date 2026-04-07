ok. ini adalah tentang astro space. misalkan mau mengganti tema. apa yang harus saya lakukan?
untuk penggantian tema Ada 4 file utama yang harus diubah:

1. ideas.json — Hapus semua topik lama
Kosongkan isinya jadi array kosong:
json[]
Nanti akan di-generate ulang otomatis oleh idea_generator.py.

2. scripts/idea_generator.py — Bagian terpenting
Ada 3 bagian yang harus diganti:
Ganti DEFAULT_TOPICS:
python# Sekarang (astro):
DEFAULT_TOPICS = [
    "scale_comparison",
    "travel_time",
    "planetary_facts",
    ...
]

# Contoh kalau ganti ke tema Finance:
DEFAULT_TOPICS = [
    "investing_tips",
    "money_myths",
    "wealth_mindset",
    "passive_income",
    "budgeting_hacks"
]
Ganti TOPIC_DESCRIPTIONS:
python# Sekarang (astro):
TOPIC_DESCRIPTIONS = {
    "scale_comparison": "comparing sizes of cosmic objects...",
    ...
}

# Contoh Finance:
TOPIC_DESCRIPTIONS = {
    "investing_tips": "practical tips about stocks, ETF, crypto for beginners",
    "money_myths": "debunking common misconceptions about money and wealth",
    "wealth_mindset": "mindset shifts that separate rich vs poor thinking",
    "passive_income": "real ways to make money while you sleep",
    "budgeting_hacks": "simple tricks to save more money every month"
}
Ganti prompt ke Gemini — cari bagian yang ada teks "astrophysics" atau "space" di dalam fungsi yang call Gemini API, ganti dengan tema baru.

3. scripts/script_formatter.py — Ganti prompt
Cari prompt yang dikirim ke Gemini, biasanya ada kata-kata seperti:
"You are an expert astrophysics educator..."
Ganti dengan:
"You are an expert financial educator..."

4. scripts/video_renderer.py — Visual style
Ini opsional tapi bikin video lebih relevan. Yang bisa diganti:

Warna — sekarang pakai dark space palette (hitam, biru, ungu). Bisa ganti sesuai tema
Background — sekarang starfield animasi. Bisa ganti ke solid color atau gradient
Assets audio — folder assets/audio/ berisi music ambient space. Ganti dengan musik yang sesuai tema baru


5. data/strategy.json & data/analytics.json — Reset
Hapus data lama, reset ke kosong karena data performance-nya spesifik untuk topik astro:
data/strategy.json:
json{
  "generated_at": "",
  "top_performing_topics": [],
  "avoid_topics": [],
  "suggested_next": [],
  "insights": []
}
data/analytics.json:
json{
  "last_run": "",
  "channel_id": "",
  "videos_analyzed": 0,
  "topic_scores": {}
}

Ringkasan
FilePerubahanideas.jsonKosongkan []idea_generator.pyGanti topic list & deskripsiscript_formatter.pyGanti prompt persona AIvideo_renderer.pyGanti warna & musik (opsional)data/strategy.jsonResetdata/analytics.jsonReset
Mau ganti ke tema apa? Nanti bisa saya bantu buatkan konten DEFAULT_TOPICS dan TOPIC_DESCRIPTIONS-nya yang sudah disesuaikan.
