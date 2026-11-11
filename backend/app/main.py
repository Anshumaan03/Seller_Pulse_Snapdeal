"""FastAPI app: JSON API + static frontend. All secrets stay server-side."""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv  # noqa: E402  (python-dotenv)
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

from . import agent, tools, db, llm, analytics  # noqa: E402
from .models import ActionItem  # noqa: E402

@asynccontextmanager
async def lifespan(_app):
    db.init_db()
    yield


app = FastAPI(title="SellerPulse - Virtual KAM prototype (synthetic demo data)", lifespan=lifespan)
SESSIONS: dict[str, agent.Session] = {}
DEFAULT_SELLER = "DEMO-1042"


def _seller_or_404(seller_id: str) -> None:
    try:
        tools.load_data(seller_id)
    except tools.ToolError as e:
        raise HTTPException(404, str(e))


def _session_or_404(session_id: str) -> agent.Session:
    s = SESSIONS.get(session_id)
    if not s:
        raise HTTPException(404, "Unknown call session. Start a new call.")
    return s


@app.get("/api/health")
def health():
    return {"status": "ok", "data": "synthetic demo data"}


@app.get("/api/config")
def config():
    return {
        "default_seller_id": DEFAULT_SELLER,
        "voice_mode": "browser",   # browser STT + TTS (Web Speech API)
        "llm": llm.info(),
        "data_label": tools.DATA_LABEL,
    }


@app.get("/api/seller/{seller_id}/snapshot")
def snapshot(seller_id: str):
    _seller_or_404(seller_id)
    data = tools.load_data(seller_id)
    return {
        "profile": tools.get_seller_profile(seller_id),
        "comparison": tools.get_period_comparison(seller_id),
        "reconciliation_problems": analytics.reconcile(data),
        "targets_note": "Benchmarks and targets are fabricated demo inputs, not live market data or Snapdeal standards.",
    }


@app.get("/api/seller/{seller_id}/diagnosis")
def diagnosis(seller_id: str):
    _seller_or_404(seller_id)
    return {
        "skus": tools.get_sku_diagnostics(seller_id),
        "drivers": tools.identify_sales_drivers(seller_id),
    }


class PlanRequest(BaseModel):
    approved_actions: list[ActionItem]
    consent_confirmed: bool = False


@app.post("/api/seller/{seller_id}/action-plan")
def create_plan(seller_id: str, req: PlanRequest):
    _seller_or_404(seller_id)
    try:
        return tools.create_action_plan(seller_id, req.approved_actions, req.consent_confirmed)
    except tools.ToolError as e:
        raise HTTPException(400, str(e))


@app.get("/api/seller/{seller_id}/action-plan")
def read_plan(seller_id: str):
    _seller_or_404(seller_id)
    return tools.get_action_plan(seller_id)


class SummaryRequest(BaseModel):
    summary: str
    decisions: list[str] = []
    follow_up: str = ""


@app.post("/api/seller/{seller_id}/call-summary")
def write_summary(seller_id: str, req: SummaryRequest):
    _seller_or_404(seller_id)
    return tools.log_call_summary(seller_id, req.summary, req.decisions, req.follow_up)


@app.get("/api/seller/{seller_id}/call-summary")
def read_summaries(seller_id: str):
    _seller_or_404(seller_id)
    return tools.get_call_summaries(seller_id)


class StartRequest(BaseModel):
    seller_id: str = DEFAULT_SELLER


def _turn_payload(s: agent.Session, reply: str, new_tools: list[str]) -> dict:
    plan = tools.get_action_plan(s.seller_id)
    return {
        "session_id": s.session_id,
        "reply": reply,
        "stage": s.stage,
        "call_ended": s.ended,
        "facts": agent.public_facts(s),
        "proposed": [i.model_dump() for i in s.proposed] if not s.plan_saved else [],
        "plan": plan.model_dump() if plan.items else None,
        "tools_used": new_tools,
        "tool_log": s.tool_log,
        "transcript": s.transcript,
    }


@app.post("/api/call/start")
def call_start(req: StartRequest):
    _seller_or_404(req.seller_id)
    s, greeting = agent.start_call(req.seller_id)
    SESSIONS[s.session_id] = s
    return _turn_payload(s, greeting, ["get_seller_profile"])


class MessageRequest(BaseModel):
    text: str


@app.post("/api/call/{session_id}/message")
def call_message(session_id: str, req: MessageRequest):
    s = _session_or_404(session_id)
    before = len(s.tool_log)
    reply = agent.handle_turn(s, req.text)
    return _turn_payload(s, reply, [t["tool"] for t in s.tool_log[before:]])


@app.post("/api/call/{session_id}/end")
def call_end(session_id: str):
    s = _session_or_404(session_id)
    if not s.ended:
        before = len(s.tool_log)
        agent._close(s, "early")
        return _turn_payload(s, "Call ended.", [t["tool"] for t in s.tool_log[before:]])
    return _turn_payload(s, "Call ended.", [])


@app.post("/api/reset")
def reset(req: StartRequest):
    _seller_or_404(req.seller_id)
    tools.reset_demo(req.seller_id)
    for sid in [k for k, v in SESSIONS.items() if v.seller_id == req.seller_id]:
        del SESSIONS[sid]
    return {"status": "reset", "seller_id": req.seller_id}


FRONTEND = ROOT / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")
