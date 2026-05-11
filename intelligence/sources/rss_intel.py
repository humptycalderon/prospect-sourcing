"""
RSS intelligence: monitors curated AI/ML newsletters and blogs
for coverage of RLHF, model evaluation, and human feedback data.
"""

import io
import time
import logging
import requests
import feedparser
from datetime import datetime, timedelta, timezone

# Reddit and some feeds block the default feedparser user agent
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; market-intel-bot/1.0)"}

log = logging.getLogger(__name__)

# Curated feeds relevant to AI training, alignment, and evaluation
FEEDS = [
    {
        "name": "Import AI (Jack Clark)",
        "url": "https://importai.substack.com/feed",
    },
    {
        "name": "The Gradient",
        "url": "https://thegradient.pub/rss/",
    },
    {
        "name": "Ahead of AI (Sebastian Raschka)",
        "url": "https://magazine.sebastianraschka.com/feed",
    },
    {
        "name": "ML Safety Newsletter",
        "url": "https://newsletter.mlsafety.org/feed",
    },
    {
        "name": "Interconnects (AI Research)",
        "url": "https://www.interconnects.ai/feed",
    },
    {
        "name": "The Batch (deeplearning.ai)",
        "url": "https://www.deeplearning.ai/the-batch/feed.xml",
    },
    {
        "name": "r/MachineLearning",
        "url": "https://www.reddit.com/r/MachineLearning/.rss",
    },
    {
        "name": "r/LanguageModelEval",
        "url": "https://www.reddit.com/r/LanguageModelEval/.rss",
    },
    {
        "name": "Latent Space Podcast",
        "url": "https://www.latent.space/feed",
    },
]

# Keywords to filter articles for relevance — broader net than before
RELEVANCE_KEYWORDS = [
    "rlhf", "reinforcement learning from human feedback",
    "human feedback", "preference data", "reward model",
    "model evaluation", "benchmark", "alignment",
    "fine-tun", "instruction tun", "data annotation",
    "human evaluator", "training data", "ai safety",
    "language model", "llm", "foundation model",
    "human label", "annotator", "data quality",
    "evaluation", "sft", "dpo", "ppo", "rlaif",
]


def _is_relevant(text):
    t = text.lower()
    return any(kw in t for kw in RELEVANCE_KEYWORDS)


def _parse_date(entry):
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def fetch(days_back=7):
    """
    Fetch recent relevant articles from curated RSS feeds.
    Returns list of article dicts.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    articles = []

    log.info(f"RSS intel: fetching {len(FEEDS)} feeds …")
    for feed_meta in FEEDS:
        name = feed_meta["name"]
        url = feed_meta["url"]
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            feed = feedparser.parse(io.BytesIO(resp.content))
            for entry in feed.entries:
                pub_date = _parse_date(entry)
                if pub_date < cutoff:
                    continue

                title = getattr(entry, "title", "") or ""
                summary = getattr(entry, "summary", "") or ""
                content_list = getattr(entry, "content", [])
                content_text = content_list[0].value if content_list else ""
                full_text = f"{title} {summary} {content_text}"

                if not _is_relevant(full_text):
                    continue

                articles.append({
                    "source": "rss",
                    "feed": name,
                    "title": title,
                    "text": summary[:600],
                    "url": getattr(entry, "link", ""),
                    "date": pub_date.strftime("%Y-%m-%d"),
                    "points": 0,
                    "author": name,
                    "query": "rss_feed",
                })
        except Exception as e:
            log.warning(f"RSS feed '{name}' failed: {e}")
        time.sleep(0.5)

    log.info(f"RSS intel: {len(articles)} relevant articles found")
    return articles
