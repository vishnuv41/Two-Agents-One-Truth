"""Python side of the twoagents Omega plugin. Set TWOAGENTS_HOME to the two-agents-one-truth folder."""
import os, sys
_home = os.environ.get("TWOAGENTS_HOME")
if _home: sys.path.insert(0, _home)
from core import engine

def negotiate(arg) -> str:
    arg = str(arg).strip().strip('"')
    try:
        r = engine.run(arg) if arg in engine.scenarios() else engine.run_scenario(engine.intake(arg))
    except Exception as e:
        return f"negotiate error: {e}"
    return "RESOLUTION: " + r["resolution"]["text"] + " || TRACE: " + " | ".join(e["text"] for e in r["events"])
