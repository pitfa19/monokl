#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DIST="$ROOT/dist"

if [[ -e "$DIST" || -L "$DIST" ]]; then
  echo "refusing to overwrite existing release directory: $DIST" >&2
  exit 2
fi

cd "$ROOT"
PYTHONPATH=src python3 -m pytest -q
python3 -m pip wheel . --no-deps --wheel-dir "$DIST"
(
  cd "$DIST"
  sha256sum monokl-0.1.0-*.whl > SHA256SUMS
)
echo "release artifacts: $DIST"

