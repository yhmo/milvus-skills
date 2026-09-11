#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 SYMBOL" >&2
  echo "example: $0 search" >&2
  echo "example: $0 createCollection" >&2
  exit 2
fi

symbol=$1
repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -d "$repo_root/milvus" || ! -f "$repo_root/milvus/MilvusClient.ts" ]]; then
  echo "error: run this script from the milvus-sdk-node repo root" >&2
  exit 1
fi

cd "$repo_root"

search_file() {
  local pattern="$1"
  local file="$2"
  if command -v rg >/dev/null 2>&1; then
    rg -n "$pattern" "$file" || true
  else
    grep -nE "$pattern" "$file" || true
  fi
}

search_dir() {
  local pattern="$1"
  local dir="$2"
  if command -v rg >/dev/null 2>&1; then
    rg -n "$pattern" "$dir" || true
  else
    grep -RInE "$pattern" "$dir" || true
  fi
}

echo "== Public client declarations matching '$symbol' =="
search_file "$symbol" milvus/MilvusClient.ts
search_dir "$symbol" milvus/grpc
search_dir "$symbol" milvus/http

echo
echo "== Types matching '$symbol' =="
search_dir "$symbol" milvus/types

echo
echo "== Utils/conversion matching '$symbol' =="
search_dir "$symbol" milvus/utils

echo
echo "== Telemetry/bulkwriter matching '$symbol' =="
search_dir "$symbol" milvus/telemetry
search_dir "$symbol" milvus/bulkwriter

echo
echo "== Tests and examples matching '$symbol' =="
search_dir "$symbol" test
search_dir "$symbol" examples
