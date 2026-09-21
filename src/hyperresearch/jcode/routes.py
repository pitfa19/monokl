"""Strict model-route and capability helpers for the Jcode host layer."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from hyperresearch.jcode.install import JcodeInstallError

ROUTES_ENV = "MONOKL_MODEL_ROUTES_JSON"
VALID_STAGE_KEYS = {
    "default",
    "1", "1.5", "2", "3", "4", "5", "6", "7", "8", "9",
    "10", "11", "12", "13", "14", "14.5", "15", "16",
}


def load_model_routes(raw: str | None = None) -> dict[str, str | None]:
    """Parse a stage-to-model map, rejecting unknown or non-string values."""
    text = os.environ.get(ROUTES_ENV, "{}") if raw is None else raw
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JcodeInstallError(f"invalid {ROUTES_ENV}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise JcodeInstallError(f"{ROUTES_ENV} must be a JSON object")
    unknown = sorted(set(value) - VALID_STAGE_KEYS)
    if unknown:
        raise JcodeInstallError(f"unknown model-route stage keys: {', '.join(unknown)}")
    routes: dict[str, str | None] = {"default": None}
    for key, model in value.items():
        if not isinstance(model, str) or not model.strip():
            raise JcodeInstallError(f"model route for stage {key} must be a non-empty string")
        routes[str(key)] = model.strip()
    return routes


def doctor(home: Path, project: Path | None = None) -> dict[str, Any]:
    """Check the executable and receipt-owned payload without starting a run."""
    skill_root = home.resolve() / ".jcode" / "skills" / "monokl"
    checks: list[dict[str, Any]] = []
    checks.append({"id": "jcode_executable", "passed": shutil.which("jcode") is not None})
    for name in ("SKILL.md", "parity-map.json", "manifest.json", ".monokl-install-receipt.json"):
        path = skill_root / name
        checks.append({"id": f"global_{name}", "passed": path.is_file() and not path.is_symlink(), "path": str(path)})
    try:
        load_model_routes()
        checks.append({"id": "model_routes", "passed": True})
    except JcodeInstallError as exc:
        checks.append({"id": "model_routes", "passed": False, "error": str(exc)})
    if project is not None:
        skills = list((project.resolve() / ".jcode" / "skills").glob("monokl-*/SKILL.md"))
        checks.append({"id": "project_stage_skills", "passed": len(skills) == 18, "observed": len(skills)})
    return {"state": "ready" if all(c["passed"] for c in checks) else "blocked_capability", "checks": checks}
