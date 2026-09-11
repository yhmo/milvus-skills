#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 SYMBOL" >&2
  echo "example: $0 SegmentWriter" >&2
  exit 2
fi

symbol=$1
repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -d "$repo_root/cpp/src/ffi" || ! -d "$repo_root/cpp/include/milvus-storage" ]]; then
  echo "error: run this script from the milvus-storage repo root" >&2
  exit 1
fi

cd "$repo_root"

if command -v rg >/dev/null 2>&1; then
  search() { rg -n -- "$symbol" "$@"; }
else
  search() { grep -rn -- "$symbol" "$@"; }
fi

echo "== C++ public headers matching '$symbol' =="
search cpp/include || true

echo
echo "== C++ implementation (core, FFI, JNI) matching '$symbol' =="
search cpp/src || true

echo
echo "== C++ tests and tools matching '$symbol' =="
search cpp/test cpp/tools || true

echo
echo "== Language bindings matching '$symbol' =="
search python/milvus_storage java/src rust/src || true

echo
echo "== Python integration/stress tests and docs matching '$symbol' =="
search tests docs || true
