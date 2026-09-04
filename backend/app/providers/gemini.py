import json
from backend.app.providers.base import LLMProvider
from backend.app.providers.parsing import parse_agent_action
from backend.app.config import settings

ALLOWED_ACTIONS = {"click", "type", "scroll", "navigate_back", "wait", "finish", "fail"}

DECIDE_PROMPT = """You are a synthetic user on a website. TASK: {task}
PERSONA ({persona_id}): {persona}
OBSERVATION: {obs}
RECENT ACTIONS: {hist}
COMPLETION CHECK: {completion_hint}
Respond ONLY with JSON, choosing target from available element IDs:
{{"action":"click|type|scroll|navigate_back|wait|finish|fail",
"target":"ELEMENT_ID for click/type","text":"text for type",
"reason":"short first-person reason","confidence":0.0-1.0}}
Use "finish" when the task is complete — if COMPLETION CHECK indicates the requested end
state already appears satisfied and the OBSERVATION confirms it, respond with finish now
instead of continuing to search. Only keep going if the requested end state genuinely has
not yet been reached. Use "fail" if impossible."""

AUTOPSY_PROMPT = """You are a UX analyst performing an autopsy on a synthetic user session.
Summary: {summary}
Deterministic friction evidence (do NOT invent new events): {friction}
Scores: {score}
Return ONLY JSON: {{"executive_summary":"3-5 sentences",
"root_causes":[{{"observed":"","possible_cause":"","likely_root_cause":"",
"recommendation":"","confidence":0.0-1.0}}]}}
Include one root_causes entry per friction evidence item, in the same order.
The numeric scores above are final and must not be changed or restated
differently. Use hedged language ("likely", "possible", "evidence suggests").
Distinguish observation from inference."""


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self):
        # Imported from the defining submodules rather than the `google.generativeai`
        # package root: the package re-exports these without an explicit `__all__`,
        # which trips static "private import" checks even though this is the
        # library's documented public API.
        from google.generativeai.client import configure
        from google.generativeai.generative_models import GenerativeModel

        configure(api_key=settings.gemini_api_key)
        self.model = GenerativeModel(settings.gemini_model)

    def decide(self, obs, task, persona, history, element_map, persona_id=None,
               completion_hint=None):
        prompt = DECIDE_PROMPT.format(
            task=task, persona=persona, persona_id=persona_id or "custom",
            obs=json.dumps(obs)[:6000], hist=json.dumps(history[-8:]),
            completion_hint=completion_hint or "No strong evidence yet that the task's end "
                                                "state has been reached.",
        )
        for _ in range(2):
            try:
                text = self.model.generate_content(prompt).text
                data = parse_agent_action(text, ALLOWED_ACTIONS)
                if data.get("action") in ("click", "type") and data.get("target") not in element_map:
                    data = {"action": "wait", "reason": "Target not found; re-observing.",
                            "confidence": 0.1}
                return data
            except Exception:
                continue
        return {"action": "wait", "reason": "LLM output invalid; safe fallback.", "confidence": 0.1}

    def autopsy(self, summary, friction, score):
        try:
            text = self.model.generate_content(AUTOPSY_PROMPT.format(
                summary=json.dumps(summary), friction=json.dumps(friction),
                score=json.dumps(score))).text
            data = _parse_autopsy_json(text)
            if "executive_summary" in data and "root_causes" in data:
                data["provider_used"] = "gemini"
                data["fallback"] = False
                data["fallback_reason"] = None
                return data
            raise ValueError("Gemini autopsy JSON missing required keys")
        except Exception as e:
            from backend.app.providers.mock import MockProvider
            fallback = MockProvider().autopsy(summary, friction, score)
            fallback["provider_used"] = "mock"
            fallback["fallback"] = True
            fallback["fallback_reason"] = f"{type(e).__name__}: {e}"
            return fallback


def _parse_autopsy_json(text: str) -> dict:
    """The autopsy response has a different shape than an agent action (no
    'action'/'target' fields to validate against), so it uses the same
    balanced-brace extraction as parse_agent_action but its own minimal
    shape check instead of the action-schema validator."""
    from backend.app.providers.parsing import _strip_fences, _balanced_objects, _try_json

    candidates = []
    for block in _strip_fences(text):
        for fragment in _balanced_objects(block) or [block]:
            data = _try_json(fragment)
            if isinstance(data, dict) and "executive_summary" in data and "root_causes" in data:
                if not any(data == c for c in candidates):
                    candidates.append(data)
    if not candidates:
        for fragment in _balanced_objects(text):
            data = _try_json(fragment)
            if isinstance(data, dict) and "executive_summary" in data and "root_causes" in data:
                if not any(data == c for c in candidates):
                    candidates.append(data)
    if len(candidates) != 1:
        raise ValueError("no unambiguous autopsy JSON found in LLM output")
    return candidates[0]
