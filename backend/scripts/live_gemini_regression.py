"""Live Gemini regression — the ONLY intentional path to a real Gemini API
call in this repository's tooling.

This is a plain script, not a pytest test, and is never collected or run by
`pytest`/`playwright test`. It exists precisely because those normal test
suites must never consume live Gemini quota (see backend/tests/conftest.py).

Requirements before running:
  1. The backend server must already be running, configured for real Gemini
     (LLM_PROVIDER=gemini or auto + a real GEMINI_API_KEY in .env), e.g.:
         python -m uvicorn backend.app.main:app --port 8000
  2. You must explicitly opt in via an environment variable — this script
     refuses to run otherwise:
         UX_AUTOPSY_ALLOW_LIVE_GEMINI=1

Usage (from the project root, with the venv active):
    UX_AUTOPSY_ALLOW_LIVE_GEMINI=1 backend/.venv/Scripts/python.exe \\
        backend/scripts/live_gemini_regression.py \\
        [--base-url http://localhost:8000] \\
        [--url https://www.demoblaze.com/] \\
        [--persona beginner] \\
        [--task "Find a laptop priced below $800 and add it to the cart."]

This consumes real Gemini API quota. Run it deliberately and sparingly, not
as part of routine development.

A NOTE ON SHELL QUOTING: a task string containing "$" (as in a price, e.g.
"$800") is at risk of shell variable expansion if it's ever placed inside
DOUBLE quotes on a command line — bash expands "$800" to positional
parameter $8 (empty) followed by "00", silently corrupting the task before
this script ever sees it. This is a shell-invocation hazard, not something
this script's own argument parsing can detect after the fact. Two safe
options, in order of robustness:
  1. --task-file PATH — reads the task text verbatim from a local file.
     Immune to shell quoting entirely, regardless of shell (bash/
     PowerShell/cmd.exe). This is the recommended way to pass any task
     text containing "$", quotes, or other shell metacharacters.
  2. Single-quote --task in bash/PowerShell (single quotes never expand
     variables in either shell): --task 'Find a laptop priced below $800
     and add it to the cart.'
Never double-quote a --task value containing "$" followed by digits.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _fail(message: str) -> None:
    print(f"REFUSED: {message}", file=sys.stderr)
    sys.exit(1)


DEFAULT_TASK = "Find a laptop priced below $800 and add it to the cart."


def build_parser() -> argparse.ArgumentParser:
    """Pure argument-parser construction — no I/O, no network. Kept separate
    from main() so tests can exercise argument/task resolution in isolation,
    without making any real Gemini API request."""
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--url", default="https://www.demoblaze.com/")
    parser.add_argument("--persona", default="beginner")
    parser.add_argument("--task", default=DEFAULT_TASK,
                         help="Task text. WARNING: if it contains \"$\" followed by digits "
                              "(e.g. a price), double-quoting it on a command line risks shell "
                              "variable expansion — prefer --task-file, or single-quote it.")
    parser.add_argument("--task-file", default=None,
                         help="Path to a file containing the task text verbatim. Takes "
                              "priority over --task when given. Immune to shell quoting — the "
                              "safest way to pass task text containing \"$\" or other "
                              "shell-special characters.")
    parser.add_argument("--max-wait-seconds", type=int, default=300)
    return parser


def resolve_task(args: argparse.Namespace) -> str:
    """The exact task string to send, with --task-file taking priority. No
    shell is involved in reading a file's contents, so this is immune to
    the variable-expansion hazard described in the module docstring."""
    if args.task_file:
        return Path(args.task_file).read_text(encoding="utf-8").strip()
    return args.task


def _get(base_url: str, path: str) -> dict:
    with urllib.request.urlopen(f"{base_url}{path}", timeout=10) as resp:
        return json.load(resp)


def _post(base_url: str, path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def main() -> None:
    args = build_parser().parse_args()
    task = resolve_task(args)

    if os.getenv("UX_AUTOPSY_ALLOW_LIVE_GEMINI") != "1":
        _fail(
            "This script makes a real Gemini API call and consumes live quota. "
            "Set UX_AUTOPSY_ALLOW_LIVE_GEMINI=1 to explicitly opt in. "
            "Normal development and the automated test suites never need this."
        )

    try:
        health = _get(args.base_url, "/api/health")
    except urllib.error.URLError as e:
        _fail(f"Could not reach backend at {args.base_url} — is uvicorn running? ({e})")
        return

    if health.get("provider") != "gemini":
        _fail(
            f"Backend at {args.base_url} reports provider={health.get('provider')!r}, "
            "not 'gemini'. Configure LLM_PROVIDER=gemini/auto and a real "
            "GEMINI_API_KEY in .env, then restart the backend, before running this script."
        )

    print(f"Live Gemini regression starting against {args.url!r} "
          f"(persona={args.persona!r}) — this WILL consume real API quota.")
    print(f"Task: {task!r}")

    session = _post(args.base_url, "/api/sessions",
                     {"url": args.url, "task": task, "persona": args.persona})
    sid = session["id"]
    print(f"Session created: {sid}")

    deadline = time.time() + args.max_wait_seconds
    status = "pending"
    while time.time() < deadline:
        s = _get(args.base_url, f"/api/sessions/{sid}")
        status = s["status"]
        if status in ("completed", "failed"):
            break
        time.sleep(2)

    s = _get(args.base_url, f"/api/sessions/{sid}")
    events = _get(args.base_url, f"/api/sessions/{sid}/events")
    analysis = _get(args.base_url, f"/api/sessions/{sid}/analysis")

    parser_failures = sum(
        1 for e in events if (e.get("reason") or "") == "LLM output invalid; safe fallback."
    )

    print("\n--- Session ---")
    print(json.dumps(s, indent=2))
    print(f"\n--- Events: {len(events)} total, {parser_failures} parser-fallback ---")
    # Per-event timing breakdown — makes an unexplained gap directly visible
    # (e.g. a large ts_ms delta not accounted for by decide_ms/observe_ms)
    # without needing to manually diff raw timestamps after the fact.
    prev_ts = None
    for e in events:
        ts = e.get("ts_ms")
        gap = f"{ts - prev_ts}ms" if prev_ts is not None and ts is not None else "-"
        prev_ts = ts if ts is not None else prev_ts
        print(f"  [{ts:>8}ms] gap={gap:<10} decide_ms={e.get('decide_ms')} "
              f"observe_ms={e.get('observe_ms')}  {e.get('event_type')}: "
              f"{e.get('reason') or e.get('element_text') or ''}")
    print("\n--- Analysis / provenance ---")
    a = analysis.get("analysis") or {}
    print(f"action provider (session.provider): {s.get('provider')}")
    print(f"autopsy provider: {a.get('provider')}")
    print(f"autopsy fallback: {a.get('fallback')}  reason: {a.get('fallback_reason')}")
    print(f"friction points: {len(analysis.get('friction_points') or [])}")
    print(f"\nScreenshots: screenshots/{sid}_*.png ({sum(1 for e in events if e.get('screenshot_path'))} captured)")


if __name__ == "__main__":
    main()
