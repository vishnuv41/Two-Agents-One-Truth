"""
SQLite Storage Engine for Two Agents, One Truth.
Handles persistent relational storage of runs, claims, evidence, learned rules, reliability histories, and human decisions.
"""
import os
import sqlite3
import json
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(ROOT, "memory")
DB_FILE = os.path.join(DB_DIR, "two_agents.db")

class SQLiteStore:
    """Manages SQLite database connection, table initialization, and CRUD operations."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_FILE
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_tables()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                context TEXT NOT NULL,
                topic TEXT NOT NULL,
                resolution_type TEXT,
                reason TEXT,
                accepted_agent TEXT,
                accepted_claim TEXT,
                value TEXT,
                timestamp INTEGER NOT NULL,
                scenario TEXT,
                resolution_json TEXT,
                scenario_def_json TEXT
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                topic TEXT NOT NULL,
                value TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                source TEXT NOT NULL,
                obs TEXT,
                age INTEGER,
                directness REAL,
                FOREIGN KEY(claim_id) REFERENCES claims(id)
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS learned_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context TEXT NOT NULL,
                topic TEXT NOT NULL,
                version INTEGER NOT NULL,
                rule_type TEXT NOT NULL,
                value TEXT NOT NULL,
                cond TEXT,
                created_from_run TEXT,
                timestamp INTEGER NOT NULL,
                UNIQUE(context, topic) ON CONFLICT REPLACE
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS source_reliability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context TEXT NOT NULL,
                source TEXT NOT NULL,
                reliability REAL NOT NULL,
                updated_at INTEGER NOT NULL,
                UNIQUE(context, source) ON CONFLICT REPLACE
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS reliability_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context TEXT NOT NULL,
                source TEXT NOT NULL,
                old_rel REAL NOT NULL,
                new_rel REAL NOT NULL,
                run_id TEXT,
                timestamp INTEGER NOT NULL
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS human_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                topic TEXT NOT NULL,
                context TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT,
                timestamp INTEGER NOT NULL
            );
            """)
            conn.commit()

    def save_mem(self, mem_data: dict):
        """Persist initial context reliability values passed in mem_data dictionary."""
        if not isinstance(mem_data, dict) or "ctx" not in mem_data:
            return
        now = int(time.time())
        with self._get_conn() as conn:
            cur = conn.cursor()
            for ctx, cm in mem_data.get("ctx", {}).items():
                for src, rel in cm.get("reliability", {}).items():
                    cur.execute("""
                    INSERT INTO source_reliability (context, source, reliability, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(context, source) DO UPDATE SET reliability=excluded.reliability
                    """, (ctx, src, float(rel), now))
            conn.commit()

    def reset(self):
        """Clear database tables."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM runs")
            cur.execute("DELETE FROM claims")
            cur.execute("DELETE FROM evidence")
            cur.execute("DELETE FROM learned_rules")
            cur.execute("DELETE FROM source_reliability")
            cur.execute("DELETE FROM reliability_history")
            cur.execute("DELETE FROM human_decisions")
            conn.commit()

    def generate_run_id(self) -> str:
        ts = time.strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:6]
        return f"run_{ts}_{uid}"

    def record_run(self, run_id: str, context: str, topic: str, resolution: dict, sc: dict) -> dict:
        now = int(time.time())
        record = {
            "run_id": run_id,
            "context": context,
            "topic": topic,
            "resolution_type": resolution.get("type"),
            "reason": resolution.get("reason"),
            "accepted_agent": resolution.get("accepted_agent"),
            "accepted_claim": resolution.get("accepted_claim"),
            "value": resolution.get("value"),
            "timestamp": now,
            "scenario": sc.get("id")
        }

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT OR REPLACE INTO runs 
            (run_id, context, topic, resolution_type, reason, accepted_agent, accepted_claim, value, timestamp, scenario, resolution_json, scenario_def_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, context, topic, resolution.get("type"), resolution.get("reason"),
                resolution.get("accepted_agent"), resolution.get("accepted_claim"),
                resolution.get("value"), now, sc.get("id"), json.dumps(resolution), json.dumps(sc)
            ))

            # Store claims & evidence relational items
            claims_def = sc.get("claims", {})
            for ag, cdata in claims_def.items():
                cid = cdata.get("id", f"{run_id}_{ag}")
                cur.execute("""
                INSERT OR REPLACE INTO claims (id, run_id, agent, topic, value)
                VALUES (?, ?, ?, ?, ?)
                """, (cid, run_id, ag, topic, cdata.get("value", "")))

            for ev in sc.get("evidence", []):
                eid = f"{ev.get('claim')}_{ev.get('source')}_{uuid.uuid4().hex[:4]}"
                cur.execute("""
                INSERT OR REPLACE INTO evidence (id, claim_id, source, obs, age, directness)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (eid, ev.get("claim"), ev.get("source"), ev.get("obs"), ev.get("age", 0), ev.get("directness", 1.0)))

            conn.commit()
        return record

    def update_source_reliability(self, context: str, source: str, old_rel: float, new_rel: float, run_id: str) -> dict:
        now = int(time.time())
        diff = {"what": f"reliability[{context}/{source}]", "old": old_rel, "new": new_rel, "run_id": run_id, "ts": now}
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT OR REPLACE INTO source_reliability (context, source, reliability, updated_at)
            VALUES (?, ?, ?, ?)
            """, (context, source, new_rel, now))

            cur.execute("""
            INSERT INTO reliability_history (context, source, old_rel, new_rel, run_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (context, source, old_rel, new_rel, run_id, now))
            conn.commit()
        return diff

    def record_learned_rule(self, context: str, topic: str, rule_type: str, value: str, cond: str, run_id: str) -> dict:
        now = int(time.time())
        old_rule = self.get_topic_memory(context, topic)
        ver = (old_rule["version"] + 1) if old_rule else 1

        rule_entry = {
            "context": context,
            "topic": topic,
            "version": ver,
            "type": rule_type,
            "value": value,
            "cond": cond,
            "created_from_run": run_id,
            "timestamp": now
        }

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO learned_rules (context, topic, version, rule_type, value, cond, created_from_run, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (context, topic, ver, rule_type, value, cond, run_id, now))

            # Record human decision if human source
            if cond == "human":
                cur.execute("""
                INSERT INTO human_decisions (run_id, topic, context, decision, reason, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (run_id, topic, context, value, f"Human selected {value}", now))

            conn.commit()
        return rule_entry

    def get_topic_memory(self, context: str, topic: str) -> dict:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
            SELECT context, topic, version, rule_type, value, cond, created_from_run, timestamp
            FROM learned_rules
            WHERE context = ? AND topic = ?
            ORDER BY version DESC LIMIT 1
            """, (context, topic))
            row = cur.fetchone()
            if row:
                return {
                    "context": row["context"],
                    "topic": row["topic"],
                    "version": row["version"],
                    "type": row["rule_type"],
                    "value": row["value"],
                    "cond": row["cond"],
                    "created_from_run": row["created_from_run"],
                    "timestamp": row["timestamp"]
                }
        return None

    def load_mem(self) -> dict:
        """Assembles full memory dict structure from SQLite tables for engine & API consumers."""
        ctx_data = {}
        runs = []
        diffs = []

        with self._get_conn() as conn:
            cur = conn.cursor()

            # Load reliability
            cur.execute("SELECT context, source, reliability FROM source_reliability")
            for r in cur.fetchall():
                cm = ctx_data.setdefault(r["context"], {"reliability": {}, "reliability_history": {}, "learned": {}})
                cm["reliability"][r["source"]] = r["reliability"]

            # Load reliability history & diffs
            cur.execute("SELECT context, source, old_rel, new_rel, run_id, timestamp FROM reliability_history ORDER BY timestamp ASC")
            for r in cur.fetchall():
                cm = ctx_data.setdefault(r["context"], {"reliability": {}, "reliability_history": {}, "learned": {}})
                hist = cm["reliability_history"].setdefault(r["source"], [])
                diff = {"what": f"reliability[{r['context']}/{r['source']}]", "old": r["old_rel"], "new": r["new_rel"], "run_id": r["run_id"], "ts": r["timestamp"]}
                hist.append(diff)
                diffs.append(diff)

            # Load learned rules
            cur.execute("SELECT context, topic, version, rule_type, value, cond, created_from_run, timestamp FROM learned_rules ORDER BY version ASC")
            for r in cur.fetchall():
                cm = ctx_data.setdefault(r["context"], {"reliability": {}, "reliability_history": {}, "learned": {}})
                rule_entry = {
                    "context": r["context"],
                    "topic": r["topic"],
                    "version": r["version"],
                    "type": r["rule_type"],
                    "value": r["value"],
                    "cond": r["cond"],
                    "created_from_run": r["created_from_run"],
                    "timestamp": r["timestamp"]
                }
                cm["learned"][r["topic"]] = rule_entry
                diffs.append({
                    "what": f"rule[{r['context']}/{r['topic']}] v{r['version']}",
                    "old": None,
                    "new": f"{r['rule_type']} {r['value']} ({r['cond']})",
                    "run_id": r["created_from_run"],
                    "ts": r["timestamp"]
                })

            # Load runs
            cur.execute("SELECT run_id, context, topic, resolution_type, reason, accepted_agent, accepted_claim, value, timestamp, scenario FROM runs ORDER BY timestamp ASC")
            for r in cur.fetchall():
                runs.append({
                    "run_id": r["run_id"],
                    "context": r["context"],
                    "topic": r["topic"],
                    "resolution_type": r["resolution_type"],
                    "reason": r["reason"],
                    "accepted_agent": r["accepted_agent"],
                    "accepted_claim": r["accepted_claim"],
                    "value": r["value"],
                    "timestamp": r["timestamp"],
                    "scenario": r["scenario"]
                })

        return {"ctx": ctx_data, "runs": runs, "diffs": diffs, "run_count": len(runs)}

    def search_memory(self, query: str) -> list:
        mem = self.load_mem()
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

    def get_runs(self, limit: int = 50) -> list:
        mem = self.load_mem()
        return mem.get("runs", [])[-limit:]

    def get_run(self, run_id: str) -> dict:
        mem = self.load_mem()
        for run in mem.get("runs", []):
            if run.get("run_id") == run_id:
                return run
        return None

# Global store singleton
store = SQLiteStore()
