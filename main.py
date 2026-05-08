"""
Prospect Sourcing — AI companies needing RLHF / model evaluation data.

Usage:
  python main.py                        # run all sources, write prospects.csv
  python main.py --no-hn                # skip Hacker News
  python main.py --no-enrich            # skip Hunter.io enrichment
  python main.py --out results.csv      # custom output file
  python main.py --dedupe existing.csv  # skip orgs already in a CSV
"""

import os
import sys
import csv
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

# Local imports (after dotenv so env is ready)
from config import GITHUB_QUERIES, HN_QUERIES, MIN_SCORE_THRESHOLD
from sources import github_source, hn_source
from enrichment import hunter_enricher
from scoring import filter_and_rank

OUTPUT_COLUMNS = [
    "score",
    "name",
    "website",
    "source",
    "contact_name",
    "contact_title",
    "contact_email",
    "contact_linkedin",
    "email_confidence",
    "description",
    "topics",
    "location",
    "public_repos",
    "max_repo_stars",
    "days_since_last_push",
    "github_url",
    "twitter",
    "hn_title",
    "hn_url",
    "hn_author",
    "query_count",
    "score_reasons",
    "login",
]


def load_existing_logins(path):
    """Return set of 'login' values from an existing CSV to skip dupes."""
    if not path or not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row.get("login", "") for row in reader if row.get("login")}


def write_csv(prospects, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=OUTPUT_COLUMNS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for p in prospects:
            # Serialize lists to pipe-separated strings for CSV
            row = dict(p)
            if isinstance(row.get("topics"), list):
                row["topics"] = " | ".join(row["topics"])
            writer.writerow(row)
    log.info(f"Wrote {len(prospects)} prospects to {path}")


def main():
    parser = argparse.ArgumentParser(description="Prospect sourcing for AI RLHF buyers")
    parser.add_argument("--no-github", action="store_true", help="Skip GitHub source")
    parser.add_argument("--no-hn", action="store_true", help="Skip Hacker News source")
    parser.add_argument("--no-enrich", action="store_true", help="Skip Hunter.io enrichment")
    parser.add_argument("--out", default=f"prospects_{date.today()}.csv", help="Output CSV path")
    parser.add_argument("--dedupe", default=None, help="Path to existing CSV; skip matching logins")
    args = parser.parse_args()

    existing_logins = load_existing_logins(args.dedupe)
    if existing_logins:
        log.info(f"Deduplication: loaded {len(existing_logins)} existing logins from {args.dedupe}")

    all_prospects = []

    # --- GitHub ---
    if not args.no_github:
        gh_prospects = github_source.run(GITHUB_QUERIES, max_per_query=30)
        all_prospects.extend(gh_prospects)
        log.info(f"GitHub: {len(gh_prospects)} prospects collected")
    else:
        log.info("GitHub: skipped")

    # --- Hacker News ---
    if not args.no_hn:
        hn_prospects = hn_source.run(HN_QUERIES, min_points=5, max_per_query=20)
        all_prospects.extend(hn_prospects)
        log.info(f"HN: {len(hn_prospects)} prospects collected")
    else:
        log.info("HN: skipped")

    if not all_prospects:
        log.warning("No prospects collected. Check your API keys and network.")
        sys.exit(0)

    # --- Deduplication ---
    before = len(all_prospects)
    seen = set()
    deduped = []
    for p in all_prospects:
        key = p.get("login") or p.get("website") or p.get("name")
        if key and key not in seen and key not in existing_logins:
            seen.add(key)
            deduped.append(p)
    log.info(f"Deduplication: {before} → {len(deduped)} unique prospects")

    # --- Score and filter ---
    ranked = filter_and_rank(deduped)

    # --- Enrich with Hunter.io ---
    if not args.no_enrich:
        ranked = hunter_enricher.enrich(ranked)
    else:
        log.info("Enrichment: skipped")
        for p in ranked:
            p.update({
                "contact_name": "",
                "contact_title": "",
                "contact_email": "",
                "contact_linkedin": "",
                "is_target_title": False,
                "email_confidence": 0,
            })

    # --- Output ---
    write_csv(ranked, args.out)

    # Print summary table to terminal
    print(f"\n{'─'*80}")
    print(f"{'SCORE':>5}  {'NAME':<30}  {'CONTACT':<25}  {'EMAIL'}")
    print(f"{'─'*80}")
    for p in ranked[:20]:
        print(
            f"{p['score']:>5}  "
            f"{str(p.get('name',''))[:30]:<30}  "
            f"{str(p.get('contact_name',''))[:25]:<25}  "
            f"{p.get('contact_email','')}"
        )
    if len(ranked) > 20:
        print(f"  … and {len(ranked) - 20} more in {args.out}")
    print(f"{'─'*80}\n")
    print(f"Full results: {args.out}")


if __name__ == "__main__":
    main()
