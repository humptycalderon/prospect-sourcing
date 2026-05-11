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
            lines.append(f"• {re.sub(r'^\\d+\\.\\s', '', stripped)}")
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
