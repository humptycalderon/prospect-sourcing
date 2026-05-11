"""
Outreach Personalization Pipeline — generates cold email drafts for top prospects.

Reads scored prospects from the latest CSV, generates personalised outreach
using Claude Opus 4.6, saves drafts to CSV, and updates Notion CRM records.

Usage:
  python run_outreach.py                   # top 20 prospects, score >= 50
  python run_outreach.py --top 10          # limit to top 10
  python run_outreach.py --min-score 70    # higher quality bar
  python run_outreach.py --no-notion       # skip Notion update
  python run_outreach.py --out drafts.csv  # custom output file
"""

import os
import csv
import sys
import glob
import logging
import argparse
from datetime import date
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

from outreach import prospect_reader, personalizer, notion_outreach


def _load_digest_context(directory="."):
    """Load the latest market intel digest for positioning context."""
    pattern = os.path.join(directory, "digest_*.md")
    files = sorted(glob.glob(pattern), reverse=True)
    if not files:
        log.info("No digest file found — outreach will use default positioning.")
        return ""
    with open(files[0], encoding="utf-8") as f:
        content = f.read()
    log.info(f"Loaded digest context from {files[0]}")
    return content


def _save_csv(results, path):
    """Save outreach drafts to CSV."""
    rows = []
    for prospect, draft in results:
        if not draft:
            continue
        rows.append({
            "name":            prospect.get("name") or prospect.get("login", ""),
            "website":         prospect.get("website", ""),
            "score":           prospect.get("score", ""),
            "contact_name":    prospect.get("contact_name", ""),
            "contact_email":   prospect.get("contact_email", ""),
            "contact_linkedin": prospect.get("contact_linkedin", ""),
            "subject":         draft.get("subject", ""),
            "body":            draft.get("body", ""),
        })

    if not rows:
        log.warning("No drafts to save.")
        return

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    log.info(f"Outreach drafts saved to {path} ({len(rows)} records)")


def main():
    parser = argparse.ArgumentParser(description="Generate personalised outreach drafts")
    parser.add_argument("--top", type=int, default=20, help="Max prospects to process (default: 20)")
    parser.add_argument("--min-score", type=int, default=50, help="Minimum ICP score (default: 50)")
    parser.add_argument("--no-notion", action="store_true", help="Skip Notion update")
    parser.add_argument("--out", default=f"outreach_{date.today()}.csv", help="Output CSV file")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # --- Load prospects ---
    prospects = prospect_reader.load(
        directory=base_dir,
        min_score=args.min_score,
        top_n=args.top,
    )
    if not prospects:
        log.error("No prospects found. Run main.py first to source and score prospects.")
        sys.exit(1)

    # --- Load digest context for positioning ---
    digest_context = _load_digest_context(base_dir)

    # --- Generate outreach drafts ---
    log.info(f"Generating outreach for {len(prospects)} prospects …")
    results = personalizer.generate_batch(prospects, digest_context=digest_context)

    succeeded = sum(1 for _, d in results if d)
    log.info(f"Generated {succeeded}/{len(prospects)} drafts successfully")

    # --- Print previews ---
    print("\n" + "=" * 70)
    for prospect, draft in results:
        if not draft:
            continue
        name = prospect.get("name") or prospect.get("login", "unknown")
        print(f"\n[Score: {prospect.get('score')}] {name}")
        print(f"Subject: {draft.get('subject', '')}")
        print("-" * 40)
        print(draft.get("body", ""))
        print("=" * 70)

    # --- Save CSV ---
    out_path = os.path.join(base_dir, args.out)
    _save_csv(results, out_path)

    # --- Update Notion ---
    if not args.no_notion:
        notion_outreach.push_drafts(results)
    else:
        log.info("Notion update: skipped")


if __name__ == "__main__":
    main()
