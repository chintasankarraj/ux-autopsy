# PROJECT_STATUS

Last updated: 2026-09-05

## Status at a glance

- **Version:** v1.4
- **Code status:** implemented, tested, committed, pushed
- **Current commit:** `7b6055f` — "feat: strengthen completion evidence" (branch `master`, `origin/master` synchronized)
- **Test status:** 72/72 pytest passed · pyright clean (0/0/0) · frontend TypeScript clean · Playwright E2E 2/2 passed
- **Live Gemini status:** inconclusive — the free-tier daily quota (`generate_content_free_tier_requests`, limit 20/day/project/model) returned `429 ResourceExhausted` on every decision across three separate live-regression attempts (2026-09-05), before genuine model decisions could be produced. **This is a stated external-quota limitation, not an application failure or code defect** — the safe-fallback contract itself was exercised correctly each time (session completed cleanly via `ABANDONMENT`, no crash, no false completion).

**Validated vs. pending, explicitly:**

| | Validated |
|---|---|
| Mock/Demo Mode pipeline (agent loop, friction, scoring, autopsy, UI) | ✅ locally tested + live-verified via Playwright E2E |
| v1.3.2 observation-stall fix | ✅ tested locally **and** live-validated (real Gemini runs since the fix complete in <90s, no stall recurrence) |
| v1.4 dialog capture / completion evidence — local fixtures (Mock provider, no live site) | ✅ tested locally (`test_dialog_evidence.py`, 8/8 passing) |
| v1.4 dialog capture / completion evidence — live Gemini + live site, end to end | ⏳ pending — blocked by Gemini free-tier quota exhaustion, not yet observed to succeed live |

## Summary

UX Autopsy is now a working, end-to-end product with a genuinely
evidence-driven demo (v1.1), more reliable real-world Gemini execution and
trustworthy evidence (v1.2), automated tests fully isolated from the real
Gemini API (v1.3), a hardened live-regression harness that can't silently
corrupt its own task text (v1.3.1), a fix for a ~181-second Playwright
observation stall live-validated against the real API (v1.3.2), and, as of
v1.4, a stronger, dialog-backed completion-evidence signal — see "v1.4:
strengthen completion evidence" below for what's tested locally versus what
remains pending live validation. Every item on the Phase 20 acceptance
checklist (see below) passes locally. This document records what was
inherited, what was broken, what was fixed, and what remains a known
limitation.

## v1.4: strengthen completion evidence (2026-09-04, commit `7b6055f`)

**Problem:** the v1.3.2 live regression showed a model-issued `finish`
trusted right after a successful "Add to cart" click, backed only by a
page-text keyword match (the word "cart") that DemoBlaze's nav bar makes
permanently true regardless of whether anything was actually added. A
Gemini-free Playwright diagnostic against the real site found a much
stronger, fully generic signal going unused: a native browser dialog
("Product added") firing as a direct, synchronous side effect of the click
itself.

**Changes:**

- `capture_dialogs()` (`backend/app/agents/agent.py`) — a generic Playwright
  dialog listener that records each dialog's type/message and dismisses it,
  preserving the exact auto-dismiss behavior Playwright already applies when
  no listener is registered.
- `dialog_completion_evidence()` (`backend/app/agents/completion.py`) —
  relevance-gated evidence derived purely from keyword overlap between a
  captured dialog's text and the task's own words (via a small,
  site-agnostic prefix-match helper for simple inflections like
  add/added) — never a hardcoded phrase for any specific site.
- The new dialog hint feeds into the exact same `completion_hint` channel
  `completion_evidence()` already used, so `evaluate_completion()`'s
  existing two-consecutive-signal safety net applies unchanged, and a
  model-issued `finish` remains trusted unconditionally, exactly as in v1.2
  — this only gives the model (and the safety net) better evidence, it does
  not gate or block completion. `completion_evidence()` and
  `evaluate_completion()` themselves are untouched.
