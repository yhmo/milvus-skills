#!/usr/bin/env bash
set -euo pipefail

version="${1:-}"
if [[ -z "$version" ]]; then
  echo "usage: $0 <version>" >&2
  echo "example: $0 X.Y.Z" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -f "$repo_root/Cargo.toml" || ! -f "$repo_root/CHANGELOG.md" ]]; then
  echo "error: run this from the milvus-sdk-rust git repository" >&2
  exit 1
fi

cd "$repo_root"
normalized="${version#v}"

echo "== Release markers =="
git log --grep '^Prepare for v' --date=short --format='%h %ad %s'

echo
echo "== Changelog entry for ${normalized} =="
entry="$(awk -v version="$normalized" '
  $0 ~ "^##[[:space:]]+.*" version "([[:space:]]|$|\\()" { found=1; print; next }
  found && $0 ~ "^##[[:space:]]+" { exit }
  found { print }
' CHANGELOG.md)"

if [[ -z "$entry" ]]; then
  echo "error: no CHANGELOG.md entry found for ${normalized}" >&2
  exit 1
fi

printf '%s\n' "$entry"
