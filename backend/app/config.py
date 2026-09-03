"""Application configuration, read from environment variables (.env via os.environ)."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _bool(name, default=False):
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    """Lazily reads env vars on each access so tests can monkeypatch os.environ."""

    @property
    def gemini_api_key(self):
        return os.getenv("GEMINI_API_KEY", "").strip() or None

    @property
    def gemini_model(self):
        return os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    @property
    def provider(self):
        """Configured provider preference: auto | gemini | mock."""
        return os.getenv("LLM_PROVIDER", "auto").strip().lower()

    @property
    def resolved_provider(self):
        """The provider actually used this run. 'auto' resolves to gemini only
        if a key is configured, otherwise falls back to the deterministic mock
        (demo mode) — the app must never become unusable without a key."""
        if self.provider == "gemini":
            return "gemini" if self.gemini_api_key else "mock"
        if self.provider == "mock":
            return "mock"
        return "gemini" if self.gemini_api_key else "mock"

    @property
    def demo_mode(self):
        return self.resolved_provider == "mock"

    @property
    def max_actions(self):
        return int(os.getenv("MAX_ACTIONS", "25"))

    @property
    def max_session_seconds(self):
        return int(os.getenv("MAX_SESSION_SECONDS", "180"))

    @property
    def max_navigations(self):
        return int(os.getenv("MAX_NAVIGATIONS", "10"))

    @property
    def action_timeout_ms(self):
        return int(os.getenv("ACTION_TIMEOUT_MS", "8000"))

    @property
    def headless(self):
        return _bool("BROWSER_HEADLESS", default=True)

    @property
    def demo_url(self):
        port = os.getenv("PORT", "8000")
        return os.getenv("DEMO_SITE_URL", f"http://localhost:{port}/api/demo-site/")


settings = Settings()
