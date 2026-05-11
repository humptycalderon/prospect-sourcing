"""
Claude-powered outreach personalizer.
Generates a cold email draft per prospect, grounded in their specific
signals and the current week's market positioning.
"""

import os
import logging
import anthropic

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a senior growth marketer writing cold outreach emails for an AI data platform.

COMPANY BACKGROUND:
We have deep experience building identity and reputation products. Our existing platform \
already has hundreds of thousands of verified humans with evolving reputation scores that \
track consistency, reliability, and demonstrated skill over time. Many of these people are \
already completing annotation, evaluation, and preference labeling tasks — the exact work \
AI labs need for RLHF and model benchmarking.

WHAT WE'RE BUILDING:
A data marketplace that extends our verified human base specifically for AI/ML teams who \
need high-consistency evaluators for RLHF, reward model training, and model benchmarking. \
Key differentiators:
- Longitudinal behavioral data: evaluator performance tracked over time, not just per task
- Verifiable uniqueness: every human is verified — no duplicates, no synthetic profiles
- Evolving reputation scores: clients filter evaluators by demonstrated consistency
- Existing scale: hundreds of thousands of verified humans already active on the platform

STAGE: Pre-demo. We are having discovery conversations to understand pain points and \
build the demo from what we learn.

EMAIL RULES:
- 4–5 sentences maximum. No fluff, no buzzwords.
- Open with their specific pain point — not our product.
- Mention our existing platform scale as credibility, briefly.
- Close with a low-friction ask: a 20-minute research conversation to understand their \
  current approach. Frame it as research, not a sales call.
- Tone: direct, peer-to-peer, technical. These are AI/ML engineers and research leads.
- Subject line: one line, specific to their situation. No clickbait.
- Do not mention pricing, contracts, or timelines.
- Output format: Subject: [line] then a blank line then the email body. Nothing else."""


def _build_prompt(prospect, digest_context=""):
    name = prospect.get("name") or prospect.get("login") or "the team"
    company = name  # for orgs, name is the company
    website = prospect.get("website", "")
    description = prospect.get("description", "")
    topics = prospect.get("topics", "")
    score_reasons = prospect.get("score_reasons", "")
    contact_name = prospect.get("contact_name", "")
    contact_title = prospect.get("contact_title", "")
    hn_title = prospect.get("hn_title", "")
    source = prospect.get("source", "github")
    score = prospect.get("score", 0)

    contact_line = ""
    if contact_name and contact_title:
        contact_line = f"Contact: {contact_name} ({contact_title})"
    elif contact_name:
        contact_line = f"Contact: {contact_name}"

    return f"""\
Write a personalised cold outreach email for this prospect.

PROSPECT:
Company/Name: {company}
Website: {website}
Source: {source}
ICP Score: {score}/100
Description: {description}
Topics/Keywords: {topics}
Why they scored high: {score_reasons}
{contact_line}
HN discussion (if any): {hn_title}

CURRENT MARKET CONTEXT (from this week's intelligence digest — use only if directly relevant):
{digest_context[:1500] if digest_context else 'Not available.'}

Write the email now. Subject line first, then body. Nothing else."""


def generate(prospect, digest_context="", api_key=None):
    """
    Generate a personalised outreach email for a single prospect.
    Returns a dict with 'subject' and 'body', or None on failure.
    """
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not set")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(prospect, digest_context)

    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Parse subject and body
        lines = raw.split("\n", 2)
        subject_line = next((l for l in lines if l.lower().startswith("subject:")), "")
        subject = subject_line.replace("Subject:", "").replace("subject:", "").strip()
        body = raw[len(subject_line):].strip().lstrip("\n")

        return {"subject": subject, "body": body}

    except Exception as e:
        log.error(f"Personalizer failed for {prospect.get('name')}: {e}")
        return None


def generate_batch(prospects, digest_context="", api_key=None):
    """
    Generate outreach emails for a list of prospects.
    Returns list of (prospect, draft) tuples. draft is None if generation failed.
    """
    results = []
    total = len(prospects)
    for i, prospect in enumerate(prospects, 1):
        name = prospect.get("name") or prospect.get("login") or "unknown"
        log.info(f"Generating outreach {i}/{total}: {name}")
        draft = generate(prospect, digest_context=digest_context, api_key=api_key)
        results.append((prospect, draft))
    return results
