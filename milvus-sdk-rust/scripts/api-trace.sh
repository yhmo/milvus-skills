#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 SYMBOL" >&2
  echo "example: $0 search" >&2
  exit 2
fi

symbol=$1

if [[ ! -f Cargo.toml || ! -d src/v1 || ! -d src/v2 ]]; then
  echo "error: run this script from the milvus-sdk-rust repo root" >&2
  exit 1
fi

search() {
  local pattern=$1
  shift
  if command -v rg >/dev/null 2>&1; then
    rg -n "$pattern" "$@" 2>/dev/null || true
  else
    grep -RInE "$pattern" "$@" 2>/dev/null || true
  fi
}

echo "== V2 public/API definitions matching '$symbol' =="
search "pub .*${symbol}|fn .*${symbol}|struct .*${symbol}|enum .*${symbol}" src/v2 tests/v2 examples/v2

echo
echo "== V2 call sites matching '$symbol' =="
search "$symbol" src/v2 tests/v2 examples/v2

echo
echo "== V1 compatibility surface matching '$symbol' =="
search "pub .*${symbol}|fn .*${symbol}|struct .*${symbol}|enum .*${symbol}|${symbol}" src/v1 tests/v1 examples/v1 src/lib.rs

echo
echo "== Generated protobuf matches in Cargo OUT_DIR =="
generated=()
while IFS= read -r path; do
  generated+=("$path")
done < <(find target -path '*/build/milvus-sdk-rust-*/out/milvus.proto.*.rs' -type f 2>/dev/null | sort -u)

if [[ ${#generated[@]} -eq 0 ]]; then
  echo "no generated bindings found; run cargo check first"
else
  search "${symbol}|/${symbol}" "${generated[@]}"
fi
