"""Regression coverage for the v1.3.2 observation-stall fix.

Root cause (see PROJECT_STATUS.md v1.3.1 investigation): observe() and
build_map() enumerate Playwright Locators via `count()` then `nth(i)`.
`count()` takes a DOM snapshot, but `nth(i)` re-resolves lazily against the
live DOM on every later call. If the page mutates between `count()` and a
per-element probe (e.g. immediately after a navigation, since run_agent()
calls observe() with no settle wait), a probe for an index that no longer
resolves blocks for Playwright's unset default of 30000ms before raising --
and that TimeoutError was silently swallowed by the existing
`except Exception` handling. Six such probes (3 selectors x 2 redundant
sweeps) matched the observed ~181s production stall almost exactly.

These tests use only local, in-memory HTML fixtures (`page.set_content()`)
and a real (headless) Playwright browser -- no network, no DemoBlaze, no
agent/provider/LLM code, so they make zero Gemini calls regardless of
conftest.py's isolation guard.
"""
import time

import pytest
from playwright.sync_api import Locator, sync_playwright

from backend.app.agents.agent import build_map
from backend.app.browser.observer import OBSERVE_PROBE_TIMEOUT_MS, SELECTORS, observe

FIXTURE_HTML = """
<!doctype html><html><body>
  <button id="btn-visible-1">Visible One</button>
  <button id="btn-visible-2">Visible Two</button>
  <button id="btn-disabled" disabled>Disabled</button>
  <a id="link-hidden" href="#hidden" style="display:none">Hidden Link</a>
  <a id="link-visible" href="#visible">Visible Link</a>
  <input id="input-placeholder" placeholder="Type here" />
</body></html>
"""


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    pg = browser.new_page()
    pg.set_content(FIXTURE_HTML)
    yield pg
    pg.close()


# --- 3. Existing normal observation behavior remains unchanged -------------

def test_observe_and_build_map_agree_on_normal_elements(page):
    obs = observe(page)
    texts = {e["text"] for e in obs["elements"]}

    assert "Visible One" in texts
    assert "Visible Two" in texts
    assert "Visible Link" in texts
    assert "Type here" in texts  # placeholder fallback still works
    assert "Disabled" not in texts  # is_disabled() filtering still works
    assert "Hidden Link" not in texts  # bounding_box() visibility filtering still works

    emap = build_map(page)
    # decide-time ids (observe) must still resolve to the same elements at
    # execute-time (build_map) -- the safety invariant documented in both
    # modules must survive the timeout change untouched.
    assert set(emap.keys()) == {e["id"] for e in obs["elements"]}


# --- 2. The explicit timeout is actually passed to the locator methods -----

def test_probe_calls_carry_the_explicit_timeout(monkeypatch, page):
    calls = []
    originals = {
        "is_disabled": Locator.is_disabled,
        "bounding_box": Locator.bounding_box,
        "inner_text": Locator.inner_text,
        "get_attribute": Locator.get_attribute,
    }

    def make_spy(name):
        def spy(self, *args, **kwargs):
            calls.append((name, kwargs))
            return originals[name](self, *args, **kwargs)
        return spy

    for name, fn in originals.items():
        monkeypatch.setattr(Locator, name, make_spy(name))

    observe(page)
    build_map(page)

    assert calls, "expected observe()/build_map() to invoke locator probes"
    for name, kwargs in calls:
        assert kwargs.get("timeout") == OBSERVE_PROBE_TIMEOUT_MS, (
            f"{name}() was called without the explicit {OBSERVE_PROBE_TIMEOUT_MS}ms "
            "timeout -- a stale/mutated locator could block for Playwright's "
            "30000ms default and stall the whole agent loop"
        )


# --- 1. A DOM mutation between count() and nth(i) cannot cause a 30s wait --

def test_stale_locator_index_fails_fast_not_30_seconds(page):
    # Reproduces the production race deterministically: count() reports one
    # more "button" element than actually exists in the DOM, exactly like a
    # count() snapshot taken just before a live re-render removes/shifts an
    # element. The resulting phantom index can never resolve.
    orig_locator = page.locator

    def inflating_locator(selector, **kwargs):
        loc = orig_locator(selector, **kwargs)
        if selector == SELECTORS["button"]:
            real_count = loc.count
            loc.count = lambda: real_count() + 1
        return loc

    page.locator = inflating_locator

    start = time.perf_counter()
    obs = observe(page)
    observe_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    emap = build_map(page)
    build_map_elapsed = time.perf_counter() - start

    # Before the fix, a single phantom index blocked for Playwright's unset
    # 30000ms default. With the fix, the same miss costs at most
    # OBSERVE_PROBE_TIMEOUT_MS. Assert well under 30s -- tight enough that a
    # regression back to the unset default fails this test, loose enough to
    # tolerate normal CI scheduling jitter.
    assert observe_elapsed < 5.0, (
        f"observe() took {observe_elapsed:.2f}s against a phantom locator index "
        "-- looks like the 30s stall regressed"
    )
    assert build_map_elapsed < 5.0, (
        f"build_map() took {build_map_elapsed:.2f}s against a phantom locator index "
        "-- looks like the 30s stall regressed"
    )

    # --- 4. Existing exception/fallback behavior remains safe -------------
    # The phantom index is silently skipped (not fatal), and the real,
    # still-present elements surface exactly as before.
    texts = {e["text"] for e in obs["elements"]}
    assert "Visible One" in texts
    assert "Visible Two" in texts
    assert set(emap.keys()) == {e["id"] for e in obs["elements"]}


def test_body_text_extraction_failure_is_non_fatal(monkeypatch, page):
    def boom(self, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(Locator, "inner_text", boom)

    obs = observe(page)  # must not raise
    assert obs["text_sample"] == ""
