"""Command-line setup and planning routes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .contracts import Budget, Scope

STATE_DIR = ".monokl"
SCOPE_FILE = "scope.json"


def write_json_new(path: Path, value: object) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def init_run(run_dir: Path) -> dict[str, object]:
    if run_dir.exists() or run_dir.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing run directory: {run_dir}")
    run_dir.mkdir(parents=False)
    state = run_dir / STATE_DIR
    state.mkdir()
    receipt = {"schema_version": 1, "command": "init", "state": "initialized"}
    write_json_new(state / "run.json", receipt)
    return receipt


def plan_run(
    run_dir: Path,
    question: str,
    included: Sequence[str],
    excluded: Sequence[str],
    max_sources: int,
) -> dict[str, object]:
    state = run_dir / STATE_DIR
    if not state.is_dir() or state.is_symlink():
        raise ValueError("run is not initialized")
    scope = Scope(
        question=question,
        included=tuple(included),
        excluded=tuple(excluded),
        budget=Budget(max_sources=max_sources),
    )
    payload = scope.to_dict()
    write_json_new(state / SCOPE_FILE, payload)
    return {"schema_version": 1, "command": "plan", "state": "scoped", "scope": payload}


def status(run_dir: Path) -> dict[str, object]:
    state = run_dir / STATE_DIR
    if not state.is_dir() or state.is_symlink():
        return {"schema_version": 1, "command": "status", "state": "absent"}
    return {
        "schema_version": 1,
        "command": "status",
        "state": "scoped" if (state / SCOPE_FILE).is_file() else "initialized",
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
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            result = init_run(args.run_dir)
        elif args.command == "plan":
            result = plan_run(args.run_dir, args.question, args.include, args.exclude, args.max_sources)
        else:
            result = status(args.run_dir)
    except (FileExistsError, OSError, ValueError) as error:
        print(json.dumps({"schema_version": 1, "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
