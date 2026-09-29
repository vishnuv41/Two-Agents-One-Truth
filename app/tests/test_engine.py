import pytest
from core import engine
@pytest.fixture(autouse=True)
def fresh(): engine.reset(); yield; engine.reset()
def test_conditional(): assert engine.run("crop")["resolution"]["type"] == "conditional"
def test_concede(): assert engine.run("campus")["resolution"]["type"] == "concede"
def test_escalate(): assert engine.run("tie")["resolution"]["type"] == "escalate"
def test_second_run_uses_learned_rule():
    engine.run("campus"); r2 = engine.run("campus")
    assert r2["rule_hit"] and engine.load_mem()["diffs"]
def test_agents_use_different_lenses():
    kinds = [e["kind"] for e in engine.run("crop")["events"]]
    assert kinds.count("lens") == 2
def test_text_intake_and_injection_safe():
    sc = engine.intake("topic: sow)(evidence x\nA: now\nB: wait\nA evidence: cal, window, 20, 0.9\nB evidence: soil, dry, 1, 0.7\ncondition: wait, dry")
    assert ")" not in sc["topic"] and engine.run_scenario(sc)["resolution"]["type"] in ("conditional", "concede")
def test_bad_text_rejected():
    import pytest as p
    with p.raises(ValueError): engine.intake("hello")

def T(topic, a, b, ea, eb, cond=None, ctx=None, ra=0.8, rb=0.8):
    d = {"topic": topic, "context": ctx or topic, "claims": {"A": {"id": "a", "value": a}, "B": {"id": "b", "value": b}},
         "evidence": [dict(claim="a", **x) for x in ea] + [dict(claim="b", **x) for x in eb],
         "reliability": {x["source"]: ra for x in ea} | {x["source"]: rb for x in eb}}
    if cond: d["condition"] = {"value": cond[0], "test": cond[1]}
    return d
E = lambda s, age, o="o": {"source": s, "obs": o, "age": age}
def kind(sc): return engine.run_scenario(sc)["resolution"]["type"]

def test_matrix_strong_a_and_b():
    assert kind(T("t1", "x", "y", [E("m1", 1), E("m2", 2)], [E("w", 400)])) == "concede"
    r = engine.run_scenario(T("t2", "x", "y", [E("p", 400)], [E("q", 1), E("r", 2)]))
    assert "concedes" in r["resolution"]["text"]
def test_matrix_close_condition_vs_none():
    assert kind(T("t3", "85c", "75c", [E("spec", 20)], [E("test", 20)], cond=("75c", "failures-above-75c"))) == "conditional"
    assert kind(T("t4", "x", "y", [E("s1", 20)], [E("s2", 20)])) == "escalate"
def test_matrix_same_claim_no_conflict():
    assert kind(T("t5", "friday", "friday", [E("web", 3)], [E("notice", 3)])) == "agree"
def test_matrix_missing_evidence_escalates():
    assert kind(T("t6", "x", "y", [E("s1", 3)], [])) == "escalate"
def test_matrix_human_then_memory():
    engine.run_scenario(T("t7", "x", "y", [E("s1", 20)], [E("s2", 20)]))
    engine.human("t7", "x"); r = engine.run_scenario(T("t7", "x", "y", [E("s1", 20)], [E("s2", 20)]))
    assert r["rule_hit"] and r["resolution"]["value"] == "x"
def test_matrix_new_domains_generic():
    for i, (a, b, ctx) in enumerate([("85c", "75c", "electronics"), ("fri", "thu", "college"), ("monolith", "microservices", "software")]):
        assert kind(T(f"d{i}", a, b, [E("official", 5)], [E("field", 2), E("field", 3)], ctx=ctx)) in ("concede", "conditional", "escalate")
def test_context_scoping():
    engine.run_scenario(T("u1", "x", "y", [E("official", 2)], [E("field", 400)], ctx="c1"))
    mem = engine.load_mem(); assert "official" in mem["ctx"]["c1"]["reliability"]
    engine.run_scenario(T("u2", "x", "y", [E("official", 2)], [E("field", 400)], ctx="c2"))
    assert engine.load_mem()["ctx"]["c2"]["reliability"]["official"] == 0.8  # c1 learning did not leak
