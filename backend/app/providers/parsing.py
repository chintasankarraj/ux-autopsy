"""Robust extraction of a single structured action from raw LLM text output.

Real Gemini responses are frequently NOT bare JSON: they arrive wrapped in
markdown code fences, preceded by explanatory prose ("Here's my decision:"),
or followed by trailing commentary — any of which can itself contain stray
brace characters. A naive "first { to last }" regex grabs the wrong span in
those cases and corrupts an otherwise-valid response.

This module extracts every balanced top-level JSON object literal from the
text (proper brace/string-aware scanning, not a greedy regex), tries each as
JSON (with one harmless-formatting repair pass for trailing commas), and
accepts the result only if it validates as a plausible action dict. Ambiguous
output (more than one distinct valid candidate) is rejected rather than
guessed at — callers keep their existing safe-fallback behavior.
"""
import json
import re

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


def _strip_fences(text: str) -> list[str]:
    """Return fenced-block contents if any exist, else the original text."""
    blocks = [m.group(1) for m in _FENCE_RE.finditer(text)]
    return blocks if blocks else [text]


def _balanced_objects(text: str) -> list[str]:
    """Scan for every top-level {...} substring with balanced braces,
    respecting (double-)quoted strings so a brace inside a string value
    doesn't throw off the count."""
    candidates = []
    depth = 0
    start = None
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    candidates.append(text[start:i + 1])
                    start = None
    return candidates


def _try_json(fragment: str):
    try:
        return json.loads(fragment)
    except (ValueError, TypeError):
        pass
    # One conservative repair: a trailing comma before a closing bracket is a
    # common, harmless LLM formatting slip — not a structural ambiguity.
    repaired = _TRAILING_COMMA_RE.sub(r"\1", fragment)
    try:
        return json.loads(repaired)
    except (ValueError, TypeError):
        return None


def _validate_action(data, allowed_actions) -> bool:
    if not isinstance(data, dict):
        return False
    action = data.get("action")
    if not isinstance(action, str) or action not in allowed_actions:
        return False
    if action in ("click", "type"):
        target = data.get("target")
        if not isinstance(target, str) or not target.strip():
            return False
    if "confidence" in data and data["confidence"] is not None:
        try:
            float(data["confidence"])
        except (TypeError, ValueError):
            return False
    return True


def parse_agent_action(text: str, allowed_actions) -> dict:
    """Extract a single valid action dict from raw LLM output.

    Raises ValueError if no valid action is found, or if the output is
    ambiguous (multiple distinct valid candidates) — callers should treat
    both as parse failure and fall back to a safe default action.
    """
    if not text or not text.strip():
        raise ValueError("empty LLM output")

    valid: list[dict] = []
    for block in _strip_fences(text):
        for fragment in _balanced_objects(block) or [block]:
            data = _try_json(fragment)
            if data is not None and _validate_action(data, allowed_actions):
                if data.get("confidence") is not None:
                    try:
                        data["confidence"] = max(0.0, min(1.0, float(data["confidence"])))
                    except (TypeError, ValueError):
                        data["confidence"] = None
                if not any(data == v for v in valid):
                    valid.append(data)

    if not valid:
        # Fall back to scanning the raw (unfenced) text too, in case fences
        # were absent but the JSON still had surrounding prose.
        for fragment in _balanced_objects(text):
            data = _try_json(fragment)
            if data is not None and _validate_action(data, allowed_actions):
                if not any(data == v for v in valid):
                    valid.append(data)

    if len(valid) == 0:
        raise ValueError("no valid action JSON found in LLM output")
    if len(valid) > 1:
        raise ValueError("ambiguous LLM output: multiple distinct action candidates")
    return valid[0]
