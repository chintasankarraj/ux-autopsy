import json
from typing import cast
from unittest.mock import patch, MagicMock

from backend.app.providers.mock import MockProvider
from backend.app.analysis.autopsy import run_autopsy


def _summary(**kw):
    base = {"completed": True, "actions_count": 3, "pages_visited": 1, "duration_ms": 1000,
            "persona_id": "custom", "persona_display": "Custom Persona", "task": "do the thing"}
    base.update(kw)
    return base


def test_mock_autopsy_reports_itself_honestly():
    result = MockProvider().autopsy(_summary(), [], {"ux_score": 90.0})
    assert result["provider_used"] == "mock"
    assert result["fallback"] is False
    assert result["fallback_reason"] is None


def _make_gemini_provider_without_network_init():
    from backend.app.providers.gemini import GeminiProvider
    provider = GeminiProvider.__new__(GeminiProvider)
    mock_model = MagicMock()
    provider.model = mock_model  # type: ignore[assignment]
    return provider, mock_model


def test_gemini_autopsy_success_reports_gemini_as_provider_used():
    provider, mock_model = _make_gemini_provider_without_network_init()
    mock_model.generate_content.return_value = MagicMock(
        text=json.dumps({"executive_summary": "All good.", "root_causes": []})
    )
    result = provider.autopsy(_summary(), [], {"ux_score": 90.0})
    assert result["provider_used"] == "gemini"
    assert result["fallback"] is False
    assert result["fallback_reason"] is None


def test_gemini_autopsy_failure_falls_back_to_mock_and_says_so():
    provider, mock_model = _make_gemini_provider_without_network_init()
    mock_model.generate_content.side_effect = RuntimeError("API timeout")
    result = provider.autopsy(_summary(), [], {"ux_score": 40.0})
    # Content must actually be Mock-generated, and the record must say so —
    # never presented as if Gemini produced it.
    assert result["provider_used"] == "mock"
    assert result["fallback"] is True
    assert result["fallback_reason"]
    assert "executive_summary" in result and result["executive_summary"]


def test_gemini_autopsy_invalid_json_falls_back_to_mock_and_says_so():
    provider, mock_model = _make_gemini_provider_without_network_init()
    mock_model.generate_content.return_value = MagicMock(text="not json at all")
    result = provider.autopsy(_summary(), [], {"ux_score": 40.0})
    assert result["provider_used"] == "mock"
    assert result["fallback"] is True
    assert result["fallback_reason"]


def test_run_autopsy_trusts_actual_provider_not_outer_instance():
    # Even though settings would resolve to "gemini", a session whose autopsy
    # call internally fell back to Mock must have run_autopsy() report
    # "mock" as the provider that actually generated the narrative.
    with patch("backend.app.analysis.autopsy.settings") as mock_settings, \
         patch("backend.app.analysis.autopsy.get_provider") as mock_get_provider:
        mock_settings.resolved_provider = "gemini"
        fake_provider = MagicMock()
        fake_provider.name = "gemini"
        fake_provider.autopsy.return_value = {
            "executive_summary": "Fallback summary.", "root_causes": [],
            "provider_used": "mock", "fallback": True, "fallback_reason": "boom",
        }
        mock_get_provider.return_value = fake_provider

        events = [{"event_type": "TASK_SUCCESS", "url": "u", "ts_ms": 100, "element_id": None,
                   "element_text": None, "confidence": None, "reason": None, "error": None,
                   "decide_ms": None}]
        result = run_autopsy(events, _summary())

    assert result["provider"] == "mock"
    assert result["fallback"] is True
    assert result["fallback_reason"] == "boom"
