"""Orchestrator. Python only moves data; every decision comes from core/weigh.metta."""
import json, os, copy
from hyperon import MeTTa
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEM = os.path.join(ROOT, "memory", "memory.json")
SC = os.path.join(ROOT, "scenarios")

def scenarios():
    out = {}
    for f in sorted(os.listdir(SC)):
        if f.endswith(".json"):
            s = json.load(open(os.path.join(SC, f))); out[s["id"]] = s
    return out

def load_mem():
    if os.path.exists(MEM): return json.load(open(MEM))
    return {"reliability": {}, "learned": {}, "diffs": [], "runs": 0}

def save_mem(m):
    json.dump(m, open(MEM, "w"), indent=2)

def reset():
    if os.path.exists(MEM): os.remove(MEM)

def q(m, expr):
    r = m.run("!" + expr)
    return r[0][0] if r and r[0] else None

def num(a): return float(str(a))

def run(sid):
    return run_scenario(scenarios()[sid])

def run_scenario(sc):
    sc = validate(sc); sid = sc["id"]; mem = load_mem(); ev = []
    def emit(kind, text, **kw): ev.append({"kind": kind, "text": text, **kw})
    for s, r in sc["reliability"].items(): mem["reliability"].setdefault(s, r)
    m = MeTTa(); m.run(open(os.path.join(ROOT, "core", "weigh.metta")).read())
    for s, r in mem["reliability"].items(): m.run(f"(reliability {s} {r})")
    t = sc["topic"]; cl = sc["claims"]
    for ag, c in cl.items(): m.run(f"(claim {ag} {t} {c['value']} {c['id']})")
    for e in sc["evidence"]: m.run(f"(evidence {e['claim']} {e['source']} {e['obs']} {e['age']})")
    if sc.get("condition"): m.run(f"(condition {t} {sc['condition']['value']} {sc['condition']['test']})")
    if t in mem["learned"]:
        l = mem["learned"][t]; m.run(f"(learned-rule {t} {l['type']} {l['value']} {l['cond']})")
    emit("assert", f"Agent A ({sc['personas']['A']}) claims {t} = {cl['A']['value']}", agent="A")
    emit("assert", f"Agent B ({sc['personas']['B']}) claims {t} = {cl['B']['value']}", agent="B")
    conflict = cl["A"]["value"] != cl["B"]["value"]
    emit("conflict", "CONFLICT DETECTED" if conflict else "No conflict: agents agree")
    for ag in "AB":
        for e in sc["evidence"]:
            if e["claim"] == cl[ag]["id"]:
                age = e["age"]
                src = e["source"]
                emit("challenge", f"{ag} evidence: {src} '{e['obs']}' age {age}d "
                     f"-> reliability {mem['reliability'][src]}, recency {num(q(m, f'(rec {age})')):.1f}", agent=ag)
    for ag in "AB":
        la = num(q(m, f"(lens {ag} {cl['A']['id']})")); lb = num(q(m, f"(lens {ag} {cl['B']['id']})"))
        emit("lens", f"Lens {ag} ({sc['personas'][ag]}): claim A={la:.2f}, claim B={lb:.2f} -> prefers {'A' if la > lb else 'B' if lb > la else 'neither'}", agent=ag)
    sa = num(q(m, f"(support {cl['A']['id']})")); sb = num(q(m, f"(support {cl['B']['id']})"))
    emit("weigh", f"support(A)={sa:.2f}  support(B)={sb:.2f}  [avg of both agents' lenses]", sa=sa, sb=sb)
    d = str(q(m, f"(decide {t} {cl['A']['id']} {cl['B']['id']} {sa} {sb})")).strip("()").split()
    rule_hit = t in mem["learned"]
    if d[0] == "learned":
        d = ["conditional", d[2], d[3]] if d[1] == "conditional" else ["applied", d[2]]
    kind = d[0]; resolution = {"type": kind}
    if rule_hit: emit("rule", f"Learned rule from a previous run applied -> converged without re-arguing")
    if kind == "concede":
        loser, wid = d[1], d[2]
        win = "B" if loser == "A" else "A"
        val = cl[win]["value"]
        resolution.update(value=val, text=f"Agent {loser} concedes to Agent {win}: {t} = {val}")
        if not rule_hit:
            for e in sc["evidence"]:
                dl = 0.05 if e["claim"] == cl[win]["id"] else -0.05
                new = num(q(m, f"(adjust {mem['reliability'][e['source']]} {dl})"))
                if abs(new - mem["reliability"][e["source"]]) > 1e-9:
                    mem["diffs"].append({"what": f"reliability[{e['source']}]", "old": mem["reliability"][e["source"]], "new": round(new, 3)})
                    mem["reliability"][e["source"]] = round(new, 3)
            mem["learned"][t] = {"type": "concede", "value": val, "cond": "none"}
            mem["diffs"].append({"what": f"rule[{t}]", "old": None, "new": f"concede -> {val}"})
    elif kind == "conditional":
        val, cond = d[1], d[2]
        resolution.update(value=val, cond=cond, text=f"Conditional truth: {t} = {val}, subject to {cond}; otherwise follow the other agent's claim")
        if not rule_hit:
            mem["learned"][t] = {"type": "conditional", "value": val, "cond": cond}
            mem["diffs"].append({"what": f"rule[{t}]", "old": None, "new": f"conditional {val} if {cond}"})
    elif kind == "applied":
        resolution.update(type="concede", value=d[1], text=f"Both agents apply the learned rule: {t} = {d[1]} (no re-argument needed)")
    elif kind == "escalate":
        resolution["text"] = "Scores too close and no condition known: ESCALATED to a human reviewer"
    emit("resolve", resolution["text"], resolution=resolution)
    mem["runs"] += 1; save_mem(mem)
    narr = narrate(ev)
    return {"scenario": sid, "events": ev, "resolution": resolution, "narrative": narr,
            "rule_hit": rule_hit, "memory": mem, "topic": t, "scenario_def": sc}

