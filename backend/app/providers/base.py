from abc import ABC, abstractmethod

class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    def decide(self, observation, task, persona, history, element_map, persona_id=None,
               completion_hint=None): ...

    @abstractmethod
    def autopsy(self, session_summary, friction_points, score): ...

def get_provider(name):
    if name == "gemini":
        from backend.app.providers.gemini import GeminiProvider
        return GeminiProvider()
    from backend.app.providers.mock import MockProvider
    return MockProvider()
