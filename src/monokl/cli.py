"""Command-line setup and planning routes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .contracts import Budget, ContractError, Scope, canonical_json_bytes
from .ledger import STATE_DIR, add_retrieval, add_scope, create_run, resume_run, validate_run
from .retrieval import Crawl4AIRetriever, RetrievalBudgets, RetrievalRequest, StdlibRetriever

SCOPE_FILE = "artifacts/scope.json"


def write_json_new(path: Path, value: object) -> None:
    """Compatibility helper for create-only canonical writes."""

    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.write_bytes(canonical_json_bytes(value))


def init_run(run_dir: Path) -> dict[str, object]:
    return create_run(run_dir)


def plan_run(
    run_dir: Path,
    question: str,
    included: Sequence[str],
    excluded: Sequence[str],
    max_sources: int,
) -> dict[str, object]:
    scope = Scope(
        question=question,
        included=tuple(included),
        excluded=tuple(excluded),
        budget=Budget(max_sources=max_sources),
    )
    return add_scope(run_dir, scope)


def status(run_dir: Path) -> dict[str, object]:
    state = run_dir / STATE_DIR
    if not state.is_dir() or state.is_symlink():
        return {"schema_version": 1, "command": "status", "state": "absent"}
    validation = validate_run(run_dir)
    return {
        "schema_version": 1,
        "command": "status",
        "state": validation.state if validation.valid else "invalid",
        "valid": validation.valid,
    }


def retrieve_run(
    run_dir: Path,
    url: str,
    *,
    max_bytes: int,
    max_redirects: int,
    timeout: float,
    allowed_host: Sequence[str],
    use_crawl4ai: bool = False,
    crawl4ai_version: str | None = None,
) -> dict[str, object]:
    budgets = RetrievalBudgets(
        max_pages=1,
        max_bytes_per_page=max_bytes,
        max_redirects=max_redirects,
        timeout_seconds=timeout,
        allowed_hosts=tuple(allowed_host),
    )
    request = RetrievalRequest(url=url, budgets=budgets, config={})
    retriever = Crawl4AIRetriever(crawl4ai_version) if use_crawl4ai else StdlibRetriever()
    return add_retrieval(run_dir, retriever.retrieve(request))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="monokl")
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("run_dir", type=Path)
    plan = commands.add_parser("plan")
    plan.add_argument("run_dir", type=Path)
    plan.add_argument("question")
    plan.add_argument("--include", action="append", default=[])
    plan.add_argument("--exclude", action="append", default=[])
    plan.add_argument("--max-sources", type=int, default=30)
    show = commands.add_parser("status")
    show.add_argument("run_dir", type=Path)
    validate = commands.add_parser("validate")
    validate.add_argument("run_dir", type=Path)
    resume = commands.add_parser("resume")
    resume.add_argument("run_dir", type=Path)
    retrieve = commands.add_parser("retrieve")
    retrieve.add_argument("run_dir", type=Path)
    retrieve.add_argument("url")
    retrieve.add_argument("--max-bytes", type=int, default=2_000_000)
    retrieve.add_argument("--max-redirects", type=int, default=5)
    retrieve.add_argument("--timeout", type=float, default=15.0)
    retrieve.add_argument("--allowed-host", action="append", default=[])
    retrieve.add_argument("--crawl4ai", action="store_true")
    retrieve.add_argument("--crawl4ai-version")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            result = init_run(args.run_dir)
        elif args.command == "plan":
            result = plan_run(args.run_dir, args.question, args.include, args.exclude, args.max_sources)
        elif args.command == "validate":
            result = validate_run(args.run_dir).to_dict()
        elif args.command == "resume":
            result = resume_run(args.run_dir)
        elif args.command == "retrieve":
            result = retrieve_run(
                args.run_dir,
                args.url,
                max_bytes=args.max_bytes,
                max_redirects=args.max_redirects,
                timeout=args.timeout,
                allowed_host=args.allowed_host,
                use_crawl4ai=args.crawl4ai,
                crawl4ai_version=args.crawl4ai_version,
            )
        else:
            result = status(args.run_dir)
    except (ContractError, FileExistsError, OSError, RuntimeError, ValueError) as error:
        print(json.dumps({"schema_version": 1, "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
