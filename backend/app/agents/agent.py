import os, time
from playwright.sync_api import sync_playwright, ViewportSize
from backend.app.config import settings
from backend.app.browser.observer import observe, SELECTORS, OBSERVE_PROBE_TIMEOUT_MS
from backend.app.browser.executor import execute
from backend.app.providers.base import get_provider
from backend.app.agents.completion import (
    completion_evidence,
    dialog_completion_evidence,
    evaluate_completion,
)

ALLOWED_ACTIONS = {"click", "type", "scroll", "navigate_back", "wait", "finish", "fail"}


def capture_dialogs(page) -> list[dict]:
    """Register a generic Playwright dialog listener (alert/confirm/prompt/
    beforeunload -- a browser primitive, not a site-specific one) and return
    the list it appends {"type", "message"} dicts to as dialogs occur.

    Left unhandled, Playwright already auto-dismisses any dialog silently --
    this preserves that exact dismiss behavior, it just also records what
    the dialog said, so completion evidence has something to work with
    instead of the content being discarded.
    """
    dialogs: list[dict] = []

    def on_dialog(dialog):
        dialogs.append({"type": dialog.type, "message": dialog.message})
        try:
            dialog.dismiss()
        except Exception:
            pass

    page.on("dialog", on_dialog)
    return dialogs


def build_map(page):
    """Rebuild element_id -> Locator with the same ordering rules as the observer."""
    mapping = {}
    for prefix, sel in SELECTORS.items():
        loc = page.locator(sel)
        for i in range(loc.count()):
            el = loc.nth(i)
            try:
                if el.is_disabled(timeout=OBSERVE_PROBE_TIMEOUT_MS):
                    continue
                box = el.bounding_box(timeout=OBSERVE_PROBE_TIMEOUT_MS)
            except Exception:
                box = None
            if box and box["width"] > 0 and box["height"] > 0:
                mapping[f"{prefix}_{len([k for k in mapping if k.startswith(prefix)]) + 1:02d}"] = el
    return mapping

