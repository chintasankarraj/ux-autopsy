import re
from collections import Counter

WEIGHTS = {"repeated_action": 10, "backtrack": 8, "hesitation": 10, "error": 15,
           "dead_end": 12, "abandonment": 30, "excessive_actions": 12, "repeated_search": 10,
           "task_failed": 20, "incorrect_click": 15}
HESITATION_MS = 6000
# A click the agent itself made with confidence below this is a genuinely
# shaky attempt, not just "not the very last click" — the latter would
# false-positive on every necessary step of any multi-step flow (open a
# filter, pick a bracket, open checkout, confirm) since only the final click
# is ever literally "last."
LOW_CONFIDENCE = 0.45

# Generic words that carry no target-identifying information, so their
# presence in a "reason" string never counts as evidence of what the agent
# meant to click — kept deliberately small and site-agnostic (no product,
# brand, or selector vocabulary).
_GENERIC_REASON_WORDS = {
    "click", "open", "page", "link", "button", "control", "filter", "option",
    "item", "this", "that", "using", "goal", "task", "search", "progresses",
    "toward", "completing", "purchase", "matches", "best", "trying", "first",
    "prominent", "closely", "reading", "without", "narrowing", "opening",
    "budget", "right", "category",
}


def _content_words(text):
    return {w for w in re.findall(r"[a-zA-Z]{4,}", (text or "").lower())
            if w not in _GENERIC_REASON_WORDS}


def _reasoning_target_mismatch(event):
    """True when the agent's own stated reason names something specific that
    doesn't overlap at all with the label of what it actually clicked — a
    general, site-agnostic proxy for "reasoned about A but clicked B" that
    works regardless of self-reported confidence or session outcome."""
    reason_words = _content_words(event.get("reason"))
    label_words = _content_words(event.get("element_text"))
    if not reason_words or not label_words:
        return False
    return reason_words.isdisjoint(label_words)

# Internal element ids (e.g. "button_06") are ephemeral, DOM-order-based
# bookkeeping — never meaningful to a person reading an analysis. Anything
# shown in user-facing text uses the element's actual label; only when no
# label was recorded does this fall back to a generic, still-readable phrase
# derived from the id's kind prefix, never the raw id itself.
_KIND_FALLBACKS = {
    "button": "the action button",
    "input": "the input field",
    "link": "a navigation link",
}


def _humanize_id(raw_id, fallback="the relevant control"):
    if not raw_id:
        return fallback
    prefix = str(raw_id).split("_")[0].lower()
    return _KIND_FALLBACKS.get(prefix, fallback)


def _label(event, fallback="the relevant control"):
    """Human-readable identifier for the element an event acted on."""
    text = event.get("element_text")
    if text:
        return text
    return _humanize_id(event.get("element_id"), fallback)

