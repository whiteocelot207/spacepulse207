"""
Idea Generator Agent - SMART VERSION with Robust Retry Logic
Generates astrophysics YouTube Shorts ideas using Gemini API.
Uses analytics data to prioritize winning topic types,
with exponential backoff to handle 429/503 gracefully.
Target: US Audience 18-34
"""

import os
import json
import random
import requests
import re
import time
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================
STRATEGY_FILE = "data/strategy.json"
PERFORMANCE_FILE = "data/performance_history.json"
IDEAS_FILE = "ideas.json"

DEFAULT_TOPICS = [
    "scale_comparison",
    "travel_time",
    "planetary_facts",
    "hypothetical",
    "myth_busting"
]

TOPIC_DESCRIPTIONS = {
    "scale_comparison": "comparing sizes of cosmic objects (How many Earths fit in the Sun? How big is the Milky Way compared to...?)",
    "travel_time": "how long it takes to travel to cosmic destinations at various speeds (How long to reach Mars at light speed?)",
    "planetary_facts": "surprising facts about planets, moons, or other bodies (A day on Venus is longer than its year)",
    "hypothetical": "what-if scenarios in space (What if you fell into a black hole? Could you survive on...?)",
    "myth_busting": "correcting common misconceptions about space (Is the Sun actually yellow? Can you hear explosions in space?)",
    "cosmic_mystery": "unexplained phenomena and mysteries of the universe (What is dark matter? Why is the universe expanding faster?)",
    "extreme_conditions": "extreme environments and conditions in space (hottest planet, coldest place, strongest gravity)"
}

RECENT_FAMILY_BLOCK = 3
MAX_GENERATION_ATTEMPTS = 3

# Gemini config
GEMINI_MAX_RETRIES = 4
GEMINI_BASE_DELAY  = 20   # seconds — doubles each retry: 20 → 40 → 80 → 160
GEMINI_MODEL       = "gemini-2.5-flash"


# =============================================================================
# TEXT NORMALIZATION / SIMILARITY
# =============================================================================
def normalize_text(text):
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def tokenize(text):
    return set(normalize_text(text).split())


def jaccard_similarity(a, b):
    a_words = tokenize(a)
    b_words = tokenize(b)
    if not a_words or not b_words:
        return 0.0
    intersection = len(a_words & b_words)
    union = len(a_words | b_words)
    return intersection / union if union else 0.0


