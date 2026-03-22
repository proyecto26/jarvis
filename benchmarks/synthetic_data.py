"""Synthetic data generator for memory system benchmarks.

Generates:
- Journal entries (100 days of dreams, judgments, executions, learnings)
- Beliefs (50 beliefs with varying strengths)
- Known-answer query pairs (20 queries with expected recall targets)
- Contradiction pairs (10 pairs of semantically conflicting beliefs)
"""

import hashlib
import random
from datetime import datetime, timedelta

# Seed for reproducibility
random.seed(42)

# --- Domains and topics for realistic variety ---

TOPICS = [
    "user authentication", "database optimization", "API rate limiting",
    "error handling patterns", "caching strategies", "security best practices",
    "testing methodology", "deployment pipelines", "monitoring and alerting",
    "code review process", "microservices architecture", "data validation",
    "logging standards", "performance profiling", "memory management",
    "concurrency patterns", "configuration management", "dependency updates",
    "feature flag rollouts", "incident response procedures",
]

ACTIONS = [
    "refactor", "implement", "review", "optimize", "debug",
    "migrate", "deploy", "rollback", "investigate", "document",
]

OUTCOMES = ["success", "partial", "deferred", "failed"]

DREAM_SEEDS = [
    "What if we treated every API call as a potential failure?",
    "Imagine a world where tests write themselves",
    "Could we build a self-healing deployment pipeline?",
    "What patterns emerge from our incident history?",
    "How would a purely event-driven architecture look?",
    "What if caching was declarative rather than imperative?",
    "Could belief strength be modeled as a wave function?",
    "What if we merged code review with AI pair programming?",
    "Imagine a database that anticipates query patterns",
    "What if monitoring could predict failures before they happen?",
]

BELIEF_TEMPLATES = [
    "Always validate input at the {layer} boundary",
    "Prefer {strategy} over {alt_strategy} for {topic}",
    "The {component} should be {quality} to reduce {risk}",
    "When {topic} fails, prioritize {action} before {alt_action}",
    "{pattern} is more effective than {alt_pattern} for {topic}",
]

LAYERS = ["API", "service", "repository", "controller", "gateway"]
STRATEGIES = ["composition", "inheritance", "delegation", "inversion", "encapsulation"]
COMPONENTS = ["logger", "cache", "queue", "scheduler", "validator"]
QUALITIES = ["idempotent", "stateless", "immutable", "thread-safe", "lazy-loaded"]
RISKS = ["data loss", "race conditions", "memory leaks", "deadlocks", "cascading failures"]
PATTERNS = ["circuit breaker", "retry with backoff", "bulkhead", "saga", "event sourcing"]


def _make_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:8]


