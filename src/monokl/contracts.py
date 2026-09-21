"""Immutable run contracts for the first Monokl milestone."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Budget:
    max_sources: int = 30
    max_pages_per_source: int = 5
    max_bytes_per_page: int = 2_000_000

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class Scope:
    question: str
    included: tuple[str, ...]
    excluded: tuple[str, ...]
    budget: Budget

    def validate(self) -> None:
        if not self.question.strip():
            raise ValueError("question must not be empty")
        self.budget.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": 1,
            "question": self.question,
            "included": list(self.included),
            "excluded": list(self.excluded),
            "budget": asdict(self.budget),
            "authority": "proposal_only",
            "retrieved_content_is_untrusted": True,
        }
