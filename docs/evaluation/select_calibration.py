#!/usr/bin/env python3
"""Select the pre-registered Monokl DRB calibration task."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SEED = "monokl-drb-calibration-v1"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: select_calibration.py QUERY_JSONL", file=sys.stderr)
        return 2

    query_path = Path(sys.argv[1])
    rows = [json.loads(line) for line in query_path.read_text().splitlines() if line.strip()]
    eligible = [row for row in rows if row.get("language") == "en"]
    if not eligible:
        print("no English tasks found", file=sys.stderr)
        return 1

    selected = min(
        eligible,
        key=lambda row: hashlib.sha256(f"{SEED}:{row['id']}".encode()).hexdigest(),
    )
    result = {
        "schema_version": 1,
        "seed": SEED,
        "eligible_rule": "language == en",
        "eligible_count": len(eligible),
        "selected_id": selected["id"],
        "selected_topic": selected["topic"],
        "selected_prompt": selected["prompt"],
        "selection_hash": hashlib.sha256(f"{SEED}:{selected['id']}".encode()).hexdigest(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
