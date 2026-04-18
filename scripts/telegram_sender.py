"""
Telegram Sender — SpacePulse207
Sends the rendered video and full metadata to a Telegram chat/channel.

Required secrets (GitHub Secrets):
  TELEGRAM_BOT_TOKEN  — bot token from @BotFather
  TELEGRAM_CHAT_ID    — numeric chat/channel ID (e.g. -100xxxxxxxxxx)

Fix v2:
  - Migrated from legacy Markdown → MarkdownV2
  - Full escape of all MarkdownV2 special chars in dynamic content
  - Bold/italic formatting preserved via pre-escaped wrappers
"""

import json
import os
import re
import sys
from datetime import datetime

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("'requests' library not available")


# ── helpers ───────────────────────────────────────────────────────────────────

def get_env(name: str) -> str | None:
    val = os.environ.get(name, "").strip()
    return val if val else None


def _esc(text: str) -> str:
    """
    Escape ALL MarkdownV2 special characters in plain-text content.

    MarkdownV2 special chars: _ * [ ] ( ) ~ ` > # + - = | { } . ! \\
    These MUST be escaped with a preceding backslash when they appear
    in content (not as formatting markers).
    """
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!\\])', r'\\\1', str(text))


def _bold(text: str) -> str:
    """Return MarkdownV2 bold — content is escaped before wrapping."""
    return f"*{_esc(text)}*"


def _code(text: str) -> str:
    """Return MarkdownV2 inline code block — backticks escaped inside."""
    # In MarkdownV2 code spans, only ` and \ need escaping
    safe = text.replace("\\", "\\\\").replace("`", "\\`")
    return f"`{safe}`"


def _pre(text: str) -> str:
    """Return MarkdownV2 pre-formatted block."""
    safe = text.replace("\\", "\\\\").replace("`", "\\`")
    return f"```\n{safe}\n```"


def build_caption(script_data: dict) -> str:
    """Build a rich Telegram caption from script metadata (MarkdownV2)."""
    idea = script_data.get("idea", {})

    title        = idea.get("title", "Untitled")
    hook         = idea.get("hook", "")
    payoff       = idea.get("payoff", "")
    facts        = idea.get("facts", [])
    hashtags     = idea.get("hashtags", [])
    topic        = idea.get("topic", "")
    topic_family = idea.get("topic_family", "")
    generated_at = idea.get("generated_at", "")
    rendered_at  = script_data.get("rendered_at", "")

    # ── tags line ─────────────────────────────────────────────────────────
    tags_raw  = [tag.replace("#", "") for tag in hashtags]
    tags_raw += ["Shorts", "Space", "Astrophysics", "Science", "SpaceFacts", "Astronomy"]
    tags_str  = ", ".join(dict.fromkeys(tags_raw))

    # ── timestamps ────────────────────────────────────────────────────────
    def fmt_ts(ts: str) -> str:
        if not ts:
            return ""
        try:
            return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            return ts

    gen_fmt = fmt_ts(generated_at)
    ren_fmt = fmt_ts(rendered_at)

    # ── assemble lines ────────────────────────────────────────────────────
    lines: list[str] = []

    lines.append(f"🚀 {_bold(title)}")
    lines.append("")

    if hook:
        lines.append(f"🪝 {_bold('Hook:')} {_esc(hook)}")

    if facts:
        lines.append("")
        lines.append(f"📌 {_bold('Facts:')}")
        for f in facts:
            lines.append(f"  • {_esc(f)}")

    if payoff:
        lines.append("")
        lines.append(f"💡 {_bold('Payoff:')} {_esc(payoff)}")

    lines.append("")
    lines.append(_esc("─" * 30))
    lines.append("")

    if topic:
        lines.append(f"🏷 {_bold('Topic:')} {_esc(topic)}")
    if topic_family:
        lines.append(f"📂 {_bold('Family:')} {_esc(topic_family)}")
    if gen_fmt:
        lines.append(f"🕐 {_bold('Generated:')} {_esc(gen_fmt)}")
    if ren_fmt:
        lines.append(f"🎬 {_bold('Rendered:')}  {_esc(ren_fmt)}")

    lines.append("")
    lines.append(_esc("─" * 30))
    lines.append("")

    # ── YouTube description block (copy-paste ready) ───────────────────────
    description_lines: list[str] = []
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

    #lines.append(f"📝 {_bold('YouTube Description (copy\\-paste ready):')}")
    lines.append(f"📝 {_bold('YouTube Description (copy-paste ready):')}")

    raw_desc = "\n".join(description_lines)
    lines.append(_pre(raw_desc))

    lines.append("")
    lines.append(f"🏷 {_bold('Tags:')} {_code(tags_str)}")

    caption = "\n".join(lines)

    # Telegram captions: 1024 chars max for sendVideo
    # Smart truncation: never cut inside a ``` block
    if len(caption) > 1024:
        # Find the opening ``` — if truncation would land inside the block, drop the block entirely
        pre_start = caption.find("```")
        if pre_start != -1 and pre_start < 1020:
            # Truncate before the pre block, then close cleanly
            caption = caption[:pre_start].rstrip() + "\n…"
        else:
            caption = caption[:1020] + "…"

    return caption


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
                    "chat_id":           chat_id,
                    "caption":           caption,
                    "parse_mode":        "MarkdownV2",
                    "supports_streaming": "true",
                },
                files={"video": vf},
                timeout=300,   # 5 min for large files
            )

        result = resp.json()
        if result.get("ok"):
            msg = result["result"]
            print(f"✅ Sent! message_id={msg['message_id']}")
            return {
                "message_id": msg["message_id"],
                "chat_id":    chat_id,
                "sent_at":    datetime.now().isoformat(),
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
    # Plain text fallback — no parse_mode to avoid any escaping issues
    try:
        requests.post(
            url,
            data={"chat_id": chat_id, "text": text},
            timeout=30,
        )
    except Exception:
        pass


# ── candidate picker ──────────────────────────────────────────────────────────

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
            "video_path":  video_path,
            "rendered_at": data.get("rendered_at", ""),
        })

    candidates.sort(key=lambda x: x.get("rendered_at", ""), reverse=True)
    return candidates


