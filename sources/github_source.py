"""
GitHub source: finds orgs and companies building RLHF / model evaluation tooling.

Strategy:
  1. Search repos by query string
  2. Collect the owning org/user for each repo
  3. Fetch org metadata (website, description, member count)
  4. Deduplicate by org login
"""

import os
import time
import logging
import requests
from datetime import datetime, timezone

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _headers():
    token = os.getenv("GITHUB_TOKEN")
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    else:
        log.warning("GITHUB_TOKEN not set — rate limited to 60 req/hour")
    return h


def _get(url, params=None, retries=3):
    for attempt in range(retries):
        resp = requests.get(url, headers=_headers(), params=params, timeout=15)
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - int(time.time()), 1)
            log.warning(f"Rate limited. Sleeping {wait}s …")
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            return resp.json()
        log.debug(f"GitHub {resp.status_code} for {url}")
        return None
    return None


def _days_since(iso_str):
    if not iso_str:
        return 9999
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days


def fetch_org_details(login, account_type):
    """Return enriched org/user record or None."""
    endpoint = "orgs" if account_type == "Organization" else "users"
    data = _get(f"{GITHUB_API}/{endpoint}/{login}")
    if not data:
        return None
    return {
        "login": data.get("login"),
        "name": data.get("name") or data.get("login"),
        "type": account_type,
        "description": data.get("description") or data.get("bio") or "",
        "website": data.get("blog") or data.get("html_url", ""),
        "location": data.get("location") or "",
        "public_repos": data.get("public_repos", 0),
        "followers": data.get("followers", 0),
        "github_url": data.get("html_url"),
        "email": data.get("email") or "",
        "twitter": data.get("twitter_username") or "",
    }


def search_repos(query, max_results=30):
    """Search GitHub repos and return list of repo records."""
    params = {
        "q": query,
        "sort": "updated",
        "order": "desc",
        "per_page": min(max_results, 30),
    }
    data = _get(f"{GITHUB_API}/search/repositories", params=params)
    if not data:
        return []

    repos = []
    for item in data.get("items", []):
        repos.append({
            "repo_name": item.get("full_name"),
            "repo_description": item.get("description") or "",
            "topics": item.get("topics", []),
            "stars": item.get("stargazers_count", 0),
            "last_pushed": item.get("pushed_at"),
            "days_since_push": _days_since(item.get("pushed_at")),
            "owner_login": item["owner"]["login"],
            "owner_type": item["owner"]["type"],  # "Organization" | "User"
        })
        time.sleep(0.1)  # stay well under rate limits

    return repos


def run(queries, max_per_query=30):
    """
    Run all queries, collect unique orgs, enrich with org details.

    Returns list of dicts keyed by org login.
    """
    seen_logins = set()
    repo_map = {}  # login -> list of repos (for signal aggregation)

    log.info(f"GitHub: running {len(queries)} queries …")
    for query in queries:
        log.info(f"  Searching: '{query}'")
        repos = search_repos(query, max_results=max_per_query)
        log.info(f"    → {len(repos)} repos")
        for repo in repos:
            login = repo["owner_login"]
            repo_map.setdefault(login, []).append(repo)
            seen_logins.add(login)
        time.sleep(1.5)  # between search queries

    log.info(f"GitHub: {len(seen_logins)} unique orgs/users found. Fetching details …")
    prospects = []
    for login in seen_logins:
        repos = repo_map[login]
        # Use owner_type from first repo seen
        account_type = repos[0]["owner_type"]
        details = fetch_org_details(login, account_type)
        if not details:
            continue

        # Aggregate signals across all repos found for this org
        all_topics = set()
        best_repo_days = 9999
        best_repo_stars = 0
        repo_descriptions = []
        for r in repos:
            all_topics.update(r["topics"])
            best_repo_days = min(best_repo_days, r["days_since_push"])
            best_repo_stars = max(best_repo_stars, r["stars"])
            if r["repo_description"]:
                repo_descriptions.append(r["repo_description"])

        details["topics"] = sorted(all_topics)
        details["days_since_last_push"] = best_repo_days
        details["max_repo_stars"] = best_repo_stars
        details["repo_descriptions"] = " | ".join(repo_descriptions)
        details["source"] = "github"
        details["query_count"] = len(repos)  # how many queries matched this org
        prospects.append(details)
        time.sleep(0.3)

    log.info(f"GitHub: returning {len(prospects)} enriched prospects")
    return prospects
