#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT=${MONOKL_INSTALL_ROOT:-"$HOME/.local/share/monokl"}
BIN_DIR=${MONOKL_BIN_DIR:-"$HOME/.local/bin"}
COMMAND="$BIN_DIR/monokl"
EXPECTED="$INSTALL_ROOT/venv/bin/monokl"

if [[ ! -f "$INSTALL_ROOT/install.json" ]]; then
  echo "refusing to remove unrecognized install root: $INSTALL_ROOT" >&2
  exit 2
fi
if [[ ! -L "$COMMAND" || "$(readlink "$COMMAND")" != "$EXPECTED" ]]; then
  echo "refusing to remove unexpected command: $COMMAND" >&2
  exit 2
fi

rm "$COMMAND"
rm -rf "$INSTALL_ROOT"
echo "removed Monokl from $INSTALL_ROOT"

