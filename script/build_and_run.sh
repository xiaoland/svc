#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
case "${1:-run}" in
  run|--verify) pdm run python -m tools.macos_app install --launch ;;
  --install) pdm run python -m tools.macos_app install ;;
  --build-only) pdm run python -m tools.macos_app build ;;
  *) echo "usage: $0 [--install|--verify|--build-only]" >&2; exit 2 ;;
esac
if [[ "${1:-run}" == --verify ]]; then
    sleep 1
    pgrep -x SVCMenuBar >/dev/null
fi
