from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from core import engine
app = FastAPI(title="Two Agents, One Truth")
@app.get("/")
def index(): return FileResponse("static/index.html")
@app.get("/scenarios")
def sc(): return [{"id": k, "title": v["title"]} for k, v in engine.scenarios().items()]
@app.post("/run/{sid}")
def run(sid: str): return engine.run(sid)
@app.get("/memory")
def mem(): return engine.load_mem()
@app.post("/run_text")
def run_text(body: dict):
    try: sc = engine.intake(body.get("text", ""))
    except Exception as e: return JSONResponse({"error": str(e)}, status_code=400)
    return engine.run_scenario(sc)
@app.post("/human/{topic}/{value}")
def human(topic: str, value: str): return engine.human(topic, value)
@app.post("/reset")
def reset(): engine.reset(); return {"ok": True}
