"""
Hacker News source: surfaces companies/people actively discussing RLHF,
model evaluation, and human feedback data pain points.

Uses the public Algolia HN Search API (no key required).
"""

import time
import logging
import requests
from urllib.parse import urlparse

log = logging.getLogger(__name__)

ALGOLIA_API = "https://hn.algolia.com/api/v1/search"


def _extract_domain(url):
    if not url:
        return ""
    try:
        parsed = urlparse(url if url.startswith("http") else f"https://{url}")
        domain = parsed.netloc.lower().replace("www.", "")
        return domain
    except Exception:
        return ""


def search_hn(query, tags="story", min_points=5, max_results=20):
    """Query Algolia HN API for posts matching a query."""
    params = {
        "query": query,
        "tags": tags,
        "hitsPerPage": max_results,
        "numericFilters": f"points>={min_points}",
    }
    try:
        resp = requests.get(ALGOLIA_API, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("hits", [])
    except Exception as e:
        log.warning(f"HN search failed for '{query}': {e}")
        return []


def get_user_profile(username):
    """Fetch HN user profile to extract company/URL info."""
    try:
        resp = requests.get(
            f"https://hn.algolia.com/api/v1/users/{username}", timeout=8
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def run(queries, min_points=5, max_per_query=20):
    """
    Search HN for each query. For each result, attempt to extract
    a company domain from the post URL or the author's profile.

    Returns list of prospect dicts.
    """
    seen_domains = set()
    seen_authors = set()
    prospects = []

    log.info(f"HN: running {len(queries)} queries …")
    for query in queries:
        log.info(f"  Searching HN: '{query}'")
        hits = search_hn(query, min_points=min_points, max_results=max_per_query)
        log.info(f"    → {len(hits)} hits")

        for hit in hits:
            author = hit.get("author", "")
            post_url = hit.get("url") or ""
            title = hit.get("title") or ""
            story_text = hit.get("story_text") or ""
            points = hit.get("points") or 0
            post_domain = _extract_domain(post_url)

            # Skip personal blogs and major news domains
            noise_domains = {
                "github.com", "arxiv.org", "medium.com", "substack.com",
                "youtube.com", "twitter.com", "x.com", "reddit.com",
                "huggingface.co", "openai.com", "anthropic.com",
            }
            if post_domain in noise_domains:
                post_domain = ""

            # Try to get company from author profile if no domain yet
            company_domain = post_domain
            company_name = ""
            if author and author not in seen_authors:
                seen_authors.add(author)
                profile = get_user_profile(author)
                about = profile.get("about") or ""
                # Many HN users put their company URL in about
                # Simple heuristic: look for a domain-like string
                import re
                url_match = re.search(
                    r'https?://([a-zA-Z0-9\-]+\.[a-zA-Z]{2,})', about
                )
                if url_match and not company_domain:
                    company_domain = _extract_domain(url_match.group(0))
                time.sleep(0.2)

            if not company_domain:
                # Still record as an author lead even without domain
                key = f"hn_author:{author}"
            else:
                key = company_domain

            if key in seen_domains:
                continue
            seen_domains.add(key)

            prospects.append({
                "login": key,
                "name": company_name or company_domain or author,
                "type": "HN_User",
                "description": f"[HN] {title}",
                "website": f"https://{company_domain}" if company_domain else "",
                "location": "",
                "public_repos": 0,
                "followers": 0,
                "github_url": "",
                "email": "",
                "twitter": "",
                "topics": [],
                "days_since_last_push": 0,
                "max_repo_stars": 0,
                "repo_descriptions": story_text[:300],
                "source": "hackernews",
                "query_count": 1,
                "hn_points": points,
                "hn_author": author,
                "hn_title": title,
                "hn_url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
            })
        time.sleep(1.0)

    log.info(f"HN: returning {len(prospects)} prospects")
    return prospects