def update_script_status(
    filepath: str,
    new_status: str,
    send_info: dict | None = None,
) -> None:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["status"]  = new_status
    data["sent_at"] = datetime.now().isoformat()
    if send_info:
        data["telegram"] = send_info

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── artifact saver ────────────────────────────────────────────────────────────

def _save_artifact(script_data: dict, video_path: str, script_path: str) -> None:
    """
    Even when Telegram send fails, copy the video + write a metadata .json
    to videos_output/ so the GitHub Actions upload-artifact step can capture it.
    This also updates the script status to 'send_failed' so it won't be retried
    as 'rendered' next run.
    """
    import shutil

    out_dir = "videos_output"
    os.makedirs(out_dir, exist_ok=True)

    # Video is already in videos_output (rendered there), so nothing to copy.
    # Just write a sidecar metadata file.
    base = os.path.splitext(os.path.basename(video_path))[0]
    meta_path = os.path.join(out_dir, f"{base}_meta.json")

    idea = script_data.get("idea", {})
    meta = {
        "status":       "send_failed",
        "video_file":   os.path.basename(video_path),
        "topic":        idea.get("topic", ""),
        "title":        idea.get("title", ""),
        "hook":         idea.get("hook", ""),
        "payoff":       idea.get("payoff", ""),
        "facts":        idea.get("facts", []),
        "hashtags":     idea.get("hashtags", []),
        "rendered_at":  script_data.get("rendered_at", ""),
        "failed_at":    datetime.now().isoformat(),
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"📁 Artifact metadata saved → {meta_path}")
    print(f"📹 Video still at          → {video_path}")

    # Mark script as send_failed so next run won't retry
    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["status"] = "send_failed"
    data["failed_at"] = datetime.now().isoformat()
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"🔖 Script status → send_failed")


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
            f"⚠️ SpacePulse207: Failed to send video '{os.path.basename(video_path)}'"
        )
        # ── Save artifact metadata so the video is still accessible ──────────
        _save_artifact(script_data, video_path, script_path)
        print("Send failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
