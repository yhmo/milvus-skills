#!/usr/bin/env bash
set -euo pipefail

query="${1:-}"
if [[ -z "$query" ]]; then
  echo "usage: $0 <method-or-class>" >&2
  echo "example: $0 describeCollection" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -d "$repo_root/sdk-core/src/main/java/io/milvus/v2" ]]; then
  echo "error: run this from the milvus-sdk-java git repository" >&2
  exit 1
fi

cd "$repo_root"
root="sdk-core/src/main/java/io/milvus/v2"
shared_root="sdk-core/src/main/java/io/milvus"
stem="$(printf '%s' "$query" | sed 's/Req$//; s/Resp$//')"
pascal_stem="$(printf '%s%s' "$(printf '%s' "$stem" | cut -c1 | tr '[:lower:]' '[:upper:]')" "$(printf '%s' "$stem" | cut -c2-)")"

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

echo "== MilvusClientV2 matches =="
search_file "$query" "$root/client/MilvusClientV2.java"

echo
echo "== v2 service matches =="
search_dir "$query" "$root/service"

echo
echo "== v2 utility/client matches =="
search_dir "$query" "$root/utils"
search_dir "$query" "$root/client"

echo
echo "== shared cache/iterator/pool matches =="
search_dir "$query" "$shared_root/common/utils/cache"
search_dir "$query" "$shared_root/orm/iterator"
search_dir "$query" "$shared_root/pool"

echo
echo "== request/response/class candidates =="
find "$root" "$shared_root/common/utils/cache" "$shared_root/orm/iterator" -type f \
  | grep -E "${query}|${stem}|${pascal_stem}" || true
