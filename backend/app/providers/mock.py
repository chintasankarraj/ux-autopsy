from backend.app.providers.base import LLMProvider
from backend.app.agents.heuristic import decide_action

SEV_RANK = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}

# Human-readable phrasing per friction signal, used only to narrate evidence
# that friction.py already computed — never to invent a signal that wasn't
# actually detected.
SIGNAL_OBSERVED_PHRASES = {
    "repeated_action": "clicked the same control multiple times without visible progress",
    "incorrect_click": "tried one or more other controls before finding the one that worked",
    "backtrack": "returned to a page already visited",
    "hesitation": "paused noticeably before acting",
    "error": "hit an interaction error",
    "repeated_search": "searched more than once while comparing options",
    "dead_end": "ended the session without a clear outcome",
    "abandonment": "gave up before completing the task",
    "excessive_actions": "needed an unusually high number of actions",
    "task_failed": "was unable to complete the task",
}


class MockProvider(LLMProvider):
    name = "mock"

    def decide(self, obs, task, _persona, history, _element_map, persona_id=None):
        return decide_action(obs, task, persona_id or "custom", history)

    def autopsy(self, summary, friction, score):
        completed = summary.get("completed")
        persona_display = summary.get("persona_display") or "synthetic user"
        fps = sorted(friction, key=lambda f: -SEV_RANK.get(f.get("severity"), 0))

        ux_score = score.get("ux_score", 0)
        parts = [
            f"The {persona_display} {'completed' if completed else 'did not complete'} the task in "
            f"{summary.get('actions_count', 0)} actions, with a computed UX score of "
            f"{ux_score:.1f}/100."
        ]
        if fps:
            w = fps[0]
            parts.append(f"The dominant friction signal was '{w['title']}' ({w['severity']}). "
                         "Evidence suggests an interface-design problem rather than user error.")
        else:
            parts.append("No significant friction signals were detected; the journey appears efficient.")
        parts.append("Generated in demo mode from deterministic heuristics — hypotheses should be "
                     "validated with real users.")

        if fps:
            roots = []
            for f in fps:
                phrase = SIGNAL_OBSERVED_PHRASES.get(f["signal"], "ran into friction")
                roots.append({
                    "observed": f"The {persona_display} {phrase} ({f['evidence']}).",
                    "possible_cause": f"Possible cause: the expected control or information at "
                                      f"'{f.get('affected_action') or 'this step'}' was not clearly discoverable.",
                    "likely_root_cause": "Evidence suggests a discoverability or labeling issue, "
                                         "not a task-understanding issue.",
                    "recommendation": f["recommendation"],
                    "confidence": round(f.get("confidence", 0.6), 2),
                })
        else:
            roots = [{
                "observed": f"The {persona_display} completed the task with few missteps.",
                "possible_cause": "The flow matches the user's mental model.",
                "likely_root_cause": "Likely cause: clear labels and conventional layout.",
                "recommendation": "Preserve current structure; validate with more personas.",
                "confidence": 0.85,
            }]
        return {"executive_summary": " ".join(parts), "root_causes": roots}
