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
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


def _fail(message: str) -> None:
    print(f"REFUSED: {message}", file=sys.stderr)
    sys.exit(1)


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
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--url", default="https://www.demoblaze.com/")
    parser.add_argument("--persona", default="beginner")
    parser.add_argument("--task", default="Find a laptop priced below $800 and add it to the cart.")
    parser.add_argument("--max-wait-seconds", type=int, default=300)
    args = parser.parse_args()

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

    session = _post(args.base_url, "/api/sessions",
                     {"url": args.url, "task": args.task, "persona": args.persona})
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
    print("\n--- Analysis / provenance ---")
    a = analysis.get("analysis") or {}
    print(f"action provider (session.provider): {s.get('provider')}")
    print(f"autopsy provider: {a.get('provider')}")
    print(f"autopsy fallback: {a.get('fallback')}  reason: {a.get('fallback_reason')}")
    print(f"friction points: {len(analysis.get('friction_points') or [])}")
    print(f"\nScreenshots: screenshots/{sid}_*.png ({sum(1 for e in events if e.get('screenshot_path'))} captured)")


if __name__ == "__main__":
    main()
