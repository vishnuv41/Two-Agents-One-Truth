import pytest
from fastapi.testclient import TestClient
from app import app
from core import engine

client = TestClient(app)

@pytest.fixture(autouse=True)
def fresh():
    engine.reset()
    yield
    engine.reset()

def test_e2e_conflict_to_resolution():
    """Journey 1: Normal conflict submission via REST API -> 5 rounds -> structured resolution & trace."""
    text = (
        "topic: crop-sow\n"
        "context: agriculture\n"
        "A: now\n"
        "B: wait-7d\n"
        "A evidence: govt-calendar, window-open, 25, 0.8\n"
        "B evidence: soil-sensor, moisture-24pct, 1, 0.7\n"
        "condition: wait-7d, moisture-below-30pct"
    )
    response = client.post("/conflict", json={"text": text})
    assert response.status_code == 200
    data = response.json()

    # Response schema checks
    assert "run_id" in data
    assert "events" in data
    assert "resolution" in data
    assert "memory" in data
    assert "narrative" in data
    assert data["topic"] == "crop-sow"
    assert data["context"] == "agriculture"

    # Resolution state machine verification
    res = data["resolution"]
    assert res["type"] in ("concede", "conditional", "escalate")
    assert "text" in res
    assert "reason" in res

    # 5 rounds verification
    rounds = {e["round"] for e in data["events"]}
    assert rounds == {1, 2, 3, 4, 5}

def test_e2e_close_conflict_to_human():
    """Journey 2: Equal evidence conflict escalates -> Human decision submitted -> Rule learned."""
    # Scenario with identical evidence strength -> triggers ESCALATE
    text = (
        "topic: deploy-schedule\n"
        "context: devops\n"
        "A: friday-deploy\n"
        "B: monday-deploy\n"
        "A evidence: dev-team, lead-vote, 5, 0.8\n"
        "B evidence: ops-team, lead-vote, 5, 0.8"
    )
    response = client.post("/conflict", json={"text": text})
    assert response.status_code == 200
    data = response.json()
    assert data["resolution"]["type"] == "escalate"

    # Human decision override
    human_res = client.post("/human/deploy-schedule/monday-deploy?context=devops")
    assert human_res.status_code == 200
    mem = human_res.json()
    assert "monday-deploy" in str(mem["ctx"]["devops"]["learned"])

    # Subsequent run applies human decision
    run2 = client.post("/conflict", json={"text": text}).json()
    assert run2["rule_hit"] is True
    assert run2["resolution"]["value"] == "monday-deploy"

def test_e2e_conflict_to_memory_and_learned_rule():
    """Journey 3: Run 1 learns rule -> Run 2 in same context hits learned rule."""
    text = (
        "topic: lib-close\n"
        "context: campus\n"
        "A: closes-8pm\n"
        "B: closes-10pm\n"
        "A evidence: website, info-page, 150, 0.9\n"
        "B evidence: poster, door-notice, 1, 0.8\n"
        "B evidence: report, student-survey, 2, 0.8"
    )
    r1 = client.post("/conflict", json={"text": text}).json()
    assert r1["rule_hit"] is False

    r2 = client.post("/conflict", json={"text": text}).json()
    assert r2["rule_hit"] is True
    assert r2["resolution"]["reason"] == "applied_learned_rule"

def test_e2e_context_isolation():
    """Journey 4: Learning in domain 'software' does not leak into domain 'hardware'."""
    sw_text = (
        "topic: version-compat\n"
        "context: software\n"
        "A: py312-ok\n"
        "B: py311-only\n"
        "A evidence: docs, official-doc, 1, 0.9\n"
        "A evidence: ci, test-pass, 2, 0.9\n"
        "B evidence: forum, user-post, 100, 0.5"
    )
    hw_text = (
        "topic: version-compat\n"
        "context: hardware\n"
        "A: py312-ok\n"
        "B: py311-only\n"
        "A evidence: datasheet, spec, 200, 0.5\n"
        "B evidence: bench, lab-test, 1, 0.9"
    )
    r_sw = client.post("/conflict", json={"text": sw_text}).json()
    assert r_sw["resolution"]["accepted_claim"] == "py312-ok"

    # Running hw_text (same topic name, different context) should not hit software's learned rule
    r_hw = client.post("/conflict", json={"text": hw_text}).json()
    assert r_hw["rule_hit"] is False
    assert r_hw["context"] == "hardware"

def test_e2e_invalid_conflict():
    """Journey 5: Non-conflict input or bad schema gets REJECTED with 400 error."""
    # Invalid line format text missing required claims/evidence
    res1 = client.post("/conflict", json={"text": "invalid"})
    assert res1.status_code == 400
    assert "error" in res1.json()

    # Completely invalid/empty payload
    res2 = client.post("/conflict", json={"text": ""})
    assert res2.status_code == 400

def test_e2e_new_domain():
    """Journey 6: Unseen domain (e.g. Python 3.12 compatibility) resolves dynamically without preloaded files."""
    text = (
        "topic: python-compat\n"
        "context: runtime-env\n"
        "A: supports-312\n"
        "B: supports-311-max\n"
        "A evidence: official-release, release-notes, 2, 0.95\n"
        "A evidence: github-actions, green-build, 1, 0.95\n"
        "B evidence: legacy-blog, forum-thread, 400, 0.4"
    )
    res = client.post("/conflict", json={"text": text})
    assert res.status_code == 200
    data = res.json()
    assert data["context"] == "runtime-env"
    assert data["resolution"]["type"] == "concede"
    assert data["resolution"]["accepted_agent"] == "A"
    assert "python" in data["resolution"]["accepted_claim"] or "3" in data["resolution"]["accepted_claim"]

def test_e2e_omega_user_journey():
    """Journey 7: Complete Omega user path: REST API -> OmegaRuntime -> plugin -> bridge -> MeTTa -> Memory -> response."""
    # 1. Discover skills via API
    skills_res = client.get("/omega/skills")
    assert skills_res.status_code == 200
    assert any(s["name"] == "negotiate" for s in skills_res.json())

    # 2. Invoke negotiate skill via API
    text = (
        "topic: max-temp\n"
        "context: electronics\n"
        "A: 85c-ok\n"
        "B: unsafe-above-75c\n"
        "A evidence: manufacturer-spec, datasheet, 300, 0.8\n"
        "B evidence: field-test, failures-at-75c, 4, 0.7\n"
        "condition: unsafe-above-75c, ambient-above-75c"
    )
    invoke_res = client.post("/omega/invoke", json={"skill": "negotiate", "argument": text})
    assert invoke_res.status_code == 200
    result_text = invoke_res.json()["result"]
    assert "RESOLUTION:" in result_text
    assert "TRACE:" in result_text

    # 3. Verify memory recorded the run
    runs_res = client.get("/runs")
    assert runs_res.status_code == 200
    runs = runs_res.json()
    assert len(runs) > 0
