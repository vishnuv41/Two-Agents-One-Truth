"""Orchestrator. Python only moves data; every decision comes from core/weigh.metta."""
import json, os, copy
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
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

from core import memory

def load_mem():
    return memory.load_mem()

def save_mem(m):
    memory.save_mem(m)

def reset():
    memory.reset()

def q(m, expr):
    r = m.run("!" + expr)
    return r[0][0] if r and r[0] else None

def num(a): return float(str(a))
import time
ROUND = {"assert": 1, "conflict": 1, "challenge": 2, "lens": 3, "weigh": 3, "rule": 4, "resolve": 4, "learn": 5}

def run(sid): return run_scenario(scenarios()[sid])

def run_scenario(sc):
    """5 rounds: assert, challenge, weigh, resolve, learn. Every decision is a MeTTa query."""
    sc = validate(sc); t = sc["topic"]; ctx = sc["context"]; cl = sc["claims"]
    mem = load_mem(); cm = mem["ctx"].setdefault(ctx, {"reliability": {}, "reliability_history": {}, "learned": {}}); ev = []; diffs = []
    def emit(kind, text, **kw): ev.append({"kind": kind, "round": ROUND[kind], "text": text, **kw})
    for s, r in sc["reliability"].items(): cm["reliability"].setdefault(s, r)
    save_mem(mem)
    m = MeTTa(); m.run(open(os.path.join(ROOT, "core", "weigh.metta")).read())
    for s, r in cm["reliability"].items(): m.run(f"(reliability {s} {r})")
    for ag, c in cl.items(): m.run(f"(claim {ag} {t} {c['value']} {c['id']})")
    for x in sc["evidence"]: m.run(f"(evidence {x['claim']} {x['source']} {x['obs']} {x['age']} {x['directness']})")
    if sc.get("condition"): m.run(f"(condition {t} {sc['condition']['value']} {sc['condition']['test']})")
    rule_hit = t in cm["learned"]
    if rule_hit:
        l = cm["learned"][t]; m.run(f"(learned-rule {t} {l['type']} {l['value']} {l['cond']})")
    for ag in "AB": emit("assert", f"Agent {ag} ({sc['personas'][ag]}) claims {t} = {cl[ag]['value']}", agent=ag)
    for ag in "AB":
        opp = "B" if ag == "A" else "A"
        for x in sc["evidence"]:
            if x["claim"] == cl[opp]["id"]:
                age = x["age"]
                src = x["source"]
                rel = cm["reliability"].get(src, 0.6)
                rec = num(q(m, f'(rec {age})'))
                if age > 7:
                    emit("challenge", f"Agent {ag} challenges Agent {opp}: source '{src}' is {age}d old (recency {rec:.1f}); current conditions may differ", agent=ag)
                elif rel < 0.8:
                    emit("challenge", f"Agent {ag} challenges Agent {opp}: source '{src}' has lower reliability rating ({rel:.2f})", agent=ag)
                else:
                    emit("challenge", f"Agent {ag} challenges Agent {opp}: evidence '{src}' ({x['obs']}) evaluated under {ag}'s lens", agent=ag)
    for ag in "AB":
        la = num(q(m, f"(lens {ag} {cl['A']['id']})")); lb = num(q(m, f"(lens {ag} {cl['B']['id']})"))
        emit("lens", f"Lens {ag} ({sc['personas'][ag]}): claim A={la:.2f}, claim B={lb:.2f} -> prefers {'A' if la > lb else 'B' if lb > la else 'neither'}", agent=ag)
    sa = num(q(m, f"(support {cl['A']['id']})")); sb = num(q(m, f"(support {cl['B']['id']})"))
    emit("weigh", f"support(A)={sa:.2f}  support(B)={sb:.2f}  [avg of both agents' lenses]", sa=sa, sb=sb)
    d = str(q(m, f"(verdict {cl['A']['value']} {cl['B']['value']} {t} {cl['A']['id']} {cl['B']['id']} {sa} {sb})")).strip("()").split()
    if d[0] == "learned": d = ["conditional", d[2], d[3]] if d[1] == "conditional" else ["applied", d[2]]
    kind = d[0]; res = {"type": kind}
    emit("conflict", "No conflict: both agents agree" if kind == "agree" else "CONFLICT DETECTED")
    if rule_hit and kind in ("conditional", "applied"): emit("rule", "Learned rule from an earlier run applied: converged without re-arguing")
    run_id = memory.generate_run_id()
    def learn_rule(ty, val, cond):
        rule_rec = memory.record_learned_rule(ctx, t, ty, val, cond, run_id)
        ver = rule_rec["version"]
        diffs.append({"what": f"rule[{ctx}/{t}] v{ver}", "old": (cm["learned"].get(t) or {}).get("type") and f"{cm['learned'][t]['type']} {cm['learned'][t]['value']}", "new": f"{ty} {val} ({cond})"})
    if kind == "agree":
        res.update(
            reason="identical_claims",
            accepted_agent=None,
            accepted_claim=cl["A"]["value"],
            value=cl["A"]["value"],
            text=f"Agents already agree: {t} = {cl['A']['value']}"
        )
    elif kind == "concede":
        loser = d[1]; win = "B" if loser == "A" else "A"; val = cl[win]["value"]
        res.update(
            reason="support_margin_exceeded",
            accepted_agent=win,
            accepted_claim=val,
            value=val,
            text=f"Agent {loser} concedes to Agent {win}: {t} = {val}"
        )
        for x in sc["evidence"]:
            dl = 0.05 if x["claim"] == cl[win]["id"] else -0.05; old = cm["reliability"][x["source"]]
            new = round(num(q(m, f"(adjust {old} {dl})")), 3)
            if new != old:
                memory.update_source_reliability(ctx, x["source"], old, new, run_id)
                diffs.append({"what": f"reliability[{ctx}/{x['source']}]", "old": old, "new": new})
        learn_rule("concede", val, "none")
    elif kind == "conditional":
        res.update(
            reason="condition_applied",
            accepted_agent=None,
            accepted_claim=d[1],
            value=d[1],
            cond=d[2],
            text=f"Conditional truth: {t} = {d[1]} if {d[2]}; otherwise follow the other agent's claim"
        )
        if not rule_hit: learn_rule("conditional", d[1], d[2])
    elif kind == "applied":
        res.update(
            type="concede",
            reason="applied_learned_rule",
            accepted_agent=None,
            accepted_claim=d[1],
            value=d[1],
            text=f"Both agents apply the learned rule: {t} = {d[1]}"
        )
    else:
        reason_code = "insufficient_evidence" if kind == "escalate-missing" else "support_margin_close"
        res.update(
            type="escalate",
            reason=reason_code,
            accepted_agent=None,
            accepted_claim=None,
            text=("One side has no evidence" if kind == "escalate-missing" else "Scores too close and no usable condition") + ": ESCALATED to a human reviewer"
        )
    emit("resolve", res["text"], resolution=res)
    emit("learn", "; ".join(f"{x['what']}: {x['old']} -> {x['new']}" for x in diffs) or "Nothing new to learn (memory unchanged)")
    memory.record_run(run_id, ctx, t, res, sc)
    mem = load_mem()
    return {"run_id": run_id, "scenario": sc["id"], "events": ev, "resolution": res, "narrative": narrate(ev), "rule_hit": rule_hit,
            "memory": mem, "topic": t, "context": ctx, "scenario_def": sc}