- Each captured dialog also becomes its own `DIALOG` timeline event, using
  only existing `events` table columns, so no schema migration or frontend
  change was needed (the timeline already renders unknown event types
  generically, via a fallback icon).
- 8 new tests (`backend/tests/test_dialog_evidence.py`) cover: real dialog
  capture without blocking, relevant vs. irrelevant dialog text, no-dialog
  behavior, the finish-is-trusted-unconditionally boundary at the
  `execute()` layer, and two full local-fixture sessions (Mock provider, no
  Gemini, no DemoBlaze) proving the dialog event is DB-schema-compatible end
  to end.

**Verified locally (2026-09-04):** `pytest backend/tests/ -v` — 72/72
passed; `pyright` — 0/0/0; `npx tsc -b` — clean; `npx playwright test` —
2/2 passed. All against local fixtures / the mock provider, per the test
isolation established in v1.3.

**Live validation status — inconclusive, not yet observed to succeed
(2026-09-05):** three separate live-regression attempts against
`https://www.demoblaze.com/` (persona `beginner`, task "Find a laptop
priced below $800 and add it to the cart.") each returned
`google.api_core.exceptions.ResourceExhausted: 429` (`quota_id:
GenerateRequestsPerDayPerProjectPerModel-FreeTier`, `quota_value: 20`) on
every decision, before the agent ever reached a real click — including one
attempt after explicit confirmation that the daily quota had reset, and
one attempt immediately following a single successful minimal API probe
call (which itself likely consumed the last available request of that
day's allotment). No `DIALOG` event, no dialog-backed completion evidence,
and no model-issued `finish` have yet been observed in a live run — this
remains **untested against a real end-to-end Gemini session**, honestly
reported as pending rather than assumed to work from the code and local
tests alone. Each attempt's safe-fallback contract itself held correctly
(session completed via `ABANDONMENT: Action limit reached`, no crash, no
false completion, correct friction/UX-score reporting under total, sustained
API failure) — consistent with the same contract validated under real
failure conditions in v1.2. Re-run
`backend/scripts/live_gemini_regression.py --task-file <path>` once quota is
confirmed available (verified by an actual successful decision in the
run itself, not merely by elapsed time) to complete this validation.

## v1.3.2: prevent Playwright observation stalls (2026-09-04, commit `f70da2c`)

**Root cause:** `observe()` and `build_map()`
(`backend/app/browser/observer.py`, `backend/app/agents/agent.py`) enumerate
Locators via `count()` then `nth(i)` — `count()` takes a DOM snapshot while
`nth(i)` re-resolves lazily against the live DOM. If the page mutates between
the two (e.g. right after a navigation, since `run_agent()` calls `observe()`
with no settle wait), a probe against a now-stale index blocked for
Playwright's unset default of 30000ms before the existing
except-`Exception` handling silently swallowed it. Six such probes (3
selectors × 2 redundant sweeps) matched a measured **~181-second** production
stall almost exactly.

**Change:** gave `is_disabled()`/`bounding_box()`/`inner_text()`/
`get_attribute()` an explicit 1500ms timeout
(`OBSERVE_PROBE_TIMEOUT_MS`, defined once in `observer.py` and shared by
`agent.py`), so one stale locator now costs at most 1.5s instead of 30s. No
prompt, provider, completion, friction, scoring, or frontend behavior
changed. New test file: `backend/tests/test_observe_probe_timeout.py`.

**Live-validated, not just unit-tested:** live Gemini regression runs
performed after this fix (2026-09-05) completed in well under 90 seconds
total (25-action sessions finishing in ~69–90s), with no recurrence of the
~181s gap in any run's `observe_ms`/`decide_ms` timing breakdown — the fix
holds under real conditions, not only in the dedicated timeout tests.

## v1.3.1: harden live regression task invocation (2026-09-04)

**Root cause:** a live regression run passed `--task "Find a laptop priced
below $800 and add it to the cart."` inside bash double quotes. Bash expands
`"$800"` as positional parameter `$8` (empty) followed by literal `00`
*before* Python ever sees the argument — silently sending "...below 00..."
to Gemini. This is a shell-invocation hazard, not a defect in the script's
own argument parsing (which never touched or mangled the string it received).
Separately, the same run's ~182-second gap between the "Laptops" click and
the agent's next decision was, until now, unattributed: `decide_ms`
(Gemini latency) accounted for only ~7s of it, and nothing measured how long
`observe(page)`/`build_map(page)` (reading the live page's current state)
took.

**Changes (regression harness + one small, additive instrumentation only —
no agent behavior, prompts, completion logic, parser, friction detection,
scoring, provider implementation, or frontend touched):**

- `backend/scripts/live_gemini_regression.py` — added `--task-file PATH`
  (reads the task verbatim from a file; immune to shell quoting in any
  shell) alongside the existing `--task`; extracted `build_parser()` and
  `resolve_task()` as pure, network-free functions so they're independently
  testable; the resolved task is now printed (`Task: '...'`) before the
  session is created; the per-event report line now shows `decide_ms` and
  `observe_ms` so a gap can be attributed (or shown to be unattributed)
  without manual timestamp arithmetic. `backend/scripts/__init__.py` added
  so the script is importable as `backend.scripts.live_gemini_regression`
  from a test.
- `backend/app/agents/agent.py` — added a single wall-clock timer around
  the existing `observe(page)` + `build_map(page)` calls (unchanged
  themselves), recorded as `observe_ms` on the same event that already
  carries `decide_ms`. Purely additive measurement; not wired into
  friction/scoring (per instruction not to touch those).
- `backend/app/db.py` / `backend/app/services/session_service.py` — added
  `events.observe_ms` column (with an `_ensure_column` migration for
  existing local databases) and persist it.
- `backend/tests/test_live_regression_harness.py` (new) — proves the exact
  string `"Find a laptop priced below $800 and add it to the cart."`
  survives `build_parser()`/`resolve_task()` unchanged via both `--task` and
  `--task-file`, and that the built-in default is correct — all without any
  network call (tests stop before `main()`'s HTTP-calling code).
- README.md — documented the safe invocation (`--task-file`, or single
  quotes) and the new timing fields.

**Timing investigation — where the ~182s went:** not determined further
than "somewhere inside `observe()`/`build_map()`, not `decide()` (Gemini)
and not `execute()` (the click itself, which had already completed and been
recorded before the gap began)." The new `observe_ms` instrumentation will
show this precisely on the *next* live run, but this task deliberately made
no live Gemini call, so it hasn't been observed with the new field yet.
`MAX_SESSION_SECONDS` was deliberately **not** changed — the goal here was
attribution, not tuning a timeout around one unexplained sample.

**Verified — zero live Gemini calls made:** `pytest backend/tests/ -v` —
**60/60 passed in ~4.6s**; `pyright` — 0/0/0; `npx tsc -b --force` — clean;
`npx playwright test` — **2/2 passed in ~10.7s**, servers auto-started and
torn down by Playwright's own `webServer` config (unchanged from v1.3).
`.env`/`.env.example` untouched; no secrets in any new/changed file.

## v1.3: test isolation from live Gemini (2026-09-04)

**Problem:** the v1.2 regression attempt showed that `pytest`/
`playwright test` could silently consume real Gemini quota whenever the
developer's `.env` had `LLM_PROVIDER=gemini` — because provider resolution
(`settings.resolved_provider`) reads that same `.env` no matter who's
asking. `test_api.py` drives a real end-to-end session, and
`app.spec.ts`'s E2E test drives whatever backend happens to be running —
both inherited the ambient environment's provider choice. This is exactly
what exhausted the day's 20-request free-tier quota before the v1.2 live
regression could run.

**Changes (test/config only — no agent behavior, prompting, completion
logic, friction logic, parsing, provenance, scoring, or UI touched):**

- **`backend/tests/conftest.py`** (new) — forces `LLM_PROVIDER=mock` as a
  plain environment variable for the whole `pytest` process, at import time
  (before any test module can import `config.py`). This uses an
  already-existing, documented override (`LLM_PROVIDER=mock`); no
  application code changed. As defense in depth, the same file
  monkeypatches the real Gemini SDK's `GenerativeModel.generate_content` at
  the class level to raise a `RuntimeError` if anything ever calls it for
  real during a test run, rather than silently reaching the live API. Tests
  that inject their own `MagicMock` in place of `provider.model` (e.g.
  `test_provenance.py`) are unaffected — they never touch the real class.
- **`backend/tests/test_provider_isolation.py`** (new) — asserts
  `LLM_PROVIDER` is forced to `mock`, `settings.resolved_provider` is
  `"mock"` during tests, `get_provider()` returns a `MockProvider`, and a
  direct call to the real SDK's `generate_content` raises the guard's
  `RuntimeError`.
- **`frontend/playwright.config.ts`** — added a `webServer` array so
  Playwright starts both the backend and frontend itself for every run
  (`reuseExistingServer: false`, deliberately — not just for CI — so a
  leftover manually-started server, possibly configured for real Gemini,
  is never silently reused) and passes `LLM_PROVIDER: "mock"` in the
  backend process's environment. `__dirname` isn't available in this
  project's ESM config files (`"type": "module"` in `package.json`), so it's
  derived via `fileURLToPath(import.meta.url)`.
- **`backend/scripts/live_gemini_regression.py`** (new) — the one
  intentional path to a real Gemini call, kept structurally outside pytest
  (`pytest.ini`'s `testpaths = tests` never collects `backend/scripts/`).
  Refuses to run without `UX_AUTOPSY_ALLOW_LIVE_GEMINI=1`, and refuses if
  the backend it's pointed at doesn't report `provider: gemini`. Talks to an
  already-running backend over HTTP and prints a full report (session,
  event/parser-failure counts, provider provenance, friction count,
  screenshot location) — never touches or prints `GEMINI_API_KEY` itself.
- **README.md** — documented the isolation mechanism, corrected an initial
  overstatement (a real `uvicorn` process is still needed for
  `test_api.py`'s Playwright browser to load the built-in demo site page —
  a plain local HTTP fetch, unrelated to Gemini; the session's *decisions*
  still always resolve to mock because `run_agent()` executes inside the
  `pytest` process itself, not by delegating to that separate server), and
  added the live-regression command.

**`.env`/`.env.example`: unchanged.** No change was required — isolation is
achieved entirely by overriding the `LLM_PROVIDER` environment variable at
the test-runner level (already a first-class, documented override), never
by touching the developer's own configuration file.

**Verified (2026-09-04, no live Gemini calls made during this work):**
- `pytest backend/tests/ -v` — **54/54 passed in ~4.5s** (down from 150s+
  when real Gemini was in the loop) — with a real `uvicorn` process running
  and its own `.env` still set to `LLM_PROVIDER=gemini`, `GEMINI_API_KEY`
  present.
- `pyright` — 0/0/0. `npx tsc -b --force` — clean.
- `npx playwright test` — **2/2 passed in ~10s** (down from ~50s), with
  Playwright printing `Uvicorn running on http://0.0.0.0:8000` from its own
  spawned process and tearing both servers down afterward — confirmed no
  server was listening on `:8000`/`:5173` before or after the run.
- Direct confirmation: manually launching the exact spawned command with
  `LLM_PROVIDER=mock` set reports `{"status":"ok","provider":"mock",
  "demo_mode":true}` from `/api/health`, while the on-disk `.env` still says
  `LLM_PROVIDER=gemini` — proving the override, not the file, is what's in
  effect for tests.
- No Gemini API request was made at any point during this v1.3 work
  (confirmed by inspection — no code path in any test or script reaches
  `generate_content` unless a developer explicitly runs
  `live_gemini_regression.py` with its opt-in variable set).

**The v1.2 live regression is still unvalidated** — this work only fixes
test isolation; it does not itself run or re-attempt the live regression
(intentionally, per instruction not to consume quota during this task). Use
`backend/scripts/live_gemini_regression.py` once quota is available.

## v1.2: reliable real-world agent execution (2026-09-04)

**Problem being solved:** a real Gemini baseline run against
`https://www.demoblaze.com/` (persona: Confused Beginner, task: "Find a
laptop priced below $800 and add it to the cart.") surfaced five real-world
reliability/trust problems that the v1.1 demo-mode work never exercised,
because demo mode only ever runs the deterministic mock/heuristic provider.
All five were traced to an actual code path (not guessed) before any fix was
written; none of the fixes are DemoBlaze-specific.

1. **Fragile Gemini action parsing** (`providers/gemini.py`) — the old
   `_parse()` was a single greedy regex (`\{.*\}`, DOTALL) spanning the
   first `{` to the last `}` in the whole response. Real Gemini output
   routinely wraps JSON in markdown fences, adds leading/trailing prose that
   itself contains stray braces, or leaves a trailing comma — any of which
   corrupted the greedy match. In the baseline, 12/25 (48%) of decisions hit
   the safe fallback because of this. Replaced with
   `providers/parsing.py::parse_agent_action()`: fence-stripping, a
   brace/string-aware balanced-object scanner (not a regex), a
   trailing-comma repair pass, schema validation against the actual action
   whitelist, and an explicit ambiguity check (multiple distinct valid
   candidates are rejected, not guessed at) — all schema-driven, no
   site-specific vocabulary. 14 new unit tests in
   `tests/test_gemini_parsing.py` cover the realistic formatting variations
   above plus the safe-fallback/rejection paths.
2. **No task-completion recognition** (`agents/agent.py`,
   `agents/completion.py` — new) — the loop only ever finished when the
   model itself emitted `finish`; nothing told it explicitly that the
   requested end state might already be satisfied, so a long-running session
   could drift back into exploring after actually finishing (observed:
   Gemini reached the cart, verified the item, then resumed searching until
   `MAX_ACTIONS`). `completion.py::completion_evidence()` derives a
   site-agnostic signal purely from the task's own wording (a completion verb
   already performed + an object keyword from the task still present on the
   current page) and surfaces it to Gemini as an explicit `COMPLETION CHECK`
   line in the prompt. `evaluate_completion()` is a conservative safety net:
   only after the *same* strong evidence persists across two consecutive
   decisions, and only if the model still hasn't finished, does the harness
   override to `finish` — a single, unconfirmed observation never triggers
   it. 8 unit tests cover detection, non-detection, generalization to an
   unrelated task/site, and the override/streak/reset behavior.
3. **Incorrect-click signal blind to confident wrong clicks**
   (`analysis/friction.py`) — the only detector was "self-reported
   `confidence < 0.45`," which works for the scripted mock persona (which
   deliberately reports low confidence for its staged wrong click) but is
   blind to a real Gemini call that clicks the wrong element while reporting
   *high* confidence (baseline: reasoned about "Sony vaio i5," clicked
   "Samsung galaxy s6" — no low-confidence signal existed to catch this, and
   the only passing test for the signal happened to always end in
   `TASK_SUCCESS`, i.e. the detector was never exercised in an unsuccessful
   session). Added a second, independent detector,
   `_reasoning_target_mismatch()`: a click is also flagged when the agent's
   own stated `reason` names specific content words that share zero overlap
   with the label of what it actually clicked — a general proxy for
   "reasoned about A, clicked B" that requires no site vocabulary and no
   session-outcome gating. 4 new tests cover a mismatched click in a *failed*
   session, a correctly-matching click in a failed session (must not flag),
   and the existing low-confidence/multi-step-flow tests still pass
   unchanged.
4. **Dishonest provider provenance** (`analysis/autopsy.py`,
   `services/session_service.py`, `db.py`) — `GeminiProvider.autopsy()`
   silently fell back to `MockProvider().autopsy()` on any exception or bad
   JSON, and the caller reported `provider.name` (the outer instance type,
   always `"gemini"`) regardless — so a Mock-generated narrative could be
   filed and displayed as Gemini's. Separately, `sessions.provider` (set
   correctly at session creation to the action-deciding provider) was
   overwritten at the end of the run with this same wrong autopsy-provider
   value. Fixed: `GeminiProvider.autopsy()`/`MockProvider.autopsy()` both now
   return `provider_used`/`fallback`/`fallback_reason`; `run_autopsy()`
   trusts those fields instead of the outer provider instance;
   `sessions.provider` is never overwritten again (it stays the
   action-provider for the whole session); `analyses` gained `fallback`/
   `fallback_reason` columns. The results page now shows the action provider
   and the autopsy provider separately, with an explicit "this text was NOT
   generated by Gemini" note when a fallback occurred. 5 new tests cover the
   Gemini-success, Gemini-failure→Mock-fallback (both exception and
   invalid-JSON paths), Mock-direct, and the `run_autopsy()`
   trust-the-actual-provider behavior.
5. **Hesitation signal conflated with model latency**
   (`analysis/friction.py`, `agents/agent.py`, `services/session_service.py`,
   `db.py`) — event timestamps were stamped *after* `provider.decide()` (a
   full Gemini API round trip) completed, so the gap between consecutive
   events included however long Gemini took to respond. A 69.9s Gemini
   round trip was misreported as a 69.9s user hesitation. Added a real,
   measured `decide_ms` per event (timed around the actual `provider.decide()`
   call in `agents/agent.py`, persisted via a new `events.decide_ms` column)
   and changed hesitation detection to flag only the *residual* gap after
   subtracting that measured model latency — no fabricated timing, just using
   data the harness already has. 2 new tests confirm a latency-dominated gap
   is not flagged while a genuine low-latency pause still is.

**Also fixed while verifying (test-infrastructure, not application code):**
`tests/test_api.py`'s session-completion fixture polled for a fixed 150s,
shorter than the session's own `settings.max_session_seconds` (180s) plus
the time a single slow real-LLM call or autopsy generation can add after
that check — a legitimately-still-running real-Gemini session could read as
"stuck." Changed the poll budget to derive from `settings.max_session_seconds`
with a margin, instead of a shorter hardcoded number.

**Test results (2026-09-04):** `pytest backend/tests/ -v` — 50/50 passed
(includes a real, non-mocked Gemini session via `test_api.py`, run against
the live API). `pyright` — 0 errors/0 warnings/0 informations. `npx tsc -b
--force` — clean, no output. `npx playwright test` — 2/2 passed (the
end-to-end test also runs a real Gemini-decided session).

**Real Gemini regression run — blocked by exhausted API quota, not a code
defect:** re-ran the exact baseline scenario
(`https://www.demoblaze.com/`, persona `beginner`, task "Find a laptop
priced below $800 and add it to the cart.") against the real Gemini API.
The session ran to completion (`status: completed`, no crash), but all 25
decisions returned the safe fallback ("LLM output invalid; safe fallback"),
and `pages_visited` stayed at 1 — i.e. Gemini was never actually consulted
successfully. Isolated by calling `model.generate_content()` directly
outside the app: `google.api_core.exceptions.ResourceExhausted: 429 ... Quota
exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests
... quota_value: 20 ...` for the configured model (`gemini-3.5-flash`,
free tier). The Phase 3 test run immediately before this (the full pytest
suite run twice, `test_api.py`, and the Playwright e2e test — each launching
a real Gemini-backed session of up to 25 actions × up to 2 retries) had
already exhausted the day's free-tier allotment before the regression
session ever made its first call. A follow-up direct API call after a short
wait reproduced the same `ResourceExhausted` error, confirming this is the
daily per-project/per-model cap, not a transient burst limit that would
clear within the session.

This is an honest, unmet acceptance item, not a claimed success: **the v1.2
fixes have not yet been validated end-to-end against live demoblaze.com
with a working Gemini connection** in this session. What the run does
confirm is that the existing safe-fallback contract held under total,
sustained real-world API failure — the session completed cleanly (no crash,
no false completion, correct `abandonment`/friction reporting) rather than
hanging or corrupting state. The parser, completion-recognition, and
incorrect-click fixes were validated only via the unit tests above and the
mocked-Gemini test in `test_provenance.py`, not via a live end-to-end
demoblaze.com run. Re-running the regression once the daily quota resets (or
with a paid-tier key) is the recommended next step and was intentionally not
retried automatically in this session, per instruction not to retry a failed
regression with modified behavior to force a different outcome.

**Scope note:** no DemoBlaze-specific selector, product name, price, or URL
path was added anywhere in `backend/app` or `frontend/src` (verified via
`grep -rniE "demoblaze|samsung|sony vaio|galaxy s6" backend/app frontend/src`
— no matches; those strings appear only in `test_friction.py` as realistic
fixture data for the general-purpose reasoning-mismatch detector, not as
application logic).

## v1.1: realistic, evidence-driven demo (2026-09-04)

**Problem being solved:** the demo previously behaved like a scripted
happy path (91.5 score, 4 actions, 0 friction, every persona identical) —
technically working but unconvincing as a demonstration of *why* UX Autopsy
is useful. This round made persona behavior, friction detection, and the
autopsy narrative genuinely evidence-driven, without hard-coding any result.

**What changed, by area:**

- **Demo site redesign** (`backend/app/browser/demo_site.html`) — PixelMart
  now has deliberate, structural (not random) UX friction: "Add to Cart"
  sits beside "Buy Now"; the price filter is a low-contrast toggle grouped
  tightly against the sort pills; at a narrow viewport the filter collapses
  behind a "☰ Menu" button. Category and price are real, functional
  client-side facets (button pills, not `<select>` — the agent's action
  whitelist has no "select an option" action, so keeping filters as buttons
  avoided a larger, riskier change to that whitelist).
- **Persona-differentiated heuristic** (`backend/app/agents/heuristic.py`) —
  rewritten around a per-persona behavior profile (which controls to try, in
  what order, with a plausible wrong-first-attempt for some personas, a real
  `time.sleep()`-based hesitation for Beginner, and a real 390×844 viewport
  for Mobile User set in `agents/agent.py`). Verified via a scripted run of
  all 5 personas that every one produces a **distinct event-label
  sequence** (see "Persona verification" below).
- **`incorrect_click` friction signal, done right** — the first version of
  this (in the prior diagnostic-cleanup session) flagged *every* click that
  wasn't literally the last one, which false-positives on any legitimate
  multi-step flow. Redefined around the action's own `confidence` value
  (now persisted per event, `events.confidence`): a genuinely low-confidence
  click is real evidence of a shaky attempt; a confident necessary step
  never is. Two new unit tests lock this in
  (`test_low_confidence_click_produces_incorrect_click_friction`,
  `test_multi_step_confident_flow_has_no_incorrect_click_friction`).
- **"Why did this happen?"** — each root-cause entry the provider generates
  is merged back onto its corresponding friction point by index
  (`analysis/autopsy.py`), persisted as `friction_points.why_json`, and
  rendered as an expandable panel in `FrictionList.tsx` showing observed
  behavior / possible cause / likely root cause / recommendation /
  confidence — generated from that session's real evidence, not invented
  fresh for display.
- **Screenshots surfaced in the timeline** — this turned out to already be
  wired up in `Timeline.tsx` from earlier work; verified it actually
  renders (`naturalWidth`/`naturalHeight` checked via Playwright, not just
  "no console error") and added a graceful fallback (`onError` hides a
  broken image and shows "Screenshot unavailable" instead). Also enriched
  the expanded event panel with explicit Timestamp/URL, and cross-referenced
  events against friction points by label so a friction-causing event shows
  an inline "Related friction" note with a severity badge.
- **Score consistency fix** — `providers/mock.py`'s narrative used
  `{score:.0f}` (rounds to nearest integer) while the results page showed
  the raw one-decimal value, so 91.5 could narrate as "92". Both now use
  `.1f`, one source of truth.
- **`GEMINI_MODEL` respected** — found while touching `providers/gemini.py`:
  `GenerativeModel("gemini-1.5-flash")` was hardcoded, silently ignoring the
  configured model. Now uses `settings.gemini_model`.

**Bugs found and fixed while verifying this (all confirmed via real
Playwright sessions, not just code review):**

1. `_best_price_pill` picked the *first* "Under ₹X" pill in DOM order
   (₹30,000) instead of the bracket matching the task's actual budget
   (₹60,000) — filtered the target product out of the grid entirely. Fixed
   by parsing the task's `₹` amount and every pill's own amount, then
   picking the tightest bracket that still covers the budget.
2. The generic keyword best-match fallback had no "already clicked this"
   guard, so once the correct price pill's specific label was excluded (via
   fix above) it would loop forever re-selecting an unhelpful pill until the
   action budget ran out (~150s, ending in `task_failed`). Added an
   already-clicked-by-label guard to all three fallback blocks (a general
   robustness fix, not persona-specific).
3. `_keywords()` kept purely-numeric tokens (`"000"` out of "₹60,000"),
   which coincidentally substring-matches *every* price pill's label
   ("Under ₹30,000" also contains "000") — caused false keyword-relevance
   matches that made Budget Shopper click through all three price brackets.
   Numbers are now excluded from generic keyword matching; `_target_price()`
   handles numeric amounts specifically instead.
4. My own manual `curl -d '...'` testing mangled the ₹ character via shell
   encoding (became a literal `?`), which surfaced bug #1 in a confusing
   way before I isolated it as a test-harness artifact, not a product bug —
   noted here since it cost real debugging time and the fix (writing
   request bodies to a UTF-8 file, `curl --data-binary @file`) is worth
   remembering for future manual API testing on this stack.

**Persona verification** (scripted run against a live server, all 5
personas, same task): every persona produced a distinct event-label
sequence and different friction signals —

| Persona | Actions | UX Score | Friction |
|---|---|---|---|
| Budget Shopper | 7 | 83.6 | none |
| Power User | 6 | 85.0 | none (shortest path — skips search) |
| Confused Beginner | 5 (+7s real hesitation) | 85.5 | `hesitation`, `incorrect_click` |
| Impatient User | 5 | 86.7 | `incorrect_click` |
| Mobile User | 8 | 82.2 | none (extra action opening the mobile menu) |

A separate run of Impatient User against a mismatched task (no matching
product on the demo site) produced a genuine, honestly-earned failure:
`completed: false`, `ux_score: 46.1`, with `task_failed` and
`incorrect_click` friction — demonstrating the realistic-low-score case
without ever hard-coding a score or fabricating an event.

**Environment note — a session-local port artifact:** partway through this
round, `localhost:8000` became unreachable through normal process
management — `netstat`/`Get-NetTCPConnection` reported it LISTENING under a
PID that neither `tasklist`, `Get-Process`, nor a WMI query could find, and
`Stop-Process`/`taskkill` on that PID reported "no such process." It kept
answering real HTTP requests throughout. This is almost certainly an
orphaned WSL/container network port-forward left over from very early in
this long session, invisible to native Windows process tools. All testing
in this round was done on port 8001 instead (temporarily repointing
`vite.config.ts`'s proxy and `NewTest.tsx`'s `DEMO_URL`, both reverted to
8000 before finishing) and `backend/tests/test_api.py`'s hardcoded demo URL
was changed to `settings.demo_url` (respects `PORT`) so it no longer
silently depends on a literal 8000. This is a one-off artifact of this
session's history, not a code or configuration defect — a fresh environment
won't have it, but if you hit the same symptom, using a different `PORT` env
var value works around it without needing to resolve the underlying stuck
socket.

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

- The mock/heuristic provider's persona-differentiated behavior (see v1.1
  above) is tuned specifically against the bundled demo site's markup — it
  won't reproduce nuanced, persona-specific behavior against an arbitrary
  real website the way the Gemini path can. Documented in the README.
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
