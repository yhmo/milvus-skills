#!/usr/bin/env bash
set -euo pipefail

symbol="${1:-}"
if [[ -z "$symbol" ]]; then
  echo "Usage: $0 SYMBOL" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -d "$repo_root/pymilvus" || ! -f "$repo_root/pyproject.toml" ]]; then
  echo "Run this script from the PyMilvus repository root." >&2
  exit 1
fi

cd "$repo_root"

search() {
  local label="$1"
  shift
  echo
  echo "## $label"
  if command -v rg >/dev/null 2>&1; then
    rg -n --hidden --glob '!*.pyc' --glob '!pymilvus/grpc_gen/milvus-proto/**' "$symbol" "$@" || true
  else
    grep -RIn --exclude='*.pyc' --exclude-dir='.git' --exclude-dir='__pycache__' --exclude-dir='milvus-proto' "$symbol" "$@" || true
  fi
}

echo "Tracing symbol: $symbol"
search "Public import surface" pymilvus/__init__.py
search "MilvusClient layer" pymilvus/milvus_client
search "Low-level client/transport" pymilvus/client
search "Legacy ORM" pymilvus/orm
search "Tests" tests
search "Examples" examples