def human(topic, value):
    mem = load_mem(); t = sym(topic); value = sym(value)
    mem["learned"][t] = {"type": "concede", "value": value, "cond": "human"}
    mem["diffs"].append({"what": f"rule[{t}]", "old": None, "new": f"human decision -> {value}"})
    save_mem(mem); return mem

def narrate(ev):
    """Optional LLM prose; falls back to a template. LLM never decides anything."""
    trace = "\n".join(e["text"] for e in ev)
    key, base, model = os.getenv("LLM_KEY"), os.getenv("LLM_BASE_URL"), os.getenv("LLM_MODEL")
    if key and base and model:
        try:
            import urllib.request
            body = json.dumps({"model": model, "temperature": 0, "messages": [
                {"role": "system", "content": "Explain this symbolic reasoning trace in 3 plain sentences. Do not change the outcome."},
                {"role": "user", "content": trace}]}).encode()
            r = urllib.request.Request(base.rstrip("/") + "/chat/completions", body,
                {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(r, timeout=15))["choices"][0]["message"]["content"]
        except Exception:
            pass
    return "Final: " + ev[-1]["text"] + ". (Template narration; set LLM_KEY/LLM_BASE_URL/LLM_MODEL for LLM prose.)"


import re
def sym(x, n=40):
    """Sanitize to a safe MeTTa symbol (blocks atom injection from free text)."""
    x = re.sub(r"[^a-z0-9_.<>%-]+", "-", str(x).lower()).strip("-")[:n]
    return x or "unknown"

def validate(sc):
    """Normalize a scenario dict (preloaded or LLM/user supplied) into safe symbols."""
    t = sym(sc["topic"]); out = {"id": sc.get("id") or "custom-" + t, "title": sc.get("title", t), "topic": t,
        "personas": sc.get("personas") or {"A": "Evidence Advocate", "B": "Skeptical Auditor"}, "claims": {}, "evidence": [], "reliability": {}}
    for ag in "AB": out["claims"][ag] = {"id": "c-" + ag.lower() + "-" + t, "value": sym(sc["claims"][ag]["value"])}
    ids = {sc["claims"][ag]["id"]: out["claims"][ag]["id"] for ag in "AB"}
    for e in sc["evidence"]:
        if e["claim"] not in ids: raise ValueError("evidence refers to unknown claim")
        src = sym(e["source"]); out["evidence"].append({"claim": ids[e["claim"]], "source": src, "obs": sym(e.get("obs", "obs")),
            "age": max(0, min(3650, int(float(e.get("age", 0)))))})
        r = sc.get("reliability", {}).get(e["source"], 0.6)
        out["reliability"][src] = max(0.05, min(0.98, float(r)))
    if not out["evidence"]: raise ValueError("no evidence")
    c = sc.get("condition")
    if c: out["condition"] = {"value": sym(c["value"]), "test": sym(c["test"])}
    return out

SCHEMA = ('Return ONLY JSON: {"topic":str,"claims":{"A":{"id":"a","value":str},"B":{"id":"b","value":str}},'
 '"evidence":[{"claim":"a"|"b","source":str,"obs":str,"age":days_int}],"reliability":{source:0..1},'
 '"condition":{"value":str,"test":str}|null}. Agent A is an evidence advocate holding one position; agent B a skeptical '
 'auditor holding the conflicting position. Use short kebab-case values. Do not decide who is right.')

def _llm_json(text):
    key, base, model = os.getenv("LLM_KEY"), os.getenv("LLM_BASE_URL"), os.getenv("LLM_MODEL")
    if not (key and base and model): return None
    import urllib.request
    for _ in range(2):  # retry once on malformed output
        try:
            body = json.dumps({"model": model, "temperature": 0, "messages": [
                {"role": "system", "content": SCHEMA}, {"role": "user", "content": text}]}).encode()
            r = urllib.request.Request(base.rstrip("/") + "/chat/completions", body,
                {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            raw = json.load(urllib.request.urlopen(r, timeout=30))["choices"][0]["message"]["content"]
            d = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            return validate(d)
        except Exception:
            continue
    return None

def parse_lines(text):
    """No-LLM fallback. Format: topic:/A:/B:/A evidence: source, obs, age /B evidence:/condition: value, test"""
    d = {"claims": {}, "evidence": [], "reliability": {}}
    for ln in text.splitlines():
        if ":" not in ln: continue
        k, v = [x.strip() for x in ln.split(":", 1)]; kl = k.lower()
        if kl == "topic": d["topic"] = v
        elif kl in ("a", "b"): d["claims"][k.upper()] = {"id": kl, "value": v}
        elif kl.endswith(" evidence"):
            p = [x.strip() for x in v.split(",")]
            d["evidence"].append({"claim": kl[0], "source": p[0], "obs": p[1] if len(p) > 1 else "obs", "age": p[2] if len(p) > 2 else 0})
            if len(p) > 3: d["reliability"][p[0]] = p[3]
        elif kl == "condition":
            p = [x.strip() for x in v.split(",")]; d["condition"] = {"value": p[0], "test": p[1]}
    if "topic" not in d or set(d["claims"]) != {"A", "B"}:
        raise ValueError("Could not parse. Use lines: topic: x / A: v / B: v / A evidence: source, obs, age / B evidence: ... / condition: value, test  (or configure an LLM)")
    return validate(d)

def intake(text):
    """Free text -> validated scenario. LLM first, line-format fallback. The LLM never decides."""
    return _llm_json(text) or parse_lines(text)
