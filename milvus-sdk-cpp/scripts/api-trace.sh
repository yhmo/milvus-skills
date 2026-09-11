#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 SYMBOL" >&2
  echo "example: $0 DescribeCollection" >&2
  exit 2
fi

symbol=$1
repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -f "$repo_root/src/include/milvus/MilvusClientV2.h" || ! -d "$repo_root/src/impl" ]]; then
  echo "error: run this script from the milvus-sdk-cpp repo root" >&2
  exit 1
fi

cd "$repo_root"

search() {
  if command -v rg >/dev/null 2>&1; then
    rg -n -- "$symbol" "$@"
  else
    grep -rn -- "$symbol" "$@"
  fi
}

echo "== Public API declarations matching '$symbol' =="
search src/include/milvus || true

echo
echo "== Implementations, helpers, and connection mappings matching '$symbol' =="
search src/impl || true

echo
echo "== Tests and examples matching '$symbol' =="
search test examples || true

echo
echo "== Generated/proto references in build tree matching '$symbol' =="
if [[ -d cmake_build/_deps/milvus_proto-build ]]; then
  search cmake_build/_deps/milvus_proto-build | head -80 || true
else
  echo "generated protobuf directory not found; configure/build the repository first"
fi
