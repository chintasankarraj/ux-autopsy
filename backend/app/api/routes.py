import json
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from backend.app.config import settings
from backend.app.db import get_db, row_to_dict
from backend.app.schemas import PERSONAS, SessionCreate
from backend.app.services import session_service

router = APIRouter(prefix="/api")

def _url_ok(url):
    return bool(re.match(r"^https?://[^\s/.?#].[^\s]*", url))

def _session(sid) -> dict:
    row = get_db().execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise HTTPException(404, "Session not found")
    d = row_to_dict(row)
    assert d is not None  # row_to_dict only returns None when row is None, ruled out above
    if d.get("score_breakdown"):
        d["score_breakdown"] = json.loads(d["score_breakdown"])
    return d

@router.get("/health")
def health():
    return {"status": "ok", "provider": settings.resolved_provider,
            "demo_mode": settings.demo_mode}

@router.get("/personas")
def personas():
    return [{"id": pid, "description": desc} for pid, desc in PERSONAS.items()]

@router.post("/sessions", status_code=201)
def create(body: SessionCreate):
    url = body.url.strip()
    if "demo-site" in url:
        url = settings.demo_url
    if not _url_ok(url):
        raise HTTPException(422, "Please enter a valid http(s) URL.")
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url
    sid = session_service.create_session(url, body.task.strip(), body.persona,
                                         body.custom_persona)
    return {"id": sid}

@router.get("/sessions")
def list_sessions():
    rows = get_db().execute(
        "SELECT * FROM sessions ORDER BY started_at DESC LIMIT 50").fetchall()
    return [row_to_dict(r) for r in rows]

@router.get("/sessions/{sid}")
def get_session(sid):
    s = _session(sid)
    if s["status"] == "running":
        s["progress"] = session_service.get_progress(sid)
    return s

@router.get("/sessions/{sid}/events")
def get_events(sid):
    _session(sid)
    rows = get_db().execute(
        "SELECT * FROM events WHERE session_id=? ORDER BY ts_ms,id", (sid,)).fetchall()
    return [row_to_dict(r) for r in rows]

@router.get("/sessions/{sid}/analysis")
def get_analysis(sid):
    _session(sid)
    fps = [dict(r) for r in get_db().execute(
        "SELECT * FROM friction_points WHERE session_id=?", (sid,)).fetchall()]
    for fp in fps:
        if fp.get("why_json"):
            fp["why"] = json.loads(fp["why_json"])
        del fp["why_json"]
    a = get_db().execute("SELECT * FROM analyses WHERE session_id=?", (sid,)).fetchone()
    analysis = row_to_dict(a)
    if analysis and analysis.get("root_causes"):
        analysis["root_causes"] = json.loads(analysis["root_causes"])
    return {"friction_points": fps, "analysis": analysis}

@router.post("/sessions/{sid}/retest", status_code=201)
def retest(sid):
    _session(sid)
    new_sid = session_service.retest(sid)
    if new_sid is None:
        raise HTTPException(500, "Retest failed")
    return {"id": new_sid}

@router.get("/stats")
def stats():
    return session_service.dashboard_stats()

@router.get("/demo-site/", response_class=HTMLResponse)
@router.get("/demo-site/{_}", response_class=HTMLResponse)
def demo_site(_=""):
    return (Path(__file__).resolve().parents[1] / "browser" / "demo_site.html").read_text(encoding="utf-8")

@router.get("/screenshots/{name}")
def screenshot(name):
    if "/" in name or ".." in name:
        raise HTTPException(400, "Invalid path")
    p = Path("screenshots") / name
    if not p.exists():
        raise HTTPException(404, "Screenshot not found")
    return FileResponse(p)
