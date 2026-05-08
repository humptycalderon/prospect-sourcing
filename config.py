"""
ICP: AI companies that train or fine-tune models and need high-quality
human evaluators for RLHF, preference labeling, and model benchmarking.
"""

# --- GitHub search queries ---
# Each query is run against the GitHub repository search API.
GITHUB_QUERIES = [
    "rlhf training data",
    "reinforcement learning human feedback",
    "llm fine-tuning evaluation",
    "model alignment human feedback",
    "preference data annotation",
    "reward model training",
    "llm benchmark evaluation",
    "instruction tuning dataset",
    "human preference dataset",
    "ai model evaluation framework",
]

# Topics that signal a company is building/training models (not just using them)
HIGH_SIGNAL_TOPICS = {
    "rlhf", "reinforcement-learning-from-human-feedback", "reward-model",
    "fine-tuning", "finetuning", "instruction-tuning", "alignment",
    "llm-training", "model-evaluation", "benchmarking", "preference-learning",
    "human-feedback", "data-annotation", "model-alignment", "ai-safety",
}

# Topics that provide supporting signal
SUPPORTING_TOPICS = {
    "large-language-models", "llm", "transformers", "nlp", "deep-learning",
    "machine-learning", "pytorch", "huggingface", "openai", "anthropic",
    "foundation-models", "generative-ai", "prompt-engineering",
}

# Keywords scored in org/repo descriptions
DESCRIPTION_KEYWORDS = {
    # Highest value — direct RLHF/evaluation signal
    "rlhf": 10,
    "reinforcement learning from human feedback": 10,
    "human feedback": 8,
    "preference data": 8,
    "reward model": 8,
    "model alignment": 7,
    "ai alignment": 7,
    "model evaluation": 7,
    "benchmarking": 6,
    "fine-tun": 6,       # catches fine-tune, fine-tuning, fine-tuned
    "instruction tun": 6,
    "data annotation": 5,
    "ai safety": 5,
    "foundation model": 5,
    "llm training": 5,
    # Moderate — building AI products that will eventually need evaluators
    "large language model": 4,
    "generative ai": 3,
    "language model": 3,
    "training data": 3,
}

# --- Hacker News search queries ---
HN_QUERIES = [
    "RLHF data quality",
    "human feedback training data",
    "model evaluation benchmark",
    "preference labeling",
    "AI alignment data",
    "RLHF evaluators",
    "reward model training data",
    "LLM fine-tuning data",
]

# HN post types to include (story = top-level post, comment = included too)
HN_TAGS = ["story", "comment"]

# Minimum HN post points to include (filters noise)
HN_MIN_POINTS = 5

# --- Scoring weights ---
SCORE_WEIGHTS = {
    "high_signal_topic_match": 15,   # per matching topic
    "supporting_topic_match": 5,     # per matching topic
    "description_keyword": 1,        # scaled by keyword weight above
    "recent_activity": 10,           # repo updated within 90 days
    "has_website": 5,                # org has a company domain
    "is_org": 8,                     # GitHub org (vs personal account)
    "multiple_repos": 5,             # org has >3 repos (real company)
    "hn_source": 12,                 # found on HN discussing the pain point
}

# Max total score (used to normalize to 0–100)
MAX_SCORE = 100

# Minimum score to include in output
MIN_SCORE_THRESHOLD = 20
