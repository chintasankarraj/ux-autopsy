import json
import os
import threading
import time

from backend.app.db import get_db, new_id, now_iso
from backend.app.schemas import PERSONAS, PERSONA_NAMES
from backend.app.agents.agent import run_agent
from backend.app.analysis.autopsy import run_autopsy
from backend.app.config import settings

STEPS = ["Initializing browser", "Loading website", "Understanding page",
         "Performing task", "Recording interactions", "Analyzing behavior",
         "Generating UX Autopsy"]
_progress = {}


def get_progress(sid):
    return _progress.get(sid, {"step": STEPS[0], "idx": 0})


def create_session(url, task, persona, custom):
    sid = new_id()
    get_db().execute(
        "INSERT INTO sessions (id,url,task,persona,custom_persona,status,started_at,provider) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (sid, url, task, persona, custom, "pending", now_iso(), settings.resolved_provider),
    )
    get_db().commit()
    threading.Thread(target=_run, args=(sid, url, task, persona, custom), daemon=True).start()
    return sid


def retest(sid):
    row = get_db().execute(
        "SELECT url, task, persona, custom_persona FROM sessions WHERE id=?", (sid,)
    ).fetchone()
    if row is None:
        return None
    return create_session(row["url"], row["task"], row["persona"], row["custom_persona"])


def dashboard_stats():
    # A bare COUNT/AVG/SUM with no GROUP BY always returns exactly one row
    # (0/NULL on an empty table, never zero rows), so these fetchone() calls
    # can't actually return None — asserted below so that invariant is
    # explicit rather than left for a type checker to guess at.
    db = get_db()

    total_row = db.execute("SELECT COUNT(*) c FROM sessions").fetchone()
    assert total_row is not None

    successful_row = db.execute(
        "SELECT COUNT(*) c FROM sessions WHERE status='completed' AND completed=1"
    ).fetchone()
    assert successful_row is not None

    avg_row = db.execute(
        "SELECT AVG(ux_score) a FROM sessions WHERE status='completed' AND ux_score IS NOT NULL"
    ).fetchone()
    assert avg_row is not None

    friction_row = db.execute(
        "SELECT SUM(friction_count) f FROM sessions WHERE friction_count IS NOT NULL"
    ).fetchone()
    assert friction_row is not None

    return {
        "total_sessions": total_row["c"],
        "successful_sessions": successful_row["c"],
        "avg_ux_score": round(avg_row["a"], 1) if avg_row["a"] is not None else None,
        "total_friction": friction_row["f"] or 0,
    }


def _run(sid, url, task, persona, custom):
    db = get_db()
    db.execute("UPDATE sessions SET status='running' WHERE id=?", (sid,))
    db.commit()
    os.makedirs("screenshots", exist_ok=True)
    events = []
    start = time.time()
    persona_desc = (custom or "").strip() or PERSONAS.get(persona, persona)
    persona_display = PERSONA_NAMES.get(persona, persona)

    def on_event(ev):
        ev["ts_ms"] = int((time.time() - start) * 1000)
        db.execute(
            """INSERT INTO events (session_id,ts_ms,event_type,url,element_id,
              element_text,action,reason,confidence,screenshot_path,duration_ms,success,error)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, ev["ts_ms"], ev["event_type"], ev.get("url"), ev.get("element_id"),
             ev.get("element_text"), ev.get("action"), ev.get("reason"), ev.get("confidence"),
             ev.get("screenshot_path"), ev.get("duration_ms"),
             ev.get("success", 1), ev.get("error")),
        )
        db.commit()
        events.append(ev)
        idx = min(4, len(events) // 4)
        _progress[sid] = {"step": STEPS[idx], "idx": idx}

    try:
        provider_name = settings.resolved_provider
        summary = run_agent(sid, url, task, persona_desc, provider_name, on_event, persona_id=persona)
        summary["persona_id"] = persona
        summary["persona_display"] = persona_display
        summary["task"] = task

        if summary.get("error"):
            db.execute(
                "UPDATE sessions SET status='failed', finished_at=?, error=? WHERE id=?",
                (now_iso(), summary["error"], sid),
            )
            db.commit()
            return

        _progress[sid] = {"step": STEPS[5], "idx": 5}
        autopsy = run_autopsy(events, summary)
        _progress[sid] = {"step": STEPS[6], "idx": 6}

        for f in autopsy["friction_points"]:
            db.execute(
                """INSERT INTO friction_points (session_id,title,severity,evidence,
                  affected_action,confidence,recommendation,signal,why_json) VALUES (?,?,?,?,?,?,?,?,?)""",
                (sid, f["title"], f["severity"], f["evidence"], f["affected_action"],
                 f["confidence"], f["recommendation"], f["signal"],
                 json.dumps(f["why"]) if f.get("why") else None),
            )

        score = autopsy["score"]
        db.execute(
            """INSERT INTO analyses (session_id,executive_summary,root_causes,provider)
              VALUES (?,?,?,?)""",
            (sid, autopsy["ai"]["executive_summary"],
             json.dumps(autopsy["ai"]["root_causes"]), autopsy["provider"]),
        )

        db.execute(
            """UPDATE sessions SET status='completed', finished_at=?, completed=?,
              actions_count=?, duration_ms=?, pages_visited=?, friction_count=?, ux_score=?,
              score_breakdown=?, provider=? WHERE id=?""",
            (
                now_iso(),
                int(bool(summary.get("completed"))),
                summary.get("actions_count", 0),
                summary.get("duration_ms"),
                summary.get("pages_visited", 0),
                len(autopsy["friction_points"]),
                score["ux_score"],
                json.dumps(score),
                autopsy["provider"],
                sid,
            ),
        )
        db.commit()
    except Exception as e:
        db.execute(
            "UPDATE sessions SET status='failed', finished_at=?, error=? WHERE id=?",
            (now_iso(), f"{type(e).__name__}: {e}", sid),
        )
        db.commit()
    finally:
        _progress.pop(sid, None)
