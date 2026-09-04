"""Request schema and built-in persona definitions."""
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator

PERSONAS: dict[str, str] = {
    "budget_shopper": (
        "Budget-conscious shopper. Checks the price of anything before committing, "
        "compares options, low-to-medium patience for friction that doesn't relate to price."
    ),
    "impatient": (
        "Impatient user with very low tolerance for friction. Abandons a task quickly if "
        "progress isn't obvious within a few actions."
    ),
    "beginner": (
        "Confused beginner with low technical/domain knowledge. Needs clear labels and obvious "
        "affordances; easily stalls on ambiguous controls."
    ),
    "power_user": (
        "Experienced power user who knows common UI conventions. Moves quickly, scans rather than "
        "reads, goes straight for filters/search/shortcuts."
    ),
    "mobile_user": (
        "Mobile-first user with small-screen assumptions. Expects large, obvious tap targets and "
        "minimal typing; frustrated by dense, desktop-only layouts."
    ),
}

# Display names only (narrative text) — the persona/friction/scoring pipeline
# itself keys everything off the ids above.
PERSONA_NAMES: dict[str, str] = {
    "budget_shopper": "Budget Shopper",
    "impatient": "Impatient User",
    "beginner": "Confused Beginner",
    "power_user": "Power User",
    "mobile_user": "Mobile User",
    "custom": "Custom Persona",
}


class SessionCreate(BaseModel):
    url: str
    task: str
    persona: str
    custom_persona: Optional[str] = None

    @field_validator("task")
    @classmethod
    def _task_len(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Task must be at least 5 characters.")
        return v

    @field_validator("persona")
    @classmethod
    def _persona_known(cls, v: str) -> str:
        if v not in PERSONAS and v != "custom":
            raise ValueError(f"Unknown persona '{v}'.")
        return v

    @model_validator(mode="after")
    def _custom_requires_description(self) -> "SessionCreate":
        if self.persona == "custom" and not (self.custom_persona or "").strip():
            raise ValueError("custom_persona is required when persona is 'custom'.")
        return self
