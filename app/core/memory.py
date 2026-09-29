"""
Dedicated Memory & Search Subsystem.
Manages persistent run records, context-scoped learned rules, source reliability history, and query/search APIs.
"""
import json, os, time, uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEM_FILE = os.path.join(ROOT, "memory", "memory.json")

def load_mem() -> dict:
    if os.path.exists(MEM_FILE):
        try:
            m = json.load(open(MEM_FILE))
            if "ctx" in m:
                return m
        except Exception:
            pass
    return {"ctx": {}, "runs": [], "diffs": [], "run_count": 0}

def save_mem(mem_data: dict):
    os.makedirs(os.path.dirname(MEM_FILE), exist_ok=True)
    with open(MEM_FILE, "w") as f:
        json.dump(mem_data, f, indent=2)

def reset():
    if os.path.exists(MEM_FILE):
        os.remove(MEM_FILE)

def generate_run_id() -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:6]
    return f"run_{ts}_{uid}"

def record_run(run_id: str, context: str, topic: str, resolution: dict, sc: dict) -> dict:
    mem = load_mem()
    record = {
        "run_id": run_id,
        "context": context,
        "topic": topic,
        "resolution_type": resolution.get("type"),
        "reason": resolution.get("reason"),
        "accepted_agent": resolution.get("accepted_agent"),
        "accepted_claim": resolution.get("accepted_claim"),
        "value": resolution.get("value"),
        "timestamp": int(time.time()),
        "scenario": sc.get("id")
    }
    mem["runs"].append(record)
    mem["run_count"] += 1
    save_mem(mem)
    return record

def update_source_reliability(context: str, source: str, old_rel: float, new_rel: float, run_id: str) -> dict:
    mem = load_mem()
    cm = mem["ctx"].setdefault(context, {"reliability": {}, "reliability_history": {}, "learned": {}})
    cm["reliability"][source] = new_rel
    hist = cm["reliability_history"].setdefault(source, [])
    diff = {"what": f"reliability[{context}/{source}]", "old": old_rel, "new": new_rel, "run_id": run_id, "ts": int(time.time())}
    hist.append(diff)
    mem["diffs"].append(diff)
    save_mem(mem)
    return diff

def record_learned_rule(context: str, topic: str, rule_type: str, value: str, cond: str, run_id: str) -> dict:
    mem = load_mem()
    cm = mem["ctx"].setdefault(context, {"reliability": {}, "reliability_history": {}, "learned": {}})
    old = cm["learned"].get(topic)
    ver = (old["version"] + 1) if old else 1
    rule_entry = {
        "context": context,
        "topic": topic,
        "version": ver,
        "type": rule_type,
        "value": value,
        "cond": cond,
        "created_from_run": run_id,
        "timestamp": int(time.time())
    }
    cm["learned"][topic] = rule_entry
    diff = {"what": f"rule[{context}/{topic}] v{ver}", "old": (old or {}).get("type") and f"{old['type']} {old['value']}", "new": f"{rule_type} {value} ({cond})", "run_id": run_id, "ts": int(time.time())}
    mem["diffs"].append(diff)
    save_mem(mem)
    return rule_entry

def get_context_memory(context: str) -> dict:
    mem = load_mem()
    return mem["ctx"].get(context, {"reliability": {}, "reliability_history": {}, "learned": {}})

def get_topic_memory(context: str, topic: str) -> dict:
    cm = get_context_memory(context)
    return cm.get("learned", {}).get(topic)

def search_memory(query: str) -> list:
    mem = load_mem()
    query = query.lower().strip()
    results = []
    for ctx, cm in mem.get("ctx", {}).items():
        for topic, rule in cm.get("learned", {}).items():
            if query in ctx.lower() or query in topic.lower() or query in str(rule.get("value")).lower() or query in str(rule.get("cond")).lower():
                results.append({"type": "rule", "context": ctx, "topic": topic, "data": rule})
        for src, rel in cm.get("reliability", {}).items():
            if query in src.lower() or query in ctx.lower():
                results.append({"type": "reliability", "context": ctx, "source": src, "reliability": rel})
    for run in mem.get("runs", []):
        if query in run.get("context", "").lower() or query in run.get("topic", "").lower() or query in str(run.get("value")).lower():
            results.append({"type": "run", "data": run})
    return results

def get_runs(limit: int = 50) -> list:
    mem = load_mem()
    return mem.get("runs", [])[-limit:]

def get_run(run_id: str) -> dict:
    mem = load_mem()
    for run in mem.get("runs", []):
        if run.get("run_id") == run_id:
            return run
    return None
