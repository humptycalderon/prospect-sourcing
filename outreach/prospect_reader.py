"""
Reads top-scored prospects from the latest CSV export.
Prioritises prospects with contact emails; falls back to LinkedIn.
"""

import os
import glob
import csv
import logging

log = logging.getLogger(__name__)

DEFAULT_MIN_SCORE = 50
DEFAULT_TOP_N = 20


def _latest_csv(directory="."):
    pattern = os.path.join(directory, "prospects_*.csv")
    files = sorted(glob.glob(pattern), reverse=True)
    return files[0] if files else None


def load(directory=".", min_score=DEFAULT_MIN_SCORE, top_n=DEFAULT_TOP_N):
    """
    Return the top N prospects above min_score from the latest CSV.
    Sorts by score descending. Includes all prospects regardless of
    whether contact info is available — personalizer handles both cases.
    """
    path = _latest_csv(directory)
    if not path:
        log.error(f"No prospects_*.csv found in {directory}")
        return []

    log.info(f"Reading prospects from {path}")
    prospects = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                score = int(float(row.get("score", 0)))
            except (ValueError, TypeError):
                score = 0
            if score >= min_score:
                row["score"] = score
                prospects.append(row)

    prospects.sort(key=lambda p: p["score"], reverse=True)
    selected = prospects[:top_n]
    log.info(
        f"Loaded {len(selected)} prospects (score >= {min_score}, top {top_n}) "
        f"from {len(prospects)} above threshold"
    )
    return selected
