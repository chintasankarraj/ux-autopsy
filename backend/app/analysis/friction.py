from collections import Counter

WEIGHTS = {"repeated_action": 10, "backtrack": 8, "hesitation": 10, "error": 15,
           "dead_end": 12, "abandonment": 30, "excessive_actions": 12, "repeated_search": 10,
           "task_failed": 20}
HESITATION_MS = 6000

def detect_friction(events, summary):
    points, raw = [], 0
    def add(signal, title, severity, evidence, affected, rec):
        nonlocal raw
        raw += WEIGHTS[signal]
        points.append({"signal": signal, "title": title, "severity": severity,
                       "evidence": evidence, "affected_action": affected,
                       "confidence": 0.85 if signal in ("repeated_action", "error", "backtrack") else 0.7,
                       "recommendation": rec})

    actions = [e for e in events if e["event_type"] in ("CLICK", "TYPE", "SCROLL")]
    clicks = Counter(e["element_id"] for e in actions
                     if e["event_type"] == "CLICK" and e["element_id"])
    for eid, n in clicks.items():
        if n >= 3:
            add("repeated_action", f"Repeated clicks on {eid}", "HIGH" if n >= 4 else "MEDIUM",
                f"{n} clicks on the same control — expected response likely did not occur.",
                eid, "Verify the control's affordance and give visible interaction feedback.")

    seen = []
    for e in events:
        if e["url"] and e["url"] not in seen:
            seen.append(e["url"])
        elif e["url"] in seen and e["event_type"] == "NAVIGATION":
            add("backtrack", "Backtracked to a previous page", "MEDIUM",
                f"Returned to an already-visited page ({e['url']}).", e["url"],
                "Improve wayfinding so users reach goals without retracing steps.")

    prev = None
    for e in events:
        if prev is not None and e["ts_ms"] - prev["ts_ms"] > HESITATION_MS \
                and e["event_type"] not in ("WAIT", "PAGE_VIEW"):
            add("hesitation", "Long hesitation before action", "MEDIUM",
                f"{(e['ts_ms'] - prev['ts_ms']) / 1000:.1f}s pause before "
                f"{e['event_type'].lower()}.", e.get("element_id") or e["url"],
                "Likely decision uncertainty — clarify options at this step.")
        prev = e

    errs = [e for e in events if e["event_type"] == "ERROR"]
    if errs:
        add("error", f"{len(errs)} interaction error(s)", "HIGH",
            "; ".join((e.get("error") or "unknown") for e in errs[:3]),
            errs[0].get("element_id") or "", "Ensure interaction targets are stable and visible.")

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
