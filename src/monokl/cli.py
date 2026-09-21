"""Command-line setup and planning routes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .contracts import Budget, ContractError, Scope, canonical_json_bytes
from .ledger import STATE_DIR, add_scope, create_run, resume_run, validate_run

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
        else:
            result = status(args.run_dir)
    except (ContractError, FileExistsError, OSError, ValueError) as error:
        print(json.dumps({"schema_version": 1, "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
