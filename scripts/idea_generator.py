"""
Idea Generator Agent - SMART VERSION with Robust Retry Logic
Generates astrophysics YouTube Shorts ideas using Gemini API.
Uses analytics data to prioritize winning topic types,
with exponential backoff to handle 429/503 gracefully.
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

RECENT_TOPIC_LIMIT = 10
RECENT_FAMILY_BLOCK = 3
MAX_GENERATION_ATTEMPTS = 3  # Reduced to avoid hammering API

# Gemini retry config
GEMINI_MAX_RETRIES = 4
GEMINI_BASE_DELAY = 20   # seconds — first retry wait
GEMINI_MODEL = "gemini-2.5-flash"


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
# ANALYTICS INTEGRATION
# =============================================================================
def load_strategy():
    if os.path.exists(STRATEGY_FILE):
        try:
            with open(STRATEGY_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Could not load strategy: {e}")
    return None


def load_performance_history():
    if os.path.exists(PERFORMANCE_FILE):
        try:
            with open(PERFORMANCE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Could not load performance history: {e}")
    return []


def load_ideas():
    if os.path.exists(IDEAS_FILE):
        try:
            with open(IDEAS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Could not load ideas: {e}")
    return []


def get_recent_topics(history, limit=10):
    recent = sorted(history, key=lambda x: x.get("published_at", ""), reverse=True)[:limit]
    return [v.get("topic_family", "general") for v in recent]


def get_recent_titles(history, limit=10):
    recent = sorted(history, key=lambda x: x.get("published_at", ""), reverse=True)[:limit]
    return [v.get("title", "") for v in recent if v.get("title")]


def family_on_cooldown(topic_family, history, cooldown_count=3):
    recent_families = get_recent_topics(history, limit=cooldown_count)
    return topic_family in recent_families


def select_topic_family(strategy, history):
    if not strategy or not strategy.get("top_performing_topics"):
        print("📊 No analytics data yet, using balanced selection")
        available = [t for t in DEFAULT_TOPICS if not family_on_cooldown(t, history, cooldown_count=2)]
        return random.choice(available or DEFAULT_TOPICS)

    top_topics = strategy.get("top_performing_topics", [])
    suggested = strategy.get("suggested_next", DEFAULT_TOPICS)
    avoid = [t["topic"] for t in strategy.get("avoid_topics", [])]
    recent_topics = get_recent_topics(history, limit=5)

    roll = random.random()

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
    used_entries = []
    for item in history[-50:]:
        used_entries.append({
            "topic": item.get("topic", ""),
            "hook": item.get("hook", ""),
            "title": item.get("title", ""),
            "topic_family": item.get("topic_family", "")
        })
    for item in existing_ideas[-50:]:
        used_entries.append({
            "topic": item.get("topic", ""),
            "hook": item.get("hook", ""),
            "title": item.get("title", ""),
            "topic_family": item.get("topic_family", "")
        })
    return used_entries


def is_too_similar(new_idea, used_entries, similarity_threshold=0.65):
    new_topic = new_idea.get("topic", "")
    new_hook = new_idea.get("hook", "")
    new_title = new_idea.get("title", "")
    new_family = new_idea.get("topic_family", "")

    for existing in used_entries:
        existing_topic = existing.get("topic", "")
        existing_hook = existing.get("hook", "")
        existing_title = existing.get("title", "")
        existing_family = existing.get("topic_family", "")

        if normalize_text(new_topic) and normalize_text(new_topic) == normalize_text(existing_topic):
            print(f"⚠️  Duplicate topic: {new_topic}")
            return True
        if normalize_text(new_hook) and normalize_text(new_hook) == normalize_text(existing_hook):
            print(f"⚠️  Duplicate hook: {new_hook}")
            return True
        if normalize_text(new_title) and normalize_text(new_title) == normalize_text(existing_title):
            print(f"⚠️  Duplicate title: {new_title}")
            return True

        if jaccard_similarity(new_topic, existing_topic) >= similarity_threshold:
            print(f"⚠️  Near-duplicate topic")
            return True
        if jaccard_similarity(new_hook, existing_hook) >= similarity_threshold:
            print(f"⚠️  Near-duplicate hook")
            return True
        if jaccard_similarity(new_title, existing_title) >= similarity_threshold:
            print(f"⚠️  Near-duplicate title")
            return True

        if new_family == existing_family:
            if (jaccard_similarity(new_topic, existing_topic) >= 0.45 or
                    jaccard_similarity(new_hook, existing_hook) >= 0.45):
                print("⚠️  Same family + too semantically close")
                return True

    return False


# =============================================================================
# GEMINI API — EXPONENTIAL BACKOFF
# =============================================================================
def call_gemini(prompt, api_key):
    """
    Call Gemini API with exponential backoff.
    Delays: 20s → 40s → 80s → 160s
    Handles both 429 (rate limit) and 503 (overload).
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
            print(f"  🚀 Gemini call attempt {attempt + 1}/{GEMINI_MAX_RETRIES}...")
            response = requests.post(url, json=payload, headers=headers, timeout=90)

            # Rate limit or overload — back off and retry
            if response.status_code in (429, 503):
                if attempt < GEMINI_MAX_RETRIES - 1:
                    print(f"  ⏳ HTTP {response.status_code} — waiting {wait:.0f}s...")
                    time.sleep(wait)
                    continue
                else:
                    print(f"  ❌ HTTP {response.status_code} — no retries left")
                    return None

            response.raise_for_status()
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            clean = text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)

        except requests.exceptions.Timeout:
            print(f"  ⚠️  Timeout on attempt {attempt + 1}")
            if attempt < GEMINI_MAX_RETRIES - 1:
                time.sleep(wait)

        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  Request error: {e}")
            if attempt < GEMINI_MAX_RETRIES - 1:
                print(f"  ⏳ Waiting {wait:.0f}s...")
                time.sleep(wait)

        except json.JSONDecodeError as e:
            print(f"  ❌ JSON parse error: {e}")
            return None  # Bad response format — no point retrying

        except Exception as e:
            print(f"  ❌ Unexpected: {e}")
            return None

    print("  ❌ Gemini exhausted all retries")
    return None


