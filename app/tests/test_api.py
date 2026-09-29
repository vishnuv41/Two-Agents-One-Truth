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

def test_get_agents_endpoint():
    response = client.get("/agents")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {a["id"] for a in data} == {"A", "B"}

def test_get_scenarios_endpoint():
    response = client.get("/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3

def test_post_run_preset_endpoint():
    response = client.post("/run/crop")
    assert response.status_code == 200
    data = response.json()
    assert "resolution" in data
    assert "events" in data

def test_memory_endpoints():
    client.post("/run/campus")
    
    res_mem = client.get("/memory")
    assert res_mem.status_code == 200
    
    res_search = client.get("/memory/search?q=library")
    assert res_search.status_code == 200
    
    res_ctx = client.get("/memory/library-hours")
    assert res_ctx.status_code == 200
    
    res_topic = client.get("/memory/library-hours/library-hours")
    assert res_topic.status_code == 200

def test_runs_endpoints():
    r = client.post("/run/crop")
    run_id = r.json()["run_id"]
    
    runs_res = client.get("/runs")
    assert runs_res.status_code == 200
    assert any(x["run_id"] == run_id for x in runs_res.json())
    
    detail_res = client.get(f"/runs/{run_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["run_id"] == run_id

def test_conflict_post_endpoint():
    payload = {"text": "topic: sow\ncontext: agriculture\nA: now\nB: wait-7d\nA evidence: govt-calendar, window-open, 25, 0.8\nB evidence: soil-sensor, moisture-24pct, 1, 0.7"}
    response = client.post("/conflict", json=payload)
    assert response.status_code == 200
    assert "resolution" in response.json()

def test_human_escalation_endpoint():
    response = client.post("/human/max-temp/85c?context=electronics")
    assert response.status_code == 200
    mem = response.json()
    assert "ctx" in mem
