from __future__ import annotations

import hashlib
import json
from importlib import resources

import pytest

from hyperresearch.jcode.install import (
    JcodeInstallError,
    install_jcode_payload,
    uninstall_jcode_payload,
)


def test_jcode_payload_resources_and_parity_map_complete():
    root = resources.files("hyperresearch") / "jcode"
    skill = (root / "skills" / "monokl" / "SKILL.md").read_text(encoding="utf-8")
    parity = json.loads((root / "maps" / "parity-map.json").read_text(encoding="utf-8"))

    assert "name: monokl" in skill
    assert "Claude `Task` becomes Jcode `swarm`" in skill
    assert "blocked_capability" in skill
    assert parity["compatibility_commands"] == ["monokl", "hpr", "hyperresearch"]
    assert len(parity["stages"]) == 16
    assert {stage["stage"] for stage in parity["stages"]} == set(range(1, 17))
    assert all(stage["upstream_skill"].startswith("hyperresearch-") for stage in parity["stages"])
    assert parity["model_routes"]["config_key"] == "MONOKL_MODEL_ROUTES_JSON"


def test_jcode_install_idempotent_and_uninstall_guarded(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()

    receipt = install_jcode_payload(home=home, project=project)
    skill_path = home / ".jcode" / "skills" / "monokl" / "SKILL.md"
    project_skill = project / ".jcode" / "skills" / "monokl-stage-reference" / "SKILL.md"
    assert skill_path.exists()
    assert project_skill.exists()
    assert (home / ".jcode" / "skills" / "monokl" / ".monokl-install-receipt.json").exists()

    receipt2 = install_jcode_payload(home=home, project=project)
    assert receipt2["files"] == receipt["files"]

    skill_path.write_text(skill_path.read_text(encoding="utf-8") + "\nuser edit\n", encoding="utf-8")
    with pytest.raises(JcodeInstallError, match="drifted managed file"):
        install_jcode_payload(home=home, project=project)
    with pytest.raises(JcodeInstallError, match="drifted file"):
        uninstall_jcode_payload(home=home)

    skill_path.write_text((resources.files("hyperresearch") / "jcode" / "skills" / "monokl" / "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")
    result = uninstall_jcode_payload(home=home)
    assert str(skill_path) in result["removed"]
    assert not skill_path.exists()
    assert not project_skill.exists()


def test_jcode_install_refuses_unowned_existing_file(tmp_path):
    home = tmp_path / "home"
    target = home / ".jcode" / "skills" / "monokl"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("mine", encoding="utf-8")

    with pytest.raises(JcodeInstallError, match="unowned file"):
        install_jcode_payload(home=home)


def test_jcode_receipt_hashes_match_installed_bytes(tmp_path):
    home = tmp_path / "home"
    receipt = install_jcode_payload(home=home)
    for item in receipt["files"]:
        data = __import__("pathlib").Path(item["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
