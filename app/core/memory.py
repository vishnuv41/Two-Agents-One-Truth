"""
Public Memory Subsystem Interface.
Delegates persistence to core.sqlite_store (SQLite database at app/memory/two_agents.db).
Preserves 100% backward compatibility for engine, REST API, UI, and test suites.
"""
from core.sqlite_store import store

def load_mem() -> dict:
    return store.load_mem()

def save_mem(mem_data: dict):
    store.save_mem(mem_data)

def reset():
    store.reset()

def generate_run_id() -> str:
    return store.generate_run_id()

def record_run(run_id: str, context: str, topic: str, resolution: dict, sc: dict) -> dict:
    return store.record_run(run_id, context, topic, resolution, sc)

def update_source_reliability(context: str, source: str, old_rel: float, new_rel: float, run_id: str) -> dict:
    return store.update_source_reliability(context, source, old_rel, new_rel, run_id)

def record_learned_rule(context: str, topic: str, rule_type: str, value: str, cond: str, run_id: str) -> dict:
    return store.record_learned_rule(context, topic, rule_type, value, cond, run_id)

def get_context_memory(context: str) -> dict:
    mem = store.load_mem()
    return mem["ctx"].get(context, {"reliability": {}, "reliability_history": {}, "learned": {}})

def get_topic_memory(context: str, topic: str) -> dict:
    return store.get_topic_memory(context, topic)

def search_memory(query: str) -> list:
    return store.search_memory(query)

def get_runs(limit: int = 50) -> list:
    return store.get_runs(limit)

def get_run(run_id: str) -> dict:
    return store.get_run(run_id)
