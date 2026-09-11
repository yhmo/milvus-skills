#!/usr/bin/env bash
set -euo pipefail

symbol="${1:-}"
if [[ -z "$symbol" ]]; then
  echo "Usage: $0 SYMBOL" >&2
  echo "Example: $0 Search" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -f "$repo_root/client/go.mod" ]]; then
  echo "Run this script from the milvus repository root." >&2
  exit 1
fi

cd "$repo_root"
sdk="$repo_root/client"

search() {
  local label="$1"
  shift
  echo
  echo "## $label"
  if command -v rg >/dev/null 2>&1; then
    rg -n --hidden --glob '!**/*_test.go' "$symbol" "$@" || true
  else
    # strip rg-only --glob args for the grep fallback
    local args=()
    for arg in "$@"; do
      [[ "$arg" == "--glob" ]] && continue
      [[ "$arg" == -* ]] && continue
      args+=("$arg")
    done
    grep -RIn --exclude='*_test.go' --exclude-dir='.git' "$symbol" "${args[@]}" || true
  fi
}

echo "Tracing symbol: $symbol"
search "Public Client methods" "$sdk/milvusclient" --glob '!*_test.go'
search "Option types / request building" "$sdk/milvusclient" --glob '*_options.go'
search "Results / results handling" "$sdk/milvusclient/results.go"
search "Entity types" "$sdk/entity"
search "Column types / conversion" "$sdk/column"
search "Index builders" "$sdk/index"
search "Row unmarshal" "$sdk/row"
search "Internal (merr/retry/typeutil)" "$sdk/internal"
search "E2E (tests/go_client)" "$repo_root/tests/go_client"
