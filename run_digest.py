"""
Market Intelligence Digest — daily briefing for AI RLHF data buyers.

Usage:
  python run_digest.py                  # full run: markdown + Notion + Telegram
  python run_digest.py --no-notion      # skip Notion
  python run_digest.py --no-telegram    # skip Telegram
  python run_digest.py --no-arxiv       # skip arXiv (faster)
  python run_digest.py --days 3         # look back 3 days instead of 7
  python run_digest.py --out brief.md   # custom output file
"""

import os
import sys
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

from intelligence.sources import hn_intel, arxiv_intel, rss_intel
from intelligence import synthesizer, notion_digest, telegram_digest


def main():
    parser = argparse.ArgumentParser(description="Generate market intelligence digest")
    parser.add_argument("--days", type=int, default=7, help="Days to look back (default: 7)")
    parser.add_argument("--no-arxiv", action="store_true", help="Skip arXiv source")
    parser.add_argument("--no-rss", action="store_true", help="Skip RSS feeds")
    parser.add_argument("--no-notion", action="store_true", help="Skip Notion publish")
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram delivery")
    parser.add_argument("--out", default=f"digest_{date.today()}.md", help="Output markdown file")
    args = parser.parse_args()

    all_items = []

    # --- Hacker News ---
    log.info("Collecting HN signals …")
    hn_items = hn_intel.fetch(days_back=args.days)
    all_items.extend(hn_items)

    # --- arXiv ---
    if not args.no_arxiv:
        log.info("Collecting arXiv signals …")
        arxiv_items = arxiv_intel.fetch(days_back=args.days)
        all_items.extend(arxiv_items)
    else:
        log.info("arXiv: skipped")

    # --- RSS ---
    if not args.no_rss:
        log.info("Collecting RSS signals …")
        rss_items = rss_intel.fetch(days_back=args.days)
        all_items.extend(rss_items)
    else:
        log.info("RSS: skipped")

    log.info(f"Total signals: {len(all_items)} items collected")

    if not all_items:
        log.warning("No signals found. Check your network or expand the date range with --days.")
        sys.exit(0)

    # --- Synthesize with Claude ---
    briefing = synthesizer.synthesize(all_items)
    if not briefing:
        log.error("Synthesis failed. Check ANTHROPIC_API_KEY.")
        sys.exit(1)

    # --- Save markdown ---
    today = date.today().isoformat()
    header = f"# Market Intelligence Briefing — {today}\n\n"
    full_content = header + briefing

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(full_content)
    log.info(f"Digest saved to {args.out}")

    # --- Print to terminal ---
    print("\n" + "="*70)
    print(full_content)
    print("="*70 + "\n")

    # --- Notion ---
    if not args.no_notion:
        page_url = notion_digest.push(briefing, run_date=today)
        if page_url:
            print(f"Notion page: {page_url}")
    else:
        log.info("Notion publish: skipped")

    # --- Telegram ---
    if not args.no_telegram:
        telegram_digest.push(briefing, run_date=today)
    else:
        log.info("Telegram delivery: skipped")


if __name__ == "__main__":
    main()