def generate_journal_entries(num_days: int = 100) -> list[dict]:
    """Generate synthetic journal entries spanning num_days."""
    entries = []
    start_date = datetime(2025, 1, 1)

    for day in range(num_days):
        entry_date = (start_date + timedelta(days=day)).strftime("%Y-%m-%d")
        topic_idx = day % len(TOPICS)
        topic = TOPICS[topic_idx]

        entry = {
            "metadata": {
                "date": entry_date,
                "mode_cycles": {
                    "awake": random.randint(1, 5),
                    "sleep": random.randint(0, 2),
                    "reflective": random.randint(0, 1),
                },
                "active_skills": random.sample(
                    ["communication-style", "journal-entry-writer", "escalation-handler"],
                    k=random.randint(1, 3),
                ),
                "dominant_theme": topic,
            },
            "dreams": [
                {
                    "timestamp": f"{entry_date}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:00",
                    "seed": random.choice(DREAM_SEEDS),
                    "branches": [
                        f"Branch exploring {random.choice(TOPICS)}"
                        for _ in range(random.randint(1, 3))
                    ],
                    "depth_reached": random.randint(1, 8),
                    "breakthrough": (
                        f"Insight: {topic} can be improved by applying {random.choice(PATTERNS)}"
                        if random.random() > 0.7
                        else None
                    ),
                }
                for _ in range(random.randint(0, 3))
            ],
            "judgments": [
                {
                    "timestamp": f"{entry_date}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:00",
                    "action": f"{random.choice(ACTIONS)} {topic}",
                    "action_weight": random.randint(1, 10),
                    "verdict": random.choice(["approved", "modified", "blocked"]),
                    "reasoning": f"Evaluated {topic} against current beliefs about {random.choice(TOPICS)}. "
                    f"Risk level assessed as {random.choice(['low', 'medium', 'high'])}.",
                }
                for _ in range(random.randint(1, 4))
            ],
            "executions": [
                {
                    "timestamp": f"{entry_date}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:00",
                    "action": f"{random.choice(ACTIONS)} {topic}",
                    "status": random.choice(OUTCOMES),
                    "outcome": f"Applied {random.choice(PATTERNS)} pattern to {topic}",
                    "artifacts": [f"file_{random.randint(1,100)}.py"],
                }
                for _ in range(random.randint(0, 3))
            ],
            "learnings": [
                {
                    "content": f"Learned that {random.choice(PATTERNS)} works well for {topic} "
                    f"when combined with {random.choice(STRATEGIES)}",
                    "source_mode": random.choice(["awake", "reflective", "sleep"]),
                }
                for _ in range(random.randint(0, 3))
            ],
            "belief_mutations": [
                {
                    "timestamp": f"{entry_date}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:00",
                    "mutation_type": random.choice(["created", "updated", "weakened", "strengthened"]),
                    "belief": f"{random.choice(PATTERNS)} is effective for {topic}",
                    "strength": round(random.uniform(0.3, 1.0), 2),
                    "reason": f"Based on execution outcome in {topic}",
                }
                for _ in range(random.randint(0, 2))
            ],
            "open_questions": [
                f"How does {random.choice(PATTERNS)} interact with {topic}?"
                for _ in range(random.randint(0, 2))
            ],
            "connections": [
                f"Related to day {max(0, day - random.randint(1, 10))} insights on {random.choice(TOPICS)}"
                for _ in range(random.randint(0, 2))
            ],
        }
        entries.append(entry)

    return entries


def generate_beliefs(num_beliefs: int = 50) -> list[dict]:
    """Generate synthetic beliefs with varying strengths."""
    beliefs = []
    for i in range(num_beliefs):
        topic = TOPICS[i % len(TOPICS)]
        pattern = random.choice(PATTERNS)
        belief_text = f"{pattern} is the preferred approach for {topic}"
        beliefs.append({
            "belief": belief_text,
            "strength": round(random.uniform(0.2, 1.0), 2),
            "reason": f"Validated through {random.randint(1, 20)} experiences with {topic}",
            "created": (datetime(2025, 1, 1) + timedelta(days=i)).isoformat(),
            "updated": (datetime(2025, 1, 1) + timedelta(days=i + random.randint(0, 30))).isoformat(),
        })
    return beliefs


# Semantic synonyms/paraphrases for topics (queries that don't use exact keywords)
SEMANTIC_QUERIES = {
    "user authentication": "login security and credential verification",
    "database optimization": "improving query performance and indexing",
    "API rate limiting": "throttling and request quota enforcement",
    "error handling patterns": "exception management and fault tolerance",
    "caching strategies": "storing frequently accessed data in memory",
    "security best practices": "protecting systems against vulnerabilities",
    "testing methodology": "quality assurance and automated verification",
    "deployment pipelines": "CI/CD and release automation",
    "monitoring and alerting": "observability and incident notification",
    "code review process": "peer evaluation of source code changes",
    "microservices architecture": "distributed service decomposition",
    "data validation": "input sanitization and schema enforcement",
    "logging standards": "structured application output and tracing",
    "performance profiling": "identifying bottlenecks and hotspots",
    "memory management": "heap allocation and garbage collection",
    "concurrency patterns": "parallel execution and thread safety",
    "configuration management": "environment settings and feature toggles",
    "dependency updates": "upgrading third-party libraries and packages",
    "feature flag rollouts": "gradual release of new functionality",
    "incident response procedures": "on-call escalation and postmortem processes",
}


