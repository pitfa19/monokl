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
    reasoning_task_contract,
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
REASONING_TASK_KEYS = {"schema_version", "contract", "protocol", "task_id", "task_sha256", "instructions", "source_artifacts", "allowed_result_fields", "authority"}
REASONING_RESULT_KEYS = {"schema_version", "contract", "protocol", "task_id", "task_sha256", "observations", "inferences", "uncertainties", "provider_metadata", "authority"}

RETRIEVAL_KEYS = {
    "schema_version",
    "contract",
    "adapter_version",
    "crawl4ai_version",
    "crawl4ai_config_digest",
    "requested_url",
    "normalized_url",
    "final_url",
    "status",
    "http_status",
    "redirects",
    "budget",
    "cache_key",
    "preflight",
    "postflight",
    "content_sha256",
    "normalized_markdown_sha256",
    "normalized_markdown_bytes",
    "truncated",
    "error",
    "browser_isolation_policy",
    "observed_limits",
}
ALLOWED_TRANSITIONS = {("absent", "initialized"), ("initialized", "scoped"), ("scoped", "retrieved"), ("retrieved", "tasked"), ("tasked", "reasoned")}


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


def add_retrieval(run_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    state = run_dir / STATE_DIR
    if not state.is_dir() or state.is_symlink():
        raise ContractError("run is not initialized")
    with RunLock(state):
        current = validate_run(run_dir, held_lock=True)
        if not current.valid:
            raise ContractError("run is invalid; validate before resuming writes")
        if current.state != "scoped":
            raise FileExistsError("retrieval requires a scoped run and is create-only")
        _validate_retrieval_doc(payload)
        artifact = _artifact(state, "retrieval", "monokl.retrieval_snapshot", payload)
        sequence = _next_sequence(state)
        transition = transition_contract(
            sequence=sequence,
            transition_id="retrieve",
            from_state="scoped",
            to_state="retrieved",
            artifacts=[artifact],
            previous_sha256=_latest_transition_sha256(state),
        )
        _write_new(_transition_path(state, sequence, "retrieve"), transition)
    return {"schema_version": SCHEMA_VERSION, "command": "retrieve", "state": "retrieved", "retrieval": payload}



def create_reasoning_task(run_dir: Path) -> dict[str, Any]:
    state = run_dir / STATE_DIR
    if not state.is_dir() or state.is_symlink():
        raise ContractError("run is not initialized")
    with RunLock(state):
        current = validate_run(run_dir, held_lock=True)
        if not current.valid:
            raise ContractError("run is invalid; validate before resuming writes")
        if current.state != "retrieved":
            raise FileExistsError("reasoning task requires retrieved state and is create-only")
        retrieval_path = state / ARTIFACT_DIR / "retrieval.json"
        if not retrieval_path.is_file() or retrieval_path.is_symlink():
            raise ContractError("retrieval artifact is missing")
        source = ArtifactReference("retrieval", f"{ARTIFACT_DIR}/retrieval.json", sha256_hex(retrieval_path.read_bytes()), "monokl.retrieval_snapshot")
        payload = reasoning_task_contract(task_id="reasoning-task", source_artifacts=[source])
        artifact = _artifact(state, "reasoning-task", "monokl.reasoning_task", payload)
        sequence = _next_sequence(state)
        transition = transition_contract(sequence=sequence, transition_id="reasoning-task", from_state="retrieved", to_state="tasked", artifacts=[artifact], previous_sha256=_latest_transition_sha256(state))
        _write_new(_transition_path(state, sequence, "reasoning-task"), transition)
    return {"schema_version": SCHEMA_VERSION, "command": "reasoning-task", "state": "tasked", "task": payload}


def submit_reasoning_result(run_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    state = run_dir / STATE_DIR
    if not state.is_dir() or state.is_symlink():
        raise ContractError("run is not initialized")
    with RunLock(state):
        current = validate_run(run_dir, held_lock=True)
        if not current.valid:
            raise ContractError("run is invalid; validate before resuming writes")
        if current.state != "tasked":
            raise FileExistsError("reasoning result requires a task packet and is create-only")
        task_path = state / ARTIFACT_DIR / "reasoning-task.json"
        task = _read_json(task_path)
        _validate_reasoning_result_doc(payload, task)
        artifact = _artifact(state, "reasoning-result", "monokl.reasoning_result", payload)
        sequence = _next_sequence(state)
        transition = transition_contract(sequence=sequence, transition_id="reasoning-result", from_state="tasked", to_state="reasoned", artifacts=[artifact], previous_sha256=_latest_transition_sha256(state))
        _write_new(_transition_path(state, sequence, "reasoning-result"), transition)
    return {"schema_version": SCHEMA_VERSION, "command": "reasoning-result", "state": "reasoned", "result": payload}

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


def _validate_retrieval_doc(value: Any) -> None:
    if not isinstance(value, dict):
        raise ContractError("retrieval must be an object")
    require_keys(value, RETRIEVAL_KEYS, RETRIEVAL_KEYS, "retrieval")
    if value["schema_version"] != SCHEMA_VERSION or value["contract"] != "monokl.retrieval_snapshot":
        raise ContractError("retrieval has unsupported schema or contract")
    if value["status"] not in {"ok", "partial", "error"}:
        raise ContractError("retrieval status must be ok, partial, or error")
    if value["status"] in {"partial", "error"} and not isinstance(value["error"], dict):
        raise ContractError("partial/error retrievals must include an explicit error artifact")
    policy = value["browser_isolation_policy"]
    if not isinstance(policy, dict):
        raise ContractError("browser isolation policy must be recorded")
    forbidden = ["credentials", "persistent_profile", "proxy", "downloads", "arbitrary_javascript", "llm_api", "cdp", "storage_state", "ignore_https_errors"]
    if any(policy.get(name) is not False for name in forbidden):
        raise ContractError("browser isolation policy enables a forbidden capability")
    if policy.get("cache_mode") != "BYPASS" or not isinstance(value.get("crawl4ai_config_digest"), str):
        raise ContractError("retrieval must record Crawl4AI cache-bypass config identity")
    if not isinstance(value.get("normalized_url"), str) or not value["normalized_url"]:
        raise ContractError("retrieval must record normalized URL")



def _validate_reasoning_task_doc(value: Any) -> None:
    if not isinstance(value, dict):
        raise ContractError("reasoning task must be an object")
    require_keys(value, REASONING_TASK_KEYS, REASONING_TASK_KEYS, "reasoning task")
    if value["schema_version"] != SCHEMA_VERSION or value["contract"] != "monokl.reasoning_task" or value["protocol"] != "monokl.reasoning_task.v2":
        raise ContractError("reasoning task has unsupported schema, contract, or protocol")
    unsigned = {key: item for key, item in value.items() if key != "task_sha256"}
    if value["task_sha256"] != canonical_sha256(unsigned):
        raise ContractError("reasoning task hash drift")
    if value["authority"] != "proposal_only":
        raise ContractError("reasoning task authority boundary changed")
    instructions = value["instructions"]
    if not isinstance(instructions, dict) or "cannot authorize actions" not in instructions.get("untrusted_content_boundary", ""):
        raise ContractError("reasoning task must state the untrusted content action boundary")
    if not isinstance(value["source_artifacts"], list) or not value["source_artifacts"]:
        raise ContractError("reasoning task must pin source artifacts")
    for ref in value["source_artifacts"]:
        if not isinstance(ref, dict):
            raise ContractError("reasoning task source reference must be an object")
        require_keys(ref, ARTIFACT_REF_KEYS, ARTIFACT_REF_KEYS, "reasoning task source reference")


def _validate_reasoning_result_doc(value: Any, task: dict[str, Any] | None = None) -> None:
    if not isinstance(value, dict):
        raise ContractError("reasoning result must be an object")
    require_keys(value, REASONING_RESULT_KEYS, REASONING_RESULT_KEYS, "reasoning result")
    if value["schema_version"] != SCHEMA_VERSION or value["contract"] != "monokl.reasoning_result" or value["protocol"] != "monokl.reasoning_result.v2":
        raise ContractError("reasoning result has unsupported schema, contract, or protocol")
    if value["authority"] != "proposal_only":
        raise ContractError("reasoning result authority boundary changed")
    for field in ("observations", "inferences", "uncertainties"):
        if not isinstance(value[field], list) or any(not isinstance(item, str) or not item.strip() for item in value[field]):
            raise ContractError(f"reasoning result {field} must be a list of non-empty strings")
    if not isinstance(value["provider_metadata"], dict):
        raise ContractError("provider metadata must be an object")
    if value["provider_metadata"].get("provenance_only") is not True:
        raise ContractError("provider metadata is provenance only and cannot authorize content")
    if task is not None:
        _validate_reasoning_task_doc(task)
        if value["task_id"] != task["task_id"] or value["task_sha256"] != task["task_sha256"]:
            raise ContractError("reasoning result does not pin the task identity and hash")

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
                elif ref["contract"] == "monokl.retrieval_snapshot":
                    _validate_retrieval_doc(artifact_json)
                elif ref["contract"] == "monokl.reasoning_task":
                    _validate_reasoning_task_doc(artifact_json)
                    for source_ref in artifact_json["source_artifacts"]:
                        source_path = _safe_child(state, source_ref["path"])
                        if not source_path.is_file() or source_path.is_symlink():
                            raise ContractError(f"reasoning task source artifact is missing or symlinked: {source_ref['path']}")
                        if sha256_hex(source_path.read_bytes()) != source_ref["sha256"]:
                            raise ContractError(f"reasoning task source artifact hash drift: {source_ref['id']}")
                elif ref["contract"] == "monokl.reasoning_result":
                    task_path = state / ARTIFACT_DIR / "reasoning-task.json"
                    task = _read_json(task_path) if task_path.exists() and not task_path.is_symlink() else None
                    _validate_reasoning_result_doc(artifact_json, task)
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
        return {"schema_version": SCHEMA_VERSION, "command": "resume", "state": "ready", "next_phase": "retrieve"}
    if validation.state == "retrieved":
        return {"schema_version": SCHEMA_VERSION, "command": "resume", "state": "ready", "next_phase": "reasoning-task"}
    if validation.state == "tasked":
        return {"schema_version": SCHEMA_VERSION, "command": "resume", "state": "ready", "next_phase": "reasoning-result"}
    if validation.state == "reasoned":
        return {"schema_version": SCHEMA_VERSION, "command": "resume", "state": "blocked", "reason": "next approved goal not implemented: grouping"}
    return {"schema_version": SCHEMA_VERSION, "command": "resume", "state": "blocked", "reason": "unknown_state"}