# =============================================================================
# DATA LOADERS
# =============================================================================
def load_json_file(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Could not load {filepath}: {e}")
    return default


def load_strategy():
    return load_json_file(STRATEGY_FILE, None)


def load_performance_history():
    return load_json_file(PERFORMANCE_FILE, [])


def load_ideas():
    return load_json_file(IDEAS_FILE, [])


# =============================================================================
# TOPIC SELECTION
# =============================================================================
def get_recent_topics(history, limit=10):
    recent = sorted(history, key=lambda x: x.get("published_at", ""), reverse=True)[:limit]
    return [v.get("topic_family", "general") for v in recent]


def get_recent_titles(history, limit=10):
    recent = sorted(history, key=lambda x: x.get("published_at", ""), reverse=True)[:limit]
    return [v.get("title", "") for v in recent if v.get("title")]


def select_topic_family(strategy, history):
    recent_topics = get_recent_topics(history, limit=5)

    if not strategy or not strategy.get("top_performing_topics"):
        print("📊 No analytics data yet — using balanced selection")
        available = [
            t for t in DEFAULT_TOPICS
            if t not in recent_topics[:RECENT_FAMILY_BLOCK]
        ]
        return random.choice(available or DEFAULT_TOPICS)

    top_topics = strategy.get("top_performing_topics", [])
    suggested  = strategy.get("suggested_next", DEFAULT_TOPICS)
    avoid      = [t["topic"] for t in strategy.get("avoid_topics", [])]

    roll = random.random()

    # 60% — top performers
    if roll < 0.6 and top_topics:
        candidates = [
            t["topic"] for t in top_topics
            if t["topic"] not in recent_topics[:RECENT_FAMILY_BLOCK]
            and t["topic"] not in avoid
        ]
        if candidates:
            selected = random.choice(candidates)
            print(f"📊 Selected top performer: {selected}")
            return selected

    # 30% — suggested
    if roll < 0.9 and suggested:
        candidates = [
            t for t in suggested
            if t not in recent_topics[:RECENT_FAMILY_BLOCK]
            and t not in avoid
        ]
        if candidates:
            selected = random.choice(candidates)
            print(f"📊 Selected from suggestions: {selected}")
            return selected

    # 10% — exploration
    all_topics = list(TOPIC_DESCRIPTIONS.keys())
    candidates = [
        t for t in all_topics
        if t not in recent_topics[:RECENT_FAMILY_BLOCK]
        and t not in avoid
    ]
    if candidates:
        selected = random.choice(candidates)
        print(f"📊 Exploration pick: {selected}")
        return selected

    fallback = [t for t in DEFAULT_TOPICS if t not in avoid]
    return random.choice(fallback or DEFAULT_TOPICS)


def get_topic_guidance(topic_family):
    return TOPIC_DESCRIPTIONS.get(topic_family, "interesting astrophysics facts")


# =============================================================================
# DUPLICATE DETECTION
# =============================================================================
def build_used_text_bank(history, existing_ideas):
    used = []
    for item in list(history)[-50:] + list(existing_ideas)[-50:]:
        used.append({
            "topic":        item.get("topic", ""),
            "hook":         item.get("hook", ""),
            "title":        item.get("title", ""),
            "topic_family": item.get("topic_family", "")
        })
    return used


def is_too_similar(new_idea, used_entries, threshold=0.65):
    nt = new_idea.get("topic", "")
    nh = new_idea.get("hook", "")
    ni = new_idea.get("title", "")
    nf = new_idea.get("topic_family", "")

    for ex in used_entries:
        et = ex.get("topic", "")
        eh = ex.get("hook", "")
        ei = ex.get("title", "")
        ef = ex.get("topic_family", "")

        # Exact match
        if normalize_text(nt) and normalize_text(nt) == normalize_text(et):
            print(f"⚠️  Exact duplicate topic: {nt}")
            return True
        if normalize_text(nh) and normalize_text(nh) == normalize_text(eh):
            print(f"⚠️  Exact duplicate hook")
            return True
        if normalize_text(ni) and normalize_text(ni) == normalize_text(ei):
            print(f"⚠️  Exact duplicate title")
            return True

        # Near-duplicate
        if jaccard_similarity(nt, et) >= threshold:
            print(f"⚠️  Near-duplicate topic ({jaccard_similarity(nt, et):.2f})")
            return True
        if jaccard_similarity(nh, eh) >= threshold:
            print(f"⚠️  Near-duplicate hook ({jaccard_similarity(nh, eh):.2f})")
            return True
        if jaccard_similarity(ni, ei) >= threshold:
            print(f"⚠️  Near-duplicate title ({jaccard_similarity(ni, ei):.2f})")
            return True

        # Same family + semantically close
        if nf == ef and (
            jaccard_similarity(nt, et) >= 0.45 or
            jaccard_similarity(nh, eh) >= 0.45
        ):
            print("⚠️  Same family and too semantically close")
            return True

    return False


# =============================================================================
# GEMINI API — EXPONENTIAL BACKOFF
# =============================================================================
def call_gemini(prompt, api_key):
    """
    Call Gemini with exponential backoff.
    Wait times: 20s → 40s → 80s → 160s
    Handles 429 (rate limit) and 503 (overload).
    """
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}

    for attempt in range(GEMINI_MAX_RETRIES):
        wait = GEMINI_BASE_DELAY * (2 ** attempt) + random.uniform(1, 6)

        try:
            print(f"  🚀 Gemini attempt {attempt + 1}/{GEMINI_MAX_RETRIES}...")
            response = requests.post(
                url, json=payload, headers=headers, timeout=90
            )

            if response.status_code in (429, 503):
                if attempt < GEMINI_MAX_RETRIES - 1:
                    print(f"  ⏳ HTTP {response.status_code} — backing off {wait:.0f}s...")
                    time.sleep(wait)
                    continue
                else:
                    print(f"  ❌ HTTP {response.status_code} — retries exhausted")
                    return None

            response.raise_for_status()

            data  = response.json()
            text  = data["candidates"][0]["content"]["parts"][0]["text"]
            clean = text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)

        except requests.exceptions.Timeout:
            print(f"  ⚠️  Timeout on attempt {attempt + 1}")
            if attempt < GEMINI_MAX_RETRIES - 1:
                print(f"  ⏳ Waiting {wait:.0f}s...")
                time.sleep(wait)

        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  Request error: {e}")
            if attempt < GEMINI_MAX_RETRIES - 1:
                print(f"  ⏳ Waiting {wait:.0f}s...")
                time.sleep(wait)

        except json.JSONDecodeError as e:
            print(f"  ❌ JSON parse error — skipping retry: {e}")
            return None

        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            return None

    print("  ❌ All Gemini retries failed")
    return None


