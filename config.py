"""
ICP: AI companies that build or deploy agents and need high-quality human evaluators
to assess agent outputs, verify multi-step trajectories, and validate compatibility
claims. Includes RLHF / LLM evaluation as a foundation, with agent evaluation
frameworks as the primary growth focus. Physical AI and robotics are high-priority
subsets within agent evaluation.
"""

# --- GitHub search queries ---
# Each query is run against the GitHub repository search API.
GITHUB_QUERIES = [
    # Agent evaluation — primary focus
    "agent evaluation framework",
    "llm agent evaluation",
    "multi-step agent benchmark",
    "agentic workflow evaluation",
    "agent trajectory evaluation",
    "tool use evaluation benchmark",
    "agent output verification",
    "autonomous agent testing",
    # RLHF / LLM evaluation — foundation
    "rlhf training data",
    "reinforcement learning human feedback",
    "llm fine-tuning evaluation",
    "reward model training",
    "human preference dataset",
    "ai model evaluation framework",
    # Physical AI / robotics — subset
    "robotics policy evaluation",
    "embodied ai evaluation",
    "robot deployment compatibility",
]

# Topics that signal a company is building/training agents or models
HIGH_SIGNAL_TOPICS = {
    # Agent evaluation
    "agent-evaluation", "agentic", "agent-benchmark", "tool-use",
    "multi-agent", "agent-framework", "agent-testing", "trajectory-evaluation",
    # RLHF / LLM
    "rlhf", "reinforcement-learning-from-human-feedback", "reward-model",
    "fine-tuning", "finetuning", "instruction-tuning", "alignment",
    "llm-training", "model-evaluation", "benchmarking", "preference-learning",
    "human-feedback", "data-annotation", "model-alignment", "ai-safety",
    # Physical AI subset
    "embodied-ai", "physical-ai", "robot-policy", "policy-evaluation",
}

# Topics that provide supporting signal
SUPPORTING_TOPICS = {
    "large-language-models", "llm", "transformers", "nlp", "deep-learning",
    "machine-learning", "pytorch", "huggingface", "openai", "anthropic",
    "foundation-models", "generative-ai", "prompt-engineering",
    "autonomous-agents", "ai-agents", "langchain", "autogen",
    "robotics", "sim-to-real", "robot-learning",
}

# Keywords scored in org/repo descriptions
DESCRIPTION_KEYWORDS = {
    # Highest value — agent evaluation
    "agent evaluation": 10,
    "agentic evaluation": 10,
    "agent trajectory": 9,
    "multi-step agent": 9,
    "agent verification": 9,
    "agent benchmark": 8,
    "tool use evaluation": 8,
    "agent output": 7,
    "autonomous agent": 7,
    "agent workflow": 7,
    # RLHF / LLM evaluation
    "rlhf": 10,
    "reinforcement learning from human feedback": 10,
    "human feedback": 8,
    "preference data": 8,
    "reward model": 8,
    "model alignment": 7,
    "ai alignment": 7,
    "model evaluation": 7,
    "benchmarking": 6,
    "fine-tun": 6,
    "instruction tun": 6,
    "data annotation": 5,
    "ai safety": 5,
    "foundation model": 5,
    "llm training": 5,
    # Moderate
    "large language model": 4,
    "generative ai": 3,
    "language model": 3,
    "training data": 3,
    # Physical AI subset
    "physical ai": 8,
    "embodied ai": 8,
    "robotics policy": 7,
    "robot compatibility": 7,
    "robot evaluation": 7,
    "sim to real": 5,
}

# --- Hacker News search queries ---
HN_QUERIES = [
    # Agent evaluation — primary
    "agent evaluation framework",
    "LLM agent benchmark",
    "agentic workflow evaluation",
    "agent trajectory human evaluation",
    "multi-step agent testing",
    "agent output verification",
    # RLHF / LLM evaluation — foundation
    "RLHF data quality",
    "human feedback training data",
    "model evaluation benchmark",
    "preference labeling",
    "reward model training data",
    # Physical AI subset
    "physical AI agent evaluation",
    "embodied AI benchmark",
    "robot policy evaluation",
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
