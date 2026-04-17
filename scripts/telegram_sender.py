"""
Telegram Sender — SpacePulse207
Sends the rendered video and full metadata to a Telegram chat/channel.

Required secrets (GitHub Secrets):
  TELEGRAM_BOT_TOKEN  — bot token from @BotFather
  TELEGRAM_CHAT_ID    — numeric chat/channel ID (e.g. -100xxxxxxxxxx)
"""

import json
import os
import sys
from datetime import datetime

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("'requests' library not available")


TELEGRAM_API = "https://api.telegram.org/bot{token}"


# ── helpers ───────────────────────────────────────────────────────────────────

def get_env(name: str) -> str | None:
    val = os.environ.get(name, "").strip()
    return val if val else None


def build_caption(script_data: dict) -> str:
    """Build a rich Telegram caption from script metadata."""
    idea = script_data.get("idea", {})

    title       = idea.get("title", "Untitled")
    hook        = idea.get("hook", "")
    payoff      = idea.get("payoff", "")
    facts       = idea.get("facts", [])
    hashtags    = idea.get("hashtags", [])
    topic       = idea.get("topic", "")
    topic_family = idea.get("topic_family", "")
    generated_at = idea.get("generated_at", "")
    rendered_at  = script_data.get("rendered_at", "")

    # tags line
    tags_raw   = [tag.replace("#", "") for tag in hashtags]
    tags_raw  += ["Shorts", "Space", "Astrophysics", "Science", "SpaceFacts", "Astronomy"]
    tags_str   = ", ".join(dict.fromkeys(tags_raw))  # deduplicate while preserving order

    # facts block
    facts_block = ""
    if facts:
        facts_block = "\n".join(f"  • {f}" for f in facts)

    # timestamps
    gen_fmt = ""
    if generated_at:
        try:
            gen_fmt = datetime.fromisoformat(generated_at).strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            gen_fmt = generated_at

    ren_fmt = ""
    if rendered_at:
        try:
            ren_fmt = datetime.fromisoformat(rendered_at).strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            ren_fmt = rendered_at

    lines = []
    lines.append(f"🚀 *{_esc(title)}*")
    lines.append("")

    if hook:
        lines.append(f"🪝 *Hook:* {_esc(hook)}")

    if facts_block:
        lines.append("")
        lines.append("📌 *Facts:*")
        lines.append(_esc(facts_block))

    if payoff:
        lines.append("")
        lines.append(f"💡 *Payoff:* {_esc(payoff)}")

    lines.append("")
    lines.append("─" * 30)
    lines.append("")

    if topic:
        lines.append(f"🏷 *Topic:* {_esc(topic)}")
    if topic_family:
        lines.append(f"📂 *Family:* {_esc(topic_family)}")
    if gen_fmt:
        lines.append(f"🕐 *Generated:* {gen_fmt}")
    if ren_fmt:
        lines.append(f"🎬 *Rendered:*  {ren_fmt}")

    lines.append("")
    lines.append("─" * 30)
    lines.append("")

    # description block (same format as YouTube)
    description_lines = []
    if hook:
        description_lines.append(hook)
    if payoff:
        description_lines.append("")
        description_lines.append(payoff)
    if hashtags:
        description_lines.append("")
        description_lines.append(" ".join(hashtags))
    description_lines.append("")
    description_lines.append("#Shorts #Space #Astrophysics #Science #SpaceFacts")

    lines.append("📝 *YouTube Description (copy-paste ready):*")
    lines.append("```")
    lines.append("\n".join(description_lines))
    lines.append("```")

    lines.append("")
    lines.append(f"🏷 *Tags:* `{_esc(tags_str)}`")

    caption = "\n".join(lines)

    # Telegram captions have a 1024-char limit for sendVideo
    # If over limit, trim the description block
    if len(caption) > 1024:
        caption = caption[:1020] + "…"

    return caption


def _esc(text: str) -> str:
    """Escape MarkdownV2 special chars for Telegram."""
    # We're using legacy Markdown (parse_mode=Markdown) so only * ` _ [ ] need care.
    # We keep * and ` intentional; escape _ to avoid accidental italics.
    return text.replace("_", "\\_")


