"""
Updates existing Notion CRM prospect records with generated outreach drafts.
Adds 'Outreach Draft', 'Outreach Subject', and 'Outreach Status' properties.
"""

import os
import time
import logging
import requests

log = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

OUTREACH_PROPERTIES = {
    "Outreach Subject": {"rich_text": {}},
    "Outreach Draft":   {"rich_text": {}},
    "Outreach Status":  {"select": {}},
}


def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _ensure_outreach_schema(db_id, token):
    """Add outreach properties to the database if they don't exist."""
    r = requests.get(f"{NOTION_API}/databases/{db_id}", headers=_headers(token))
    r.raise_for_status()
    existing = set(r.json().get("properties", {}).keys())

    to_add = {k: v for k, v in OUTREACH_PROPERTIES.items() if k not in existing}
    if not to_add:
        return

    log.info(f"Notion: adding outreach schema properties: {list(to_add.keys())}")
    patch = requests.patch(
        f"{NOTION_API}/databases/{db_id}",
        headers=_headers(token),
        json={"properties": to_add},
    )
    if patch.status_code != 200:
        log.error(f"Schema update failed: {patch.text[:200]}")


def _get_page_ids_by_website(db_id, token):
    """Return dict mapping website URL → Notion page ID."""
    mapping = {}
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(
            f"{NOTION_API}/databases/{db_id}/query",
            headers=_headers(token),
            json=body,
        )
        if r.status_code != 200:
            log.warning(f"Could not fetch Notion records: {r.text[:200]}")
            break
        data = r.json()
        for page in data.get("results", []):
            url = page.get("properties", {}).get("Website", {}).get("url")
            if url:
                mapping[url.lower().rstrip("/")] = page["id"]
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return mapping


def _text(value):
    return [{"text": {"content": str(value)[:2000]}}] if value else []


def push_drafts(results, db_id=None, token=None):
    """
    Update Notion prospect records with outreach drafts.
    results: list of (prospect, draft) tuples from personalizer.generate_batch()
    Returns (updated_count, skipped_count).
    """
    token = token or os.getenv("NOTION_TOKEN")
    db_id = db_id or os.getenv("NOTION_DATABASE_ID")

    if not token or not db_id:
        log.error("NOTION_TOKEN or NOTION_DATABASE_ID not set — skipping Notion update")
        return 0, 0

    _ensure_outreach_schema(db_id, token)

    log.info("Notion: fetching prospect page IDs …")
    page_map = _get_page_ids_by_website(db_id, token)
    log.info(f"Notion: found {len(page_map)} existing prospect records")

    updated, skipped = 0, 0
    for prospect, draft in results:
        if not draft:
            skipped += 1
            continue

        website = (prospect.get("website") or "").lower().rstrip("/")
        page_id = page_map.get(website)
        if not page_id:
            log.warning(f"No Notion page found for {prospect.get('name')} ({website}) — skipping")
            skipped += 1
            continue

        props = {
            "Outreach Subject": {"rich_text": _text(draft.get("subject", ""))},
            "Outreach Draft":   {"rich_text": _text(draft.get("body", ""))},
            "Outreach Status":  {"select": {"name": "Draft Ready"}},
        }

        r = requests.patch(
            f"{NOTION_API}/pages/{page_id}",
            headers=_headers(token),
            json={"properties": props},
        )
        if r.status_code == 200:
            updated += 1
            log.debug(f"  updated: {prospect.get('name')}")
        else:
            log.warning(f"  failed ({r.status_code}): {prospect.get('name')} — {r.text[:200]}")

        time.sleep(0.35)  # Notion API rate limit

    log.info(f"Notion: updated {updated}, skipped {skipped}")
    return updated, skipped
