"""Versioned contracts and validation helpers for Monokl's durable run ledger."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping

SCHEMA_VERSION = 1


class ContractError(ValueError):
    """Raised when a contract cannot be constructed or validated."""


@dataclass(frozen=True)
class Budget:
    max_sources: int = 30
    max_pages_per_source: int = 5
    max_bytes_per_page: int = 2_000_000

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, int) or value <= 0:
                raise ContractError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class Scope:
    question: str
    included: tuple[str, ...]
    excluded: tuple[str, ...]
    budget: Budget

    def validate(self) -> None:
        if not self.question.strip():
            raise ContractError("question must not be empty")
        self.budget.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": SCHEMA_VERSION,
            "question": self.question,
            "included": list(self.included),
            "excluded": list(self.excluded),
            "budget": asdict(self.budget),
            "authority": "proposal_only",
            "retrieved_content_is_untrusted": True,
        }


@dataclass(frozen=True)
class ArtifactReference:
    id: str
    path: str
    sha256: str
    contract: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "path": self.path, "sha256": self.sha256, "contract": self.contract}


@dataclass(frozen=True)
class ValidationErrorRecord:
    code: str
    message: str
    path: str | None = None

    def to_dict(self) -> dict[str, str]:
        result = {"code": self.code, "message": self.message}
        if self.path is not None:
            result["path"] = self.path
        return result


def canonical_json_bytes(value: object) -> bytes:
    """Return the canonical JSON bytes used for SHA-256 identity."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: object) -> str:
    return sha256_hex(canonical_json_bytes(value))


def require_keys(value: Mapping[str, Any], allowed: set[str], required: set[str], contract: str) -> None:
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        raise ContractError(f"{contract} has unknown field(s): {', '.join(sorted(unknown))}")
    if missing:
        raise ContractError(f"{contract} is missing field(s): {', '.join(sorted(missing))}")


def run_contract(run_id: str) -> dict[str, Any]:
    if not run_id or "/" in run_id or "\\" in run_id or run_id in {".", ".."}:
        raise ContractError("run_id must be a non-empty path-safe identifier")
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": "monokl.run",
        "run_id": run_id,
        "state": "initialized",
        "migration_policy": "schema migrations create new artifacts and never mutate prior evidence in place",
    }


def transition_contract(
    *,
    sequence: int,
    transition_id: str,
    from_state: str,
    to_state: str,
    artifacts: list[ArtifactReference],
) -> dict[str, Any]:
    if sequence <= 0:
        raise ContractError("transition sequence must be positive")
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": "monokl.transition",
        "sequence": sequence,
        "id": transition_id,
        "from_state": from_state,
        "to_state": to_state,
        "artifacts": [artifact.to_dict() for artifact in artifacts],
    }
