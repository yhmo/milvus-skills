#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 SYMBOL" >&2
  echo "example: $0 search" >&2
  echo "example: $0 handleSearch" >&2
  echo "example: $0 SearchAction" >&2
  exit 2
fi

symbol=$1
repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
hsdir="internal/distributed/proxy/httpserver"
if [[ -z "$repo_root" || ! -d "$repo_root/$hsdir" ]]; then
  echo "error: run this script from the milvus repo root (missing $hsdir)" >&2
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

echo "== Route/action constants matching '$symbol' =="
search_file "$symbol" "$hsdir/constant.go"

echo
echo "== Route registration (handler_v2.go / handler_v1.go / handler.go) =="
search_dir "$symbol" "$hsdir/handler_v2.go"
search_dir "$symbol" "$hsdir/handler_v1.go"
search_dir "$symbol" "$hsdir/handler.go"

echo
echo "== routeToMethod metric mapping =="
search_file "$symbol" "$hsdir/handler_v2.go"

echo
echo "== Request types matching '$symbol' =="
search_dir "$symbol" "$hsdir/request.go"
search_dir "$symbol" "$hsdir/request_v2.go"
search_dir "$symbol" "$hsdir/wrap_request.go"

echo
echo "== Handler implementations matching '$symbol' =="
search_dir "$symbol" "$hsdir/handler_v2.go"
search_dir "$symbol" "$hsdir/handler_v1.go"
search_dir "$symbol" "$hsdir/resource_group_handler_v2.go"
search_dir "$symbol" "$hsdir/file_resource_handler_v2.go"
search_dir "$symbol" "$hsdir/snapshot_handler_v2.go"

echo
echo "== Conversion/result helpers matching '$symbol' =="
search_dir "$symbol" "$hsdir/utils.go"

echo
echo "== Proxy RPC call sites matching '$symbol' (h.proxy.<Method>) =="
search_dir "proxy\.$symbol\b" "$hsdir"

echo
echo "== Tests matching '$symbol' =="
if command -v rg >/dev/null 2>&1; then
  rg -n "$symbol" "$hsdir" -g '*_test.go' || true
else
  grep -RInE "$symbol" "$hsdir" --include='*_test.go' || true
fi
