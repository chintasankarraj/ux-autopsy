# PROJECT_STATUS

Last updated: 2026-09-04

## Summary

UX Autopsy is now a working, end-to-end product. Every item on the Phase 20
acceptance checklist (see below) passes locally. This document records what
was inherited, what was broken, what was fixed, and what remains a known
limitation.

## What was inherited

The repository contained file/folder scaffolding for the full intended
architecture, but **every file was 0 bytes** except
`backend/app/providers/base.py`, which contained a corrupted RAR archive
header instead of Python. There was no working code to take over at the
start of this session.

Partway through the session, real generated code was pasted into most files
(backend business logic, most of the frontend). That pasted implementation —
a raw-SQLite, dict-based FastAPI backend + React/Vite frontend — was adopted
as the architecture of record. Files it didn't reach (`config.py`, `db.py`,
`schemas.py`, the `browser/` module, two frontend components) were written
fresh to match its expected interfaces.

## Current status: working

- Backend starts cleanly, frontend starts cleanly, SQLite schema initializes
  on first run.
- Demo mode works with zero configuration (no API key needed).
- The full flow — dashboard → new test → demo → running → results → UX
  Autopsy → timeline → comparison — works in a real browser, verified with
  Playwright screenshots.
- 16/16 backend tests pass (unit + live-server API integration). 2/2
  frontend Playwright E2E tests pass. Frontend type-checks clean (`tsc -b`).

## Bugs found and fixed this session

1. **`session_service.py` was corrupted mid-file** — the paste was cut off
   by an LLM response-length limit and a literal "Reply **continue**"
   message was embedded in the file, followed by a duplicated, still-broken
   continuation. Rewrote the file cleanly, including the missing `retest()`
   and `dashboard_stats()` functions and a real `except` clause so a crash
   during a session marks it `failed` with an error message instead of
   leaving it stuck `running` forever.
2. **`page.title` bug in `agents/agent.py`** — missing call parentheses, so
   the PAGE_VIEW event recorded a bound method object instead of the actual
   page title. Fixed to `page.title()`.
3. **Demo-mode provider resolution bug** — `analysis/autopsy.py` called
   `get_provider(settings.provider)` directly, which only understands
   `"gemini"` or falls back to mock — so with the (correct) default
   `LLM_PROVIDER=auto`, the *string* `"auto"` was passed straight through and
   silently always resolved to mock for the autopsy step, even if a real
   Gemini key was configured for action-deciding. Centralized resolution
   into `settings.resolved_provider` and used it consistently in
   `session_service.py`, `analysis/autopsy.py`, and the `/api/health`
   endpoint.
4. **ID-scheme mismatch between decide-time and execute-time** — the
   element-observer excludes disabled elements when assigning sequential IDs
   (`button_01`, etc.), but `agents/agent.py`'s `build_map()` did not apply
   the same filter. Once any element became disabled mid-session (e.g. an
   "Add to Cart" button after being clicked), the two functions disagreed on
   what `button_01` referred to, and the agent would repeatedly try to click
   a stale, disabled element until it timed out and gave up. This was the
   root cause of demo sessions taking ~150s and ending in `task_failed`
   instead of completing in ~1s. Fixed `build_map()` to apply the same
   `is_disabled()` filter as the observer.
5. **Demo site actionability trap** — even after fix #4, a second product's
   still-enabled "Buy Now" button sat behind the checkout modal overlay,
   which Playwright correctly refused to click through (pointer-events
   interception), causing the same kind of stall. Fixed the demo site to
   disable *all* "Buy Now" buttons once checkout starts.
6. **SQLite cross-thread race** — `db.py`'s connection wrapper only held its
   lock during `execute()`, not the subsequent `fetchone()`/`fetchall()`.
   Under real concurrent traffic (a session's background thread writing
   events while the frontend polls `GET /api/sessions/{id}`), this produced
   `sqlite3.InterfaceError: bad parameter or other API misuse` and a 500 on
   the results page. Fixed by materializing rows while still holding the
   lock.
7. **`demo_site.html` served with wrong encoding** — `read_text()` used the
   platform default encoding (cp1252 on Windows) instead of UTF-8, corrupting
   the em dash and ₹ symbol. Fixed to `read_text(encoding="utf-8")`.
8. **Missing `recharts` dependency** — `Compare.tsx` and `ScoreBreakdown.tsx`
   imported it, but it wasn't in `package.json`. Added.
9. **Corrupted JSX in `SessionResults.tsx`** — a duplicated `<div>`/stray
   `<p>` tag (another mid-paste artifact) broke the root-cause section.
   Rewritten cleanly.
10. **`SessionResults.tsx` had no handling for a non-terminal session** — if
    opened on a `pending`/`running` session (e.g. via Retest, which redirects
    immediately), it rendered a mostly-blank page instead of a progress
    view. Extracted the step-progress UI into a shared `RunningTest`
    component (previously an empty stub file) and wired it into both
    `NewTest.tsx` and `SessionResults.tsx`.
11. **`pytest.ini` `pythonpath` pointed at the wrong directory** — it lived
    in `backend/` with `pythonpath = .`, which doesn't put the project root
    on `sys.path`, so `from backend.app... import` failed. Fixed to `..`.
12. **No friction signal for an explicit task failure** — a session that
    ended in `TASK_FAILURE` without also triggering `dead_end`,
    `abandonment`, `excessive_actions`, etc. produced *zero* friction points
    despite failing, which undermines the product's core purpose. Added a
    dedicated `task_failed` friction signal.
