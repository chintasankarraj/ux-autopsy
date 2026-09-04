"""Regression coverage for the v1.4 completion-evidence improvement.

v1.3.2's live regression showed a model-issued FINISH trusted immediately
after a successful "Add to cart" click, with the only completion evidence
being a page-text keyword match ("cart") that DemoBlaze's nav bar makes
permanently true regardless of whether anything was actually added. A
Gemini-free Playwright diagnostic against the real site found a much
stronger, fully generic signal going unused: a native browser dialog
("Product added") that fires as a direct, synchronous side effect of the
click itself.

This file tests the two pieces added to close that gap:
  - agents/agent.py:capture_dialogs() -- generic dialog capture, preserving
    Playwright's existing auto-dismiss behavior.
  - agents/completion.py:dialog_completion_evidence() -- relevance-gated
    evidence derived from a captured dialog's own text vs. the task's own
    words, never a hardcoded site phrase.

All tests use local fixtures (data: URLs / direct function calls) and the
deterministic MockProvider -- no DemoBlaze, no Gemini/LLM calls.
"""
import urllib.parse

from playwright.sync_api import sync_playwright

from backend.app.agents.agent import capture_dialogs, run_agent
from backend.app.agents.completion import dialog_completion_evidence
from backend.app.browser.executor import execute

TASK = "Find a laptop priced below $800 and add it to the cart."

# Every key an emitted event dict may carry, mirroring backend/app/db.py's
# `events` table columns exactly -- proves a DIALOG event is insertable
# through the existing session_service.py on_event() path with zero schema
# change.
KNOWN_EVENT_KEYS = {
    "event_type", "url", "element_id", "element_text", "action", "reason",
    "confidence", "screenshot_path", "duration_ms", "decide_ms",
    "observe_ms", "success", "error",
}


def _data_url(html: str) -> str:
    return "data:text/html," + urllib.parse.quote(html)


# --- capture_dialogs(): real Playwright, generic browser primitive --------

def test_capture_dialogs_records_type_and_message_without_blocking():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(_data_url("<!doctype html><html><body>ok</body></html>"))
        dialogs = capture_dialogs(page)

        # If dialogs were left unhandled and no auto-dismiss occurred, each
        # of these evaluate() calls would hang until Playwright's own
        # timeout -- their both returning promptly IS the "does not block"
        # proof, not just an incidental assertion.
        alert_result = page.evaluate("() => { alert('Product added'); return 'after-alert'; }")
        confirm_result = page.evaluate("() => confirm('Are you sure?')")

        assert alert_result == "after-alert"
        assert confirm_result is False  # dismiss() == Cancel, matching prior auto-dismiss behavior
        assert dialogs == [
            {"type": "alert", "message": "Product added"},
            {"type": "confirm", "message": "Are you sure?"},
        ]
        browser.close()


# --- dialog_completion_evidence(): relevance-gated, generic, no site vocab -

def test_relevant_dialog_text_strengthens_completion_evidence():
    dialogs = [{"type": "alert", "message": "Product added"}]
    evidence = dialog_completion_evidence(TASK, dialogs)
    assert evidence is not None
    assert "add" in evidence


def test_irrelevant_dialog_text_is_not_completion_evidence():
    dialogs = [{"type": "alert", "message": "Welcome"}]
    assert dialog_completion_evidence(TASK, dialogs) is None


def test_no_dialogs_means_no_dialog_evidence():
    assert dialog_completion_evidence(TASK, []) is None
    assert dialog_completion_evidence(TASK, None) is None


def test_persistent_page_keyword_alone_is_not_dialog_evidence():
    # A permanent nav-bar-style keyword (e.g. DemoBlaze's "Cart" link) is
    # page text, not a dialog -- dialog_completion_evidence() only ever
    # looks at actually-captured dialogs, so it cannot be fooled into
    # treating page text as if a dialog had confirmed anything.
    assert dialog_completion_evidence(TASK, []) is None


# --- Model-issued FINISH: tested explicitly, behavior preserved -----------

def test_finish_action_succeeds_unconditionally_at_execute_layer():
    # This is the exact trust boundary the investigation identified: once
    # the model (or the streak override) picks "finish", execute() never
    # re-checks page state, emap, or evidence -- v1.4 does not change this.
    result = execute(page=None, action={"action": "finish", "reason": "done"},
                      emap={}, settings=None)
    assert result == {"success": True}


# --- Full local session: real dialog capture feeds real completion path ---

FIXTURE_WITH_ALERT_THEN_THANK_YOU = """
<!doctype html><html><body>
<button onclick="alert('Product added'); document.body.innerHTML='<p>Thank you for your order</p>';">
  Add to Cart
</button>
</body></html>
"""


def test_full_session_captures_dialog_and_reaches_trustworthy_finish(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # keep run_agent()'s screenshots/ out of the repo
    events = []

    summary = run_agent(
        "test-dialog-session", _data_url(FIXTURE_WITH_ALERT_THEN_THANK_YOU), TASK,
        "a generic synthetic user", "mock", events.append, persona_id="custom",
    )

    dialog_events = [e for e in events if e["event_type"] == "DIALOG"]
    assert len(dialog_events) == 1
    dialog_event = dialog_events[0]
    assert dialog_event["element_text"] == "Product added"
    assert dialog_event["action"] == "alert"
    assert set(dialog_event.keys()) <= KNOWN_EVENT_KEYS  # no schema change needed

    # The captured dialog is independently strong completion evidence for
    # this task -- confirmed generically, not by trusting the session alone.
    evidence = dialog_completion_evidence(
        TASK, [{"type": dialog_event["action"], "message": dialog_event["element_text"]}]
    )
    assert evidence is not None

    # MockProvider's own (unrelated) "thank you" check finishes the session
    # on the next step -- proving a model-issued finish is still trusted
    # unconditionally end-to-end, exactly as before v1.4.
    assert summary["completed"] is True
    assert any(e["event_type"] == "TASK_SUCCESS" for e in events)


def test_full_session_with_irrelevant_dialog_does_not_claim_relevance(tmp_path, monkeypatch):
    # The clicked control's own label ("Add to Cart") is clearly relevant --
    # this is deliberately NOT "no dialog fires at all". The point is that
    # even though a plausible action was taken, an unrelated dialog message
    # ("Welcome") must not be treated as completion confirmation.
    monkeypatch.chdir(tmp_path)
    events = []
    fixture = """
    <!doctype html><html><body>
    <button onclick="alert('Welcome')">Add to Cart</button>
    </body></html>
    """
    run_agent(
        "test-irrelevant-dialog-session", _data_url(fixture), TASK,
        "a generic synthetic user", "mock", events.append, persona_id="custom",
    )
    dialog_events = [e for e in events if e["event_type"] == "DIALOG"]
    assert dialog_events, "expected the 'Add to Cart' click to trigger the alert"
    evidence = dialog_completion_evidence(
        TASK, [{"type": d["action"], "message": d["element_text"]} for d in dialog_events]
    )
    assert evidence is None
