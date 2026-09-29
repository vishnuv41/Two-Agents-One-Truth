"""Python bridge so an Omega agent can call the negotiation engine as a skill.
Copy this file next to Omega's other python bridges and set TWOAGENTS_HOME to this repo.
Input: a preloaded scenario id (crop | campus | tie) or the line format from README. Returns a short string."""
import os, sys
sys.path.insert(0, os.environ.get("TWOAGENTS_HOME", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core import engine

def negotiate(arg: str) -> str:
    arg = str(arg).strip()
    try:
        r = engine.run(arg) if arg in engine.scenarios() else engine.run_scenario(engine.intake(arg))
    except Exception as e:
        return f"negotiate error: {e}"
    trace = " | ".join(e["text"] for e in r["events"])
    return f"RESOLUTION: {r['resolution']['text']} || TRACE: {trace}"
