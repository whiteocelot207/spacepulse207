"""
Script Formatter Agent
Transforms raw ideas into scene-by-scene video scripts ready for rendering.

Changes:
  - Exponential backoff on 503 / transient errors (5s → 15s → 30s → 60s)
  - Fallback model list: gemini-2.5-flash → gemini-2.0-flash → gemini-1.5-flash
  - Graceful skip on failure (no exit(1)) — idea marked as 'error' so the
    workflow stays green and the next run picks a fresh idea
  - Per-attempt timeout bump (30s → 45s)
"""

import json
import os
import time
from datetime import datetime

import requests

# =============================================================================
# CONFIG
# =============================================================================
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

RETRY_DELAYS = [5, 15, 30, 60]   # seconds between retries (exponential-ish)
REQUEST_TIMEOUT = 45              # seconds per HTTP request

# =============================================================================
# FILE MANAGEMENT
# =============================================================================
def load_ideas(filename="ideas.json"):
    if not os.path.exists(filename):
        print(f"❌ {filename} not found")
        return []
    with open(filename, "r") as f:
        return json.load(f)


def save_ideas(ideas, filename="ideas.json"):
    with open(filename, "w") as f:
        json.dump(ideas, f, indent=2)


def get_pending_ideas(ideas):
    return [(i, idea) for i, idea in enumerate(ideas)
            if idea.get("status") == "pending"]


def get_existing_scripts(scripts_dir="scripts_output"):
    if not os.path.exists(scripts_dir):
        return set()
    existing = set()
    for f in os.listdir(scripts_dir):
        if f.endswith(".json"):
            try:
                with open(os.path.join(scripts_dir, f), "r") as fh:
                    data = json.load(fh)
                    topic = data.get("idea", {}).get("topic", "")
                    if topic:
                        existing.add(topic.lower().strip())
            except Exception:
                pass
    return existing


# =============================================================================
# SCRIPT FORMATTING
# =============================================================================
PROMPT_TEMPLATE = """\
You are a YouTube Shorts video script director.

Take this video idea and create a detailed scene-by-scene script for a 20-second silent infographic Short.

IDEA:
- Topic: {topic}
- Hook: {hook}
- Facts: {facts}
- Payoff: {payoff}

Create exactly 5 scenes that fit in 20 seconds total.

For each scene, specify:
1. Duration (in seconds)
2. Exact text to display (short, punchy, fits on screen)
3. Visual description (what the viewer sees)
4. Animation type (fade_in, zoom_in, zoom_out, slide_left, slide_right, pulse, none)
5. Text position (top, center, bottom)
6. Text size (large, medium, small)

Return ONLY this JSON format, no other text:
{{
    "total_duration": 20,
    "scenes": [
        {{
            "scene_number": 1,
            "start_time": 0,
            "duration": 3,
            "text": "Hook text here",
            "text_position": "center",
            "text_size": "large",
            "visual": "Description of background/visual",
            "animation": "fade_in"
        }},
        {{
            "scene_number": 2,
            "start_time": 3,
            "duration": 4,
            "text": "First fact",
            "text_position": "center",
            "text_size": "medium",
            "visual": "Visual description",
            "animation": "zoom_in"
        }},
        {{
            "scene_number": 3,
            "start_time": 7,
            "duration": 4,
            "text": "Second fact",
            "text_position": "center",
            "text_size": "medium",
            "visual": "Visual description",
            "animation": "slide_left"
        }},
        {{
            "scene_number": 4,
            "start_time": 11,
            "duration": 4,
            "text": "Third fact",
            "text_position": "center",
            "text_size": "medium",
            "visual": "Visual description",
            "animation": "slide_right"
        }},
        {{
            "scene_number": 5,
            "start_time": 15,
            "duration": 5,
            "text": "Payoff/conclusion",
            "text_position": "center",
            "text_size": "large",
            "animation": "pulse",
            "visual": "Final impactful visual"
        }}
    ],
    "thumbnail_text": "Short punchy text for thumbnail",
    "background_style": "space_dark OR space_nebula OR space_stars OR earth_orbit"
}}\
"""


def _call_gemini(api_key, model, prompt):
    """
    Single attempt to call one Gemini model.
    Returns (script_dict, None) on success or (None, error_str) on failure.
    """
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}

    resp = requests.post(url, json=payload, headers=headers,
                         timeout=REQUEST_TIMEOUT)

    if resp.status_code in (429, 500, 502, 503, 504):
        return None, f"HTTP {resp.status_code}"

    resp.raise_for_status()

    data = resp.json()
    raw = data["candidates"][0]["content"]["parts"][0]["text"]
    clean = raw.replace("```json", "").replace("```", "").strip()
    script = json.loads(clean)
    return script, None


