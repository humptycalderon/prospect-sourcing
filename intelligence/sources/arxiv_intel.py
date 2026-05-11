"""
arXiv intelligence: fetches recent papers on RLHF, alignment,
model evaluation, and human preference data.
Uses the arXiv Atom API (no key required).
"""

import time
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

log = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"

# Single consolidated query using abs: (abstract) for precision
# OR logic gives broad recall; abs: prevents matching unrelated papers
ARXIV_QUERY = (
    'abs:RLHF OR abs:"reward model" OR abs:"human feedback" '
    'OR abs:"preference data" OR abs:"reinforcement learning from human feedback" '
    'OR abs:"model alignment" OR abs:"preference optimization" '
    'OR abs:"annotator agreement" OR abs:"human evaluation" LLM '
    'OR abs:"instruction tuning" OR abs:"DPO" direct preference'
)

NS = {"atom": "http://www.w3.org/2005/Atom"}


def _parse_entry(entry):
    def txt(tag):
        el = entry.find(f"atom:{tag}", NS)
        return el.text.strip() if el is not None and el.text else ""

    authors = [
        a.find("atom:name", NS).text.strip()
        for a in entry.findall("atom:author", NS)
        if a.find("atom:name", NS) is not None
    ]

    return {
        "source": "arxiv",
        "title": txt("title").replace("\n", " "),
        "abstract": txt("summary").replace("\n", " ")[:600],
        "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
        "url": txt("id"),
        "date": txt("published")[:10],
        "text": "",
    }


def fetch(days_back=14, max_per_query=5):
    """
    Fetch recent arXiv papers relevant to RLHF / model evaluation.
    Returns list of paper dicts, sorted by date descending.
    """
    seen_ids = set()
    papers = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    log.info(f"arXiv intel: fetching last {days_back} days …")
    try:
        params = {
            "search_query": ARXIV_QUERY,
            "start": 0,
            "max_results": max_per_query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        resp = requests.get(ARXIV_API, params=params, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        for entry in root.findall("atom:entry", NS):
            id_el = entry.find("atom:id", NS)
            if id_el is None:
                continue
            arxiv_id = id_el.text.strip()
            if arxiv_id in seen_ids:
                continue

            pub_el = entry.find("atom:published", NS)
            if pub_el is not None:
                try:
                    pub_dt = datetime.fromisoformat(
                        pub_el.text.strip().replace("Z", "+00:00")
                    )
                    if pub_dt < cutoff:
                        continue
                except Exception:
                    pass

            seen_ids.add(arxiv_id)
            papers.append(_parse_entry(entry))
    except Exception as e:
        log.warning(f"arXiv fetch failed: {e}")

    log.info(f"arXiv intel: {len(papers)} papers found")
    return papers