# =============================================================================
# PROMPT BUILDER
# =============================================================================
def build_prompt(topic_family, topic_guidance, history, existing_ideas):
    recent_titles      = get_recent_titles(history, limit=10)
    recent_idea_topics = [
        idea.get("topic", "")
        for idea in existing_ideas[-10:]
        if idea.get("topic")
    ]

    avoid_list = recent_titles + recent_idea_topics
    avoid_text = "\n".join(f"- {item}" for item in avoid_list if item) or "- None"

    return f"""You are a viral astrophysics YouTube Shorts strategist targeting US audiences aged 18-34.

Generate ONE idea for a 20-second silent infographic Short about space or astrophysics.

TOPIC TYPE: {topic_family}
DESCRIPTION: {topic_guidance}

AVOID these recently used topics/titles (do NOT rephrase them either):
{avoid_text}

WHAT MAKES US AUDIENCES SHARE:
- Opening with a shocking number ("It would take 1.3 million Earths to fill the Sun")
- Using US-relatable scale (football fields, distance NY to LA, size of Texas)
- "Wait, WHAT?!" moments that feel unbelievable but are true
- Facts that make people feel smarter for knowing them
- A payoff that invites debate or comments ("and we still don't know why")

REQUIREMENTS:
- Hook: jaw-dropping question or statement, max 15 words
- Facts: exactly 3, each with specific numbers, US-scale references where natural
- Payoff: conclusion that drives shares or comments
- Title: SEO-friendly with emoji, max 60 chars
- Hashtags: 5 tags — mix broad (#space #science) and niche (#astrophysics)
- Scientifically accurate, fresh angle only

Return ONLY valid JSON with no markdown fences, no extra text:
{{
    "topic": "brief topic name",
    "topic_family": "{topic_family}",
    "hook": "the opening question or statement",
    "facts": [
        "fact 1 with specific numbers",
        "fact 2 with specific numbers",
        "fact 3 with specific numbers"
    ],
    "payoff": "surprising conclusion that drives shares or comments",
    "title": "YouTube title with emoji (max 60 chars)",
    "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}"""


# =============================================================================
# MAIN GENERATION LOOP
# =============================================================================
def generate_idea():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY environment variable not set")
        return None

    strategy       = load_strategy()
    history        = load_performance_history()
    existing_ideas = load_ideas()
    used_entries   = build_used_text_bank(history, existing_ideas)

    for attempt in range(MAX_GENERATION_ATTEMPTS):
        print(f"\n{'─' * 50}")
        print(f"🧪 Generation attempt {attempt + 1}/{MAX_GENERATION_ATTEMPTS}")

        # Cooldown between outer attempts — 0s, 35s, 70s
        if attempt > 0:
            cooldown = 35 * attempt + random.uniform(5, 15)
            print(f"⏳ Cooldown {cooldown:.0f}s before next attempt...")
            time.sleep(cooldown)

        topic_family  = select_topic_family(strategy, history)
        topic_guidance = get_topic_guidance(topic_family)
        print(f"🎯 Topic family: {topic_family}")

        prompt = build_prompt(topic_family, topic_guidance, history, existing_ideas)
        idea   = call_gemini(prompt, api_key)

        if not idea:
            print("⚠️  No idea returned — moving to next attempt")
            continue

        # Force correct topic family
        idea["topic_family"]   = topic_family
        idea["generated_at"]   = datetime.now().isoformat()
        idea["status"]         = "pending"
        idea["strategy_based"] = strategy is not None

        if is_too_similar(idea, used_entries):
            print("🔁 Too similar to existing content — retrying")
            continue

        print("✅ Fresh idea generated!")
        print(f"   Topic : {idea.get('topic')}")
        print(f"   Hook  : {idea.get('hook')}")
        print(f"   Title : {idea.get('title')}")
        return idea

    print("❌ Could not generate a fresh idea after all attempts")
    return None


# =============================================================================
# FILE SAVE
# =============================================================================
def save_idea(idea):
    ideas = load_ideas()
    ideas.append(idea)
    with open(IDEAS_FILE, "w") as f:
        json.dump(ideas, f, indent=2)
    print(f"\n💾 Saved to {IDEAS_FILE} (total: {len(ideas)} ideas)")


# =============================================================================
# ENTRY POINT
# =============================================================================
def main():
    print("=" * 60)
    print("🌌 ASTRO SHORTS ENGINE — Smart Idea Generator")
    print("   Target: US Audience 18-34 | Viral Astrophysics")
    print("=" * 60)

    status = "smart selection" if os.path.exists(STRATEGY_FILE) else "balanced selection"
    print(f"📊 Analytics: {status}")

    idea = generate_idea()

    if idea:
        save_idea(idea)
        print("\n" + "=" * 60)
        print("🎬 Idea saved — ready for script_formatter.py")
        print("=" * 60)
    else:
        print("\n❌ Generation failed — exiting with error code 1")
        exit(1)


if __name__ == "__main__":
    main()
