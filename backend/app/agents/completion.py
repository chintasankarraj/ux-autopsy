"""General-purpose task-completion evidence, independent of any specific site.

The signal is derived only from the task's own wording plus what the agent
has actually observed and done — never from a hardcoded product/selector/
site name — so it generalizes to an arbitrary website and an arbitrary task.
"""
import re

STOP = set("the a an of for find best under get to and with in on my me i "
           "is are was were be do does complete task website page".split())

# Generic English verbs that commonly express a task's completion action
# across many kinds of sites/tasks (shopping, booking, forms, subscriptions).
COMPLETION_VERBS = {
    "add", "buy", "purchase", "order", "book", "reserve", "subscribe",
    "register", "submit", "checkout", "apply", "download", "sign", "save",
    "confirm", "complete", "finish",
}

def extract_keywords(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
            if w not in STOP and len(w) > 2 and not w.isdigit()]


def completion_evidence(task: str, history: list[dict], obs: dict) -> str | None:
    """Return a short human-readable evidence string if the task's stated
    action already appears to have been performed AND the current page still
    shows the task's subject matter (a generic proxy for "still relevant /
    confirmed"), else None.

    Both conditions are derived purely from the task text, the recorded
    action labels, and the current page's text — nothing here is specific to
    any one website.
    """
    task_words = extract_keywords(task)
    action_words = [w for w in task_words if w in COMPLETION_VERBS] or list(COMPLETION_VERBS)
    object_words = [w for w in task_words if w not in COMPLETION_VERBS]
    if not object_words:
        return None

    performed = None
    for h in history:
        if h.get("action") not in ("click", "type"):
            continue
        label = (h.get("text") or "").lower()
        if not label:
            continue
        if any(v in label for v in action_words):
            performed = h
    if performed is None:
        return None

    page_text = (obs.get("text_sample") or "").lower()
    object_hits = [w for w in object_words if w in page_text]
    if not object_hits:
        return None

    return (
        f"Already performed '{performed.get('text')}' (matches the task's action), and the "
        f"current page still references {object_hits} from the task."
    )


def evaluate_completion(streak: int, hint: str | None, action: dict) -> tuple[int, dict | None]:
    """Update the consecutive-strong-evidence streak and decide whether to
    override the model's decision with an automatic finish.

    Only overrides when the SAME strong evidence has persisted across two or
    more consecutive decisions and the model still hasn't finished — a
    conservative safety net for the specific failure mode of an agent
    revisiting/exploring after the requested end state was already reached,
    without ever falsely finishing on a single, unconfirmed observation.
    """
    new_streak = streak + 1 if hint else 0
    if new_streak >= 2 and isinstance(action, dict) and action.get("action") not in ("finish", "fail"):
        return new_streak, {
            "action": "finish",
            "reason": f"Automatic completion check: {hint}",
            "confidence": 0.9,
        }
    return new_streak, None
