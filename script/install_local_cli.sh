#!/bin/bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
revision="$(git -C "$root" rev-parse --verify HEAD)"
data="${XDG_DATA_HOME:-$HOME/.local/share}/svc/dogfood"
artifacts="$data/wheels/$revision"
mkdir -p "$artifacts"

wheels=("$artifacts"/*.whl)
if [[ ! -f "${wheels[0]}" ]]; then
  build="$(mktemp -d "$artifacts/build.XXXXXX")"
  trap 'rm -rf -- "$build"' EXIT
  git -C "$root" archive "$revision" cli | tar -xf - -C "$build"
  SOURCE_DATE_EPOCH="$(git -C "$root" show -s --format=%ct "$revision")" \
    pdm build -p "$build/cli" --no-sdist --dest "$build/wheel"
  wheels=("$build/wheel/"*.whl)
  if [[ ${#wheels[@]} != 1 || ! -f "${wheels[0]}" ]]; then
    printf '%s\n' '预期从 HEAD 构建恰好一个 CLI wheel。' >&2
    exit 1
  fi
  mv -- "${wheels[0]}" "$artifacts/"
  wheels=("$artifacts"/*.whl)
fi

if [[ ${#wheels[@]} != 1 ]]; then
  printf '预期 %s 内恰好有一个 CLI wheel。\n' "$artifacts" >&2
  exit 1
fi

UV_TOOL_DIR="$data/tools" UV_TOOL_BIN_DIR="$data/bin" \
  uv tool install --force "$@" "${wheels[0]}"
"$data/bin/svc" --version
printf '源码提交 %s\nCLI 路径 %s/bin/svc\n' "$revision" "$data"
