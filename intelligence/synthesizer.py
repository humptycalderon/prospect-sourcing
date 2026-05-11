"""
Synthesizer: uses Claude Opus 4.6 to turn raw intelligence signals into
a structured daily briefing tailored to the platform's positioning.

Platform context:
  - Generates longitudinal human behavior data with verifiable uniqueness
  - Provides evolving reputation scores for evaluators
  - Supplies high-consistency evaluators for RLHF and model benchmarking
  - Key differentiators: data continuity over time, anti-gaming/sybil resistance,
    trust scoring on evaluators themselves
"""

import os
import logging
import anthropic

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a market intelligence analyst for a company called [Platform] that sells:
- Longitudinal human behavior data with verifiable uniqueness (anti-sybil, anti-bot)
- Evolving reputation scores on human evaluators over time
- High-consistency human evaluators for RLHF training and model benchmarking

Your ICP (ideal customer): AI companies and research labs that train or fine-tune LLMs
and need reliable human feedback data — preference labeling, reward model training,
evaluation tasks — where data quality and evaluator consistency are critical.

Your job: read raw signals from Hacker News, arXiv, and AI newsletters, then produce
a concise daily intelligence briefing that helps the sales and product team understand:
1. What pain points the market is talking about right now
2. What new research validates or challenges the platform's approach
3. Who is actively discussing these problems (potential prospects)
4. How to position the platform in conversations this week

Write in a direct, professional tone. Be specific. No filler."""


def _format_signals(items):
    """Format raw signal items into a structured prompt block."""
    sections = []

    hn = [i for i in items if i["source"] == "hackernews"]
    arxiv = [i for i in items if i["source"] == "arxiv"]
    rss = [i for i in items if i["source"] == "rss"]

    if hn:
        sections.append("=== HACKER NEWS DISCUSSIONS ===")
        for i in hn[:25]:
            sections.append(
                f"[{i['points']} pts] {i['title']}\n"
                f"Author: {i['author']} | URL: {i['url']}\n"
                f"{i['text'][:300]}\n"
            )

    if arxiv:
        sections.append("=== ARXIV PAPERS (last 7 days) ===")
        for p in arxiv[:15]:
            sections.append(
                f"Title: {p['title']}\n"
                f"Authors: {p['authors']} | Date: {p['date']}\n"
                f"Abstract: {p['abstract'][:400]}\n"
                f"URL: {p['url']}\n"
            )

    if rss:
        sections.append("=== AI NEWSLETTER COVERAGE ===")
        for a in rss[:10]:
            sections.append(
                f"[{a['feed']}] {a['title']}\n"
                f"Date: {a['date']} | URL: {a['url']}\n"
                f"{a['text'][:300]}\n"
            )

    return "\n\n".join(sections)


BRIEFING_PROMPT = """Here are the raw intelligence signals from the past 7 days:

{signals}

---

Based on these signals, write a market intelligence briefing with exactly these sections:

## Top Pain Points This Week
List the 3-5 most-discussed problems or frustrations related to AI training data,
human evaluation quality, RLHF data, or model benchmarking. For each: what the
pain is, who's feeling it, and why it matters for us.

## Research Signals
2-4 recent arXiv papers or newsletter pieces that are relevant to our positioning.
For each: what it says, why it matters, and how we can reference it in conversations.

## Prospect Signals
People or companies that appeared in discussions who might be buyers. Include
their HN username or affiliation if visible. Note what they said that signals need.

## Positioning This Week
Based on what the market is discussing RIGHT NOW, write 2-3 specific talking points
we should lead with in outreach this week. These should directly connect current
pain points to what our platform uniquely offers.

## One Thing to Watch
One emerging trend or concern that we should track — not yet a pain point,
but worth monitoring for next week.

Keep the whole briefing under 800 words. Be specific and actionable."""


def synthesize(items, api_key=None):
    """
    Take raw intelligence items and produce a structured briefing string.
    Uses Claude Opus 4.6 with adaptive thinking.
    """
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not set — cannot synthesize briefing")
        return None

    client = anthropic.Anthropic(api_key=api_key)

    signals = _format_signals(items)
    if not signals.strip():
        log.warning("No signals to synthesize — all sources returned empty")
        return None

    log.info(f"Synthesizing briefing from {len(items)} signals with Claude Opus 4.6 …")

    prompt = BRIEFING_PROMPT.format(signals=signals)

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    briefing = next(
        (b.text for b in response.content if b.type == "text"), None
    )

    tokens_used = response.usage.input_tokens + response.usage.output_tokens
    log.info(f"Synthesis complete. Tokens used: {tokens_used:,}")

    return briefing
