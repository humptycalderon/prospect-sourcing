"""
HN intelligence: surfaces trending discussions about RLHF, model evaluation,
and human feedback data from Hacker News over the past 7 days.
"""

import time
import logging
import requests
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

ALGOLIA_API = "https://hn.algolia.com/api/v1/search"

QUERIES = [
    "RLHF human feedback",
    "model evaluation benchmark",
    "AI training data quality",
    "reinforcement learning human feedback",
    "LLM fine-tuning data",
    "AI alignment data",
    "reward model training",
    "human preference data",
    "AI data annotation quality",
    "model benchmarking evaluation",
]

def _days_ago(n):
    return int((datetime.now(timezone.utc) - timedelta(days=n)).timestamp())


def fetch(days_back=14, min_points=2, max_per_query=15):
    """
    Fetch recent HN stories and comments discussing AI data pain points.
    Returns list of dicts with title, text, url, points, author, date.
    """
    seen_ids = set()
    items = []
    cutoff = _days_ago(days_back)

    log.info(f"HN intel: fetching last {days_back} days across {len(QUERIES)} queries …")
    for query in QUERIES:
        for tag in ["story", "comment"]:
            try:
                resp = requests.get(ALGOLIA_API, params={
                    "query": query,
                    "tags": tag,
                    "hitsPerPage": max_per_query,
                    "numericFilters": f"points>={min_points},created_at_i>{cutoff}",
                }, timeout=10)
                resp.raise_for_status()
                hits = resp.json().get("hits", [])
                for h in hits:
                    obj_id = h.get("objectID")
                    if obj_id in seen_ids:
                        continue
                    seen_ids.add(obj_id)
                    items.append({
                        "source": "hackernews",
                        "type": tag,
                        "title": h.get("title") or h.get("comment_text", "")[:100],
                        "text": (h.get("story_text") or h.get("comment_text") or "")[:500],
                        "url": h.get("url") or f"https://news.ycombinator.com/item?id={obj_id}",
                        "points": h.get("points") or 0,
                        "author": h.get("author") or "",
                        "date": h.get("created_at", ""),
                        "query": query,
                    })
            except Exception as e:
                log.warning(f"HN query '{query}' ({tag}) failed: {e}")
            time.sleep(0.3)

    log.info(f"HN intel: {len(items)} unique items found")
    return items
