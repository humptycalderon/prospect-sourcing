"""
Prospect Sourcing — AI companies needing RLHF / model evaluation data.

Usage:
  python main.py                        # run all sources, write prospects.csv
  python main.py --no-hn                # skip Hacker News
  python main.py --no-enrich            # skip Hunter.io enrichment
  python main.py --no-notion            # skip Notion push
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
from config import GITHUB_QUERIES, HN_QUERIES, MIN_SCORE_THRESHOLD, DESCRIPTION_KEYWORDS, INTENT_KEYWORDS
from sources import github_source, hn_source, producthunt_source
from enrichment import hunter_enricher, notion_push
from scoring import filter_and_rank
from outreach import personalizer, notion_outreach


def _load_overrides():
    """Merge icp_overrides.json into config at runtime. Returns (github_queries, hn_queries)."""
    import json
    override_path = os.path.join(os.path.dirname(__file__), "icp_overrides.json")
    if not os.path.exists(override_path):
        return list(GITHUB_QUERIES), list(HN_QUERIES)

    try:
        with open(override_path, encoding="utf-8") as f:
            ov = json.load(f)
    except Exception as e:
        log.warning(f"Could not load icp_overrides.json: {e} — using base config")
        return list(GITHUB_QUERIES), list(HN_QUERIES)

    gh_queries = list(GITHUB_QUERIES) + [q for q in ov.get("extra_github_queries", []) if q not in GITHUB_QUERIES]
    hn_queries = list(HN_QUERIES) + [q for q in ov.get("extra_hn_queries", []) if q not in HN_QUERIES]

    extra_kw = ov.get("extra_description_keywords", {})
    if extra_kw:
        DESCRIPTION_KEYWORDS.update(extra_kw)
        log.info(f"Overrides: added {len(extra_kw)} description keywords")

    extra_intent = ov.get("extra_intent_keywords", {})
    if extra_intent:
        INTENT_KEYWORDS.update(extra_intent)
        log.info(f"Overrides: added {len(extra_intent)} intent keywords")

    if ov.get("extra_github_queries"):
        log.info(f"Overrides: added {len(ov['extra_github_queries'])} GitHub queries")
    if ov.get("extra_hn_queries"):
        log.info(f"Overrides: added {len(ov['extra_hn_queries'])} HN queries")
    if ov.get("_update_reason"):
        log.info(f"Overrides last updated: {ov.get('_last_updated')} — {ov['_update_reason']}")

    return gh_queries, hn_queries

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
    parser.add_argument("--no-ph", action="store_true", help="Skip Product Hunt source")
    parser.add_argument("--no-enrich", action="store_true", help="Skip Hunter.io enrichment")
    parser.add_argument("--no-notion", action="store_true", help="Skip Notion CRM push")
    parser.add_argument("--no-outreach", action="store_true", help="Skip outreach draft generation")
    parser.add_argument("--out", default=f"prospects_{date.today()}.csv", help="Output CSV path")
    parser.add_argument("--dedupe", default=None, help="Path to existing CSV; skip matching logins")
    args = parser.parse_args()

    existing_logins = load_existing_logins(args.dedupe)
    if existing_logins:
        log.info(f"Deduplication: loaded {len(existing_logins)} existing logins from {args.dedupe}")

    github_queries, hn_queries = _load_overrides()

    all_prospects = []

    # --- GitHub ---
    if not args.no_github:
        gh_prospects = github_source.run(github_queries, max_per_query=30)
        all_prospects.extend(gh_prospects)
        log.info(f"GitHub: {len(gh_prospects)} prospects collected")
    else:
        log.info("GitHub: skipped")

    # --- Hacker News ---
    if not args.no_hn:
        hn_prospects = hn_source.run(hn_queries, min_points=5, max_per_query=20)
        all_prospects.extend(hn_prospects)
        log.info(f"HN: {len(hn_prospects)} prospects collected")
    else:
        log.info("HN: skipped")

    # --- Product Hunt ---
    if not args.no_ph:
        ph_prospects = producthunt_source.run(days_back=30, max_results=50)
        all_prospects.extend(ph_prospects)
        log.info(f"Product Hunt: {len(ph_prospects)} prospects collected")
    else:
        log.info("Product Hunt: skipped")

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

    # --- Notion CRM push ---
    if not args.no_notion:
        notion_db_id = os.getenv("NOTION_DATABASE_ID", "35acd830bd3580d7aabffaae480073c4")
        pushed, skipped = notion_push.push(ranked, db_id=notion_db_id)
        print(f"Notion: {pushed} new prospects pushed, {skipped} contacts updated")
    else:
        log.info("Notion push: skipped")

    # --- Outreach draft generation ---
    if not args.no_outreach and not args.no_notion:
        import glob
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # Load latest digest for positioning context
        digest_files = sorted(glob.glob(os.path.join(base_dir, "digest_*.md")), reverse=True)
        digest_context = ""
        if digest_files:
            with open(digest_files[0], encoding="utf-8") as f:
                digest_context = f.read()
            log.info(f"Outreach: loaded digest context from {digest_files[0]}")

        # Generate drafts for top prospects without existing drafts (score >= 50)
        top = [p for p in ranked if p.get("score", 0) >= 50][:20]
        if top:
            log.info(f"Outreach: generating drafts for {len(top)} prospects …")
            results = personalizer.generate_batch(top, digest_context=digest_context)
            succeeded = sum(1 for _, d in results if d)
            log.info(f"Outreach: {succeeded}/{len(top)} drafts generated")
            notion_outreach.push_drafts(results)
        else:
            log.info("Outreach: no prospects above score 50 — skipping draft generation")
    elif args.no_outreach:
        log.info("Outreach draft generation: skipped")

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