def generate_query_pairs(entries: list[dict], num_queries: int = 20) -> list[dict]:
    """Generate query-answer pairs for evaluating recall precision.

    Includes both keyword-based queries (easy) and semantic/paraphrase
    queries (hard) to test whether the backend can handle synonyms.

    Each pair has:
    - query: a natural language question
    - expected_dates: list of dates whose entries should be recalled
    - expected_topics: list of topics that should appear in results
    - difficulty: "keyword" or "semantic"
    """
    pairs = []
    for i in range(num_queries):
        topic = TOPICS[i % len(TOPICS)]
        # Find all entries where this topic appears
        matching_dates = []
        for entry in entries:
            theme = entry["metadata"].get("dominant_theme", "")
            learnings_text = " ".join(
                l["content"] for l in entry.get("learnings", [])
            )
            judgments_text = " ".join(
                j["reasoning"] for j in entry.get("judgments", [])
            )
            if topic.lower() in (theme + learnings_text + judgments_text).lower():
                matching_dates.append(entry["metadata"]["date"])

        # Alternate between keyword queries and semantic queries
        if i % 2 == 0:
            # Keyword-based query (exact topic terms)
            query_variants = [
                f"What do I know about {topic}?",
                f"Recall experiences related to {topic}",
            ]
            difficulty = "keyword"
        else:
            # Semantic query (synonyms/paraphrases — no exact keyword match)
            semantic_text = SEMANTIC_QUERIES.get(topic, topic)
            query_variants = [
                f"Tell me about {semantic_text}",
                f"What have I learned about {semantic_text}?",
            ]
            difficulty = "semantic"

        pairs.append({
            "query": query_variants[i % 2],
            "expected_dates": matching_dates,
            "expected_topics": [topic],
            "topic": topic,
            "difficulty": difficulty,
        })

    return pairs


def generate_contradiction_pairs(num_pairs: int = 10) -> list[dict]:
    """Generate pairs of beliefs that semantically contradict each other."""
    pairs = []
    for i in range(num_pairs):
        topic = TOPICS[i % len(TOPICS)]
        pattern_a = PATTERNS[i % len(PATTERNS)]
        pattern_b = PATTERNS[(i + 1) % len(PATTERNS)]

        pairs.append({
            "belief_a": f"{pattern_a} is the preferred approach for {topic}",
            "belief_b": f"{pattern_b} is the preferred approach for {topic}",
            "expected_conflict": True,
            "topic": topic,
        })

    # Add some non-contradictory pairs as negative examples
    for i in range(5):
        topic_a = TOPICS[i]
        topic_b = TOPICS[i + 10]
        pattern = PATTERNS[i % len(PATTERNS)]
        pairs.append({
            "belief_a": f"{pattern} is effective for {topic_a}",
            "belief_b": f"{pattern} is effective for {topic_b}",
            "expected_conflict": False,
            "topic": f"{topic_a} vs {topic_b}",
        })

    return pairs


def generate_all() -> dict:
    """Generate the complete synthetic dataset."""
    entries = generate_journal_entries(100)
    beliefs = generate_beliefs(50)
    query_pairs = generate_query_pairs(entries, 20)
    contradiction_pairs = generate_contradiction_pairs(10)

    return {
        "entries": entries,
        "beliefs": beliefs,
        "query_pairs": query_pairs,
        "contradiction_pairs": contradiction_pairs,
        "stats": {
            "num_entries": len(entries),
            "num_beliefs": len(beliefs),
            "num_queries": len(query_pairs),
            "num_contradictions": len(contradiction_pairs),
            "total_dreams": sum(len(e["dreams"]) for e in entries),
            "total_judgments": sum(len(e["judgments"]) for e in entries),
            "total_executions": sum(len(e["executions"]) for e in entries),
            "total_learnings": sum(len(e["learnings"]) for e in entries),
        },
    }


if __name__ == "__main__":
    import json
    data = generate_all()
    print(json.dumps(data["stats"], indent=2))
    print(f"\nGenerated {data['stats']['num_entries']} entries, "
          f"{data['stats']['num_beliefs']} beliefs, "
          f"{data['stats']['num_queries']} query pairs, "
          f"{data['stats']['num_contradictions']} contradiction pairs")