def format_script(idea):
    """
    Try each model in GEMINI_MODELS with exponential-backoff retries.
    Returns the parsed script dict, or None on total failure.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
        return None

    prompt = PROMPT_TEMPLATE.format(
        topic=idea.get("topic"),
        hook=idea.get("hook"),
        facts=json.dumps(idea.get("facts", [])),
        payoff=idea.get("payoff"),
    )

    for model in GEMINI_MODELS:
        print(f"🤖 Trying model: {model}")
        for attempt, delay in enumerate(RETRY_DELAYS, start=1):
            print(f"   🎬 Attempt {attempt}/{len(RETRY_DELAYS)} — "
                  f"topic: {idea.get('topic')}")
            try:
                script, err = _call_gemini(api_key, model, prompt)
                if script is not None:
                    print(f"   ✅ Success with {model}")
                    return script
                # Transient error → wait and retry
                print(f"   ⚠️ {err} — waiting {delay}s before retry...")
                time.sleep(delay)
            except Exception as exc:
                print(f"   ⚠️ Exception: {exc} — waiting {delay}s...")
                time.sleep(delay)

        print(f"   ❌ All retries exhausted for {model}, trying next model...")

    print("❌ All models failed.")
    return None


# =============================================================================
# SAVE / CLEANUP
# =============================================================================
def save_script(idea, script, scripts_dir="scripts_output"):
    os.makedirs(scripts_dir, exist_ok=True)

    safe_topic = idea.get("topic", "untitled").lower()
    safe_topic = "".join(c if c.isalnum() or c == " " else "" for c in safe_topic)
    safe_topic = safe_topic.replace(" ", "_")[:30]
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{scripts_dir}/{safe_topic}_{ts}.json"

    full_script = {
        "idea": idea,
        "script": script,
        "formatted_at": datetime.now().isoformat(),
        "status": "ready_to_render",
    }
    with open(filename, "w") as f:
        json.dump(full_script, f, indent=2)

    print(f"💾 Saved script to: {filename}")
    return filename


def cleanup_old_scripts(scripts_dir="scripts_output", keep_latest=0):
    if not os.path.exists(scripts_dir):
        return
    scripts = []
    for f in os.listdir(scripts_dir):
        if f.endswith(".json"):
            path = os.path.join(scripts_dir, f)
            scripts.append((path, os.path.getmtime(path)))
    scripts.sort(key=lambda x: x[1], reverse=True)
    for path, _ in scripts[keep_latest:]:
        try:
            os.remove(path)
            print(f"🗑️ Removed old script: {os.path.basename(path)}")
        except Exception:
            pass


# =============================================================================
# MAIN
# =============================================================================
def main():
    print("=" * 60)
    print("🎬 ASTRO SHORTS ENGINE - Script Formatter")
    print("=" * 60)
    print()

    ideas = load_ideas()
    if not ideas:
        print("No ideas found. Run the idea generator first.")
        return

    print(f"📚 Found {len(ideas)} total ideas")

    pending = get_pending_ideas(ideas)
    print(f"⏳ {len(pending)} ideas pending formatting")

    if not pending:
        print("✨ All ideas have been formatted!")
        return

    idea_index, idea = pending[-1]

    # Safety check: already scripted?
    existing = get_existing_scripts()
    if idea.get("topic", "").lower().strip() in existing:
        print(f"⚠️ Already scripted, marking as formatted: {idea.get('topic')}")
        ideas[idea_index]["status"] = "formatted"
        ideas[idea_index]["formatted_at"] = datetime.now().isoformat()
        save_ideas(ideas)
        return

    print()
    print(f"📝 Processing: {idea.get('topic')}")
    print("-" * 40)

    script = format_script(idea)

    if script:
        cleanup_old_scripts(keep_latest=0)
        script_file = save_script(idea, script)

        ideas[idea_index]["status"] = "formatted"
        ideas[idea_index]["formatted_at"] = datetime.now().isoformat()
        save_ideas(ideas)

        print()
        print("=" * 60)
        print(f"✅ Script ready: {script_file}")
        print("🎬 Next step: Video rendering")
        print("=" * 60)
        print()
        print("📋 Script Preview:")
        print("-" * 40)
        for scene in script.get("scenes", [])[:3]:
            preview = scene.get("text", "")[:50]
            print(f"  Scene {scene.get('scene_number')} "
                  f"({scene.get('duration')}s): {preview}...")
    else:
        # ── Graceful failure: mark idea as 'error', DON'T exit(1) ──────────
        # The workflow continues; video_renderer will find no ready scripts
        # and exit cleanly. Next scheduled run will try a fresh idea.
        print()
        print("⚠️ Script formatting failed — marking idea as 'error'.")
        print("   The workflow will not crash. Next run picks a new idea.")
        ideas[idea_index]["status"] = "error"
        ideas[idea_index]["error_at"] = datetime.now().isoformat()
        save_ideas(ideas)
        # No exit(1) — let the workflow continue naturally


if __name__ == "__main__":
    main()