def run_agent(session_id, url, task, persona_desc, provider_name, on_event, persona_id="custom"):
    provider = get_provider(provider_name)
    summary = {"actions_count": 0, "pages_visited": 0, "completed": False,
               "duration_ms": 0, "error": None, "abandoned": False, "abandon_reason": ""}
    history = []
    os.makedirs("screenshots", exist_ok=True)
    # Mobile User gets a real narrow viewport, not just a label — the demo
    # site's responsive layout genuinely renders (and hides) different
    # controls at this width, so any resulting friction is structural.
    viewport: ViewportSize = (
        {"width": 390, "height": 844} if persona_id == "mobile_user" else {"width": 1280, "height": 800}
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=settings.headless)
        page = browser.new_page(viewport=viewport)
        navs, start = 0, time.time()
        t0 = time.time()
        completion_streak = 0
        all_dialogs = capture_dialogs(page)
        dialogs_seen = 0
        last_action_dialogs = []

        def shot(name):
            path = f"screenshots/{session_id}_{name}.png"
            try:
                page.screenshot(path=path)
                return path
            except Exception:
                return None

        try:
            page.goto(url, timeout=25000, wait_until="domcontentloaded")
        except Exception as e:
            summary["error"] = f"Website could not be loaded: {type(e).__name__}"
            on_event({"event_type": "ERROR", "url": url, "error": summary["error"]})
            browser.close()
            return summary

        summary["pages_visited"] += 1
        on_event({"event_type": "PAGE_VIEW", "url": page.url,
                  "element_text": page.title(), "screenshot_path": shot("load")})

        for step in range(settings.max_actions):
            if time.time() - start > settings.max_session_seconds:
                summary["abandoned"] = True
                summary["abandon_reason"] = "Session time limit reached."
                on_event({"event_type": "ABANDONMENT", "url": page.url,
                          "element_text": summary["abandon_reason"]})
                break
            observe_start = time.time()
            obs = observe(page)
            emap = build_map(page)
            observe_ms = int((time.time() - observe_start) * 1000)
            # A dialog is stronger evidence than a page-text keyword because
            # it only ever appears as a direct, synchronous side effect of
            # the single action that just ran (last_action_dialogs), not
            # something that could be permanently present on every page
            # (e.g. a nav-bar "Cart" link) regardless of what happened.
            hint = dialog_completion_evidence(task, last_action_dialogs) or completion_evidence(task, history, obs)
            decide_start = time.time()
            action = provider.decide(obs, task, persona_desc, history, emap, persona_id=persona_id,
                                      completion_hint=hint)
            decide_ms = int((time.time() - decide_start) * 1000)
            if (
                not isinstance(action, dict)
                or action.get("action") not in ALLOWED_ACTIONS
                or (action.get("action") in ("click", "type") and action.get("target") not in emap)
            ):
                action = {"action": "wait", "reason": "Invalid or unsafe agent output; retrying.",
                          "confidence": 0.0}

            completion_streak, override = evaluate_completion(completion_streak, hint, action)
            if override:
                action = override

            pre_url = page.url
            element_text = next((e["text"] for e in obs.get("elements", [])
                                  if e["id"] == action.get("target")), None)
            result = execute(page, action, emap, settings)
            summary["duration_ms"] = int((time.time() - t0) * 1000)

            # Any dialog the action itself triggered (e.g. a confirmation
            # alert) is now sitting in all_dialogs, captured synchronously by
            # on_dialog() during execute()'s blocking click()/fill() call.
            # Make it available to the *next* iteration's completion check
            # now; its own timeline event is emitted below, after the action
            # event that caused it, so the timeline reads causally.
            new_dialogs = all_dialogs[dialogs_seen:]
            dialogs_seen = len(all_dialogs)
            last_action_dialogs = new_dialogs
            act = action["action"]
            event_type = "BACKTRACK" if act == "navigate_back" else act.upper()

            on_event({"event_type": event_type, "url": pre_url,
                      "element_id": action.get("target"),
                      "element_text": element_text,
                      "action": act, "reason": action.get("reason", ""),
                      "confidence": action.get("confidence"),
                      "screenshot_path": shot(f"s{step}"),
                      "duration_ms": int((time.time() - t0) * 1000),
                      "decide_ms": decide_ms,
                      "observe_ms": observe_ms,
                      "success": int(result["success"]), "error": result.get("error")})

            for d in new_dialogs:
                on_event({"event_type": "DIALOG", "url": page.url,
                          "element_text": d["message"], "action": d["type"],
                          "success": 1})

            if not result["success"] and act not in ("finish", "fail"):
                on_event({"event_type": "ERROR", "url": page.url,
                          "element_id": action.get("target"), "error": result.get("error")})
                history.append({"action": "wait"})
                continue

            # `text` carries the element's label, not just its (ephemeral,
            # DOM-order-based) id — the id can refer to a different element
            # next observation, so persona logic that needs to know "have I
            # already clicked the thing labeled X" checks this instead.
            history.append({"action": act, "target": action.get("target"), "text": element_text})
            summary["actions_count"] += 1

            if page.url != pre_url:
                navs += 1
                summary["pages_visited"] += 1
                on_event({"event_type": "NAVIGATION", "url": page.url,
                          "screenshot_path": shot("nav")})
                if navs > settings.max_navigations:
                    summary["abandoned"] = True
                    summary["abandon_reason"] = "Navigation limit reached."
                    break

            if act == "finish":
                summary["completed"] = True
                on_event({"event_type": "TASK_SUCCESS", "url": page.url})
                break
            if act == "fail":
                on_event({"event_type": "TASK_FAILURE", "url": page.url,
                          "reason": action.get("reason", "")})
                break
        else:
            summary["abandoned"] = True
            summary["abandon_reason"] = "Action limit reached without task completion."
            on_event({"event_type": "ABANDONMENT", "url": page.url,
                      "element_text": summary["abandon_reason"]})
        browser.close()
    return summary
