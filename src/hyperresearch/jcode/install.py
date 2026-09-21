"""Safe Jcode payload installer for Monokl.

The installer is intentionally conservative: it writes only under declared Jcode
skill roots, rejects symlinks/traversal, upgrades only files whose previous bytes
match the receipt, and writes a receipt with SHA-256 hashes for guarded uninstall.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

RECEIPT_NAME = ".monokl-install-receipt.json"
GLOBAL_FILES = {
    "SKILL.md": "jcode/skills/monokl/SKILL.md",
    "parity-map.json": "jcode/maps/parity-map.json",
    "manifest.json": "jcode/manifest.json",
}
PROJECT_SKILL_RESOURCE_ROOT = "jcode/project-skills"


class JcodeInstallError(RuntimeError):
    """Raised when installation cannot proceed safely."""


@dataclass(frozen=True)
class ManagedFile:
    path: Path
    content: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


def _payload_bytes(resource_name: str) -> bytes:
    return (resources.files("hyperresearch") / resource_name).read_bytes()


def _project_skill_files() -> dict[str, str]:
    root = resources.files("hyperresearch") / PROJECT_SKILL_RESOURCE_ROOT
    return {entry.name: f"{PROJECT_SKILL_RESOURCE_ROOT}/{entry.name}" for entry in root.iterdir() if entry.name.endswith(".md")}


def _safe_child(root: Path, relative: str) -> Path:
    if relative.startswith(("/", "~")) or ".." in Path(relative).parts:
        raise JcodeInstallError(f"unsafe relative path: {relative}")
    target = root / relative
    root_resolved = root.resolve(strict=False)
    target_parent = target.parent.resolve(strict=False)
    if root_resolved not in (target_parent, *target_parent.parents):
        raise JcodeInstallError(f"path escapes root: {target}")
    return target


def _reject_symlink_path(path: Path) -> None:
    current = path
    parts: list[Path] = []
    while current != current.parent:
        parts.append(current)
        current = current.parent
    for candidate in reversed(parts):
        if candidate.exists() and candidate.is_symlink():
            raise JcodeInstallError(f"refusing symlink path: {candidate}")


def _read_receipt(root: Path) -> dict[str, Any] | None:
    receipt_path = root / RECEIPT_NAME
    if not receipt_path.exists():
        return None
    if receipt_path.is_symlink():
        raise JcodeInstallError(f"refusing symlink receipt: {receipt_path}")
    return json.loads(receipt_path.read_text(encoding="utf-8"))


def _verify_owned_or_absent(files: list[ManagedFile], receipt: dict[str, Any] | None) -> None:
    previous = {item["path"]: item for item in (receipt or {}).get("files", [])}
    for managed in files:
        _reject_symlink_path(managed.path)
        if not managed.path.exists():
            continue
        if managed.path.is_symlink():
            raise JcodeInstallError(f"refusing to overwrite symlink: {managed.path}")
        old = previous.get(str(managed.path))
        if old is None:
            raise JcodeInstallError(f"refusing to overwrite unowned file: {managed.path}")
        actual = hashlib.sha256(managed.path.read_bytes()).hexdigest()
        if actual != old.get("sha256"):
            raise JcodeInstallError(f"refusing drifted managed file: {managed.path}")


def _atomic_write_files(files: list[ManagedFile], receipt_root: Path, receipt: dict[str, Any]) -> None:
    staging = receipt_root / ".monokl-install-staging"
    if staging.exists() or staging.is_symlink():
        raise JcodeInstallError(f"staging path already exists: {staging}")
    backups: dict[Path, bytes | None] = {}
    try:
        staging.mkdir(parents=True)
        for managed in files:
            managed.path.parent.mkdir(parents=True, exist_ok=True)
            backups[managed.path] = managed.path.read_bytes() if managed.path.exists() else None
            tmp = staging / hashlib.sha256(str(managed.path).encode()).hexdigest()
            tmp.write_bytes(managed.content)
            shutil.copyfile(tmp, managed.path)
        (receipt_root / RECEIPT_NAME).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        for path, content in backups.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def install_jcode_payload(home: Path | None = None, project: Path | None = None) -> dict[str, Any]:
    """Install global `/monokl` and optional project step skill payloads."""
    home = Path(os.environ.get("HOME", str(Path.home())) if home is None else home).resolve()
    global_root = home / ".jcode" / "skills" / "monokl"
    files = [ManagedFile(_safe_child(global_root, name), _payload_bytes(resource)) for name, resource in GLOBAL_FILES.items()]
    roots = [global_root]
    if project is not None:
        project_root = Path(project).resolve()
        project_skills_root = project_root / ".jcode" / "skills"
        for filename, resource in _project_skill_files().items():
            skill_name = Path(filename).stem
            project_skill_root = project_skills_root / skill_name
            roots.append(project_skill_root)
            files.append(ManagedFile(_safe_child(project_skill_root, "SKILL.md"), _payload_bytes(resource)))
    receipt_root = global_root
    receipt = _read_receipt(receipt_root)
    _verify_owned_or_absent(files, receipt)
    new_receipt = {
        "schema_version": 1,
        "product": "monokl",
        "home": str(home),
        "roots": [str(root) for root in roots],
        "files": [{"path": str(f.path), "sha256": f.sha256} for f in files],
    }
    receipt_root.mkdir(parents=True, exist_ok=True)
    _atomic_write_files(files, receipt_root, new_receipt)
    return new_receipt


def uninstall_jcode_payload(home: Path | None = None) -> dict[str, Any]:
    """Remove only bytes recorded in the verified Monokl receipt."""
    home = Path(os.environ.get("HOME", str(Path.home())) if home is None else home).resolve()
    global_root = home / ".jcode" / "skills" / "monokl"
    receipt = _read_receipt(global_root)
    if receipt is None:
        raise JcodeInstallError("no Monokl receipt found")
    removed: list[str] = []
    for item in receipt.get("files", []):
        path = Path(item["path"])
        _reject_symlink_path(path)
        if not path.exists():
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != item.get("sha256"):
            raise JcodeInstallError(f"refusing to uninstall drifted file: {path}")
        path.unlink()
        removed.append(str(path))
    (global_root / RECEIPT_NAME).unlink(missing_ok=True)
    # Clean empty owned directories only.
    for root in sorted((Path(r) for r in receipt.get("roots", [])), key=lambda p: len(p.parts), reverse=True):
        try:
            root.rmdir()
        except OSError:
            pass
    return {"removed": removed, "receipt": str(global_root / RECEIPT_NAME)}
