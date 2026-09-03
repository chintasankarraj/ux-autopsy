import json, re
from backend.app.providers.base import LLMProvider
from backend.app.config import settings

DECIDE_PROMPT = """You are a synthetic user on a website. TASK: {task}
PERSONA: {persona}
OBSERVATION: {obs}
RECENT ACTIONS: {hist}
Respond ONLY with JSON, choosing target from available element IDs:
{{"action":"click|type|scroll|navigate_back|wait|finish|fail",
"target":"ELEMENT_ID for click/type","text":"text for type",
"reason":"short first-person reason","confidence":0.0-1.0}}
Use "finish" when the task is complete, "fail" if impossible."""

AUTOPSY_PROMPT = """You are a UX analyst performing an autopsy on a synthetic user session.
Summary: {summary}
Deterministic friction evidence (do NOT invent new events): {friction}
Scores: {score}
Return ONLY JSON: {{"executive_summary":"3-5 sentences",
"root_causes":[{{"observed":"","possible_cause":"","likely_root_cause":"","recommendation":""}}]}}
Use hedged language. Distinguish observation from inference."""

def _parse(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON in LLM output")
    return json.loads(m.group(0))

class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def decide(self, obs, task, persona, history, element_map):
        prompt = DECIDE_PROMPT.format(task=task, persona=persona,
            obs=json.dumps(obs)[:6000], hist=json.dumps(history[-8:]))
        for attempt in range(2):
            try:
                data = _parse(self.model.generate_content(prompt).text)
                if data.get("action") in ("click", "type") and data.get("target") not in element_map:
                    data = {"action": "wait", "reason": "Target not found; re-observing.",
                            "confidence": 0.1}
                return data
            except Exception:
                continue
        return {"action": "wait", "reason": "LLM output invalid; safe fallback.", "confidence": 0.1}

    def autopsy(self, summary, friction, score):
        try:
            data = _parse(self.model.generate_content(AUTOPSY_PROMPT.format(
                summary=json.dumps(summary), friction=json.dumps(friction),
                score=json.dumps(score))).text)
            if "executive_summary" in data and "root_causes" in data:
                return data
        except Exception:
            pass
        from backend.app.providers.mock import MockProvider
        return MockProvider().autopsy(summary, friction, score)