13. Minor: `StatCard.tsx` was an unused empty stub; implemented it and used
    it in `Dashboard.tsx` and `SessionResults.tsx` to remove duplicated
    markup. Fixed a leftover "ShopKart" demo-site name (should be
    "PixelMart") and an inaccurate `uvicorn` command in a frontend error
    message.

## Recommended implementation order (for reference)

This is the order the fixes above were actually made in, which is a
reasonable order to re-derive the system in from scratch: config → DB layer
→ schemas → browser observer/executor → demo site → agent loop → session
service → API routes → frontend data layer → frontend pages/components →
tests → manual browser verification.

## Known limitations (not fixed — by design or out of scope)

- The mock/heuristic provider does not vary its decisions by persona; only
  the Gemini path does. Documented in the README.
- Per-event screenshots are captured to disk but not shown in the timeline
  UI.
- SQLite with a global write lock is appropriate for local/demo use only.
- No authentication/authorization — this is a local tool.

## Environment notes

- **Git**: `ux-autopsy/` has its own repo (`git init` run 2026-09-04, initial
  commit `53526e2`), separate from the unrelated repo at the user's home
  directory `C:\Users\srava`. No git operations have ever touched that
  home-directory repo.
- Backend must be run from the **project root** (not `backend/`) via
  `python -m uvicorn backend.app.main:app`, since the code imports itself as
  `backend.app.*`.

## Diagnostic cleanup (2026-09-04)

VS Code was reporting 7 Problems (red/yellow underlines) despite the app
running correctly. Root cause of the disconnect: **no `.vscode/settings.json`
existed**, so Pylance was analyzing the backend against system Python 3.14
(`C:\Python314\python.exe`) instead of the project's `backend/.venv` — a
different interpreter with a different (and incomplete) set of packages
installed. The app worked at runtime because every terminal command in this
project explicitly used the venv's python; the *editor* had no way to know
that venv existed.

Fixed by adding `.vscode/settings.json` (`python.defaultInterpreterPath`
pointing at `backend/.venv`, plus `python.analysis.extraPaths` so the
`backend.app.*` self-import style resolves) and `pyrightconfig.json` at the
repo root, configured the same way. Installed `pyright` (the engine behind
Pylance) into the venv to get an authoritative, reproducible diagnostic
count instead of guessing from IDE state — went from **12 real errors** down
to **0 errors, 0 warnings, 0 informations**, plus a few more small issues
that surfaced incidentally while fixing those:

1. **`api/routes.py` — 5 `reportOptional*` errors.** `_session()` fetches a
   row, checks it's not `None`, then calls `row_to_dict(row)` — but
   `row_to_dict`'s signature is `dict | None`, so pyright couldn't see that
   *this specific call* can never actually return `None`. Every downstream
   dict access (`d["score_breakdown"]`, and later `s["status"]` /
   `s["progress"]` in `get_session()`) inherited the `| None` uncertainty.
   Fixed with an explicit `assert d is not None` right after the call — this
   makes a real invariant explicit (and would fail loudly if it were ever
   violated) rather than suppressing the check.
2. **`services/session_service.py` — 5 more of the same**, in
   `dashboard_stats()`. `SELECT COUNT/AVG/SUM ... FROM sessions` with no
   `GROUP BY` always returns exactly one row (even 0/NULL on an empty
   table), so `.fetchone()` can't return `None` here either. Same
   `assert ... is not None` fix, one per aggregate query.
3. **`providers/gemini.py` — `reportPrivateImportUsage` ×2.** The
   `google-generativeai` package's `__init__.py` re-exports `configure` and
   `GenerativeModel` without an explicit `__all__`, so pyright treats them as
   private even though they're the library's documented public API (verified
   they exist and work at runtime). Fixed by importing directly from the
   submodules where they're actually defined
   (`google.generativeai.client.configure`,
   `google.generativeai.generative_models.GenerativeModel`) — resolves the
   check without disabling it. Also fixed a real (if minor) bug found while
   in this file: `GenerativeModel("gemini-1.5-flash")` was hardcoded instead
   of reading `settings.gemini_model` (the `GEMINI_MODEL` env var was being
   silently ignored).
4. **`providers/gemini.py` — unused loop variable.** `for attempt in
   range(2):` never used `attempt`. Renamed to `for _ in range(2):` — the
   standard idiom, not a suppression.
5. **`api/routes.py` — unused route parameter.** The catch-all demo-site
   route used `_p` as both the path-template name and function parameter,
   which Pylance still flagged as unused despite the leading underscore.
   Renamed to the bare `_` (in both the decorator's `{_}` and the function
   signature), which is the convention actually recognized as
   intentionally-unused.
6. **`main.py` — deprecated `@app.on_event("startup")`.** Not an IDE
   diagnostic but a real `DeprecationWarning` surfaced by pytest on every
   run (FastAPI is dropping this API). Migrated to the modern `lifespan`
   context-manager pattern; behavior is identical (calls `init_db()` before
   serving).

**Left as-is, and why:** the `lifespan` callback's `_app: FastAPI` parameter
still shows a faded "not accessed" *hint* in the editor. This is required by
FastAPI/Starlette's lifespan protocol (the function signature must accept
it) and is already prefixed with `_` per convention — pyright's authoritative
CLI run reports 0 warnings for it, confirming it's an editor-only cosmetic
hint (a dotted underline, not a red/yellow Problem), not a real diagnostic.

Re-verified after all fixes: pyright 0/0/0, 16/16 backend tests pass
(`pytest tests/ -v`, live server up), frontend `tsc -b --force` clean, 2/2
Playwright E2E tests pass, and a manual health/proxy check confirmed the
frontend dev server correctly proxies `/api/*` to the backend
(`curl localhost:5173/api/health` → `200`).
