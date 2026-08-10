"""
ICP covers five buyer/partner types:

1. AI Evaluator buyers — AI companies building or deploying agents that need
   high-quality human evaluators to assess outputs, verify multi-step trajectories,
   and calibrate reward models. RLHF / LLM evaluation is the foundation; agent
   evaluation frameworks and physical AI are high-priority subsets. AI inference
   marketplaces (e.g. Allora) are an emerging subset needing output validation.

2. Gaming data buyers — AI x gaming companies and game developers that need verified
   player behavioral data (hours played, spend, genres, platform) for training player
   models, churn prediction, recommendation systems, and NPC AI. ONTO's Steam campaign
   is the reference PoC; PALZ is the reference partner channel.

3. EdTech AI buyers — Future category. Paired with the Student contributor persona.
   No active query coverage; will surface passively if a company hits gaming or
   evaluator signals. Revisit when university acquisition channel produces warm leads.

4. Web3 gaming campaign partners — GameFi projects, blockchain game studios, and
   NFT gaming platforms with active communities that want to run structured data
   collection campaigns through ONTO, monetizing player data with verified identity
   and on-chain provenance. PALZ is the reference example.

5. AI inference / model marketplace partners — Decentralized AI networks and model
   marketplaces that need human validation of model outputs and contributor reputation
   signals to surface model quality.
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
    # AI x Gaming — data buyers and campaign partners
    "game player behavior machine learning",
    "player behavior prediction model",
    "gaming data analytics platform",
    "npc ai behavior evaluation",
    "esports analytics machine learning",
    "game content generation evaluation",
    "player modeling reinforcement learning",
    "game churn prediction dataset",
    # Web3 gaming — campaign partners
    "blockchain gaming player data",
    "gamefi analytics platform",
    "web3 game community data",
    "play to earn player analytics",
    # AI inference marketplace — evaluator buyers
    "ai inference marketplace evaluation",
    "decentralized ai model validation",
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
    # AI x Gaming
    "game-ai", "game-analytics", "player-behavior", "player-modeling",
    "esports-analytics", "gaming-data", "npc-ai", "game-evaluation",
    "game-ml", "procedural-generation", "game-ai-evaluation", "player-data",
    # Web3 gaming
    "gamefi", "blockchain-gaming", "play-to-earn", "web3-gaming",
    "nft-game", "crypto-gaming",
    # AI inference marketplace
    "ai-marketplace", "inference-marketplace", "decentralized-ai",
}

# Topics that provide supporting signal
SUPPORTING_TOPICS = {
    "large-language-models", "llm", "transformers", "nlp", "deep-learning",
    "machine-learning", "pytorch", "huggingface", "openai", "anthropic",
    "foundation-models", "generative-ai", "prompt-engineering",
    "autonomous-agents", "ai-agents", "langchain", "autogen",
    "robotics", "sim-to-real", "robot-learning",
    # Gaming adjacent
    "gaming", "game-development", "unity", "unreal-engine", "esports",
    "steam", "game-engine", "game-design",
    # Web3 / blockchain adjacent
    "web3", "blockchain", "defi", "nft", "crypto",
    # EdTech adjacent (passive — surfaces if company also hits other signals)
    "education", "e-learning", "lms", "curriculum",
    "edtech", "ai-education", "personalized-learning", "educational-ai",
    "learning-analytics", "adaptive-learning", "ai-tutor",
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
    # AI x Gaming — data buyers
    "game ai": 9,
    "gaming ai": 9,
    "player behavior": 8,
    "player modeling": 8,
    "npc behavior": 8,
    "game evaluation": 8,
    "gaming data": 7,
    "player data": 7,
    "game analytics": 7,
    "esports analytics": 7,
    "procedural generation": 6,
    "game recommendation": 6,
    "game data": 5,
    "churn prediction": 5,
    "gaming platform": 4,
    "game developer": 4,
    # Web3 gaming — campaign partners
    "web3 gaming": 9,
    "blockchain gaming": 9,
    "gamefi": 9,
    "play to earn": 8,
    "nft game": 7,
    "crypto game": 6,
    "web3 game": 6,
    "game token": 5,
    # EdTech AI — passive signal; surfaces only if company hits other criteria
    "educational ai": 6,
    "ai tutoring": 6,
    "personalized learning": 5,
    "adaptive learning": 5,
    "learning analytics": 5,
    "edtech platform": 5,
    "ai education": 5,
    "educational data": 3,
    "learning platform": 3,
    # AI inference marketplace — evaluator buyers
    "ai inference marketplace": 9,
    "model marketplace": 8,
    "decentralized ai": 7,
    "ai network": 5,
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
    # AI x Gaming
    "gaming AI player behavior data",
    "player behavior machine learning",
    "game developer AI model training",
    "esports player data analytics",
    "gaming data monetization",
    # Web3 gaming
    "blockchain game player data",
    "GameFi community data",
    # AI inference marketplace
    "AI inference marketplace human evaluation",
    "decentralized AI model quality",
]

# HN post types to include (story = top-level post, comment = included too)
HN_TAGS = ["story", "comment"]

# Minimum HN post points to include (filters noise)
HN_MIN_POINTS = 5

# Keywords that signal production/real-org use rather than academic/hobbyist work.
# Scanned in repo descriptions. Each match adds SCORE_WEIGHTS["intent_signal"] pts, capped at 10.
INTENT_KEYWORDS = {
    "production":        2,
    "deploy":            2,
    "pipeline":          2,
    "at scale":          2,
    "enterprise":        2,
    "human eval":        3,
    "annotation":        2,
    "labeling":          2,
    "quality assurance": 2,
    "evaluate":          2,
    "benchmark":         2,
    # Gaming signals
    "game studio":       2,
    "gaming":            2,
    "esports":           2,
    "player":            1,
    # Web3 gaming signals
    "gamefi":            2,
    "web3 game":         2,
    # AI inference signals
    "inference network": 2,
    "model validation":  2,
}

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
    "intent_signal": 2,              # per production-use keyword match, capped at 10
}

# Max total score (used to normalize to 0–100)
MAX_SCORE = 100

# Minimum score to include in output
MIN_SCORE_THRESHOLD = 35
