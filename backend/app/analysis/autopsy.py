from backend.app.analysis.friction import detect_friction
from backend.app.analysis.scoring import compute_score
from backend.app.providers.base import get_provider
from backend.app.config import settings


def run_autopsy(events, summary):
    fps, _ = detect_friction(events, summary)
    score = compute_score(summary, fps, events)
    provider = get_provider(settings.resolved_provider)
    s = {k: summary.get(k) for k in (
        "completed", "actions_count", "pages_visited", "duration_ms",
        "persona_id", "persona_display", "task",
    )}
    ai = provider.autopsy(s, fps, score)

    # Attach each root-cause's explanation directly onto its friction point
    # (they're generated in the same order, one per friction item) so the UI
    # can show a "Why did this happen?" panel per friction point without
    # cross-referencing two separate arrays. Skipped if a provider returns a
    # different count than expected — never guess at a mismatched pairing.
    root_causes = ai.get("root_causes", [])
    if len(root_causes) == len(fps):
        for fp, rc in zip(fps, root_causes):
            fp["why"] = {
                "observed": rc.get("observed"),
                "possible_cause": rc.get("possible_cause"),
                "likely_root_cause": rc.get("likely_root_cause"),
                "recommendation": rc.get("recommendation"),
                "confidence": rc.get("confidence"),
            }

    # The provider instance's own `.name` reflects which class was
    # configured, not which one actually produced this narrative — a Gemini
    # instance whose autopsy() call failed internally returns Mock-generated
    # content while still being a `GeminiProvider`. Trust the provider's own
    # report of what it actually used instead of the outer instance type.
    provider_used = ai.get("provider_used", provider.name)
    return {
        "friction_points": fps,
        "score": score,
        "ai": ai,
        "provider": provider_used,
        "fallback": bool(ai.get("fallback", False)),
        "fallback_reason": ai.get("fallback_reason"),
    }
