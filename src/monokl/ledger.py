"""Durable create-only run ledger storage and validation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import (
    SCHEMA_VERSION,
    ArtifactReference,
    ContractError,
    Scope,
    ValidationErrorRecord,
    canonical_json_bytes,
    canonical_sha256,
    require_keys,
    run_contract,
    sha256_hex,
    transition_contract,
)

STATE_DIR = ".monokl"
ARTIFACT_DIR = "artifacts"
TRANSITION_DIR = "transitions"
RUN_FILE = "run.json"
LOCK_FILE = ".write-lock"

RUN_KEYS = {"schema_version", "contract", "run_id", "state", "migration_policy"}
SCOPE_KEYS = {"schema_version", "question", "included", "excluded", "budget", "authority", "retrieved_content_is_untrusted"}
TRANSITION_KEYS = {"schema_version", "contract", "sequence", "id", "from_state", "to_state", "artifacts"}
ARTIFACT_REF_KEYS = {"id", "path", "sha256", "contract"}
ALLOWED_TRANSITIONS = {("absent", "initialized"), ("initialized", "scoped")}


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    state: str
    errors: list[ValidationErrorRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "command": "validate",
            "valid": self.valid,
            "state": self.state,
            "errors": [error.to_dict() for error in self.errors],
        }


class RunLock:
    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / LOCK_FILE
        self.fd: int | None = None

    def __enter__(self) -> "RunLock":
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        self.fd = os.open(self.path, flags, 0o600)
        os.write(self.fd, str(os.getpid()).encode("ascii"))
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.fd is not None:
            os.close(self.fd)
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def _safe_child(base: Path, relative: str) -> Path:
    if relative.startswith("/") or "\\" in relative:
        raise ContractError(f"unsafe artifact path: {relative}")
    parts = Path(relative).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ContractError(f"unsafe artifact path: {relative}")
    path = base.joinpath(*parts)
    resolved_base = base.resolve(strict=False)
    resolved_parent = path.parent.resolve(strict=False)
    if resolved_base not in (resolved_parent, *resolved_parent.parents):
        raise ContractError(f"artifact path escapes run state: {relative}")
    return path


def _write_new(path: Path, value: object) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite {path}")
    data = canonical_json_bytes(value)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def _read_json(path: Path) -> Any:
    if path.is_symlink():
        raise ContractError(f"refusing symlink path: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _transition_path(state: Path, sequence: int, transition_id: str) -> Path:
    safe_id = transition_id.replace("_", "-")
    if "/" in safe_id or "\\" in safe_id or safe_id in {".", "..", ""}:
        raise ContractError("transition id must be path-safe")
    return state / TRANSITION_DIR / f"{sequence:06d}-{safe_id}.json"


def _next_sequence(state: Path) -> int:
    transitions = sorted((state / TRANSITION_DIR).glob("*.json"))
    return len(transitions) + 1


def _artifact(state: Path, artifact_id: str, contract: str, payload: object) -> ArtifactReference:
    path = _safe_child(state, f"{ARTIFACT_DIR}/{artifact_id}.json")
    _write_new(path, payload)
    return ArtifactReference(
        id=artifact_id,
        path=f"{ARTIFACT_DIR}/{artifact_id}.json",
        sha256=canonical_sha256(payload),
        contract=contract,
    )


def create_run(run_dir: Path) -> dict[str, Any]:
    if run_dir.exists() or run_dir.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing run directory: {run_dir}")
    run_dir.mkdir(parents=False)
    state = run_dir / STATE_DIR
    state.mkdir()
    (state / ARTIFACT_DIR).mkdir()
    (state / TRANSITION_DIR).mkdir()
    with RunLock(state):
        run = run_contract(run_dir.name)
        _write_new(state / RUN_FILE, run)
        sequence = 1
        transition = transition_contract(
            sequence=sequence,
            transition_id="init",
            from_state="absent",
            to_state="initialized",
            artifacts=[ArtifactReference("run", RUN_FILE, canonical_sha256(run), "monokl.run")],
        )
        _write_new(_transition_path(state, sequence, "init"), transition)
    return {"schema_version": SCHEMA_VERSION, "command": "init", "state": "initialized", "run": run}


def add_scope(run_dir: Path, scope: Scope) -> dict[str, Any]:
    state = run_dir / STATE_DIR
    if not state.is_dir() or state.is_symlink():
        raise ContractError("run is not initialized")
    with RunLock(state):
        current = validate_run(run_dir)
        if not current.valid:
            raise ContractError("run is invalid; validate before resuming writes")
        if current.state != "initialized":
            raise FileExistsError("scope already exists or run is past scope planning")
        payload = scope.to_dict()
        artifact = _artifact(state, "scope", "monokl.scope", payload)
        sequence = _next_sequence(state)
        transition = transition_contract(
            sequence=sequence,
            transition_id="plan-scope",
            from_state="initialized",
            to_state="scoped",
            artifacts=[artifact],
        )
        _write_new(_transition_path(state, sequence, "plan-scope"), transition)
    return {"schema_version": SCHEMA_VERSION, "command": "plan", "state": "scoped", "scope": payload}


def _validate_run_doc(value: Any) -> None:
    if not isinstance(value, dict):
        raise ContractError("run must be an object")
    require_keys(value, RUN_KEYS, RUN_KEYS, "run")
    if value["schema_version"] != SCHEMA_VERSION or value["contract"] != "monokl.run":
        raise ContractError("run has unsupported schema or contract")
    if value["state"] != "initialized":
        raise ContractError("run state must remain initialized evidence")


def _validate_scope_doc(value: Any) -> None:
    if not isinstance(value, dict):
        raise ContractError("scope must be an object")
    require_keys(value, SCOPE_KEYS, SCOPE_KEYS, "scope")
    if value["schema_version"] != SCHEMA_VERSION:
        raise ContractError("scope has unsupported schema")
    if value["authority"] != "proposal_only" or value["retrieved_content_is_untrusted"] is not True:
        raise ContractError("scope authority boundary changed")


def _validate_transition_doc(value: Any) -> None:
    if not isinstance(value, dict):
        raise ContractError("transition must be an object")
    require_keys(value, TRANSITION_KEYS, TRANSITION_KEYS, "transition")
    if value["schema_version"] != SCHEMA_VERSION or value["contract"] != "monokl.transition":
        raise ContractError("transition has unsupported schema or contract")
    if not isinstance(value["artifacts"], list):
        raise ContractError("transition artifacts must be a list")
    for ref in value["artifacts"]:
        if not isinstance(ref, dict):
            raise ContractError("artifact reference must be an object")
        require_keys(ref, ARTIFACT_REF_KEYS, ARTIFACT_REF_KEYS, "artifact reference")


def _record(errors: list[ValidationErrorRecord], code: str, message: str, path: Path | None = None) -> None:
    errors.append(ValidationErrorRecord(code, message, str(path) if path else None))


def validate_run(run_dir: Path) -> ValidationResult:
    state = run_dir / STATE_DIR
    errors: list[ValidationErrorRecord] = []
    if not state.is_dir() or state.is_symlink():
        return ValidationResult(False, "absent", [ValidationErrorRecord("missing_state", "run state directory is missing")])
    for child in [state / ARTIFACT_DIR, state / TRANSITION_DIR]:
        if not child.is_dir() or child.is_symlink():
            _record(errors, "invalid_directory", "required state subdirectory is missing or a symlink", child)
    run_path = state / RUN_FILE
    if not run_path.is_file() or run_path.is_symlink():
        _record(errors, "missing_run", "run contract is missing or a symlink", run_path)
    else:
        try:
            run = _read_json(run_path)
            _validate_run_doc(run)
        except Exception as error:
            _record(errors, "invalid_run", str(error), run_path)
    expected_state = "absent"
    seen_sequences: list[int] = []
    for path in sorted((state / TRANSITION_DIR).glob("*.json")) if (state / TRANSITION_DIR).is_dir() else []:
        try:
            transition = _read_json(path)
            _validate_transition_doc(transition)
            sequence = transition["sequence"]
            seen_sequences.append(sequence)
            if sequence != len(seen_sequences):
                raise ContractError("transition sequence is not contiguous")
            if transition["from_state"] != expected_state:
                raise ContractError(f"transition from_state {transition['from_state']} does not match {expected_state}")
            edge = (transition["from_state"], transition["to_state"])
            if edge not in ALLOWED_TRANSITIONS:
                raise ContractError(f"invalid transition order: {edge[0]} -> {edge[1]}")
            for ref in transition["artifacts"]:
                artifact_path = _safe_child(state, ref["path"])
                if not artifact_path.is_file() or artifact_path.is_symlink():
                    raise ContractError(f"artifact is missing or symlinked: {ref['path']}")
                artifact_bytes = artifact_path.read_bytes()
                if sha256_hex(artifact_bytes) != ref["sha256"]:
                    raise ContractError(f"artifact hash drift: {ref['id']}")
                artifact_json = json.loads(artifact_bytes.decode("utf-8"))
                if ref["contract"] == "monokl.run":
                    _validate_run_doc(artifact_json)
                elif ref["contract"] == "monokl.scope":
                    _validate_scope_doc(artifact_json)
                else:
                    raise ContractError(f"unknown artifact contract: {ref['contract']}")
            expected_state = transition["to_state"]
        except Exception as error:
            _record(errors, "invalid_transition", str(error), path)
    if not seen_sequences:
        _record(errors, "missing_transition", "no transitions were recorded", state / TRANSITION_DIR)
    return ValidationResult(not errors, expected_state if not errors else "invalid", errors)


def resume_run(run_dir: Path) -> dict[str, Any]:
    validation = validate_run(run_dir)
    if not validation.valid:
        return {
            "schema_version": SCHEMA_VERSION,
            "command": "resume",
            "state": "blocked",
            "reason": "validation_failed",
            "validation": validation.to_dict(),
        }
    if validation.state == "initialized":
        return {"schema_version": SCHEMA_VERSION, "command": "resume", "state": "ready", "next_phase": "plan"}
    if validation.state == "scoped":
        return {
            "schema_version": SCHEMA_VERSION,
            "command": "resume",
            "state": "blocked",
            "reason": "next approved goal not implemented: retrieval",
        }
    return {"schema_version": SCHEMA_VERSION, "command": "resume", "state": "blocked", "reason": "unknown_state"}
