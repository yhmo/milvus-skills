#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 SYMBOL" >&2
  echo "example: $0 Hnsw" >&2
  exit 2
fi

symbol=$1
repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -d "$repo_root/src/index" || ! -d "$repo_root/include/knowhere" ]]; then
  echo "error: run this script from the knowhere repo root" >&2
  exit 1
fi

cd "$repo_root"

search() {
  if command -v rg >/dev/null 2>&1; then
    rg -n -- "$symbol" "$@"
  elif command -v grep >/dev/null 2>&1; then
    grep -rn -- "$symbol" "$@"
  else
    echo "error: neither ripgrep (rg) nor grep is available" >&2
    return 1
  fi
}

echo "== Public headers matching '$symbol' =="
search include/knowhere || true

echo
echo "== Implementations matching '$symbol' =="
search src || true

echo
echo "== Tests and benchmarks matching '$symbol' =="
search tests benchmark || true

echo
echo "== Docs matching '$symbol' =="
search docs || true