def detect_friction(events, summary):
    points, raw = [], 0
    def add(signal, title, severity, evidence, affected, rec):
        nonlocal raw
        raw += WEIGHTS[signal]
        points.append({"signal": signal, "title": title, "severity": severity,
                       "evidence": evidence, "affected_action": affected,
                       "confidence": 0.85 if signal in ("repeated_action", "error", "backtrack",
                                                        "incorrect_click") else 0.7,
                       "recommendation": rec})

    actions = [e for e in events if e["event_type"] in ("CLICK", "TYPE", "SCROLL")]
    click_events_by_id = {}
    for e in actions:
        if e["event_type"] == "CLICK" and e.get("element_id") and e["element_id"] not in click_events_by_id:
            click_events_by_id[e["element_id"]] = e
    clicks = Counter(e["element_id"] for e in actions
                     if e["event_type"] == "CLICK" and e["element_id"])
    for eid, n in clicks.items():
        if n >= 3:
            label = _label(click_events_by_id[eid])
            add("repeated_action", f"Repeated clicks on {label}", "HIGH" if n >= 4 else "MEDIUM",
                f"{n} clicks on the same control — expected response likely did not occur.",
                label, "Verify the control's affordance and give visible interaction feedback.")

    seen = []
    for e in events:
        if e["url"] and e["url"] not in seen:
            seen.append(e["url"])
        elif e["url"] in seen and e["event_type"] == "NAVIGATION":
            add("backtrack", "Backtracked to a previous page", "MEDIUM",
                f"Returned to an already-visited page ({e['url']}).", e["url"],
                "Improve wayfinding so users reach goals without retracing steps.")

    # The gap between two consecutive events includes however long the model
    # itself took to respond (a full LLM API round trip), which is recorded
    # per-event as `decide_ms` — real, measured latency, not a fabricated
    # value. Subtracting it isolates the portion of the gap that could
    # actually be user-like hesitation, so a slow model call is never
    # misread as the agent pausing.
    prev = None
    for e in events:
        if prev is not None and e["event_type"] not in ("WAIT", "PAGE_VIEW"):
            gap_ms = e["ts_ms"] - prev["ts_ms"]
            model_latency_ms = e.get("decide_ms") or 0
            residual_ms = gap_ms - model_latency_ms
            if residual_ms > HESITATION_MS:
                add("hesitation", "Long hesitation before action", "MEDIUM",
                    f"{residual_ms / 1000:.1f}s pause before "
                    f"{e['event_type'].lower()}"
                    + (f" (after excluding {model_latency_ms / 1000:.1f}s of model "
                       "response time)." if model_latency_ms else "."),
                    _label(e, fallback=e["url"]),
                    "Likely decision uncertainty — clarify options at this step.")
        prev = e

    errs = [e for e in events if e["event_type"] == "ERROR"]
    if errs:
        add("error", f"{len(errs)} interaction error(s)", "HIGH",
            "; ".join((e.get("error") or "unknown") for e in errs[:3]),
            _label(errs[0], fallback=""), "Ensure interaction targets are stable and visible.")

    # Evidence-based, in two independent forms — neither depends on the
    # session having reached TASK_SUCCESS, so a confidently-wrong click in an
    # unsuccessful or partial session is just as visible as a low-confidence
    # one in a successful one:
    #  1. Self-reported low confidence — a genuinely shaky attempt, not just
    #     a step that happened before the last one (a multi-step flow — open
    #     filter, pick bracket, checkout, confirm — isn't "incorrect" just
    #     because only its final click is last).
    #  2. Reasoning/target mismatch — the agent's own stated reason names
    #     something with no overlap at all with what it actually clicked
    #     (e.g. reasoning about one product but clicking another). This
    #     catches a confidently-wrong click that (1) alone would miss,
    #     without ever inspecting site-specific selectors or content.
    click_events = [e for e in events if e["event_type"] == "CLICK"]
    low_conf_clicks = [
        e for e in click_events
        if e.get("confidence") is not None and e["confidence"] < LOW_CONFIDENCE
    ]
    mismatched_clicks = [
        e for e in click_events
        if e not in low_conf_clicks and _reasoning_target_mismatch(e)
    ]
    incorrect_clicks = low_conf_clicks + mismatched_clicks
    if incorrect_clicks:
        low_labels = [_label(e) for e in low_conf_clicks]
        mismatch_labels = [_label(e) for e in mismatched_clicks]
        evidence_parts = []
        if low_labels:
            evidence_parts.append(
                f"Interacted with {', '.join(repr(l) for l in low_labels)} with low confidence "
                "(the agent's own uncertainty at decision time) before proceeding."
            )
        if mismatch_labels:
            evidence_parts.append(
                f"Clicked {', '.join(repr(l) for l in mismatch_labels)} despite stating a reason "
                "that referred to something else entirely — the action didn't match the agent's "
                "own stated reasoning."
            )
        add("incorrect_click",
            f"{len(incorrect_clicks)} likely incorrect interaction(s)",
            "HIGH" if len(incorrect_clicks) >= 2 else "MEDIUM",
            " ".join(evidence_parts),
            (low_labels or mismatch_labels)[0],
            "Make the correct control easier to distinguish from similar-looking alternatives "
            "nearby.")

    if sum(1 for e in actions if e["event_type"] == "TYPE") >= 2:
        add("repeated_search", "Multiple search attempts", "MEDIUM",
            "Several separate text inputs suggest earlier queries returned poor results.",
            "search", "Improve search relevance; add suggestions/autocomplete.")

    if not any(e["event_type"] in ("TASK_SUCCESS", "TASK_FAILURE") for e in events):
        add("dead_end", "Session ended without explicit outcome", "MEDIUM",
            "Agent loop ended without completing or failing the task.", "",
            "Provide a clear path to completion from every page.")

    failure = next((e for e in events if e["event_type"] == "TASK_FAILURE"), None)
    if failure and not summary.get("abandoned"):
        add("task_failed", "Task could not be completed", "HIGH",
            failure.get("reason") or "The agent gave up without finding a path to the goal.", "",
            "Evidence suggests the critical path was not discoverable — review whether the "
            "relevant controls were visible and clearly labeled for this task.")
    if summary.get("abandoned"):
        add("abandonment", "Task abandoned", "CRITICAL",
            summary.get("abandon_reason", "Gave up before completing the task."), "",
            "Remove blockers on the critical path at the abandonment step.")
    if summary.get("actions_count", 0) >= 18:
        add("excessive_actions", "Excessive actions required", "HIGH",
            f"{summary['actions_count']} actions attempted.", "",
            "Shorten the critical path; surface key controls earlier.")

    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    points.sort(key=lambda p: order[p["severity"]])
    return points, raw
