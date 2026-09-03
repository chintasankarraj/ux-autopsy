from backend.app.providers.base import LLMProvider
from backend.app.agents.heuristic import decide_action

SEV_RANK = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}

class MockProvider(LLMProvider):
    name = "mock"

    def decide(self, obs, task, persona, history, element_map):
        return decide_action(obs, task, persona, history)

    def autopsy(self, summary, friction, score):
        completed = summary.get("completed")
        fps = sorted(friction, key=lambda f: -SEV_RANK.get(f.get("severity"), 0))
        parts = [
            f"The synthetic user {'completed' if completed else 'did not complete'} the task in "
            f"{summary.get('actions_count', 0)} actions, with a computed UX score of "
            f"{score.get('ux_score', 0):.0f}/100."]
        if fps:
            w = fps[0]
            parts.append(f"The dominant friction signal was '{w['title']}' ({w['severity']}). "
                         "Evidence suggests an interface-design problem rather than user error.")
        else:
            parts.append("No significant friction signals were detected; the journey appears efficient.")
        parts.append("Generated in demo mode from deterministic heuristics — hypotheses should be "
                     "validated with real users.")
        roots = [{"observed": f["evidence"],
                  "possible_cause": f"Likely cause: the expected control or information at "
                                    f"'{f.get('affected_action') or 'this step'}' was not clearly discoverable.",
                  "likely_root_cause": "Evidence suggests a discoverability or labeling issue, "
                                       "not a task-understanding issue.",
                  "recommendation": f["recommendation"]} for f in fps] or \
                 [{"observed": "Task completed with few missteps.",
                   "possible_cause": "The flow matches the user's mental model.",
                   "likely_root_cause": "Likely cause: clear labels and conventional layout.",
                   "recommendation": "Preserve current structure; validate with more personas."}]
        return {"executive_summary": " ".join(parts), "root_causes": roots}