# ── API calls ─────────────────────────────────────────────────────────────────

def send_video(token: str, chat_id: str, video_path: str, caption: str) -> dict | None:
    url = f"https://api.telegram.org/bot{token}/sendVideo"

    print(f"📤 Sending video to Telegram chat {chat_id}…")
    print(f"   File: {video_path} ({os.path.getsize(video_path) / 1_048_576:.1f} MB)")

    try:
        with open(video_path, "rb") as vf:
            resp = requests.post(
                url,
                data={
                    "chat_id": chat_id,
                    "caption": caption,
                    "parse_mode": "Markdown",
                    "supports_streaming": "true",
                },
                files={"video": vf},
                timeout=300,  # 5 min for large files
            )

        result = resp.json()
        if result.get("ok"):
            msg = result["result"]
            print(f"✅ Sent! message_id={msg['message_id']}")
            return {
                "message_id": msg["message_id"],
                "chat_id": chat_id,
                "sent_at": datetime.now().isoformat(),
            }
        else:
            print(f"❌ Telegram API error: {result.get('description', 'unknown')}")
            return None

    except Exception as exc:
        print(f"❌ Request failed: {exc}")
        return None


def send_message(token: str, chat_id: str, text: str) -> None:
    """Fallback: send a plain text message (e.g. error notice)."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(
            url,
            data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=30,
        )
    except Exception:
        pass


# ── candidate picker (mirrors youtube_uploader logic) ─────────────────────────

def get_upload_candidates(scripts_dir: str = "scripts_output") -> list[dict]:
    if not os.path.exists(scripts_dir):
        return []

    candidates = []
    for filename in os.listdir(scripts_dir):
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(scripts_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        if data.get("status") != "rendered":
            continue

        video_path = data.get("video_path")
        if not video_path or not os.path.exists(video_path):
            print(f"⚠️  Rendered script missing video: {filepath}")
            continue

        candidates.append({
            "script_path": filepath,
            "script_data": data,
            "video_path": video_path,
            "rendered_at": data.get("rendered_at", ""),
        })

    candidates.sort(key=lambda x: x.get("rendered_at", ""), reverse=True)
    return candidates


def update_script_status(filepath: str, new_status: str, send_info: dict | None = None) -> None:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["status"] = new_status
    data["sent_at"] = datetime.now().isoformat()
    if send_info:
        data["telegram"] = send_info

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("SPACEPULSE207 — Telegram Sender")
    print("=" * 60)
    print()

    if not REQUESTS_AVAILABLE:
        print("Install 'requests': pip install requests")
        sys.exit(1)

    token   = get_env("TELEGRAM_BOT_TOKEN")
    chat_id = get_env("TELEGRAM_CHAT_ID")

    if not token:
        print("❌ TELEGRAM_BOT_TOKEN secret is missing")
        sys.exit(1)
    if not chat_id:
        print("❌ TELEGRAM_CHAT_ID secret is missing")
        sys.exit(1)

    candidates = get_upload_candidates()
    print(f"Found {len(candidates)} rendered video(s) ready to send")
    if not candidates:
        print("Nothing to send.")
        return

    selected    = candidates[0]
    script_path = selected["script_path"]
    script_data = selected["script_data"]
    video_path  = selected["video_path"]

    print(f"\n📹 Selected: {os.path.basename(video_path)}")
    print("-" * 60)

    caption = build_caption(script_data)
    print("Caption preview (first 300 chars):")
    print(caption[:300])
    print("…" if len(caption) > 300 else "")
    print()

    result = send_video(token, chat_id, video_path, caption)

    if result:
        update_script_status(script_path, "sent_telegram", result)
        print()
        print("=" * 60)
        print("✅ VIDEO SENT TO TELEGRAM SUCCESSFULLY")
        print("=" * 60)
    else:
        send_message(
            token, chat_id,
            f"⚠️ SpacePulse207: Failed to send video `{os.path.basename(video_path)}`"
        )
        print("Send failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
