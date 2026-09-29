"""
Agent System Definitions.
First-class agent declarations with explicit capabilities, priorities, and lenses.
"""

AGENTS = {
    "A": {
        "id": "A",
        "name": "Evidence Advocate",
        "role": "Authority & Reliability Specialist",
        "focus": "Prioritizes source reliability, historical consistency, and established documentation.",
        "weights": {
            "reliability": 0.7,
            "recency": 0.3
        },
        "strategy": "Challenges opposing claims by highlighting unverified sources or low reliability ratings."
    },
    "B": {
        "id": "B",
        "name": "Skeptical Auditor",
        "role": "Recency & Verification Specialist",
        "focus": "Prioritizes fresh field data, recent observations, and empirical sensor readings.",
        "weights": {
            "reliability": 0.3,
            "recency": 0.7
        },
        "strategy": "Challenges opposing claims by highlighting stale evidence or outdated documentation."
    }
}

def get_agent(agent_id: str) -> dict:
    return AGENTS.get(agent_id, {
        "id": agent_id,
        "name": f"Agent {agent_id}",
        "role": "Generic Negotiator",
        "weights": {"reliability": 0.5, "recency": 0.5}
    })

def list_agents() -> list:
    return list(AGENTS.values())
