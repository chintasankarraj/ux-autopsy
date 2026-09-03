import time
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
DEMO = "http://localhost:8000/api/demo-site/"
TASK = "Find a laptop under ₹60,000 and add it to the cart."

@pytest.fixture(scope="module")
def session_id():
    r = client.post("/api/sessions",
                    json={"url": DEMO, "task": TASK, "persona": "budget_shopper"})
    assert r.status_code == 201
    sid = r.json()["id"]
    for _ in range(150):
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
