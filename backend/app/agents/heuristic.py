"""Deterministic, persona-differentiated agent policy for demo/mock mode.

Every branch below returns a structured action derived from the CURRENT
observed page state (obs["elements"], obs["text_sample"]) and the REAL
history of actions already taken this session — nothing here fabricates an
event or a score; it only decides what a real Playwright browser does next,
and the resulting timestamps/events are what friction detection and scoring
actually run on.

Personas differ in genuinely different ways, not just narration:
- which controls they try (and in what order)
- whether they make a plausible-but-wrong first attempt
- how much budget they have before giving up
- whether they pause (a real `time.sleep`, not a fabricated timestamp) before
  retrying, which is what makes hesitation friction detectable at all
"""
import re
import time

STOP = set("the a an of for find best under get to and with in on my me i "
           "cheapest good it that this add cart complete purchase".split())

def _keywords(task):
    # Purely-numeric tokens (e.g. "000" out of "₹60,000") are excluded here —
    # they coincidentally substring-match unrelated price labels ("Under
    # ₹30,000" also contains "000"), causing false keyword-relevance matches.
    # Numeric amounts are interpreted specifically by _target_price() instead.
    return [w for w in re.findall(r"[a-zA-Z0-9]+", task.lower())
            if w not in STOP and len(w) > 2 and not w.isdigit()]

# A control matching a HIGH_PRIORITY word always wins over one matching only a
# LOW_PRIORITY word — this is what keeps "Buy Now"/"Buy" reachable even while
# an "Add to Cart" button (a LOW_PRIORITY match) is still visible nearby,
# preventing the agent from looping on a plausible-but-incomplete control.
HIGH_PRIORITY_WORDS = ("buy", "checkout", "order", "confirm", "place")
LOW_PRIORITY_WORDS = ("filter", "sort", "apply", "add")

# Behavior profile per persona. Anything not listed falls back to DEFAULT_PROFILE.
PROFILES = {
    "budget_shopper": {"use_filter": True, "action_budget": 22},
    "power_user": {"use_filter": True, "skip_search": True, "action_budget": 20},
    "beginner": {"wrong_click_add_to_cart": True, "hesitate_before_retry": True, "action_budget": 22},
    "impatient": {"wasted_first_click": True, "action_budget": 10},
    "mobile_user": {"use_filter": True, "action_budget": 24},
}
DEFAULT_PROFILE = {"action_budget": 20}


def _find(els, words, kind=None, exclude_words=()):
    for el in els:
        if kind and el["kind"] != kind:
            continue
        t = el["text"].lower()
        if any(x in t for x in exclude_words):
            continue
        if any(w in t for w in words):
            return el
    return None


def _already_clicked(history, label):
    return any(h.get("text") == label for h in history)


def _target_price(task):
    m = re.search(r"₹\s*([\d,]+)", task)
    return int(m.group(1).replace(",", "")) if m else None


def _best_price_pill(els, target_price):
    """The tightest 'Under ₹X' bracket that still covers the task's budget —
    not just the first price pill in DOM order, which could filter the
    matching product out entirely if it names a lower amount."""
    candidates = []
    for el in els:
        if el["kind"] != "button":
            continue
        m = re.search(r"under\s*₹\s*([\d,]+)", el["text"].lower())
        if m:
            candidates.append((int(m.group(1).replace(",", "")), el))
    if not candidates:
        return None
    if target_price is None:
        return min(candidates, key=lambda c: c[0])[1]
    covering = [c for c in candidates if c[0] >= target_price]
    return min(covering, key=lambda c: c[0])[1] if covering else max(candidates, key=lambda c: c[0])[1]


