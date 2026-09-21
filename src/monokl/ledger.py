"""Durable create-only run ledger storage and validation."""

from __future__ import annotations

import json
import os
import re
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
TRANSITION_KEYS = {
    "schema_version",
    "contract",
    "sequence",
    "id",
    "from_state",
    "to_state",
    "artifacts",
    "previous_sha256",
    "sha256",
}
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
    if re.fullmatch(r"[a-z0-9][a-z0-9-]*", transition_id) is None:
        raise ContractError("transition id must be path-safe")
    return state / TRANSITION_DIR / f"{sequence:06d}-{transition_id}.json"


def _next_sequence(state: Path) -> int:
    transitions = sorted((state / TRANSITION_DIR).glob("*.json"))
    return len(transitions) + 1


def _latest_transition_sha256(state: Path) -> str | None:
    transitions = sorted((state / TRANSITION_DIR).glob("*.json"))
    if not transitions:
        return None
    return sha256_hex(transitions[-1].read_bytes())


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
            previous_sha256=None,
        )
        _write_new(_transition_path(state, sequence, "init"), transition)
    return {"schema_version": SCHEMA_VERSION, "command": "init", "state": "initialized", "run": run}


def add_scope(run_dir: Path, scope: Scope) -> dict[str, Any]:
    state = run_dir / STATE_DIR
    if not state.is_dir() or state.is_symlink():
        raise ContractError("run is not initialized")
    with RunLock(state):
        current = validate_run(run_dir, held_lock=True)
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
            previous_sha256=_latest_transition_sha256(state),
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
    if isinstance(value["sequence"], bool) or not isinstance(value["sequence"], int) or value["sequence"] <= 0:
        raise ContractError("transition sequence must be a positive integer")
    if re.fullmatch(r"[a-z0-9][a-z0-9-]*", value["id"]) is None:
        raise ContractError("transition id must be path-safe")
    unsigned = {key: item for key, item in value.items() if key != "sha256"}
    if value["sha256"] != canonical_sha256(unsigned):
        raise ContractError("transition integrity hash drift")
    previous = value["previous_sha256"]
    if previous is not None and (not isinstance(previous, str) or re.fullmatch(r"[0-9a-f]{64}", previous) is None):
        raise ContractError("transition previous_sha256 must be null or a SHA-256 hex digest")
    if not isinstance(value["artifacts"], list):
        raise ContractError("transition artifacts must be a list")
    for ref in value["artifacts"]:
        if not isinstance(ref, dict):
            raise ContractError("artifact reference must be an object")
        require_keys(ref, ARTIFACT_REF_KEYS, ARTIFACT_REF_KEYS, "artifact reference")


def _record(errors: list[ValidationErrorRecord], code: str, message: str, path: Path | None = None) -> None:
    errors.append(ValidationErrorRecord(code, message, str(path) if path else None))


def validate_run(run_dir: Path, *, held_lock: bool = False) -> ValidationResult:
    state = run_dir / STATE_DIR
    errors: list[ValidationErrorRecord] = []
    if not state.is_dir() or state.is_symlink():
        return ValidationResult(False, "absent", [ValidationErrorRecord("missing_state", "run state directory is missing")])
    lock_path = state / LOCK_FILE
    if lock_path.exists() or lock_path.is_symlink():
        if not held_lock:
            if lock_path.is_symlink():
                _record(errors, "invalid_lock", "write lock must not be a symlink", lock_path)
            else:
                try:
                    owner = lock_path.read_text(encoding="ascii").strip()
                    pid = int(owner)
                    os.kill(pid, 0)
                    message = f"write lock is active for process {pid}"
                    code = "write_in_progress"
                except ProcessLookupError:
                    message = "stale write lock found; verify no writer is active, then remove .monokl/.write-lock"
                    code = "stale_lock"
                except Exception:
                    message = "write lock is malformed or unsafe; inspect .monokl/.write-lock before removal"
                    code = "invalid_lock"
                _record(errors, code, message, lock_path)
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
    previous_transition_sha256: str | None = None
    referenced_artifacts: set[str] = set()
    for path in sorted((state / TRANSITION_DIR).glob("*.json")) if (state / TRANSITION_DIR).is_dir() else []:
        try:
            transition = _read_json(path)
            _validate_transition_doc(transition)
            sequence = transition["sequence"]
            if path != _transition_path(state, sequence, transition["id"]):
                raise ContractError("transition filename does not match its sequence and id")
            seen_sequences.append(sequence)
            if sequence != len(seen_sequences):
                raise ContractError("transition sequence is not contiguous")
            if transition["from_state"] != expected_state:
                raise ContractError(f"transition from_state {transition['from_state']} does not match {expected_state}")
            edge = (transition["from_state"], transition["to_state"])
            if edge not in ALLOWED_TRANSITIONS:
                raise ContractError(f"invalid transition order: {edge[0]} -> {edge[1]}")
            if transition["previous_sha256"] != previous_transition_sha256:
                raise ContractError("transition chain does not match the previous transition")
            for ref in transition["artifacts"]:
                referenced_artifacts.add(ref["path"])
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
            previous_transition_sha256 = sha256_hex(path.read_bytes())
        except Exception as error:
            _record(errors, "invalid_transition", str(error), path)
    if not seen_sequences:
        _record(errors, "missing_transition", "no transitions were recorded", state / TRANSITION_DIR)
    artifact_root = state / ARTIFACT_DIR
    if artifact_root.is_dir() and not artifact_root.is_symlink():
        for artifact_path in artifact_root.iterdir():
            relative = artifact_path.relative_to(state).as_posix()
            if artifact_path.is_symlink() or not artifact_path.is_file():
                _record(errors, "invalid_artifact", "artifact directory contains a symlink or non-file entry", artifact_path)
            elif relative not in referenced_artifacts:
                _record(errors, "orphan_artifact", "artifact is not referenced by any valid transition", artifact_path)
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
