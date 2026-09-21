import json
import tempfile
import unittest
from pathlib import Path

from monokl.cli import init_run, main, plan_run, status
from monokl.contracts import canonical_sha256
from monokl.ledger import RunLock, resume_run, validate_run


class MonoklCliTests(unittest.TestCase):
    def test_clean_run_validate_resume_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            self.assertEqual(resume_run(run)["next_phase"], "plan")
            result = plan_run(run, "question", ["papers"], ["opinion"], 10)
            self.assertEqual(result["state"], "scoped")
            self.assertEqual(status(run)["state"], "scoped")
            validation = validate_run(run)
            self.assertTrue(validation.valid)
            self.assertEqual(validation.state, "scoped")
            scope = json.loads((run / ".monokl" / "artifacts" / "scope.json").read_text())
            self.assertEqual(scope["budget"]["max_sources"], 10)
            self.assertTrue(scope["retrieved_content_is_untrusted"])
            self.assertEqual(resume_run(run)["state"], "blocked")

    def test_create_only_and_invalid_budget_fail(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            with self.assertRaises(FileExistsError):
                init_run(run)
            with self.assertRaises(ValueError):
                plan_run(run, "question", [], [], 0)
            plan_run(run, "question", [], [], 1)
            with self.assertRaises(FileExistsError):
                plan_run(run, "question 2", [], [], 1)

    def test_interrupted_partial_transition_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            (run / ".monokl" / "transitions" / "000002-partial.json").write_text('{"schema_version":', encoding="utf-8")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("invalid_transition", {error.code for error in validation.errors})
            self.assertEqual(resume_run(run)["reason"], "validation_failed")

    def test_hash_drift_and_stale_result_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            plan_run(run, "question", [], [], 2)
            scope_path = run / ".monokl" / "artifacts" / "scope.json"
            scope = json.loads(scope_path.read_text())
            scope["question"] = "changed"
            scope_path.write_text(json.dumps(scope, sort_keys=True) + "\n", encoding="utf-8")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("hash drift", validation.errors[0].message)

    def test_invalid_transition_order_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            transition_path = run / ".monokl" / "transitions" / "000001-init.json"
            transition = json.loads(transition_path.read_text())
            transition["to_state"] = "scoped"
            transition_path.write_text(json.dumps(transition, sort_keys=True) + "\n", encoding="utf-8")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("invalid transition order", validation.errors[0].message)

    def test_unknown_fields_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            run_path = run / ".monokl" / "run.json"
            payload = json.loads(run_path.read_text())
            payload["extra"] = True
            run_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("unknown field", validation.errors[0].message)

    def test_symlink_artifact_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            plan_run(run, "question", [], [], 2)
            scope_path = run / ".monokl" / "artifacts" / "scope.json"
            scope_path.unlink()
            scope_path.symlink_to(Path(root) / "outside.json")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("symlink", validation.errors[0].message)

    def test_path_traversal_artifact_reference_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            transition_path = run / ".monokl" / "transitions" / "000001-init.json"
            transition = json.loads(transition_path.read_text())
            transition["artifacts"][0]["path"] = "../run.json"
            transition_path.write_text(json.dumps(transition, sort_keys=True) + "\n", encoding="utf-8")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("unsafe artifact path", validation.errors[0].message)

    def test_concurrent_write_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            with RunLock(run / ".monokl"):
                with self.assertRaises(FileExistsError):
                    plan_run(run, "question", [], [], 2)

    def test_cli_validate_and_resume_commands(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            self.assertEqual(main(["init", str(run)]), 0)
            self.assertEqual(main(["validate", str(run)]), 0)
            self.assertEqual(main(["resume", str(run)]), 0)

    def test_canonical_identity_is_stable(self) -> None:
        left = {"b": 2, "a": [1, 2]}
        right = {"a": [1, 2], "b": 2}
        self.assertEqual(canonical_sha256(left), canonical_sha256(right))


if __name__ == "__main__":
    unittest.main()
