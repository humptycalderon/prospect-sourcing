"""
Exports Draft Ready prospects from Notion CRM to a send-ready CSV.
Includes contact email or LinkedIn, subject line, and email body.

Usage:
  python export_outreach.py
  python export_outreach.py --out send_list.csv
"""

import os
import csv
import logging
import argparse
import requests
from datetime import date
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

NOTION_API    = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _text_val(prop):
    parts = prop.get("rich_text", [])
    return "".join(p.get("text", {}).get("content", "") for p in parts)


def _title_val(prop):
    parts = prop.get("title", [])
    return "".join(p.get("text", {}).get("content", "") for p in parts)


def fetch_draft_ready(db_id, token):
    """Query Notion for all prospects with Outreach Status = Draft Ready."""
    records = []
    cursor = None

    log.info("Fetching Draft Ready prospects from Notion …")
    while True:
        body = {
            "page_size": 100,
            "filter": {
                "property": "Outreach Status",
                "select": {"equals": "Draft Ready"},
            },
        }
        if cursor:
            body["start_cursor"] = cursor

        r = requests.post(
            f"{NOTION_API}/databases/{db_id}/query",
            headers=_headers(token),
            json=body,
        )
        if r.status_code != 200:
            log.error(f"Notion query failed ({r.status_code}): {r.text[:200]}")
            break

        data = r.json()
        for page in data.get("results", []):
            p = page.get("properties", {})

            name    = _title_val(p.get("Name", {}))
            website = (p.get("Website") or {}).get("url", "")
            email   = (p.get("Contact Email") or {}).get("email", "")
            linkedin = (p.get("Contact LinkedIn") or {}).get("url", "")
            subject = _text_val(p.get("Outreach Subject", {}))
            body_text = _text_val(p.get("Outreach Draft", {}))
            score   = (p.get("Score") or {}).get("number", "")

            # Determine channel: email preferred, LinkedIn fallback
            if email:
                channel = "email"
                contact = email
            elif linkedin:
                channel = "linkedin"
                contact = linkedin
            else:
                channel = "none"
                contact = ""

            records.append({
                "name":          name,
                "website":       website,
                "score":         score,
                "channel":       channel,
                "contact":       contact,
                "email":         email,
                "linkedin":      linkedin,
                "subject":       subject,
                "draft":         body_text,
            })

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    log.info(f"Found {len(records)} Draft Ready prospects")
    return records


def main():
    parser = argparse.ArgumentParser(description="Export Draft Ready outreach from Notion")
    parser.add_argument("--out", default=f"send_list_{date.today()}.csv", help="Output CSV filename")
    args = parser.parse_args()

    token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("NOTION_DATABASE_ID")

    if not token or not db_id:
        log.error("NOTION_TOKEN or NOTION_DATABASE_ID not set in .env")
        return

    records = fetch_draft_ready(db_id, token)

    if not records:
        log.warning("No Draft Ready prospects found.")
        return

    # Split into email and LinkedIn lists
    email_records   = [r for r in records if r["channel"] == "email"]
    linkedin_records = [r for r in records if r["channel"] == "linkedin"]
    no_contact      = [r for r in records if r["channel"] == "none"]

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "website", "score", "channel",
            "contact", "email", "linkedin", "subject", "draft"
        ])
        writer.writeheader()
        writer.writerows(records)

    log.info(f"Exported to {out_path}")

    print(f"\n{'─'*60}")
    print(f"  Total Draft Ready:  {len(records)}")
    print(f"  → Email ready:      {len(email_records)}")
    print(f"  → LinkedIn only:    {len(linkedin_records)}")
    print(f"  → No contact info:  {len(no_contact)}")
    print(f"{'─'*60}")
    print(f"  File: {out_path}\n")

    if no_contact:
        print("Prospects with no contact info (manual research needed):")
        for r in no_contact:
            print(f"  - {r['name']} ({r['website']})")
        print()


if __name__ == "__main__":
    main()
