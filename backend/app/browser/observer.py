"""Extracts a structured, LLM-friendly summary of interactive page elements.

Elements are identified purely by a sequential, typed ID (e.g. button_01,
link_02) built from SELECTORS below. Both this module and agents/agent.py's
build_map() iterate the same selectors, in the same order, filtering to the
same visible/enabled elements — so an ID handed to the provider at decide-time
resolves to the same element at execute-time. This ID whitelist is the safety
boundary: the model only ever chooses from IDs we hand it, never raw
selectors or code.
"""

# Mutually exclusive so no element is double-counted under two kinds.
SELECTORS = {
    "input": "input:not([type=submit]):not([type=button]):not([type=hidden]), textarea",
    "button": "button, input[type=submit], input[type=button], [role=button]",
    "link": "a[href]",
}


def _text_for(el) -> str:
    try:
        txt = (el.inner_text() or "").strip()
    except Exception:
        txt = ""
    if txt:
        return txt[:80]
    for attr in ("placeholder", "aria-label", "value", "title"):
        try:
            v = el.get_attribute(attr)
        except Exception:
            v = None
        if v and v.strip():
            return v.strip()[:80]
    return ""


def observe(page) -> dict:
    """Returns {url, title, elements: [{id, kind, text}], text_sample}.

    Only visible, enabled elements are included — matches the filtering
    agents/agent.py's build_map() applies when resolving IDs back to
    Locators, so decide-time and execute-time stay in sync.
    """
    elements = []
    for kind, sel in SELECTORS.items():
        loc = page.locator(sel)
        try:
            count = loc.count()
        except Exception:
            count = 0
        idx = 0
        for i in range(count):
            el = loc.nth(i)
            try:
                if el.is_disabled():
                    continue
                box = el.bounding_box()
            except Exception:
                box = None
            if not box or box["width"] <= 0 or box["height"] <= 0:
                continue
            idx += 1
            elements.append({"id": f"{kind}_{idx:02d}", "kind": kind, "text": _text_for(el)})

    try:
        body_text = page.locator("body").inner_text()
    except Exception:
        body_text = ""

    return {
        "url": page.url,
        "title": page.title(),
        "elements": elements,
        "text_sample": body_text[:2000],
    }
