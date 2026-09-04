import time
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings

client = TestClient(app)
DEMO = settings.demo_url
TASK = "Find a laptop under ₹60,000 and complete the purchase."

@pytest.fixture(scope="module")
def session_id():
    r = client.post("/api/sessions",
                    json={"url": DEMO, "task": TASK, "persona": "budget_shopper"})
    assert r.status_code == 201
    sid = r.json()["id"]
    # The session's own internal budget is settings.max_session_seconds, checked
    # only at the top of each loop iteration — a single slow decide() call (a
    # real LLM API round trip) can finish after that check, plus autopsy
    # generation runs afterward. Wait at least that long, with a margin, rather
    # than a shorter fixed budget that can flag a still-legitimately-running
    # session as stuck.
    max_wait_s = settings.max_session_seconds + 90
    for _ in range(max_wait_s):
        s = client.get(f"/api/sessions/{sid}").json()
        if s["status"] in ("completed", "failed"):
            break
        time.sleep(1)
    return sid

def test_health():
    assert client.get("/api/health").json()["status"] == "ok"

def test_create_validation():
    r = client.post("/api/sessions", json={"url": "bad", "task": "x" * 10,
                                           "persona": "budget_shopper"})
    assert r.status_code == 422

def test_unknown_persona_rejected():
    r = client.post("/api/sessions", json={"url": DEMO, "task": TASK,
                                           "persona": "hacker"})
    assert r.status_code == 422

def test_session_completes(session_id):
    s = client.get(f"/api/sessions/{session_id}").json()
    assert s["status"] == "completed"
    assert s["ux_score"] is not None

def test_events_recorded(session_id):
    evs = client.get(f"/api/sessions/{session_id}/events").json()
    assert len(evs) > 3
    assert any(e["event_type"] == "PAGE_VIEW" for e in evs)

def test_analysis_present(session_id):
    a = client.get(f"/api/sessions/{session_id}/analysis").json()
    assert a["analysis"]["executive_summary"]
    assert a["analysis"]["root_causes"]

def test_404():
    assert client.get("/api/sessions/nope").status_code == 404
