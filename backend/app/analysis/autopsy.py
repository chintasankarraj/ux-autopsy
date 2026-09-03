from backend.app.analysis.friction import detect_friction
from backend.app.analysis.scoring import compute_score
from backend.app.providers.base import get_provider
from backend.app.config import settings

def run_autopsy(events, summary):
    fps, _ = detect_friction(events, summary)
    score = compute_score(summary, fps, events)
    provider = get_provider(settings.resolved_provider)
    s = {k: summary.get(k) for k in ("completed", "actions_count", "pages_visited", "duration_ms")}
    ai = provider.autopsy(s, fps, score)
    return {"friction_points": fps, "score": score, "ai": ai, "provider": provider.name}
