"""
Notion digest publisher: creates a new child page for each digest run
under a configured parent page. Each page is a fully formatted briefing.
"""

import os
import re
import logging
import requests
from datetime import date

log = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _text_block(content, bold=False):
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": content[:2000]},
                           "annotations": {"bold": bold}}]
        },
    }


def _heading(content, level=2):
    h_type = f"heading_{level}"
    return {
        "object": "block",
        "type": h_type,
        h_type: {
            "rich_text": [{"type": "text", "text": {"content": content[:2000]}}]
        },
    }


def _bullet(content):
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": content[:2000]}}]
        },
    }


def _divider():
    return {"object": "block", "type": "divider", "divider": {}}


def _markdown_to_blocks(markdown):
    """
    Convert the Claude-generated markdown briefing into Notion blocks.
    Handles ## headings, bullet lists (- or *), and paragraphs.
    """
    blocks = []
    for line in markdown.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            blocks.append(_heading(stripped[3:], level=2))
        elif stripped.startswith("### "):
            blocks.append(_heading(stripped[4:], level=3))
        elif stripped.startswith(("- ", "* ", "• ")):
            blocks.append(_bullet(stripped[2:]))
        elif re.match(r"^\d+\.\s", stripped):
            # numbered list → bullet
            blocks.append(_bullet(re.sub(r"^\d+\.\s", "", stripped)))
        else:
            blocks.append(_text_block(stripped))
    return blocks


def push(briefing, run_date=None, token=None, parent_page_id=None):
    """
    Create a new Notion page with the briefing content.
    Returns the new page URL or None on failure.
    """
    token = token or os.getenv("NOTION_TOKEN")
    parent_page_id = parent_page_id or os.getenv("NOTION_DIGEST_PAGE_ID")

    if not token:
        log.error("NOTION_TOKEN not set — skipping Notion digest push")
        return None
    if not parent_page_id:
        log.warning(
            "NOTION_DIGEST_PAGE_ID not set — digest will only be saved locally. "
            "Add a parent page ID to .env to enable Notion publishing."
        )
        return None

    run_date = run_date or date.today().isoformat()
    title = f"Market Intelligence — {run_date}"

    content_blocks = [
        _text_block(
            f"Auto-generated market intelligence briefing for {run_date}. "
            "Sources: Hacker News, arXiv, AI newsletters.",
            bold=False,
        ),
        _divider(),
    ] + _markdown_to_blocks(briefing)

    # Notion API limits: max 100 blocks per request
    page_body = {
        "parent": {"page_id": parent_page_id},
        "properties": {
            "title": {
                "title": [{"type": "text", "text": {"content": title}}]
            }
        },
        "children": content_blocks[:100],
    }

    r = requests.post(
        f"{NOTION_API}/pages",
        headers=_headers(token),
        json=page_body,
    )

    if r.status_code != 200:
        log.error(f"Notion digest push failed ({r.status_code}): {r.text[:300]}")
        return None

    page_url = r.json().get("url", "")
    log.info(f"Notion digest page created: {page_url}")

    # If more than 100 blocks, append the rest
    if len(content_blocks) > 100:
        page_id = r.json()["id"]
        remaining = content_blocks[100:]
        for i in range(0, len(remaining), 100):
            chunk = remaining[i:i+100]
            requests.patch(
                f"{NOTION_API}/blocks/{page_id}/children",
                headers=_headers(token),
                json={"children": chunk},
            )

    return page_url
