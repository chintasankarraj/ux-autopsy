from backend.app.analysis.friction import detect_friction

def _ev(t, eid=None, err=None, ts=0, url="u", reason=None):
    return {"event_type": t, "element_id": eid, "error": err, "ts_ms": ts, "url": url, "reason": reason}

def test_repeated_clicks_detected():
    events = [_ev("CLICK", "BUTTON_01", ts=i * 100) for i in range(4)]
    points, _ = detect_friction(events, {"actions_count": 4})
    assert any(p["signal"] == "repeated_action" for p in points)

def test_hesitation_detected():
    points, _ = detect_friction([_ev("CLICK", ts=0), _ev("CLICK", ts=9000)],
                                {"actions_count": 2})
    assert any(p["signal"] == "hesitation" for p in points)

def test_clean_session_low_friction():
    events = [_ev("CLICK", ts=i * 500, url=f"u{i}") for i in range(3)]
    events.append(_ev("TASK_SUCCESS", ts=1500))
    points, _ = detect_friction(events, {"actions_count": 3, "completed": True})
    assert not points

def test_errors_detected():
    points, _ = detect_friction([_ev("ERROR", err="Timeout")], {"actions_count": 1})
    assert any(p["signal"] == "error" for p in points)

def test_explicit_failure_produces_friction():
    events = [
        _ev("CLICK", "LINK_01", ts=0),
        _ev("TASK_FAILURE", ts=500, reason="No relevant controls found."),
    ]
    points, _ = detect_friction(events, {"actions_count": 2, "abandoned": False})
    assert any(p["signal"] == "task_failed" for p in points)
