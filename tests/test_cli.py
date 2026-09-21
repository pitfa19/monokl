import importlib.metadata
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

from monokl.cli import init_run, main, plan_run, retrieve_run, status
from monokl.contracts import canonical_sha256
from monokl.ledger import RunLock, resume_run, validate_run
from monokl.retrieval import Crawl4AIRetriever, RetrievalBudgets, RetrievalRequest, StdlibRetriever, browser_isolation_policy, check_public_url


class FakeResponse:
    def __init__(self, url: str, body: bytes, status: int = 200) -> None:
        self.url = url
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self.url

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class FakeOpener:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)

    def open(self, request, timeout):
        if not self.outcomes:
            raise AssertionError("unexpected request")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def public_dns(*args, **kwargs):
    return [(None, None, None, None, ("93.184.216.34", 443))]


def private_dns(*args, **kwargs):
    return [(None, None, None, None, ("127.0.0.1", 80))]


def redirect(location: str, code: int = 302) -> HTTPError:
    return HTTPError("http://example.com", code, "redirect", {"Location": location}, None)


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
            self.assertEqual(resume_run(run)["next_phase"], "retrieve")

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
            self.assertIn("transition integrity hash drift", validation.errors[0].message)

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
            self.assertIn("transition integrity hash drift", validation.errors[0].message)

    def test_concurrent_write_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            with RunLock(run / ".monokl"):
                with self.assertRaises(FileExistsError):
                    plan_run(run, "question", [], [], 2)

    def test_transition_tampering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            transition_path = run / ".monokl" / "transitions" / "000001-init.json"
            transition = json.loads(transition_path.read_text())
            transition["artifacts"] = []
            transition_path.write_text(json.dumps(transition, sort_keys=True) + "\n", encoding="utf-8")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("transition integrity hash drift", validation.errors[0].message)

    def test_orphan_artifact_blocks_resume(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            orphan = run / ".monokl" / "artifacts" / "scope.json"
            orphan.write_text("{}\n", encoding="utf-8")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("orphan_artifact", {error.code for error in validation.errors})
            self.assertEqual(resume_run(run)["reason"], "validation_failed")

    def test_stale_lock_blocks_resume_with_recovery_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            lock = run / ".monokl" / ".write-lock"
            lock.write_text("99999999", encoding="ascii")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("stale_lock", {error.code for error in validation.errors})
            self.assertIn("remove .monokl/.write-lock", validation.errors[0].message)

    def test_boolean_transition_sequence_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            transition_path = run / ".monokl" / "transitions" / "000001-init.json"
            transition = json.loads(transition_path.read_text())
            transition["sequence"] = True
            transition_path.write_text(json.dumps(transition, sort_keys=True) + "\n", encoding="utf-8")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("positive integer", validation.errors[0].message)

    def test_transition_filename_mismatch_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            transitions = run / ".monokl" / "transitions"
            (transitions / "000001-init.json").rename(transitions / "000001-renamed.json")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("filename does not match", validation.errors[0].message)

    def test_cli_validate_and_resume_commands(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            self.assertEqual(main(["init", str(run)]), 0)
            self.assertEqual(main(["validate", str(run)]), 0)
            self.assertEqual(main(["resume", str(run)]), 0)

    def test_url_policy_refuses_local_private_and_custom_schemes(self) -> None:
        budgets = RetrievalBudgets()
        for url in [
            "http://127.0.0.1",
            "http://[::1]",
            "http://10.0.0.1",
            "http://169.254.169.254",
            "file:///etc/passwd",
            "data:text/plain,hi",
            "custom://example.com",
        ]:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    check_public_url(url, budgets)
        with mock.patch("monokl.retrieval.socket.getaddrinfo", side_effect=private_dns):
            with self.assertRaises(ValueError):
                check_public_url("https://example.com", budgets)

    def test_refuses_credentials_profile_proxy_llm_js_download_cdp_and_storage(self) -> None:
        for field in ["credentials", "profile", "proxy", "llm", "javascript", "download", "cdp", "storage"]:
            with self.subTest(field=field):
                req = RetrievalRequest("https://example.com", RetrievalBudgets(), {field: True})
                with self.assertRaises(ValueError):
                    req.validate()

    def test_browser_isolation_policy_records_boundaries(self) -> None:
        policy = browser_isolation_policy(RetrievalBudgets(max_bytes_per_page=12, max_redirects=2, timeout_seconds=3))
        self.assertFalse(policy["credentials"])
        self.assertFalse(policy["persistent_profile"])
        self.assertFalse(policy["proxy"])
        self.assertFalse(policy["downloads"])
        self.assertFalse(policy["arbitrary_javascript"])
        self.assertFalse(policy["llm_api"])
        self.assertFalse(policy["cdp"])
        self.assertFalse(policy["storage_state"])
        self.assertFalse(policy["ignore_https_errors"])
        self.assertEqual(policy["cache_mode"], "BYPASS")
        self.assertTrue(policy["network"]["browser_request_interception"])
        self.assertTrue(policy["network"]["dns_checks_before_and_after_redirects"])
        self.assertEqual(policy["resources"]["child_process_limit"], 1)

    def test_retrieve_success_is_append_only_and_deterministic(self) -> None:
        body = b"<html><title>T</title><body>Hello</body></html>"
        with tempfile.TemporaryDirectory() as root, mock.patch("monokl.retrieval.socket.getaddrinfo", side_effect=public_dns), mock.patch(
            "monokl.retrieval.build_opener",
            side_effect=[
                FakeOpener([FakeResponse("https://example.com/a", body)]),
                FakeOpener([FakeResponse("https://example.com/a", body)]),
            ],
        ):
            run = Path(root) / "run"
            init_run(run)
            plan_run(run, "question", [], [], 1)
            result = retrieve_run(run, "https://example.com/a", max_bytes=100, max_redirects=3, timeout=1, allowed_host=["example.com"])
            self.assertEqual(result["state"], "retrieved")
            self.assertEqual(resume_run(run)["reason"], "next approved goal not implemented: reasoning")
            validation = validate_run(run)
            self.assertTrue(validation.valid)
            manifest = result["retrieval"]
            again = StdlibRetriever().retrieve(RetrievalRequest("https://example.com/a", RetrievalBudgets(max_bytes_per_page=100, max_redirects=3, timeout_seconds=1, allowed_hosts=("example.com",)), {}))
            self.assertEqual(manifest["cache_key"], again["cache_key"])
            self.assertEqual(manifest["normalized_url"], "https://example.com/a")
            self.assertIn("crawl4ai_config_digest", manifest)
            self.assertEqual(manifest["content_sha256"], again["content_sha256"])
            self.assertEqual(manifest["normalized_markdown_sha256"], again["normalized_markdown_sha256"])

    def test_crawl4ai_fake_boundary_records_limits_and_identity(self) -> None:
        body = "# ok"
        fake = {
            "status": "ok",
            "final_url": "https://example.com/a",
            "http_status": 200,
            "redirects": [],
            "markdown": body,
            "content_sha256": "0" * 64,
            "observed_limits": {"timeout_seconds": 1, "cpu_seconds": 3, "memory_bytes": 1, "temp_bytes": 1, "process_group": True},
        }
        with mock.patch("monokl.retrieval.importlib.metadata.version", return_value="1.2.3"), mock.patch(
            "monokl.retrieval.socket.getaddrinfo", side_effect=public_dns
        ), mock.patch("monokl.retrieval._run_crawl4ai_subprocess", return_value=fake):
            manifest = Crawl4AIRetriever("1.2.3").retrieve(
                RetrievalRequest("https://EXAMPLE.com/a#frag", RetrievalBudgets(timeout_seconds=1, allowed_hosts=("example.com",)), {})
            )
        self.assertEqual(manifest["status"], "ok")
        self.assertEqual(manifest["crawl4ai_version"], "1.2.3")
        self.assertEqual(manifest["normalized_url"], "https://example.com/a")
        self.assertTrue(manifest["observed_limits"]["process_group"])
        self.assertEqual(manifest["browser_isolation_policy"]["cache_mode"], "BYPASS")

    def test_crawl4ai_fake_boundary_refuses_browser_private_final_url(self) -> None:
        fake = {"status": "ok", "final_url": "http://127.0.0.1/private", "markdown": "x", "observed_limits": {"process_group": True}}
        def dns(host, *args, **kwargs):
            return private_dns() if host == "127.0.0.1" else public_dns()
        with mock.patch("monokl.retrieval.importlib.metadata.version", return_value="1.2.3"), mock.patch(
            "monokl.retrieval.socket.getaddrinfo", side_effect=dns
        ), mock.patch("monokl.retrieval._run_crawl4ai_subprocess", return_value=fake):
            manifest = Crawl4AIRetriever("1.2.3").retrieve(RetrievalRequest("https://example.com", RetrievalBudgets(), {}))
        self.assertEqual(manifest["status"], "error")
        self.assertIn("private_or_local_address_refused", manifest["error"]["code"])

    def test_redirect_to_private_is_refused(self) -> None:
        with mock.patch("monokl.retrieval.socket.getaddrinfo", side_effect=lambda host, *a, **k: private_dns() if host == "127.0.0.1" else public_dns()), mock.patch(
            "monokl.retrieval.build_opener", return_value=FakeOpener([redirect("http://127.0.0.1/private")])
        ):
            manifest = StdlibRetriever().retrieve(RetrievalRequest("https://example.com", RetrievalBudgets(), {}))
            self.assertEqual(manifest["status"], "error")
            self.assertIn("private_or_local_address_refused", manifest["error"]["code"])

    def test_timeout_redirect_loop_http_failure_malformed_and_oversized_are_artifacts(self) -> None:
        cases = [
            (FakeOpener([URLError("timed out")]), "timeout"),
            (FakeOpener([redirect("https://example.com")]), "redirect_loop"),
            (FakeOpener([HTTPError("https://example.com", 500, "server", {}, None)]), "http_failure"),
            (FakeOpener([FakeResponse("https://example.com", b"not html")]), "malformed_page"),
            (FakeOpener([FakeResponse("https://example.com", b"<html>" + b"a" * 20)]), "oversized_content"),
        ]
        for opener, code in cases:
            with self.subTest(code=code), mock.patch("monokl.retrieval.socket.getaddrinfo", side_effect=public_dns), mock.patch(
                "monokl.retrieval.build_opener", return_value=opener
            ):
                manifest = StdlibRetriever().retrieve(RetrievalRequest("https://example.com", RetrievalBudgets(max_bytes_per_page=10, max_redirects=1), {}))
                self.assertIn(manifest["status"], {"partial", "error"})
                self.assertEqual(manifest["error"]["code"], code)

    def test_cli_retrieve_route_and_crawl4ai_optional_without_dependency(self) -> None:
        body = b"<html><body>ok</body></html>"
        with tempfile.TemporaryDirectory() as root, mock.patch("monokl.retrieval.socket.getaddrinfo", side_effect=public_dns), mock.patch(
            "monokl.retrieval.build_opener", return_value=FakeOpener([FakeResponse("https://example.com", body)])
        ):
            run = Path(root) / "run"
            self.assertEqual(main(["init", str(run)]), 0)
            self.assertEqual(main(["plan", str(run), "question"]), 0)
            self.assertEqual(main(["retrieve", str(run), "https://example.com", "--allowed-host", "example.com"]), 0)
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "run"
            init_run(run)
            plan_run(run, "question", [], [], 1)
            self.assertEqual(main(["retrieve", str(run), "https://example.com", "--crawl4ai", "--crawl4ai-version", "0.0.invalid"]), 2)

    def test_canonical_identity_is_stable(self) -> None:
        left = {"b": 2, "a": [1, 2]}
        right = {"a": [1, 2], "b": 2}
        self.assertEqual(canonical_sha256(left), canonical_sha256(right))

    @unittest.skipUnless(bool(__import__("os").environ.get("MONOKL_LIVE_CRAWL")), "set MONOKL_LIVE_CRAWL=1 to run opt-in public crawl")
    def test_opt_in_live_public_crawl(self) -> None:
        manifest = StdlibRetriever().retrieve(RetrievalRequest("https://example.com", RetrievalBudgets(allowed_hosts=("example.com",)), {}))
        self.assertIn(manifest["status"], {"ok", "partial"})
        self.assertEqual(manifest["preflight"]["host"], "example.com")

    @unittest.skipUnless(bool(os.environ.get("MONOKL_LIVE_CRAWL4AI")), "set MONOKL_LIVE_CRAWL4AI=1 to run opt-in Crawl4AI crawl")
    def test_opt_in_installed_crawl4ai_public_crawl(self) -> None:
        try:
            version = importlib.metadata.version("crawl4ai")
        except importlib.metadata.PackageNotFoundError:
            self.skipTest("crawl4ai is not installed")
        manifest = Crawl4AIRetriever(version).retrieve(RetrievalRequest("https://example.com", RetrievalBudgets(allowed_hosts=("example.com",)), {}))
        self.assertIn(manifest["status"], {"ok", "partial", "error"})
        self.assertEqual(manifest["crawl4ai_version"], version)
        self.assertIsNotNone(manifest["observed_limits"])


if __name__ == "__main__":
    unittest.main()
