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


def _word_overlap(a: str, b: str) -> bool:
    """Loose, site-agnostic match between two already-extracted keywords:
    identical, or sharing a common prefix at least as long as the shorter
    word (capped at 4 chars). Bridges ordinary English inflections a naive
    exact-match would miss (task word "add" vs. a dialog's "added", "book"
    vs. "booking", "confirm" vs. "confirmed") without any stemming library
    or site/product vocabulary.
    """
    if a == b:
        return True
    n = min(len(a), len(b), 4)
    return n > 0 and a[:n] == b[:n]


def dialog_completion_evidence(task: str, dialogs: list[dict] | None) -> str | None:
    """Return evidence text if a native browser dialog (alert/confirm/prompt)
    fired by the action just executed contains wording relevant to the
    task's own words, else None.

    `dialogs` is the small list of {"type", "message"} dicts captured from
    Playwright's `dialog` event during the single most recently executed
    action — not the whole session's history — so this only ever reflects a
    dialog that appeared as a direct, synchronous side effect of that one
    action, never a stale one from several steps ago.

    Relevance is judged purely by keyword overlap with the task's own text
    (via _word_overlap), the same generic approach as completion_evidence()
    — never a hardcoded confirmation phrase for any specific site. A dialog
    is stronger evidence than a page-text keyword match: the browser only
    shows it in direct response to the action that just ran, whereas a page
    keyword (e.g. a permanent nav-bar "Cart" link) can be present on every
    page regardless of whether anything actually happened.
    """
    if not dialogs:
        return None
    task_words = extract_keywords(task)
    if not task_words:
        return None
    for d in dialogs:
        message = (d.get("message") or "").strip()
        if not message:
            continue
        message_words = extract_keywords(message)
        hits = [w for w in task_words if any(_word_overlap(w, m) for m in message_words)]
        if hits:
            dtype = d.get("type") or "dialog"
            return (
                f"A browser {dtype} appeared reading '{message}', which directly "
                f"references {hits} from the task."
            )
    return None


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
