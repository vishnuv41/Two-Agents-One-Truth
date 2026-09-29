import os
import sqlite3
import pytest
from core import engine
from core.sqlite_store import SQLiteStore, DB_FILE

@pytest.fixture(autouse=True)
def fresh():
    engine.reset()
    yield
    engine.reset()

def test_sqlite_auto_creation():
    """Verify SQLite database file and tables are initialized automatically."""
    assert os.path.exists(DB_FILE)
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    conn.close()
    expected = {"runs", "claims", "evidence", "learned_rules", "source_reliability", "reliability_history", "human_decisions"}
    assert expected.issubset(tables)

def test_sqlite_crud_operations():
    """Verify CRUD methods on SQLiteStore."""
    store = SQLiteStore()
    run_id = store.generate_run_id()
    sc = {"id": "test_sc", "claims": {"A": {"value": "x"}, "B": {"value": "y"}}, "evidence": []}
    res = {"type": "concede", "reason": "margin", "accepted_agent": "A", "accepted_claim": "x", "value": "x"}

    rec = store.record_run(run_id, "test_ctx", "test_topic", res, sc)
    assert rec["run_id"] == run_id

    rule = store.record_learned_rule("test_ctx", "test_topic", "concede", "x", "none", run_id)
    assert rule["version"] == 1
    assert rule["value"] == "x"

    topic_mem = store.get_topic_memory("test_ctx", "test_topic")
    assert topic_mem is not None
    assert topic_mem["value"] == "x"

def test_process_restart_persistence(tmp_path):
    """Critical Process Restart Simulation:
    Process 1 writes to SQLite DB -> Process 2 initializes fresh store on same DB -> verifies persistence across process boundary.
    """
    db_path = str(tmp_path / "test_restart.db")

    # Process 1: Initialize store & write learned rule
    store1 = SQLiteStore(db_path=db_path)
    run_id = store1.generate_run_id()
    store1.record_learned_rule("agriculture", "sow", "conditional", "wait-7d", "moisture-below-30pct", run_id)
    store1.update_source_reliability("agriculture", "soil-sensor", 0.7, 0.75, run_id)

    # Process 2: Brand new store instance on same DB file
    store2 = SQLiteStore(db_path=db_path)
    mem2 = store2.load_mem()

    assert "agriculture" in mem2["ctx"]
    assert mem2["ctx"]["agriculture"]["reliability"]["soil-sensor"] == 0.75
    topic_rule = store2.get_topic_memory("agriculture", "sow")
    assert topic_rule is not None
    assert topic_rule["value"] == "wait-7d"
    assert topic_rule["version"] == 1

def test_sqlite_rule_versioning(tmp_path):
    """Verify rule version increments upon update."""
    db_path = str(tmp_path / "test_ver.db")
    store = SQLiteStore(db_path=db_path)

    r1 = store.record_learned_rule("ctx1", "top1", "concede", "v1_val", "none", "run1")
    assert r1["version"] == 1

    r2 = store.record_learned_rule("ctx1", "top1", "concede", "v2_val", "none", "run2")
    assert r2["version"] == 2

    latest = store.get_topic_memory("ctx1", "top1")
    assert latest["version"] == 2
    assert latest["value"] == "v2_val"

def test_sqlite_context_isolation(tmp_path):
    """Verify learned rules are isolated by context in SQLite."""
    db_path = str(tmp_path / "test_iso.db")
    store = SQLiteStore(db_path=db_path)

    store.record_learned_rule("ctx_alpha", "same_topic", "concede", "val_alpha", "none", "run1")
    store.record_learned_rule("ctx_beta", "same_topic", "concede", "val_beta", "none", "run2")

    rule_alpha = store.get_topic_memory("ctx_alpha", "same_topic")
    rule_beta = store.get_topic_memory("ctx_beta", "same_topic")

    assert rule_alpha["value"] == "val_alpha"
    assert rule_beta["value"] == "val_beta"

def test_sqlite_human_decision_record(tmp_path):
    """Verify human escalation decision is persisted in human_decisions table."""
    db_path = str(tmp_path / "test_human.db")
    store = SQLiteStore(db_path=db_path)
    run_id = store.generate_run_id()

    store.record_learned_rule("electronics", "max-temp", "concede", "75c", "human", run_id)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT topic, context, decision FROM human_decisions WHERE run_id = ?", (run_id,))
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "max-temp"
    assert row[1] == "electronics"
    assert row[2] == "75c"

def test_sqlite_relational_tables(tmp_path):
    """Verify relational claims and evidence entries in SQLite database."""
    db_path = str(tmp_path / "test_rel.db")
    store = SQLiteStore(db_path=db_path)

    sc = {
        "id": "rel_scenario",
        "topic": "rel_topic",
        "claims": {
            "A": {"id": "c_a", "value": "val_a"},
            "B": {"id": "c_b", "value": "val_b"}
        },
        "evidence": [
            {"claim": "c_a", "source": "src_1", "obs": "obs_1", "age": 5, "directness": 0.9}
        ]
    }
    run_id = store.generate_run_id()
    store.record_run(run_id, "rel_ctx", "rel_topic", {"type": "concede"}, sc)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM claims WHERE run_id = ?", (run_id,))
    claims_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM evidence WHERE claim_id = 'c_a'")
    evidence_count = cur.fetchone()[0]
    conn.close()

    assert claims_count == 2
    assert evidence_count == 1