def decide_action(obs, task, persona_id, history):
    profile = PROFILES.get(persona_id, DEFAULT_PROFILE)
    kws = _keywords(task)
    els = obs.get("elements", [])
    text = obs.get("text_sample", "").lower()
    clicks = sum(1 for h in history if h.get("action") == "click")
    types = sum(1 for h in history if h.get("action") == "type")

    if ("order confirmed" in text or "thank you" in text) and clicks > 0:
        return {"action": "finish", "reason": "Order confirmation is visible; task complete.",
                "confidence": 0.9}
    if len(history) >= profile["action_budget"]:
        return {"action": "fail", "reason": "Effort budget exhausted; giving up.", "confidence": 0.6}

    # Impatient: tries the first prominent-looking control before reading
    # anything closely — a real, if wasteful, first move (not a fabricated one).
    if profile.get("wasted_first_click") and clicks == 0 and types == 0:
        prominent = _find(els, ("sort", "featured", "price"), kind="button")
        if prominent:
            return {"action": "click", "target": prominent["id"],
                    "reason": "Trying the first prominent control without reading it closely.",
                    "confidence": 0.35}

    # Filter-seeking personas: open the filter panel, narrow by category
    # (only needed if search was skipped) then by price.
    if profile.get("use_filter"):
        needs_search_first = not profile.get("skip_search") and types == 0
        if not needs_search_first:
            filter_toggle = _find(els, ("filter",), kind="button") or _find(els, ("filter",), kind="link")
            filter_opened = any("filter" in (h.get("text") or "").lower() for h in history)

            if not filter_opened and filter_toggle:
                return {"action": "click", "target": filter_toggle["id"],
                        "reason": "Opening the filter panel to narrow results.", "confidence": 0.6}

            if profile.get("skip_search"):
                category_pill = _find(
                    els, kws, kind="button",
                    exclude_words=("buy", "cart", "filter", "sort", "under", "price", "featured"),
                )
                if category_pill and not _already_clicked(history, category_pill["text"]):
                    return {"action": "click", "target": category_pill["id"],
                            "reason": f"Narrowing to the right category via '{category_pill['text']}'.",
                            "confidence": 0.75}

            price_pill = _best_price_pill(els, _target_price(task))
            if price_pill and not _already_clicked(history, price_pill["text"]):
                return {"action": "click", "target": price_pill["id"],
                        "reason": f"Filtering to '{price_pill['text']}' to match the budget.",
                        "confidence": 0.8}

        # Mobile: the filter toggle is tucked behind a menu button once the
        # toolbar has collapsed at a narrow viewport.
        menu_btn = _find(els, ("menu", "☰"), kind="button")
        filter_visible = _find(els, ("filter",), kind="button") or _find(els, ("filter",), kind="link")
        if menu_btn and not filter_visible and not _already_clicked(history, menu_btn["text"]):
            return {"action": "click", "target": menu_btn["id"],
                    "reason": "Opening the mobile menu to find more options.", "confidence": 0.5}

    # Type into search first (unless this persona skips search entirely).
    if not profile.get("skip_search") and types == 0:
        for el in els:
            if el["kind"] == "input" and any(w in el["text"].lower()
                    for w in ("search", "find", "query")):
                q = kws[0] if kws else "laptop"
                return {"action": "type", "target": el["id"], "text": q,
                        "reason": f"Search is the direct path to find '{q}'.", "confidence": 0.9}

    # Beginner: a plausible-but-incomplete first click before the real one.
    if profile.get("wrong_click_add_to_cart") and clicks == 0 and types >= 1:
        add_btn = _find(els, ("add to cart",), kind="button")
        if add_btn:
            return {"action": "click", "target": add_btn["id"],
                    "reason": "'Add to Cart' looks like the way to get this item.",
                    "confidence": 0.4}

    # Beginner: hesitates once, right after the wrong click — a real pause,
    # so the resulting event timestamps carry genuine evidence of it.
    if profile.get("hesitate_before_retry") and clicks == 1:
        time.sleep(7)

    # Click links/buttons matching keywords — skipping anything already
    # clicked, so a control that no longer changes anything (e.g. an already-
    # selected filter pill) can't be re-picked forever.
    best, score = None, 0
    for el in els:
        if _already_clicked(history, el["text"]):
            continue
        t = el["text"].lower()
        s = sum(1 for k in kws if k in t)
        if "price" in task.lower() and "price" in t:
            s += 2
        if s > score:
            best, score = el, s
    if best and score > 0 and clicks >= 1 or (best and best["kind"] == "link" and score > 0):
        return {"action": "click", "target": best["id"],
                "reason": f"'{best['text']}' best matches the task goal.", "confidence": 0.6}

    # Try checkout/filter/sort controls, preferring anything that completes
    # the purchase over anything that only adds/narrows — this priority is
    # what keeps "Buy Now"/"Buy" reachable even while "Add to Cart" is still
    # visible nearby, instead of looping on the plausible-but-wrong control.
    unclicked_els = [el for el in els if not _already_clicked(history, el["text"])]
    high = _find(unclicked_els, HIGH_PRIORITY_WORDS, kind="button")
    if high:
        return {"action": "click", "target": high["id"],
                "reason": f"'{high['text']}' progresses toward completing the purchase.", "confidence": 0.7}
    low = _find(unclicked_els, LOW_PRIORITY_WORDS, kind="button")
    if low:
        return {"action": "click", "target": low["id"],
                "reason": f"Trying control '{low['text']}' to progress.", "confidence": 0.5}

    # Explore: click a link containing a keyword, else first link.
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
