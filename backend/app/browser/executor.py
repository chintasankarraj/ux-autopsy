"""Safe execution of structured agent actions against a Playwright page.

Only a fixed whitelist of actions is executable (click/type/scroll/
navigate_back/wait/finish/fail), each targeting an element ID resolved by
agents/agent.py's build_map() against the current page. There is no raw
selector or code-execution path exposed to the provider (LLM) — this is the
hard safety boundary between "the model decides" and "the model can do
anything."
"""


def execute(page, action: dict, emap: dict, settings) -> dict:
    act = action.get("action")
    target = action.get("target")

    try:
        if act == "click":
            loc = emap.get(target)
            if loc is None:
                return {"success": False, "error": f"Unknown target '{target}'"}
            loc.click(timeout=settings.action_timeout_ms)
            return {"success": True}

        if act == "type":
            loc = emap.get(target)
            if loc is None:
                return {"success": False, "error": f"Unknown target '{target}'"}
            loc.fill(action.get("text") or "", timeout=settings.action_timeout_ms)
            return {"success": True}

        if act == "scroll":
            page.mouse.wheel(0, 700)
            return {"success": True}

        if act == "navigate_back":
            page.go_back(timeout=settings.action_timeout_ms)
            return {"success": True}

        if act == "wait":
            page.wait_for_timeout(1000)
            return {"success": True}

        if act in ("finish", "fail"):
            return {"success": True}

        return {"success": False, "error": f"Unknown action '{act}'"}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}
