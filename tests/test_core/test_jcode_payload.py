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
from hyperresearch.jcode.routes import ROUTES_ENV, doctor, load_model_routes


def test_jcode_payload_resources_and_parity_map_complete():
    root = resources.files("hyperresearch") / "jcode"
    skill = (root / "skills" / "monokl" / "SKILL.md").read_text(encoding="utf-8")
    parity = json.loads((root / "maps" / "parity-map.json").read_text(encoding="utf-8"))

    assert "name: monokl" in skill
    assert "Claude `Task` becomes Jcode `swarm`" in skill
    assert "blocked_capability" in skill
    assert parity["compatibility_commands"] == ["monokl", "hpr", "hyperresearch"]
    assert parity["upstream_skill_count"] == 19
    assert parity["entry_skill"] == {
        "upstream_skill": "hyperresearch",
        "jcode_skill": "monokl",
    }
    assert len(parity["stages"]) == 18
    assert {stage["stage"] for stage in parity["stages"]} == {1, 1.5, *range(2, 15), 14.5, 15, 16}
    assert all(stage["upstream_skill"].startswith("hyperresearch-") for stage in parity["stages"])
    assert parity["model_routes"]["config_key"] == "MONOKL_MODEL_ROUTES_JSON"
    assert "--steps-only" not in skill
    assert ".claude/skills" not in skill

    project_skills = list((root / "project-skills").iterdir())
    assert len(project_skills) == 18
    for project_skill in project_skills:
        text = project_skill.read_text(encoding="utf-8")
        assert len(text) > 1_000
        assert "Claude Code" not in text
        assert ".claude/skills" not in text
        assert "TodoWrite" not in text


def test_jcode_install_idempotent_and_uninstall_guarded(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()

    receipt = install_jcode_payload(home=home, project=project)
    skill_path = home / ".jcode" / "skills" / "monokl" / "SKILL.md"
    project_skill = project / ".jcode" / "skills" / "monokl-1-5-chapter-partition" / "SKILL.md"
    assert skill_path.exists()
    assert project_skill.exists()
    assert (project / ".jcode" / "skills" / "monokl-14-5-cite-check" / "SKILL.md").exists()
    assert len(list((project / ".jcode" / "skills").glob("monokl-*/SKILL.md"))) == 18
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


def test_model_routes_are_strict_and_stage_specific(monkeypatch):
    monkeypatch.delenv(ROUTES_ENV, raising=False)
    assert load_model_routes() == {"default": None}
    assert load_model_routes('{"default":"sol-low","12":"terra"}') == {
        "default": "sol-low",
        "12": "terra",
    }
    for raw, message in [
        ("[]", "JSON object"),
        ('{"17":"terra"}', "unknown model-route"),
        ('{"12":""}', "non-empty string"),
        ("{", f"invalid {ROUTES_ENV}"),
    ]:
        with pytest.raises(JcodeInstallError, match=message):
            load_model_routes(raw)


def test_doctor_blocks_before_install_and_is_ready_after_install(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr("hyperresearch.jcode.routes.shutil.which", lambda name: "/bin/jcode")

    assert doctor(home, project)["state"] == "blocked_capability"
    install_jcode_payload(home=home, project=project)
    result = doctor(home, project)
    assert result["state"] == "ready"
    assert all(check["passed"] for check in result["checks"])


def test_uninstall_refuses_receipt_path_outside_monokl_roots(tmp_path):
    home = tmp_path / "home"
    install_jcode_payload(home=home)
    receipt_path = home / ".jcode" / "skills" / "monokl" / ".monokl-install-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["files"].append({"path": str(tmp_path / "victim.txt"), "sha256": "0" * 64})
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(JcodeInstallError, match="outside Monokl skill roots"):
        uninstall_jcode_payload(home=home)
