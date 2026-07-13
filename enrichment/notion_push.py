"""
Notion CRM integration: pushes scored prospects into a Notion database.

On first run, adds any missing properties to the database automatically.
On subsequent runs, skips prospects already in the database (by website URL).
"""

import os
import time
import logging
import requests

log = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Properties to ensure exist in the Notion database and their types
REQUIRED_PROPERTIES = {
    "Website":          {"url": {}},
    "Score":            {"number": {"format": "number"}},
    "Source":           {"select": {}},
    "Contact Name":     {"rich_text": {}},
    "Contact Title":    {"rich_text": {}},
    "Contact Email":    {"email": {}},
    "Contact LinkedIn": {"url": {}},
    "Twitter":          {"url": {}},
    "Description":      {"rich_text": {}},
    "Location":         {"rich_text": {}},
    "Topics":           {"multi_select": {}},
    "GitHub URL":       {"url": {}},
    "Score Reasons":    {"rich_text": {}},
    "Status":           {"select": {}},
}


def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _ensure_schema(db_id, token):
    """Add any missing properties to the Notion database."""
    r = requests.get(f"{NOTION_API}/databases/{db_id}", headers=_headers(token))
    r.raise_for_status()
    existing = set(r.json().get("properties", {}).keys())

    to_add = {
        k: v for k, v in REQUIRED_PROPERTIES.items() if k not in existing
    }
    if not to_add:
        log.info("Notion schema: all properties already exist")
        return

    log.info(f"Notion schema: adding {len(to_add)} missing properties: {list(to_add.keys())}")
    patch = requests.patch(
        f"{NOTION_API}/databases/{db_id}",
        headers=_headers(token),
        json={"properties": to_add},
    )
    if patch.status_code != 200:
        log.error(f"Schema update failed: {patch.text}")
        patch.raise_for_status()
    log.info("Notion schema: updated successfully")


def _get_existing_pages(db_id, token):
    """Return dict mapping website URL → page_id for all existing records."""
    existing = {}
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
            log.warning(f"Could not fetch existing records: {r.text}")
            break
        data = r.json()
        for page in data.get("results", []):
            props = page.get("properties", {})
            url_prop = props.get("Website", {}).get("url")
            if url_prop:
                existing[url_prop.lower().rstrip("/")] = page["id"]
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return existing


def _contact_patch(prospect):
    """Build a properties patch dict containing only non-empty contact fields."""
    props = {}
    if prospect.get("contact_email"):
        props["Contact Email"] = {"email": prospect["contact_email"]}
    if prospect.get("contact_name"):
        props["Contact Name"] = {"rich_text": _text(prospect["contact_name"])}
    if prospect.get("contact_title"):
        props["Contact Title"] = {"rich_text": _text(prospect["contact_title"])}
    if prospect.get("contact_linkedin"):
        props["Contact LinkedIn"] = {"url": prospect["contact_linkedin"]}
    if prospect.get("twitter"):
        handle = prospect["twitter"].lstrip("@")
        props["Twitter"] = {"url": f"https://x.com/{handle}"}
    return props


def _text(value):
    return [{"text": {"content": str(value)[:2000]}}] if value else []


def _prospect_to_page(prospect, db_id):
    """Convert a prospect dict to a Notion page payload."""
    name = prospect.get("name") or prospect.get("login") or "Unknown"
    website = prospect.get("website") or ""
    topics = prospect.get("topics") or []
    if isinstance(topics, str):
        topics = [t.strip() for t in topics.split("|") if t.strip()]

    props = {
        "Name": {"title": _text(name)},
        "Score": {"number": int(prospect.get("score") or 0)},
        "Source": {"select": {"name": prospect.get("source", "github").capitalize()}},
        "Description": {"rich_text": _text(prospect.get("description") or "")},
        "Location": {"rich_text": _text(prospect.get("location") or "")},
        "Score Reasons": {"rich_text": _text(prospect.get("score_reasons") or "")},
        "Status": {"select": {"name": "New"}},
    }

    if website:
        props["Website"] = {"url": website}
    if prospect.get("github_url"):
        props["GitHub URL"] = {"url": prospect["github_url"]}
    if prospect.get("contact_name"):
        props["Contact Name"] = {"rich_text": _text(prospect["contact_name"])}
    if prospect.get("contact_title"):
        props["Contact Title"] = {"rich_text": _text(prospect["contact_title"])}
    if prospect.get("contact_email"):
        props["Contact Email"] = {"email": prospect["contact_email"]}
    if prospect.get("contact_linkedin"):
        props["Contact LinkedIn"] = {"url": prospect["contact_linkedin"]}
    if prospect.get("twitter"):
        handle = prospect["twitter"].lstrip("@")
        props["Twitter"] = {"url": f"https://x.com/{handle}"}
    if topics:
        props["Topics"] = {"multi_select": [{"name": t[:100]} for t in topics[:10]]}

    return {"parent": {"database_id": db_id}, "properties": props}


def push(prospects, db_id=None, token=None):
    """
    Push prospects to Notion. Skips duplicates by Website URL.
    Returns (pushed_count, skipped_count).
    """
    token = token or os.getenv("NOTION_TOKEN")
    db_id = db_id or os.getenv("NOTION_DATABASE_ID")

    if not token:
        log.error("NOTION_TOKEN not set — skipping Notion push")
        return 0, 0
    if not db_id:
        log.error("NOTION_DATABASE_ID not set — skipping Notion push")
        return 0, 0

    _ensure_schema(db_id, token)

    log.info("Notion: fetching existing records …")
    existing_pages = _get_existing_pages(db_id, token)
    log.info(f"Notion: {len(existing_pages)} existing records found")

    pushed = updated = skipped = 0
    for p in prospects:
        website = (p.get("website") or "").lower().rstrip("/")

        if website and website in existing_pages:
            # Record exists — patch contact fields if we have new data
            patch = _contact_patch(p)
            if patch:
                r = requests.patch(
                    f"{NOTION_API}/pages/{existing_pages[website]}",
                    headers=_headers(token),
                    json={"properties": patch},
                )
                if r.status_code == 200:
                    updated += 1
                    log.debug(f"  updated contact: {p.get('name')}")
                else:
                    log.warning(f"  update failed ({r.status_code}): {p.get('name')} — {r.text[:200]}")
                time.sleep(0.35)
            else:
                skipped += 1
            continue

        page_body = _prospect_to_page(p, db_id)
        r = requests.post(
            f"{NOTION_API}/pages",
            headers=_headers(token),
            json=page_body,
        )
        if r.status_code == 200:
            pushed += 1
            existing_pages[website] = None
            log.debug(f"  pushed: {p.get('name')}")
        else:
            log.warning(f"  failed ({r.status_code}): {p.get('name')} — {r.text[:200]}")

        time.sleep(0.35)  # Notion API: 3 req/sec limit

    log.info(f"Notion: pushed {pushed} new, updated {updated} contacts, skipped {skipped}")
    return pushed, skipped
