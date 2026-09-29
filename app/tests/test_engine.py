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
