# Shared by the scripts in this folder. Source it, don't run it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-$ROOT/.venv}"
PYTHON_VERSION="3.14"
cd "$ROOT"

need_venv() {
  if [ ! -x "$VENV/bin/python" ]; then
    echo "No virtualenv at $VENV. Run script/setup first." >&2
    exit 1
  fi
}
