#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 VERSION" >&2
  echo "example: $0 vX.Y.Z" >&2
  exit 2
fi

version=$1
plain_version=${version#v}
repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -f "$repo_root/CHANGELOG.md" || ! -f "$repo_root/src/include/milvus/MilvusClientV2.h" ]]; then
  echo "error: run this script from the milvus-sdk-cpp repo root" >&2
  exit 1
fi

cd "$repo_root"

echo "== Tags matching $version =="
git tag --list "$version" --sort=-version:refname || true

echo
echo "== Release marker commits =="
git log --oneline --decorate --grep="Prepare for ${version}" --grep="Prepare for ${plain_version}" --all || true

echo
echo "== CHANGELOG section header =="
if command -v rg >/dev/null 2>&1; then
  rg -n "^## milvus-sdk-cpp ${plain_version}" CHANGELOG.md || true
else
  grep -nE "^## milvus-sdk-cpp ${plain_version}" CHANGELOG.md || true
fi

echo
echo "== Nearby release markers =="
git log --oneline --decorate --max-count=20 --grep='Prepare for v' --all || true