def test_five_rounds():
    assert {e["round"] for e in engine.run("crop")["events"]} == {1, 2, 3, 4, 5}
def test_malformed_input():
    import pytest as p
    with p.raises(Exception): engine.validate({"topic": "x", "claims": {}, "evidence": []})

def test_agent_system():
    from core import agents
    agent_list = agents.list_agents()
    assert len(agent_list) == 2
    ids = {a["id"] for a in agent_list}
    assert ids == {"A", "B"}
    assert agents.get_agent("A")["name"] == "Evidence Advocate"
    assert agents.get_agent("B")["name"] == "Skeptical Auditor"

def test_resolution_agree():
    res = engine.run_scenario(T("st1", "friday", "friday", [E("web", 1)], [E("notice", 1)]))["resolution"]
    assert res["type"] == "agree" and res["reason"] == "identical_claims" and res["accepted_claim"] == "friday"

def test_resolution_concede():
    res = engine.run_scenario(T("st2", "x", "y", [E("m1", 1), E("m2", 2)], [E("w", 400)]))["resolution"]
    assert res["type"] == "concede" and res["reason"] == "support_margin_exceeded" and res["accepted_agent"] == "A"

def test_resolution_conditional():
    res = engine.run_scenario(T("st3", "85c", "75c", [E("spec", 20)], [E("test", 20)], cond=("75c", "failures-above-75c")))["resolution"]
    assert res["type"] == "conditional" and res["reason"] == "condition_applied" and res["accepted_claim"] == "75c"

def test_resolution_escalate():
    res = engine.run_scenario(T("st4", "x", "y", [E("s1", 20)], [E("s2", 20)]))["resolution"]
    assert res["type"] == "escalate" and res["reason"] == "support_margin_close" and res["accepted_agent"] is None

def test_resolution_insufficient_evidence():
    res = engine.run_scenario(T("st5", "x", "y", [E("s1", 3)], []))["resolution"]
    assert res["type"] == "escalate" and res["reason"] == "insufficient_evidence"

def test_resolution_output_schema():
    res = engine.run_scenario(T("st6", "a", "b", [E("s1", 1)], [E("s2", 2)]))["resolution"]
    for key in ("type", "reason", "text"):
        assert key in res

def test_memory_save_and_retrieve():
    from core import memory
    mem = memory.load_mem()
    assert "ctx" in mem and "runs" in mem

def test_memory_context_lookup():
    from core import memory
    engine.run_scenario(T("mct1", "a", "b", [E("s1", 1)], [E("s2", 200)], ctx="space"))
    ctx_mem = memory.get_context_memory("space")
    assert "s1" in ctx_mem["reliability"]

def test_memory_topic_lookup():
    from core import memory
    engine.run_scenario(T("mtp1", "a", "b", [E("m1", 1), E("m2", 2)], [E("w", 400)], ctx="space"))
    topic_mem = memory.get_topic_memory("space", "mtp1")
    assert topic_mem is not None and topic_mem["value"] == "a"

def test_memory_search():
    from core import memory
    engine.run_scenario(T("msh1", "a", "b", [E("m1", 1), E("m2", 2)], [E("w", 400)], ctx="weather"))
    results = memory.search_memory("weather")
    assert len(results) > 0

def test_runs_history_and_get():
    from core import memory
    r = engine.run_scenario(T("mrh1", "a", "b", [E("s1", 1)], [E("s2", 2)]))
    run_id = r["run_id"]
    runs = memory.get_runs()
    assert any(x["run_id"] == run_id for x in runs)
    run_detail = memory.get_run(run_id)
    assert run_detail is not None and run_detail["topic"] == "mrh1"

def test_memory_reliability_history():
    from core import memory
    engine.run_scenario(T("mrh2", "a", "b", [E("m1", 1), E("m2", 2)], [E("w", 400)], ctx="finance"))
    ctx_mem = memory.get_context_memory("finance")
    assert "m1" in ctx_mem.get("reliability_history", {})

def test_memory_versioning():
    from core import memory
    engine.run_scenario(T("mver1", "a", "b", [E("m1", 1), E("m2", 2)], [E("w", 400)], ctx="health"))
    t1 = memory.get_topic_memory("health", "mver1")
    assert t1["version"] == 1



