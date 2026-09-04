from backend.app.agents.completion import completion_evidence, evaluate_completion


def _obs(text):
    return {"text_sample": text}


def test_completion_evidence_detected_generically():
    # Generic across any site/task: the task's own action verb ("add") was
    # already performed (history), and the task's own object keyword
    # ("laptop") still appears on the current page.
    task = "Find a laptop priced below $800 and add it to the cart."
    history = [
        {"action": "click", "text": "Add to cart"},
    ]
    obs = _obs("Your cart\n1x Sony vaio i5 laptop - $790\nTotal: $790")
    evidence = completion_evidence(task, history, obs)
    assert evidence is not None
    assert "laptop" in evidence


def test_no_evidence_when_action_not_yet_performed():
    task = "Find a laptop priced below $800 and add it to the cart."
    history = [{"action": "click", "text": "Filter"}]
    obs = _obs("Laptop results: Sony vaio i5 - $790")
    assert completion_evidence(task, history, obs) is None


def test_no_evidence_when_object_no_longer_on_page():
    task = "Find a laptop priced below $800 and add it to the cart."
    history = [{"action": "click", "text": "Add to cart"}]
    obs = _obs("Welcome to the homepage. Sign in or browse categories.")
    assert completion_evidence(task, history, obs) is None


def test_generalizes_to_a_different_task_and_site():
    task = "Book a flight to Paris under $300."
    history = [{"action": "click", "text": "Book now"}]
    obs = _obs("Booking confirmed: flight to Paris - $280")
    evidence = completion_evidence(task, history, obs)
    assert evidence is not None
    assert "paris" in evidence


def test_evaluate_completion_overrides_after_two_consecutive_signals():
    action = {"action": "click", "target": "link_03", "reason": "keep searching"}
    streak, override = evaluate_completion(0, "evidence", action)
    assert streak == 1
    assert override is None

    streak, override = evaluate_completion(streak, "evidence", action)
    assert streak == 2
    assert override is not None
    assert override["action"] == "finish"


def test_evaluate_completion_does_not_override_a_single_signal():
    action = {"action": "click", "target": "link_03"}
    streak, override = evaluate_completion(0, "evidence", action)
    assert override is None


def test_evaluate_completion_resets_when_evidence_disappears():
    action = {"action": "click", "target": "link_03"}
    streak, _ = evaluate_completion(0, "evidence", action)
    streak, override = evaluate_completion(streak, None, action)
    assert streak == 0
    assert override is None


def test_evaluate_completion_never_overrides_an_already_finishing_model():
    action = {"action": "finish", "reason": "task is done"}
    streak, override = evaluate_completion(1, "evidence", action)
    assert override is None
