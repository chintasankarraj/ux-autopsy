"""Proves the test-isolation guard in conftest.py is actually active:
normal test runs resolve to the mock provider and a real Gemini network call
is blocked, regardless of the developer's own .env contents."""
import os

import pytest

from backend.app.config import settings


def test_llm_provider_env_forced_to_mock_for_tests():
    assert os.environ.get("LLM_PROVIDER") == "mock"


def test_resolved_provider_is_mock_during_tests():
    # This must hold even on a machine whose .env has LLM_PROVIDER=gemini
    # and a real GEMINI_API_KEY configured.
    assert settings.resolved_provider == "mock"
    assert settings.demo_mode is True


def test_real_gemini_sdk_call_is_blocked():
    from google.generativeai.generative_models import GenerativeModel

    # Constructing the class is harmless (no network call); calling
    # generate_content() is what would actually reach the live API, and
    # conftest.py's guard must intercept it before that happens.
    model = GenerativeModel.__new__(GenerativeModel)
    with pytest.raises(RuntimeError, match="Real Gemini API call attempted"):
        model.generate_content("this must never reach the network")


def test_get_provider_for_resolved_provider_returns_mock():
    from backend.app.providers.base import get_provider
    from backend.app.providers.mock import MockProvider

    provider = get_provider(settings.resolved_provider)
    assert isinstance(provider, MockProvider)
