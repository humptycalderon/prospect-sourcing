"""
Product Hunt source: finds recently launched AI/ML products via Product Hunt's
public RSS feed. No API key required.
"""

import logging
import requests
import feedparser
import io
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

PH_FEED_URL = "https://www.producthunt.com/feed"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; prospect-sourcing-bot/1.0)"}

ICP_KEYWORDS = [
    "rlhf", "reinforcement learning", "reward model", "human feedback",
    "preference", "annotation", "labeling", "labelling", "evaluation",
    "evaluator", "benchmark", "fine-tun", "instruction tun", "alignment",
    "training data", "llm training", "model evaluation", "data quality",
    "language model", "foundation model", "generative ai", "llm", "ai model",
    "machine learning", "deep learning", "neural network",
]


def _matches_icp(title, summary):
    text = f"{title} {summary}".lower()
    return any(kw in text for kw in ICP_KEYWORDS)


def _matched_keywords(title, summary):
    text = f"{title} {summary}".lower()
    return [kw for kw in ICP_KEYWORDS if kw in text]


def _parse_date(entry):
    published = entry.get("published_parsed")
    if published:
        return datetime(*published[:6], tzinfo=timezone.utc)
    return None


def run(days_back=30, max_results=50):
    """
    Fetch recently launched AI/ML products from Product Hunt RSS feed.
    Returns a list of prospect dicts compatible with the sourcing pipeline.
    """
    log.info("Product Hunt: fetching RSS feed …")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    try:
        resp = requests.get(PH_FEED_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(io.BytesIO(resp.content))
    except Exception as e:
        log.warning(f"Product Hunt RSS fetch failed: {e}")
        return []

    prospects = []
    seen = set()

    for entry in feed.entries:
        pub_date = _parse_date(entry)
        if pub_date and pub_date < cutoff:
            continue

        title = entry.get("title", "")
        summary = entry.get("summary", "") or ""
        link = entry.get("link", "")

        if not _matches_icp(title, summary):
            continue

        key = link or title
        if key in seen:
            continue
        seen.add(key)

        matched = _matched_keywords(title, summary)

        prospects.append({
            "name":             title,
            "website":          link,
            "source":           "producthunt",
            "description":      summary[:500],
            "topics":           ["producthunt", "ai", "machine-learning"],
            "score_reasons":    ", ".join(matched),
            "login":            title.lower().replace(" ", "-")[:60],
            "contact_name":     "",
            "contact_email":    "",
            "contact_linkedin": "",
            "twitter":          "",
        })

        if len(prospects) >= max_results:
            break

    log.info(f"Product Hunt: {len(prospects)} ICP-matching prospects found")
    return prospects
