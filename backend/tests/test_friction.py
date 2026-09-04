from backend.app.analysis.friction import detect_friction

def _ev(t, eid=None, err=None, ts=0, url="u", reason=None, confidence=None, text=None):
    return {"event_type": t, "element_id": eid, "error": err, "ts_ms": ts, "url": url,
            "reason": reason, "confidence": confidence, "element_text": text}

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

def test_low_confidence_click_produces_incorrect_click_friction():
    events = [
        _ev("CLICK", "BUTTON_01", ts=0, confidence=0.4, text="Add to Cart"),
        _ev("CLICK", "BUTTON_02", ts=100, confidence=0.7, text="Buy Now"),
    ]
    points, _ = detect_friction(events, {"actions_count": 2})
    assert any(p["signal"] == "incorrect_click" for p in points)

def test_multi_step_confident_flow_has_no_incorrect_click_friction():
    # Every click here is a necessary, confident step (open filter, pick a
    # bracket, buy, confirm) — none of them should be flagged just because
    # only the last one is literally last.
    events = [
        _ev("CLICK", "LINK_01", ts=0, confidence=0.6, text="Filter"),
        _ev("CLICK", "BUTTON_01", ts=200, confidence=0.8, text="Under $60"),
        _ev("CLICK", "BUTTON_02", ts=400, confidence=0.7, text="Buy Now"),
        _ev("CLICK", "BUTTON_03", ts=600, confidence=0.7, text="Buy"),
        _ev("TASK_SUCCESS", ts=700),
    ]
    points, _ = detect_friction(events, {"actions_count": 4, "completed": True})
    assert not any(p["signal"] == "incorrect_click" for p in points)

def test_no_raw_element_id_in_user_facing_text():
    # element_text missing everywhere on purpose — this is the exact shape
    # that used to leak "button_06"-style ids into titles/evidence/affected.
    events = [
        _ev("CLICK", "button_06", ts=0),
        _ev("CLICK", "button_06", ts=100),
        _ev("CLICK", "button_06", ts=200),
        _ev("CLICK", "button_09", ts=9000),
        _ev("ERROR", "input_02", err="Timeout"),
    ]
    points, _ = detect_friction(events, {"actions_count": 5})
    assert points
    for p in points:
        for field in ("title", "evidence", "affected_action"):
            value = p.get(field) or ""
            assert "button_06" not in value
            assert "button_09" not in value
            assert "input_02" not in value

def test_explicit_failure_produces_friction():
    events = [
        _ev("CLICK", "LINK_01", ts=0),
        _ev("TASK_FAILURE", ts=500, reason="No relevant controls found."),
    ]
    points, _ = detect_friction(events, {"actions_count": 2, "abandoned": False})
    assert any(p["signal"] == "task_failed" for p in points)
