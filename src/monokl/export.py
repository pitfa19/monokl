"""Create-only public export bundles for synthesized Monokl runs."""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
from pathlib import Path
from typing import Any

from .contracts import SCHEMA_VERSION, ContractError, canonical_json_bytes, sha256_hex
from .ledger import ARTIFACT_DIR, STATE_DIR, validate_run

EXPORT_FILES = ("report.md", "evidence.json", "gaps.json", "receipt.json", "mozak-proposal.json")


def _safe_output_dir(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing export directory: {path}")
    parent = path.parent
    if parent.is_symlink():
        raise ContractError(f"refusing symlink parent: {parent}")
    parent.mkdir(parents=True, exist_ok=True)
    resolved_parent = parent.resolve(strict=True)
    resolved_candidate = path.resolve(strict=False)
    if resolved_parent not in resolved_candidate.parents:
        raise ContractError("export directory must stay under its resolved parent")


def _read_artifact(state: Path, name: str) -> dict[str, Any]:
    path = state / ARTIFACT_DIR / f"{name}.json"
    if not path.is_file() or path.is_symlink():
        raise ContractError(f"required artifact is missing or unsafe: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_file(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ContractError(f"unsafe file in export bundle: {path}")
    return sha256_hex(path.read_bytes())


def _write_new(path: Path, data: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite {path}")
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


def _citation_index(synthesis: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    index: dict[str, list[dict[str, str]]] = {}
    for claim in synthesis["claims"]:
        index[claim["claim_id"]] = [
            {
                "source_id": loc["source_id"],
                "artifact_id": loc["artifact_id"],
                "artifact_path": loc["artifact_path"],
                "artifact_contract": loc["artifact_contract"],
                "artifact_sha256": loc["artifact_sha256"],
                "locator": loc["locator"],
            }
            for loc in claim["locators"]
        ]
    return index


def _validate_export_inputs(run_dir: Path) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    validation = validate_run(run_dir)
    if not validation.valid or validation.state != "synthesized":
        raise ContractError("export requires a valid synthesized run")
    state = run_dir / STATE_DIR
    synthesis = _read_artifact(state, "evidence-synthesis")
    audit = _read_artifact(state, "evidence-audit")
    groups = _read_artifact(state, "source-groups")
    inventory = _read_artifact(state, "source-inventory")
    retrieval = _read_artifact(state, "retrieval")
    source_ids = {source["source_id"] for source in inventory["sources"]}
    group_ids = {group["group_id"] for group in groups["groups"]}
    for claim in synthesis["claims"]:
        if not claim["locators"]:
            raise ContractError(f"unresolved citation for claim {claim['claim_id']}")
        if claim["group_id"] not in group_ids:
            raise ContractError(f"claim references missing group: {claim['claim_id']}")
        for locator in claim["locators"]:
            if locator["source_id"] not in source_ids or not locator["locator"].strip():
                raise ContractError(f"unresolved citation for claim {claim['claim_id']}")
    return state, synthesis, audit, groups, inventory, retrieval


def _render_report(synthesis: dict[str, Any], audit: dict[str, Any], groups: dict[str, Any], retrieval: dict[str, Any]) -> str:
    citations = _citation_index(synthesis)
    group_titles = {group["group_id"]: group["title"] for group in groups["groups"]}
    lines = [
        "# Monokl public report",
        "",
        "Authority: proposal_only. This export does not claim MOZAK acceptance, promotion, or owner approval beyond pinned source-group approval in the run.",
        "",
        "## Provider provenance",
        f"- Retrieval adapter: `{retrieval.get('adapter_version', 'unsupported')}`. Locator: `artifacts/retrieval.json`.",
        f"- Crawl4AI version: `{retrieval.get('crawl4ai_version')}`. Locator: `artifacts/retrieval.json`.",
        "- Reasoning provider details are in `evidence.json.provider_provenance`; claims below cite source locators, not provider authority.",
        "",
        "## Groups and claims",
    ]
    for group in synthesis["per_group_synthesis"]:
        gid = group["group_id"]
        lines.extend(["", f"### {group_titles.get(gid, gid)}", f"- Group id: `{gid}`", f"- Summary: {group['summary']}"])
        if group["limitations"]:
            lines.append("- Limitations: " + "; ".join(group["limitations"]))
        for claim_id in group["claim_ids"]:
            claim = next(item for item in synthesis["claims"] if item["claim_id"] == claim_id)
            locs = "; ".join(f"{loc['source_id']} {loc['locator']} `{loc['artifact_sha256']}`" for loc in citations[claim_id])
            lines.append(f"- Claim `{claim_id}` ({claim['label']}): {claim['text']} Evidence: {locs}")
    lines.extend(["", "## Contradictions"])
    if synthesis["contradictions"]:
        for item in synthesis["contradictions"]:
            lines.append(f"- Group `{item['group_id']}`, claims {', '.join(item['claim_ids'])}: {item['description']}")
    else:
        lines.append("- None recorded. Evidence locator: `artifacts/evidence-synthesis.json.contradictions`.")
    lines.extend(["", "## Gaps"])
    if synthesis["gaps"]:
        for item in synthesis["gaps"]:
            lines.append(f"- Group `{item['group_id']}` ({item['impact']}): {item['description']}")
    else:
        lines.append("- None recorded. Evidence locator: `artifacts/evidence-synthesis.json.gaps`.")
    lines.extend(["", "## Unsupported claims"])
    if synthesis["unsupported_claims"]:
        for item in synthesis["unsupported_claims"]:
            lines.append(f"- Claim `{item['claim_id']}` in group `{item['group_id']}`: {item['text']} Reason: {item['reason']}")
    else:
        lines.append("- None recorded. Evidence locator: `artifacts/evidence-synthesis.json.unsupported_claims`.")
    lines.extend(["", "## Validation", f"- Evidence audit status: `{audit['status']}`. Locator: `artifacts/evidence-audit.json`.", ""])
    return "\n".join(lines)


def export_run(run_dir: Path, output_dir: Path) -> dict[str, Any]:
    state, synthesis, audit, groups, inventory, retrieval = _validate_export_inputs(run_dir)
    _safe_output_dir(output_dir)
    output_dir.mkdir(mode=0o700)
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "contract": "monokl.export_evidence",
        "authority": "proposal_only",
        "claims": synthesis["claims"],
        "per_group_synthesis": synthesis["per_group_synthesis"],
        "contradictions": synthesis["contradictions"],
        "limitations": [item for group in synthesis["per_group_synthesis"] for item in group["limitations"]],
        "provider_provenance": {"retrieval_adapter": retrieval.get("adapter_version"), "crawl4ai_version": retrieval.get("crawl4ai_version"), "retrieval_status": retrieval.get("status")},
        "source_inventory_sha256": inventory["inventory_sha256"],
        "source_groups_sha256": groups["groups_sha256"],
        "synthesis_sha256": synthesis["synthesis_sha256"],
        "audit_sha256": audit["audit_sha256"],
    }
    gaps = {
        "schema_version": SCHEMA_VERSION,
        "contract": "monokl.export_gaps",
        "authority": "proposal_only",
        "gaps": synthesis["gaps"],
        "unsupported_claims": synthesis["unsupported_claims"],
        "contradictions": synthesis["contradictions"],
    }
    proposal = {
        "schema_version": SCHEMA_VERSION,
        "contract": "monokl.mozak_research_proposal",
        "authority": "proposal_only",
        "accepted": False,
        "promotion_claim": False,
        "source_run": str(run_dir),
        "source_hashes": {name: _hash_file(state / ARTIFACT_DIR / f"{name}.json") for name in ["source-inventory", "source-groups", "source-group-approval", "reasoning-result", "evidence-synthesis", "evidence-audit"]},
        "proposal": {"kind": "research_artifact_candidate", "status": "owner_review_required"},
    }
    _write_new(output_dir / "report.md", _render_report(synthesis, audit, groups, retrieval).encode("utf-8"))
    _write_new(output_dir / "evidence.json", canonical_json_bytes(evidence))
    _write_new(output_dir / "gaps.json", canonical_json_bytes(gaps))
    _write_new(output_dir / "mozak-proposal.json", canonical_json_bytes(proposal))
    hashes = {name: _hash_file(output_dir / name) for name in ("report.md", "evidence.json", "gaps.json", "mozak-proposal.json")}
    try:
        version = importlib.metadata.version("monokl")
    except importlib.metadata.PackageNotFoundError:
        version = "0+unknown"
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "contract": "monokl.export_receipt",
        "authority": "proposal_only",
        "monokl_version": version,
        "retrieval_runtime": {"adapter_version": retrieval.get("adapter_version"), "crawl4ai_version": retrieval.get("crawl4ai_version")},
        "runtime_versions": {"python": platform.python_version()},
        "validation_status": audit["status"],
        "input_pins": proposal["source_hashes"],
        "artifact_hashes": hashes,
        "mozak_acceptance_claimed": False,
    }
    _write_new(output_dir / "receipt.json", canonical_json_bytes(receipt))
    return validate_export(output_dir)


def validate_export(output_dir: Path) -> dict[str, Any]:
    if not output_dir.is_dir() or output_dir.is_symlink():
        raise ContractError("export directory is missing or unsafe")
    missing = [name for name in EXPORT_FILES if not (output_dir / name).is_file() or (output_dir / name).is_symlink()]
    if missing:
        raise ContractError("export bundle missing file(s): " + ", ".join(missing))
    receipt = json.loads((output_dir / "receipt.json").read_text(encoding="utf-8"))
    hashes = receipt.get("artifact_hashes", {})
    for name in ("report.md", "evidence.json", "gaps.json", "mozak-proposal.json"):
        if hashes.get(name) != _hash_file(output_dir / name):
            raise ContractError(f"export artifact hash drift: {name}")
    evidence = json.loads((output_dir / "evidence.json").read_text(encoding="utf-8"))
    proposal = json.loads((output_dir / "mozak-proposal.json").read_text(encoding="utf-8"))
    if evidence.get("authority") != "proposal_only" or proposal.get("accepted") is not False or receipt.get("mozak_acceptance_claimed") is not False:
        raise ContractError("export crosses proposal-only boundary")
    report = (output_dir / "report.md").read_text(encoding="utf-8")
    for claim in evidence["claims"]:
        if claim["text"] not in report or not claim["locators"]:
            raise ContractError(f"report claim lacks visible evidence locator: {claim['claim_id']}")
    forbidden = ["full_text", "body", "markdown\":", "normalized_markdown\":"]
    combined = (output_dir / "evidence.json").read_text(encoding="utf-8") + (output_dir / "gaps.json").read_text(encoding="utf-8")
    if any(token in combined for token in forbidden):
        raise ContractError("export appears to leak full source text fields")
    return {"schema_version": SCHEMA_VERSION, "command": "export-validate", "valid": True, "files": list(EXPORT_FILES), "artifact_hashes": {name: _hash_file(output_dir / name) for name in EXPORT_FILES}}