def human(topic, value, context=None):
    mem = load_mem(); t = sym(topic); value = sym(value)
    ctx = sym(context) if context else next((c for c, v in mem["ctx"].items() if t in v.get("learned", {})), t)
    run_id = memory.generate_run_id()
    memory.record_learned_rule(ctx, t, "concede", value, "human", run_id)
    return load_mem()

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
    t = sym(sc["topic"]); out = {"id": sc.get("id") or "custom-" + t, "title": sc.get("title", t), "topic": t, "context": sym(sc.get("context") or t),
        "personas": sc.get("personas") or {"A": "Evidence Advocate", "B": "Skeptical Auditor"}, "claims": {}, "evidence": [], "reliability": {}}
    for ag in "AB": out["claims"][ag] = {"id": "c-" + ag.lower() + "-" + t, "value": sym(sc["claims"][ag]["value"])}
    ids = {sc["claims"][ag]["id"]: out["claims"][ag]["id"] for ag in "AB"}
    for e in sc["evidence"]:
        if e["claim"] not in ids: raise ValueError("evidence refers to unknown claim")
        src = sym(e["source"])
        directness = round(max(0.1, min(1.0, float(e.get("directness", 1.0)))), 2)
        out["evidence"].append({"claim": ids[e["claim"]], "source": src, "obs": sym(e.get("obs", "obs")),
            "age": max(0, min(3650, int(float(e.get("age", 0))))), "directness": directness})
        r = sc.get("reliability", {}).get(e["source"], 0.6)
        out["reliability"][src] = max(0.05, min(0.98, float(r)))
    if not out["evidence"]: raise ValueError("no evidence")
    c = sc.get("condition")
    if c:
        val = sym(c["value"])
        valid_vals = {out["claims"]["A"]["value"], out["claims"]["B"]["value"]}
        if val not in valid_vals:
            val = out["claims"]["B"]["value"]
        out["condition"] = {"value": val, "test": sym(c["test"])}
    return out

SCHEMA = ('Return ONLY JSON: {"topic":str,"context":short-domain-kebab (e.g. college,electronics),"claims":{"A":{"id":"a","value":str},"B":{"id":"b","value":str}},'
 '"evidence":[{"claim":"a"|"b","source":str,"obs":str,"age":days_int}],"reliability":{source:0..1},'
 '"condition":{"value":str,"test":str}|null}. Agent A is an evidence advocate holding one position; agent B a skeptical '
 'auditor holding the conflicting position. Use descriptive kebab-case strings for claims and condition values (e.g. "environmentally-preferable", "lifecycle-emissions-lower"). Do not decide who is right.')

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
        elif kl == "context": d["context"] = v
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
    if not text or len(text.strip().split()) < 3:
        return parse_lines(text)
    return _llm_json(text) or parse_lines(text)
