"""Deterministic agent policy for demo/mock mode. Real decisions on real pages."""
import re

STOP = set("the a an of for find best under get to and with in on my me i "
           "cheapest good it that this add cart".split())

def _keywords(task):
    return [w for w in re.findall(r"[a-zA-Z0-9]+", task.lower())
            if w not in STOP and len(w) > 2]

def decide_action(obs, task, persona, history):
    kws = _keywords(task)
    els = obs.get("elements", [])
    text = obs.get("text_sample", "").lower()
    clicks = sum(1 for h in history if h.get("action") == "click")

    if ("order confirmed" in text or "thank you" in text) and clicks > 0:
        return {"action": "finish", "reason": "Order confirmation is visible; task complete.",
                "confidence": 0.85}
    if len(history) >= 20:
        return {"action": "fail", "reason": "Effort budget exhausted; giving up.", "confidence": 0.6}

    # Type into search first
    if not any(h.get("action") == "type" for h in history):
        for el in els:
            if el["kind"] == "input" and any(w in el["text"].lower()
                    for w in ("search", "find", "query")):
                q = kws[0] if kws else "laptop"
                return {"action": "type", "target": el["id"], "text": q,
                        "reason": f"Search is the direct path to find '{q}'.", "confidence": 0.9}

    # Click links/buttons matching keywords
    best, score = None, 0
    for el in els:
        t = el["text"].lower()
        s = sum(1 for k in kws if k in t)
        if "price" in task.lower() and "price" in t:
            s += 2
        if s > score:
            best, score = el, s
    if best and score > 0 and clicks >= 1 or (best and best["kind"] == "link" and score > 0):
        return {"action": "click", "target": best["id"],
                "reason": f"'{best['text']}' best matches the task goal.", "confidence": 0.6}

    # Try filter/sort/apply controls
    for el in els:
        t = el["text"].lower()
        if el["kind"] == "button" and any(w in t for w in ("filter", "sort", "apply", "add", "buy")):
            return {"action": "click", "target": el["id"],
                    "reason": f"Trying control '{el['text']}' to progress.", "confidence": 0.5}

    # Explore: click a link containing a keyword, else first link
    if clicks == 0:
        for el in els:
            if el["kind"] == "link" and any(k in el["text"].lower() for k in kws):
                return {"action": "click", "target": el["id"],
                        "reason": f"Navigating to '{el['text']}' — likely relevant.", "confidence": 0.6}
        for el in els:
            if el["kind"] == "link":
                return {"action": "click", "target": el["id"],
                        "reason": "Exploring navigation.", "confidence": 0.4}

    if sum(1 for h in history if h.get("action") == "scroll") < 2:
        return {"action": "scroll", "reason": "Scrolling to reveal more content.", "confidence": 0.4}
    return {"action": "fail", "reason": "No relevant controls found.", "confidence": 0.5}
