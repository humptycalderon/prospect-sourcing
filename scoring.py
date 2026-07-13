"""
ICP fit scoring for RLHF / model evaluation data buyers.

Score is 0–100. Anything >= MIN_SCORE_THRESHOLD in config.py is kept.
"""

import logging
from config import (
    HIGH_SIGNAL_TOPICS,
    SUPPORTING_TOPICS,
    DESCRIPTION_KEYWORDS,
    INTENT_KEYWORDS,
    SCORE_WEIGHTS,
    MAX_SCORE,
    MIN_SCORE_THRESHOLD,
)

log = logging.getLogger(__name__)


def _keyword_score(text):
    """Sum keyword weights for all matches in text."""
    if not text:
        return 0
    text_lower = text.lower()
    total = 0
    for kw, weight in DESCRIPTION_KEYWORDS.items():
        if kw in text_lower:
            total += weight
    return total


def _intent_score(text):
    """
    Score production-use intent keywords in repo descriptions.
    Returns (pts, matched_keywords). Capped at 10 pts total.
    """
    if not text:
        return 0, []
    text_lower = text.lower()
    matched = []
    pts = 0
    for kw, weight in INTENT_KEYWORDS.items():
        if kw in text_lower:
            matched.append(kw)
            pts += weight
    return min(pts, 10), matched


def score_prospect(p):
    """
    Compute a 0–100 ICP fit score for a prospect dict.
    Returns the dict with 'score' and 'score_reasons' added.
    """
    raw = 0
    reasons = []

    topics = set(p.get("topics") or [])

    # High-signal topic matches (RLHF, alignment, reward model, etc.)
    hs_matches = topics & HIGH_SIGNAL_TOPICS
    if hs_matches:
        pts = SCORE_WEIGHTS["high_signal_topic_match"] * len(hs_matches)
        raw += pts
        reasons.append(f"high-signal topics ({', '.join(sorted(hs_matches))}): +{pts}")

    # Supporting topic matches
    sup_matches = topics & SUPPORTING_TOPICS
    if sup_matches:
        pts = SCORE_WEIGHTS["supporting_topic_match"] * len(sup_matches)
        raw += pts
        reasons.append(f"supporting topics ({', '.join(sorted(sup_matches))}): +{pts}")

    # Keyword matches in description + repo descriptions
    full_text = " ".join([
        p.get("description") or "",
        p.get("repo_descriptions") or "",
        p.get("hn_title") or "",
    ])
    kw_pts = _keyword_score(full_text)
    if kw_pts:
        raw += kw_pts
        reasons.append(f"keyword matches: +{kw_pts}")

    # Recency: last repo push within 90 days
    days = p.get("days_since_last_push") or 9999
    if days <= 90:
        pts = SCORE_WEIGHTS["recent_activity"]
        raw += pts
        reasons.append(f"active recently ({days}d ago): +{pts}")

    # Has a real website (not just github.com)
    website = p.get("website") or ""
    if website and "github.com" not in website:
        pts = SCORE_WEIGHTS["has_website"]
        raw += pts
        reasons.append(f"has company website: +{pts}")

    # Is a GitHub org (not personal account)
    if p.get("type") == "Organization":
        pts = SCORE_WEIGHTS["is_org"]
        raw += pts
        reasons.append(f"GitHub org: +{pts}")

    # Multiple repos signals a real company effort
    if p.get("public_repos", 0) > 3:
        pts = SCORE_WEIGHTS["multiple_repos"]
        raw += pts
        reasons.append(f"multiple repos ({p['public_repos']}): +{pts}")

    # Found on HN discussing the pain point directly
    if p.get("source") == "hackernews":
        pts = SCORE_WEIGHTS["hn_source"]
        raw += pts
        reasons.append(f"HN pain-point signal: +{pts}")

    # Matched multiple search queries (stronger signal)
    qc = p.get("query_count", 1)
    if qc > 1:
        bonus = min(qc * 3, 15)
        raw += bonus
        reasons.append(f"matched {qc} queries: +{bonus}")

    # Intent signals: production-use keywords in repo descriptions
    intent_pts, intent_kws = _intent_score(
        " ".join([p.get("description") or "", p.get("repo_descriptions") or ""])
    )
    if intent_pts:
        raw += intent_pts
        reasons.append(f"intent keywords ({', '.join(intent_kws)}): +{intent_pts}")

    # Recency penalty: only applies to GitHub prospects with a real push date.
    # HN and Product Hunt prospects have no push date; 9999 is the "unknown" sentinel.
    if days < 9999:
        if days > 365:
            raw = round(raw * 0.50)
            reasons.append(f"stale repo ({days}d): score halved")
        elif days > 180:
            raw = round(raw * 0.70)
            reasons.append(f"stale repo ({days}d): -30%")
        elif days > 90:
            raw = round(raw * 0.85)
            reasons.append(f"aging repo ({days}d): -15%")

    # Normalize to 0–100
    score = min(round((raw / MAX_SCORE) * 100), 100)

    p["score"] = score
    p["score_reasons"] = "; ".join(reasons)
    return p


def filter_and_rank(prospects):
    """Score all prospects, filter below threshold, sort descending."""
    scored = [score_prospect(p) for p in prospects]
    kept = [p for p in scored if p["score"] >= MIN_SCORE_THRESHOLD]
    kept.sort(key=lambda x: x["score"], reverse=True)
    log.info(
        f"Scoring: {len(prospects)} total → {len(kept)} above threshold "
        f"(score >= {MIN_SCORE_THRESHOLD})"
    )
    return kept