# =============================================================================
# PROMPT BUILDER
# =============================================================================
def build_prompt(topic_family, topic_guidance, history, existing_ideas):
    recent_titles = get_recent_titles(history, limit=10)
    recent_idea_topics = [
        idea.get("topic", "")
        for idea in existing_ideas[-10:]
        if idea.get("topic")
    ]

    avoid_list = recent_titles + recent_idea_topics
    avoid_text = "\n".join([f"- {item}" for item in avoid_list if item]) or "- None"

    return f"""You are a viral astrophysics YouTube Shorts content strategist targeting US audiences aged 18-34.

Generate ONE idea for a 20-second silent infographic Short about space or astrophysics.

TOPIC TYPE: {topic_family}
DESCRIPTION: {topic_guidance}

AVOID these recently used topics/titles:
{avoid_text}

VIRAL HOOKS that work for US audiences:
- Start with a shocking number or comparison ("The Sun is so big that...")
- Use relatable US scale references (football fields, NYC, distance to LA)
- Trigger "wait, what?!" moments
- End with a fact that makes people want to share

REQUIREMENTS:
- Hook: punchy question or jaw-dropping statement (max 15 words)
- Facts: 3 facts with specific numbers, use US-friendly scale references where possible
- Payoff: surprising conclusion that invites comments or shares
- Title: SEO-friendly with emoji, max 60 chars
- Hashtags: mix of broad (#space #science) and niche (#astrophysics #spaceisfake)
- Must feel FRESH — not a rephrasing of the avoid list above
- Scientifically accurate

Return ONLY valid JSON, no markdown, no preamble:
{{
    "topic": "brief topic name",
    "topic_family": "{topic_family}",
    "hook": "the opening question or statement",
    "facts": [
        "fact 1 with specific numbers and US-scale reference",
        "fact 2 with specific numbers",
        "fact 3 with specific numbers"
    ],
    "payoff": "surprising conclusion that drives shares/comments",
    "title": "YouTube title with emoji (max 60 chars)",
    "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}"""


# =============================================================================
# IDEA GENERATION
# =============================================================================
def generate_idea():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
        return None

    strategy = load_strategy()
    history = load_performance_history()
    existing_ideas = load_ideas()
    used_entries = build_used_text_bank(history, existing_ideas)

    for attempt in range(MAX_GENERATION_ATTEMPTS):
        print(f"\n{'='*50}")
        print(f"🧪 Generation attempt {attempt + 1}/{MAX_GENERATION_ATTEMPTS}")

        # Cooldown between outer attempts to respect rate limits
        if attempt > 0:
            cooldown = 30 * attempt + random.uniform(5, 15)
            print(f"⏳ Outer cooldown: {cooldown:.0f}s before next attempt...")
            time.sleep(cooldown)

        topic_family = select_topic_family(strategy, history)
        topic_guidance = get_topic_guidance(topic_family)
        print(f"🎯 Topic family: {topic_family}")

        prompt = build_prompt(topic_family, topic_guidance, history, existing_ideas)
        idea = call_gemini(prompt, api_key)

        if not idea:
            print("⚠️  No idea returned from Gemini, trying next attempt...")
            continue

        idea["topic_family"] = topic_family
        idea["generated_at"] = datetime.now().isoformat()
        idea["status"] = "pending"
        idea["strategy_based"] = strategy is not None

        if is_too_similar(idea, used_entries):
            print("🔁 Too similar to existing content, retrying...")
            continue

        print("✅ Fresh idea generated!")
        print(f"   Topic  : {idea.get('topic')}")
        print(f"   Hook   : {idea.get('hook')}")
        print(f"   Title  : {idea.get('title')}")
        return idea

    print("❌ Failed to generate a fresh idea after all attempts")
    return None


# =============================================================================
# FILE MANAGEMENT
# =============================================================================
def save_idea(idea):
    ideas = load_ideas()
    ideas.append(idea)
    with open(IDEAS_FILE, "w") as f:
        json.dump(ideas, f, indent=2)
    print(f"\n💾 Saved to {IDEAS_FILE} (total: {len(ideas)} ideas)")


# =============================================================================
# MAIN
# =============================================================================
def main():
    print("=" * 60)
    print("🌌 ASTRO SHORTS ENGINE — Smart Idea Generator")
    print("   Target: US Audience | Viral Astrophysics Shorts")
    print("=" * 60)

    if os.path.exists(STRATEGY_FILE):
        print("📊 Analytics data found — using smart selection")
    else:
        print("📊 No analytics yet — using balanced selection")

    idea = generate_idea()

    if idea:
        save_idea(idea)
        print("\n" + "=" * 60)
        print("🎬 Idea ready — passing to script_formatter.py")
        print("=" * 60)
    else:
        print("\n❌ Idea generation failed. Exiting with error.")
        exit(1)


if __name__ == "__main__":
    main()
