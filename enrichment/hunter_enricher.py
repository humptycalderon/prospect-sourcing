"""
Hunter.io enrichment: given a company domain, find decision-maker contacts.

Targets titles relevant to RLHF/data procurement:
  - Head/VP/Director of AI, ML, Research, Data
  - CTO, CPO, CEO (for smaller orgs)
  - ML Engineer, Research Scientist (for outreach at practitioner level)
"""

import os
import time
import logging
import requests
from urllib.parse import urlparse

log = logging.getLogger(__name__)

HUNTER_API = "https://api.hunter.io/v2"

TARGET_TITLE_KEYWORDS = [
    "head of ai", "head of ml", "head of research", "head of data",
    "vp of ai", "vp ml", "vp research", "vp data",
    "director of ai", "director ml", "director research", "director data",
    "chief ai", "chief data", "chief technology", "chief product",
    "cto", "cpo", "ceo",
    "ml research", "research scientist", "machine learning engineer",
    "ai engineer", "data scientist", "rlhf", "model training",
]


def _clean_domain(website):
    """Extract bare domain from a URL or return as-is."""
    if not website:
        return ""
    try:
        parsed = urlparse(website if "://" in website else f"https://{website}")
        return parsed.netloc.lower().replace("www.", "")
    except Exception:
        return website.lower().replace("www.", "")


def _is_target_title(title):
    if not title:
        return False
    title_lower = title.lower()
    return any(kw in title_lower for kw in TARGET_TITLE_KEYWORDS)


def domain_search(domain, api_key, limit=10):
    """
    Search Hunter.io for contacts at a given domain.
    Returns list of contact dicts.
    """
    params = {
        "domain": domain,
        "api_key": api_key,
        "limit": limit,
        "type": "personal",  # prefer personal over generic emails
    }
    try:
        resp = requests.get(f"{HUNTER_API}/domain-search", params=params, timeout=12)
        if resp.status_code == 401:
            log.error("Hunter.io: invalid API key")
            return []
        if resp.status_code == 429:
            log.warning("Hunter.io: rate limited, sleeping 60s")
            time.sleep(60)
            return []
        if resp.status_code != 200:
            log.debug(f"Hunter.io {resp.status_code} for {domain}")
            return []

        data = resp.json().get("data", {})
        emails = data.get("emails", [])
        contacts = []
        for e in emails:
            first = e.get("first_name") or ""
            last = e.get("last_name") or ""
            title = e.get("position") or ""
            contacts.append({
                "contact_name": f"{first} {last}".strip(),
                "contact_title": title,
                "contact_email": e.get("value") or "",
                "contact_linkedin": e.get("linkedin") or "",
                "is_target_title": _is_target_title(title),
                "email_confidence": e.get("confidence") or 0,
            })
        return contacts

    except Exception as e:
        log.warning(f"Hunter.io error for {domain}: {e}")
        return []


def enrich(prospects):
    """
    Add contact info to each prospect dict that has a website domain.
    Modifies prospects in place and returns them.
    """
    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key:
        log.warning("HUNTER_API_KEY not set — skipping contact enrichment")
        for p in prospects:
            p.update({
                "contact_name": "",
                "contact_title": "",
                "contact_email": "",
                "contact_linkedin": "",
                "is_target_title": False,
                "email_confidence": 0,
            })
        return prospects

    log.info(f"Hunter.io: enriching {len(prospects)} prospects …")
    for p in prospects:
        domain = _clean_domain(p.get("website") or "")
        if not domain or "github.com" in domain:
            p.update({
                "contact_name": p.get("email") or "",
                "contact_title": "",
                "contact_email": p.get("email") or "",
                "contact_linkedin": "",
                "is_target_title": False,
                "email_confidence": 0,
            })
            continue

        contacts = domain_search(domain, api_key)
        # Prefer target-title contacts; fall back to first result
        target = next((c for c in contacts if c["is_target_title"]), None)
        best = target or (contacts[0] if contacts else None)

        if best:
            p.update(best)
        else:
            p.update({
                "contact_name": "",
                "contact_title": "",
                "contact_email": "",
                "contact_linkedin": "",
                "is_target_title": False,
                "email_confidence": 0,
            })

        log.debug(f"  {domain}: {'found' if best else 'no contacts'}")
        time.sleep(0.5)  # Hunter.io free tier: ~100ms minimum between requests

    return prospects
