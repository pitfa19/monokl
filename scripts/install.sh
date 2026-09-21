#!/usr/bin/env bash
set -euo pipefail

SOURCE=${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
INSTALL_ROOT=${MONOKL_INSTALL_ROOT:-"$HOME/.local/share/monokl"}
BIN_DIR=${MONOKL_BIN_DIR:-"$HOME/.local/bin"}
VENV="$INSTALL_ROOT/venv"
BROWSERS="$INSTALL_ROOT/browsers"
COMMAND="$BIN_DIR/monokl"

if [[ -e "$INSTALL_ROOT" || -L "$INSTALL_ROOT" ]]; then
  echo "refusing to overwrite existing install root: $INSTALL_ROOT" >&2
  exit 2
fi
if [[ -e "$COMMAND" || -L "$COMMAND" ]]; then
  echo "refusing to overwrite existing command: $COMMAND" >&2
  exit 2
fi

installed=0
cleanup() {
  if [[ "$installed" -ne 1 && -d "$INSTALL_ROOT" ]]; then
    rm -rf "$INSTALL_ROOT"
  fi
}
trap cleanup EXIT

mkdir -p "$INSTALL_ROOT" "$BIN_DIR"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install "${SOURCE}[crawl]"
PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" "$VENV/bin/playwright" install chromium
ln -s "$VENV/bin/monokl" "$COMMAND"

cat > "$INSTALL_ROOT/install.json" <<EOF
{"schema_version":1,"source":"$SOURCE","venv":"$VENV","browsers":"$BROWSERS","command":"$COMMAND"}
EOF

installed=1
echo "installed: $COMMAND"
echo "browser path: $BROWSERS"
