import importlib.metadata
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

from monokl.cli import init_run, main, plan_run, retrieve_run, status
from monokl.contracts import canonical_sha256, evidence_synthesis_contract, group_approval_contract, sha256_hex, source_groups_contract, source_inventory_contract
from monokl.ledger import RunLock, approve_source_groups, create_evidence_synthesis, create_reasoning_task, create_source_groups, create_source_inventory, resume_run, submit_reasoning_result, validate_run
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
            "https://user:secret@example.com/private",
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
            self.assertEqual(resume_run(run)["next_phase"], "reasoning-task")
            validation = validate_run(run)
            self.assertTrue(validation.valid)
            manifest = result["retrieval"]
            again = StdlibRetriever().retrieve(RetrievalRequest("https://example.com/a", RetrievalBudgets(max_bytes_per_page=100, max_redirects=3, timeout_seconds=1, allowed_hosts=("example.com",)), {}))
            self.assertEqual(manifest["cache_key"], again["cache_key"])
            self.assertEqual(manifest["normalized_url"], "https://example.com/a")
            self.assertIn("crawl4ai_config_digest", manifest)
            self.assertEqual(manifest["content_sha256"], again["content_sha256"])
            self.assertEqual(manifest["normalized_markdown_sha256"], again["normalized_markdown_sha256"])


    def _retrieved_run(self, root: str) -> Path:
        run = Path(root) / "run"
        init_run(run)
        plan_run(run, "question", [], [], 1)
        body = b"<html><body>Observation source</body></html>"
        with mock.patch("monokl.retrieval.socket.getaddrinfo", side_effect=public_dns), mock.patch(
            "monokl.retrieval.build_opener", return_value=FakeOpener([FakeResponse("https://example.com/a", body)])
        ):
            retrieve_run(run, "https://example.com/a", max_bytes=100, max_redirects=3, timeout=1, allowed_host=["example.com"])
        return run

    def _valid_reasoning_result(self, task: dict) -> dict:
        locator = {
            "artifact_id": task["source_artifacts"][0]["id"],
            "artifact_path": task["source_artifacts"][0]["path"],
            "artifact_contract": task["source_artifacts"][0]["contract"],
            "artifact_sha256": task["source_artifacts"][0]["sha256"],
            "locator": "normalized_markdown_sha256",
        }
        def item(item_id: str, text: str) -> dict:
            return {"id": item_id, "text": text, "source_locators": [locator]}
        return {
            "schema_version": 1,
            "contract": "monokl.reasoning_result",
            "protocol": "monokl.reasoning_result.v2",
            "task_id": task["task_id"],
            "task_sha256": task["task_sha256"],
            "observations": [item("obs-1", "Pinned retrieval contains a source document.")],
            "inferences": [item("inf-1", "The source is relevant enough for a draft finding.")],
            "uncertainties": [item("unc-1", "No independent corroboration has been performed.")],
            "provider_metadata": {"provenance_only": True, "provider": "fixture", "model": "none"},
            "authority": "proposal_only",
        }

    def test_reasoning_task_and_result_normal_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = self._retrieved_run(root)
            task_result = create_reasoning_task(run)
            task = task_result["task"]
            self.assertEqual(resume_run(run)["next_phase"], "reasoning-result")
            self.assertEqual(task["protocol"], "monokl.reasoning_task.v2")
            self.assertEqual(task["task_type"], "source_grounded_reasoning")
            self.assertIn("cannot authorize actions", task["instructions"]["untrusted_content_boundary"])
            self.assertIn("no provider-specific adapter", " ".join(task["instructions"]["execution"]))
            self.assertEqual(task["instructions"]["result_item_schema"]["required_fields"], ["id", "text", "source_locators"])
            self.assertEqual(task["source_artifacts"][0]["path"], "artifacts/retrieval.json")
            result = submit_reasoning_result(run, self._valid_reasoning_result(task))
            self.assertEqual(result["state"], "reasoned")
            self.assertEqual(resume_run(run)["next_phase"], "source-inventory")
            self.assertTrue(validate_run(run).valid)

    def test_reasoning_result_wrong_hash_unknown_fields_and_malformed_output_fail(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = self._retrieved_run(root)
            task = create_reasoning_task(run)["task"]
            bad_hash = self._valid_reasoning_result(task)
            bad_hash["task_sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                submit_reasoning_result(run, bad_hash)
            unknown = self._valid_reasoning_result(task)
            unknown["extra"] = True
            with self.assertRaises(ValueError):
                submit_reasoning_result(run, unknown)
            malformed = self._valid_reasoning_result(task)
            malformed["observations"] = "not a list"
            with self.assertRaises(ValueError):
                submit_reasoning_result(run, malformed)
            missing_locator = self._valid_reasoning_result(task)
            missing_locator["observations"][0]["source_locators"] = []
            with self.assertRaises(ValueError):
                submit_reasoning_result(run, missing_locator)
            forged_locator = self._valid_reasoning_result(task)
            forged_locator["observations"][0]["source_locators"][0]["artifact_path"] = "artifacts/forged.json"
            with self.assertRaises(ValueError):
                submit_reasoning_result(run, forged_locator)

    def test_reasoning_task_forged_source_relation_fails_even_with_recomputed_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = self._retrieved_run(root)
            create_reasoning_task(run)
            state = run / ".monokl"
            task_path = state / "artifacts" / "reasoning-task.json"
            task = json.loads(task_path.read_text())
            task["source_artifacts"][0]["path"] = "artifacts/scope.json"
            task["source_artifacts"][0]["contract"] = "monokl.scope"
            task["source_artifacts"][0]["sha256"] = sha256_hex((state / "artifacts" / "scope.json").read_bytes())
            unsigned_task = {key: value for key, value in task.items() if key != "task_sha256"}
            task["task_sha256"] = canonical_sha256(unsigned_task)
            task_path.write_text(json.dumps(task, sort_keys=True) + "\n", encoding="utf-8")
            transition_path = state / "transitions" / "000004-reasoning-task.json"
            transition = json.loads(transition_path.read_text())
            transition["artifacts"][0]["sha256"] = sha256_hex(task_path.read_bytes())
            unsigned_transition = {key: value for key, value in transition.items() if key != "sha256"}
            transition["sha256"] = canonical_sha256(unsigned_transition)
            transition_path.write_text(json.dumps(transition, sort_keys=True) + "\n", encoding="utf-8")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("exactly match the retrieval artifact", validation.errors[0].message)

    def test_reasoning_create_only_and_provider_metadata_is_provenance_only(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = self._retrieved_run(root)
            task = create_reasoning_task(run)["task"]
            with self.assertRaises(FileExistsError):
                create_reasoning_task(run)
            not_provenance = self._valid_reasoning_result(task)
            not_provenance["provider_metadata"] = {"provenance_only": False, "provider": "fixture"}
            with self.assertRaises(ValueError):
                submit_reasoning_result(run, not_provenance)
            submit_reasoning_result(run, self._valid_reasoning_result(task))
            with self.assertRaises(FileExistsError):
                submit_reasoning_result(run, self._valid_reasoning_result(task))

    def test_reasoning_task_source_hash_drift_and_partial_artifact_block_resume(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = self._retrieved_run(root)
            create_reasoning_task(run)
            retrieval_path = run / ".monokl" / "artifacts" / "retrieval.json"
            retrieval = json.loads(retrieval_path.read_text())
            retrieval["status"] = "partial"
            retrieval_path.write_text(json.dumps(retrieval, sort_keys=True) + "\n", encoding="utf-8")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("hash drift", validation.errors[0].message)
            self.assertEqual(resume_run(run)["reason"], "validation_failed")
        with tempfile.TemporaryDirectory() as root:
            run = self._retrieved_run(root)
            create_reasoning_task(run)
            result_path = run / ".monokl" / "artifacts" / "reasoning-result.json"
            result_path.write_text('{"schema_version":', encoding="utf-8")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("orphan_artifact", {error.code for error in validation.errors})

    def test_cli_reasoning_task_and_result_commands(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = self._retrieved_run(root)
            self.assertEqual(main(["reasoning-task", str(run)]), 0)
            task = json.loads((run / ".monokl" / "artifacts" / "reasoning-task.json").read_text())
            self.assertEqual(task["task_type"], "source_grounded_reasoning")
            result_path = Path(root) / "result.json"
            result_path.write_text(json.dumps(self._valid_reasoning_result(task)), encoding="utf-8")
            self.assertEqual(main(["reasoning-result", str(run), str(result_path)]), 0)
            self.assertTrue(validate_run(run).valid)

    def _reasoned_run(self, root: str) -> Path:
        run = self._retrieved_run(root)
        task = create_reasoning_task(run)["task"]
        submit_reasoning_result(run, self._valid_reasoning_result(task))
        return run

    def _inventory_payload(self, run: Path, *, duplicate: bool = False) -> dict:
        retrieval = run / ".monokl" / "artifacts" / "retrieval.json"
        ref = {"artifact_id": "retrieval", "artifact_path": "artifacts/retrieval.json", "artifact_contract": "monokl.retrieval_snapshot", "artifact_sha256": sha256_hex(retrieval.read_bytes())}
        sources = [{"source_id": "source-1", **ref, "status": "retained", "rationale": "canonical retained source"}]
        duplicates = []
        if duplicate:
            sources.append({"source_id": "source-2", **ref, "status": "duplicate", "rationale": "same canonical URL and content hash"})
            duplicates.append({"source_id": "source-2", "duplicate_of": "source-1", "rationale": "deterministic duplicate of retained source-1"})
        return source_inventory_contract(sources=sources, duplicates=duplicates)

    def _groups_payload(self, inventory: dict, *, source_ids=None, excluded=None, allow_overlap=False) -> dict:
        source_ids = source_ids if source_ids is not None else ["source-1"]
        excluded = excluded if excluded is not None else []
        return source_groups_contract(
            inventory_sha256=inventory["inventory_sha256"],
            groups=[{"group_id": "group-1", "title": "Group 1", "source_ids": source_ids, "rationale": "review grouping"}],
            excluded_source_ids=excluded,
            allow_overlap=allow_overlap,
        )

    def test_inventory_grouping_approval_public_cli_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = self._reasoned_run(root)
            self.assertEqual(resume_run(run)["next_phase"], "source-inventory")
            self.assertEqual(main(["source-inventory", str(run)]), 0)
            inventory = json.loads((run / ".monokl" / "artifacts" / "source-inventory.json").read_text())
            groups = self._groups_payload(inventory)
            groups_path = Path(root) / "groups.json"
            groups_path.write_text(json.dumps(groups), encoding="utf-8")
            self.assertEqual(main(["source-groups", str(run), str(groups_path)]), 0)
            self.assertEqual(resume_run(run)["next_phase"], "source-group-approval")
            approval = group_approval_contract(owner="pitfa", inventory_sha256=inventory["inventory_sha256"], groups_sha256=groups["groups_sha256"], decision=True, rationale="owner approves exact inventory and groups hashes")
            approval_path = Path(root) / "approval.json"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            self.assertEqual(main(["source-group-approval", str(run), str(approval_path)]), 0)
            self.assertEqual(validate_run(run).state, "groups-approved")
            self.assertEqual(resume_run(run)["next_phase"], "evidence-synthesis")

    def test_inventory_duplicates_omissions_unknown_overlap_and_approval_pins_fail(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = self._reasoned_run(root)
            missing_rationale = self._inventory_payload(run, duplicate=True)
            missing_rationale["duplicates"] = []
            missing_rationale["inventory_sha256"] = canonical_sha256({k: v for k, v in missing_rationale.items() if k != "inventory_sha256"})
            with self.assertRaises(ValueError):
                create_source_inventory(run, missing_rationale)
            inventory = create_source_inventory(run, self._inventory_payload(run, duplicate=True))["inventory"]
            with self.assertRaises(ValueError):
                create_source_groups(run, self._groups_payload(inventory, source_ids=["source-unknown"]))
            with self.assertRaises(ValueError):
                create_source_groups(run, self._groups_payload(inventory, source_ids=[]))
            overlapping = source_groups_contract(
                inventory_sha256=inventory["inventory_sha256"],
                groups=[
                    {"group_id": "group-1", "title": "A", "source_ids": ["source-1"], "rationale": "first"},
                    {"group_id": "group-2", "title": "B", "source_ids": ["source-1"], "rationale": "second"},
                ],
                excluded_source_ids=[],
                allow_overlap=False,
            )
            with self.assertRaises(ValueError):
                create_source_groups(run, overlapping)
            groups = create_source_groups(run, self._groups_payload(inventory))["groups"]
            wrong = group_approval_contract(owner="pitfa", inventory_sha256="0" * 64, groups_sha256=groups["groups_sha256"], decision=True, rationale="wrong inventory pin")
            with self.assertRaises(ValueError):
                approve_source_groups(run, wrong)
            implicit = group_approval_contract(owner="pitfa", inventory_sha256=inventory["inventory_sha256"], groups_sha256=groups["groups_sha256"], decision=False, rationale="not approved")
            with self.assertRaises(ValueError):
                approve_source_groups(run, implicit)
            wrong_groups = group_approval_contract(owner="pitfa", inventory_sha256=inventory["inventory_sha256"], groups_sha256="0" * 64, decision=True, rationale="wrong groups pin")
            with self.assertRaises(ValueError):
                approve_source_groups(run, wrong_groups)

    def test_inventory_hash_drift_overwrite_and_partial_files_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = self._reasoned_run(root)
            inventory = create_source_inventory(run)["inventory"]
            with self.assertRaises(FileExistsError):
                create_source_inventory(run)
            path = run / ".monokl" / "artifacts" / "source-inventory.json"
            tampered = json.loads(path.read_text())
            tampered["sources"][0]["rationale"] = "changed"
            path.write_text(json.dumps(tampered, sort_keys=True) + "\n", encoding="utf-8")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("hash drift", validation.errors[0].message)
        with tempfile.TemporaryDirectory() as root:
            run = self._reasoned_run(root)
            create_source_inventory(run)
            partial = run / ".monokl" / "artifacts" / "source-groups.json"
            partial.write_text('{"schema_version":', encoding="utf-8")
            validation = validate_run(run)
            self.assertFalse(validation.valid)
            self.assertIn("orphan_artifact", {error.code for error in validation.errors})

    def _approved_groups_run(self, root: str) -> Path:
        run = self._reasoned_run(root)
        inventory = create_source_inventory(run)["inventory"]
        groups = create_source_groups(run, self._groups_payload(inventory))["groups"]
        approval = group_approval_contract(owner="pitfa", inventory_sha256=inventory["inventory_sha256"], groups_sha256=groups["groups_sha256"], decision=True, rationale="approve exact group set")
        approve_source_groups(run, approval)
        return run

    def _synthesis_payload(self, run: Path) -> dict:
        state = run / ".monokl"
        inventory = json.loads((state / "artifacts" / "source-inventory.json").read_text())
        groups = json.loads((state / "artifacts" / "source-groups.json").read_text())
        approval = json.loads((state / "artifacts" / "source-group-approval.json").read_text())
        retrieval_sha = sha256_hex((state / "artifacts" / "retrieval.json").read_bytes())
        locator = {"source_id": "source-1", "artifact_id": "retrieval", "artifact_path": "artifacts/retrieval.json", "artifact_contract": "monokl.retrieval_snapshot", "artifact_sha256": retrieval_sha, "locator": "normalized_markdown_sha256"}
        return evidence_synthesis_contract(
            inventory_sha256=inventory["inventory_sha256"],
            groups_sha256=groups["groups_sha256"],
            approval_sha256=approval["approval_sha256"],
            reasoning_sha256=sha256_hex((state / "artifacts" / "reasoning-result.json").read_bytes()),
            claims=[{"claim_id": "claim-1", "group_id": "group-1", "source_ids": ["source-1"], "label": "verified_observation", "text": "The source directly records retrieved content.", "locators": [locator]}, {"claim_id": "claim-2", "group_id": "group-1", "source_ids": ["source-1"], "label": "inference", "text": "The source can support a cautious synthesized summary.", "locators": [locator]}],
            per_group_synthesis=[{"group_id": "group-1", "summary": "Group 1 has one verified observation and one explicitly labeled inference.", "claim_ids": ["claim-1", "claim-2"], "limitations": ["single source"]}],
            contradictions=[{"group_id": "group-1", "claim_ids": ["claim-1", "claim-2"], "description": "No contradiction in fixture; entry documents contradiction tracking."}],
            gaps=[{"group_id": "group-1", "description": "No independent corroboration source.", "impact": "medium"}],
            unsupported_claims=[{"claim_id": "unsupported-1", "group_id": "group-1", "text": "A deliberately unsupported claim is tracked, not synthesized.", "reason": "no resolving locator"}],
        )

    def test_evidence_synthesis_cli_resume_and_audit_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            run = self._approved_groups_run(root)
            self.assertEqual(resume_run(run)["next_phase"], "evidence-synthesis")
            payload = self._synthesis_payload(run)
            path = Path(root) / "synthesis.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(main(["evidence-synthesis", str(run), str(path)]), 0)
            self.assertEqual(validate_run(run).state, "synthesized")
            audit = json.loads((run / ".monokl" / "artifacts" / "evidence-audit.json").read_text())
            self.assertEqual(audit["status"], "passed")
            self.assertEqual(resume_run(run)["reason"], "next approved goal not implemented: export-integration")

    def test_evidence_synthesis_adversarial_inputs_fail_closed(self) -> None:
        cases = {
            "nonexistent locator": lambda p: p["claims"][0]["locators"][0].update({"artifact_path": "artifacts/missing.json"}),
            "unknown source": lambda p: p["claims"][0]["locators"][0].update({"source_id": "source-unknown"}),
            "missing group": lambda p: p["per_group_synthesis"].clear(),
            "unsupported claims malformed": lambda p: p["unsupported_claims"][0].pop("reason"),
            "contradictory evidence malformed": lambda p: p["contradictions"][0].update({"claim_ids": ["missing-claim"]}),
            "wrong pins": lambda p: p["pinned_inputs"].update({"groups_sha256": "0" * 64}),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as root:
                run = self._approved_groups_run(root)
                payload = self._synthesis_payload(run)
                mutate(payload)
                payload["synthesis_sha256"] = canonical_sha256({k: v for k, v in payload.items() if k != "synthesis_sha256"})
                with self.assertRaises(ValueError):
                    create_evidence_synthesis(run, payload)
        with tempfile.TemporaryDirectory() as root:
            run = self._approved_groups_run(root)
            create_evidence_synthesis(run, self._synthesis_payload(run))
            with self.assertRaises(FileExistsError):
                create_evidence_synthesis(run, self._synthesis_payload(run))
            (run / ".monokl" / "artifacts" / "evidence-synthesis.json").write_text('{"schema_version":', encoding="utf-8")
            self.assertFalse(validate_run(run).valid)

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
        self.assertEqual(manifest["content_sha256"], sha256_hex(body.encode("utf-8")))
        self.assertNotEqual(manifest["content_sha256"], fake["content_sha256"])
        self.assertTrue(manifest["observed_limits"]["process_group"])
        self.assertEqual(manifest["browser_isolation_policy"]["cache_mode"], "BYPASS")

    def test_crawl4ai_subprocess_env_exposes_only_explicit_browser_path(self) -> None:
        request = RetrievalRequest("https://example.com", RetrievalBudgets(timeout_seconds=1), {})
        captured = {}
        captured_command = []

        class FakeProcess:
            pid = 999999
            returncode = 0

            def communicate(self, payload, timeout):
                return ('{"status":"error","error":{"code":"fixture","message":"fixture"}}', "")

        def fake_popen(*args, **kwargs):
            captured_command.extend(args[0])
            captured.update(kwargs["env"])
            return FakeProcess()

        with mock.patch.dict(os.environ, {"PLAYWRIGHT_BROWSERS_PATH": "/safe/browsers", "OPENAI_API_KEY": "secret", "HTTPS_PROXY": "secret"}), mock.patch(
            "monokl.retrieval.subprocess.Popen", side_effect=fake_popen
        ):
            from monokl.retrieval import _run_crawl4ai_subprocess

            _run_crawl4ai_subprocess(request, "0.9.3")
        self.assertEqual(captured["PLAYWRIGHT_BROWSERS_PATH"], "/safe/browsers")
        self.assertNotIn("OPENAI_API_KEY", captured)
        self.assertNotIn("HTTPS_PROXY", captured)
        self.assertIn("MemoryMax=4294967296", captured_command)
        self.assertIn("TasksMax=256", captured_command)
        self.assertIn("CPUQuota=100%", captured_command)
        self.assertIn("RuntimeMaxSec=3.0s", captured_command)
        self.assertIn("LimitFSIZE=67108864", captured_command)
        self.assertIn("LimitNOFILE=128", captured_command)
        self.assertIn("KillMode=control-group", captured_command)
        self.assertIn("-i", captured_command)
        self.assertFalse(any("OPENAI_API_KEY" in value or "HTTPS_PROXY" in value for value in captured_command))

    def test_crawl4ai_subprocess_fails_closed_without_cgroup_runner(self) -> None:
        request = RetrievalRequest("https://example.com", RetrievalBudgets(timeout_seconds=1), {})
        with mock.patch("monokl.retrieval.shutil.which", return_value=None):
            from monokl.retrieval import _run_crawl4ai_subprocess

            result = _run_crawl4ai_subprocess(request, "0.9.3")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "isolation_unavailable")
        self.assertEqual(result["observed_limits"]["memory_limit_mechanism"], "systemd-user-cgroup-v2")

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
        self.assertIn(manifest["status"], {"ok", "partial"})
        self.assertEqual(manifest["crawl4ai_version"], version)
        self.assertIsNotNone(manifest["observed_limits"])


if __name__ == "__main__":
    unittest.main()
