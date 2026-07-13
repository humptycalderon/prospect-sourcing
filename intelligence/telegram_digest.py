"""
Telegram digest publisher: sends the market intelligence briefing
to a Telegram chat via the Bot API.

Telegram message limit is 4096 chars, so long briefings are split
into chunks and sent as a thread.
"""

import os
import re
import logging
import requests

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
MAX_MSG_LEN = 4000  # leave headroom below the 4096 hard limit


def _send(token, chat_id, text, parse_mode="Markdown"):
    """Send a single message. Returns True on success."""
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }, timeout=15)

    if resp.status_code != 200:
        log.error(f"Telegram send failed ({resp.status_code}): {resp.text[:200]}")
        return False
    return True


def _markdown_to_telegram(text):
    """
    Convert Claude's markdown to Telegram-flavored markdown.
    Telegram supports: *bold*, _italic_, `code`, ```pre```, [text](url)
    It does NOT support ## headings — convert those to bold lines.
    """
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            lines.append(f"\n*{stripped[3:].upper()}*")
        elif stripped.startswith("### "):
            lines.append(f"*{stripped[4:]}*")
        elif stripped.startswith(("- ", "* ", "• ")):
            lines.append(f"• {stripped[2:]}")
        elif re.match(r"^\d+\.\s", stripped):
            bullet_text = re.sub(r"^\d+\.\s", "", stripped)
            lines.append(f"• {bullet_text}")
        else:
            lines.append(line)
    return "\n".join(lines)


def _split(text, max_len=MAX_MSG_LEN):
    """
    Split text into chunks at paragraph boundaries to stay under max_len.
    """
    chunks = []
    current = ""
    for para in text.split("\n\n"):
        candidate = (current + "\n\n" + para).strip() if current else para
        if len(candidate) > max_len:
            if current:
                chunks.append(current.strip())
            # If single paragraph is still too long, hard-split it
            if len(para) > max_len:
                for i in range(0, len(para), max_len):
                    chunks.append(para[i:i + max_len])
                current = ""
            else:
                current = para
        else:
            current = candidate
    if current:
        chunks.append(current.strip())
    return chunks


def push_recommendations(recommendations, run_date=None, token=None, chat_id=None):
    """
    Send ICP search criteria recommendations to Telegram as an actionable message.
    The user replies to the Cloudflare Worker bot to approve or modify.
    """
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        log.error("Telegram credentials not set — skipping recommendations delivery")
        return False

    from datetime import date
    run_date = run_date or date.today().isoformat()

    lines = [f"🎯 *ICP Update Recommendations — {run_date}*"]
    lines.append(f"_Based on this week's market signals_\n{'─' * 30}")

    reason = recommendations.get("_update_reason", "")
    if reason:
        lines.append(f"*Signal:* {reason}\n")

    gh_queries = recommendations.get("extra_github_queries", [])
    hn_queries = recommendations.get("extra_hn_queries", [])
    desc_kw = recommendations.get("extra_description_keywords", {})
    intent_kw = recommendations.get("extra_intent_keywords", {})

    has_changes = any([gh_queries, hn_queries, desc_kw, intent_kw])

    if not has_changes:
        lines.append("_No updates recommended this week — current criteria look strong._")
    else:
        if gh_queries:
            lines.append("*New GitHub Queries:*")
            for q in gh_queries:
                lines.append(f"  • `{q}`")
        if hn_queries:
            lines.append("*New HN Queries:*")
            for q in hn_queries:
                lines.append(f"  • `{q}`")
        if desc_kw:
            lines.append("*New Description Keywords:*")
            for kw, w in desc_kw.items():
                lines.append(f"  • `{kw}` (weight: {w})")
        if intent_kw:
            lines.append("*New Intent Keywords:*")
            for kw, w in intent_kw.items():
                lines.append(f"  • `{kw}` (weight: {w})")

        lines.append("\n─────────────────")
        lines.append("Reply *APPLY* to add these to the pipeline, or tell me what to change.")
        lines.append("Prospect sourcing will run after you confirm.")

    msg = "\n".join(lines)
    return _send(token, chat_id, msg)


def push(briefing, run_date=None, token=None, chat_id=None):
    """
    Send the briefing to Telegram. Long briefings are split across messages.
    Returns True on success, False on failure.
    """
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not token:
        log.error("TELEGRAM_BOT_TOKEN not set — skipping Telegram delivery")
        return False
    if not chat_id:
        log.error("TELEGRAM_CHAT_ID not set — skipping Telegram delivery")
        return False

    from datetime import date
    run_date = run_date or date.today().isoformat()

    # Header message
    header = (
        f"📊 *Market Intelligence — {run_date}*\n"
        f"_Sources: Hacker News · arXiv · AI Newsletters_\n"
        f"{'─' * 30}"
    )
    _send(token, chat_id, header)

    # Convert and split the briefing body
    telegram_text = _markdown_to_telegram(briefing)
    chunks = _split(telegram_text)

    log.info(f"Telegram: sending briefing in {len(chunks)} message(s) …")
    for i, chunk in enumerate(chunks, 1):
        success = _send(token, chat_id, chunk)
        if not success:
            log.error(f"Telegram: failed on chunk {i}/{len(chunks)}")
            return False

    log.info("Telegram: briefing delivered successfully")
    return True
