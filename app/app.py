from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from core import engine, agents, memory, omega

app = FastAPI(title="Two Agents, One Truth")

@app.get("/")
def index(): return FileResponse("static/index.html")

@app.get("/omega/skills")
def omega_skills():
    return omega.runtime.list_skills()

@app.post("/omega/invoke")
def omega_invoke(body: dict):
    skill = body.get("skill", "negotiate")
    arg = body.get("argument", "")
    try:
        res = omega.runtime.invoke_skill(skill, arg)
        return {"skill": skill, "argument": arg, "result": res}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

@app.get("/agents")
def get_agents(): return agents.list_agents()

@app.get("/scenarios")
def sc(): return [{"id": k, "title": v["title"]} for k, v in engine.scenarios().items()]

@app.post("/run/{sid}")
def run(sid: str): return engine.run(sid)

@app.get("/memory")
def mem(): return memory.load_mem()

@app.get("/memory/search")
def search_mem(q: str = Query("")): return memory.search_memory(q)

@app.get("/memory/{context}")
def get_ctx_mem(context: str): return memory.get_context_memory(context)

@app.get("/memory/{context}/{topic}")
def get_topic_mem(context: str, topic: str):
    res = memory.get_topic_memory(context, topic)
    if not res: return JSONResponse({"error": "not found"}, status_code=404)
    return res

@app.get("/runs")
def list_runs(limit: int = 50): return memory.get_runs(limit)

@app.get("/runs/{run_id}")
def get_run_details(run_id: str):
    res = memory.get_run(run_id)
    if not res: return JSONResponse({"error": "run_id not found"}, status_code=404)
    return res

@app.post("/conflict")
@app.post("/run_text")
def run_text(body: dict):
    try: sc = engine.intake(body.get("text", ""))
    except Exception as e: return JSONResponse({"error": str(e)}, status_code=400)
    return engine.run_scenario(sc)

@app.post("/human/{topic}/{value}")
def human(topic: str, value: str, context: str = None): return engine.human(topic, value, context)

@app.post("/reset")
def reset(): engine.reset(); return {"ok": True}
