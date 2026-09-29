import pytest
from fastapi.testclient import TestClient
from core import engine
from core.omega import OmegaRuntime
from app import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def fresh():
    engine.reset()
    yield
    engine.reset()

def test_omega_runtime_skill_registration():
    rt = OmegaRuntime()
    skills = rt.list_skills()
    assert len(skills) >= 1
    neg_skill = next((s for s in skills if s["name"] == "negotiate"), None)
    assert neg_skill is not None
    assert neg_skill["status"] == "registered"

def test_omega_plugin_bridge_execution_preset():
    rt = OmegaRuntime()
    res = rt.invoke_skill("negotiate", "crop")
    assert "RESOLUTION:" in res
    assert "TRACE:" in res
    assert "sow" in res

def test_omega_plugin_bridge_execution_freetext():
    rt = OmegaRuntime()
    text = "topic: max-temp\ncontext: electronics\nA: 85c-ok\nB: unsafe-above-75c\nA evidence: manufacturer-spec, datasheet, 300, 0.8\nB evidence: field-test, failures-at-75c, 4, 0.7\ncondition: unsafe-above-75c, ambient-above-75c"
    res = rt.invoke_skill("negotiate", text)
    assert "RESOLUTION:" in res
    assert "TRACE:" in res
    assert "max-temp" in res

def test_omega_rest_endpoints():
    res_skills = client.get("/omega/skills")
    assert res_skills.status_code == 200
    skills = res_skills.json()
    assert any(s["name"] == "negotiate" for s in skills)

    res_invoke = client.post("/omega/invoke", json={"skill": "negotiate", "argument": "campus"})
    assert res_invoke.status_code == 200
    data = res_invoke.json()
    assert data["skill"] == "negotiate"
    assert "RESOLUTION:" in data["result"]
