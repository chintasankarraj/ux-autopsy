"""Test-isolation guard: normal `pytest` runs must never contact the real
Gemini API, regardless of what LLM_PROVIDER/GEMINI_API_KEY happen to be set
to in the developer's own `.env`.

This file changes nothing about the application's behavior — it only
constrains what happens while *tests* are running, via two independent,
overlapping layers:

1. Force `LLM_PROVIDER=mock` for this test process. This is set as a plain
   environment variable, at import time (conftest.py is always imported by
   pytest before any test module), so `config.py`'s existing, unmodified
   `resolved_provider` resolution logic naturally returns "mock" — the same
   documented override any developer could already set by hand, just applied
   consistently for test runs instead of left to chance.
2. Defense in depth: even if some test constructs a real `GeminiProvider`
   directly (bypassing provider resolution), patch the underlying SDK's
   `generate_content` so an actual network call raises loudly instead of
   silently reaching the live API and consuming quota.

The real Gemini provider itself (`providers/gemini.py`) is completely
unmodified and untouched by this file — production/live use is unaffected.
"""
import os

# Layer 1 — must happen before backend.app.config is first imported by any
# test module, which is guaranteed: pytest always imports conftest.py before
# collecting test files.
os.environ["LLM_PROVIDER"] = "mock"


def _blocked_generate_content(*_args, **_kwargs):
    raise RuntimeError(
        "Real Gemini API call attempted during an automated test run. "
        "Normal `pytest`/`playwright test` runs must never contact the live "
        "Gemini API. If you intentionally need a real Gemini call, use the "
        "separate live regression script "
        "(backend/scripts/live_gemini_regression.py) with its explicit "
        "opt-in environment variable — never the normal test suite."
    )


def pytest_configure(config):  # noqa: ARG001 — pluggy validates this hook's signature by name
    # Layer 2 — patched once per test session, on the real SDK class. Tests
    # that inject their own mock (e.g. replacing `provider.model` with a
    # MagicMock, as test_provenance.py does) are unaffected: they never touch
    # this real class.
    from google.generativeai.generative_models import GenerativeModel

    GenerativeModel.generate_content = _blocked_generate_content
