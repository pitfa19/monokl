import json
import tempfile
import unittest
from pathlib import Path

from monokl.cli import init_run, plan_run, status


class MonoklCliTests(unittest.TestCase):
    def test_init_plan_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            result = plan_run(run, "question", ["papers"], ["opinion"], 10)
            self.assertEqual(result["state"], "scoped")
            self.assertEqual(status(run)["state"], "scoped")
            scope = json.loads((run / ".monokl" / "scope.json").read_text())
            self.assertEqual(scope["budget"]["max_sources"], 10)
            self.assertTrue(scope["retrieved_content_is_untrusted"])

    def test_create_only_and_invalid_budget_fail(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            with self.assertRaises(FileExistsError):
                init_run(run)
            with self.assertRaises(ValueError):
                plan_run(run, "question", [], [], 0)


if __name__ == "__main__":
    unittest.main()
