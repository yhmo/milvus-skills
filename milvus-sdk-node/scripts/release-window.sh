#!/usr/bin/env bash
set -euo pipefail

version="${1:-}"
if [[ -z "$version" ]]; then
  echo "usage: $0 <version>" >&2
  echo "example: $0 3.0.5" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -f "$repo_root/package.json" || ! -d "$repo_root/docs/src/content/docs/reference" ]]; then
  echo "error: run this from the milvus-sdk-node git repository" >&2
  exit 1
fi

cd "$repo_root"
normalized="${version#v}"
notes="docs/src/content/docs/reference/release-notes.mdx"

# --- CI-related commit predicate ---------------------------------------------
ci_subject_re='^(ci|build\(deps\)|chore\(deps\)|dependabot):'
ci_only_path() {
  local sha="$1" paths
  paths="$(git diff-tree --no-commit-id --name-only -r "$sha")"
  [[ -z "$paths" ]] && return 1
  # any touched SDK source, user-facing doc, manifest, or lockfile keeps the
  # commit visible; everything under .github/ alone marks it CI-only.
  if grep -qE '^(src/|docs/src/content/docs/reference/release-notes|package\.json|yarn\.lock|README\.md)' <<<"$paths"; then
    return 1
  fi
  grep -qvE '^\.github/' <<<"$paths" && return 1
  return 0
}

non_ci_commits() {
  local range="$1" sha date subject
  git log --format='%H|%ad|%s' --date=short "$range" | \
  while IFS='|' read -r sha date subject; do
    [[ -z "$sha" ]] && continue
    if grep -qE "$ci_subject_re" <<<"$subject"; then
      continue
    fi
    if ci_only_path "$sha"; then
      continue
    fi
    printf '%s %s %s\n' "${sha:0:7}" "$date" "$subject"
  done
}

echo "== Tags matching $version =="
git tag --list "v${normalized}" "$version" "$normalized" --sort=-version:refname || true

echo
echo "== Release markers (chore: bump version ...) =="
git log --grep '^chore: bump version' --date=short --format='%h %ad %s'

echo
echo "== Release-notes section header =="
grep -nE "^## ${normalized}(\b|$)" "$notes" || true

echo
echo "== Release-notes entry for ${normalized} =="
entry="$(awk -v version="$normalized" '
  $0 ~ "^##[[:space:]]+" version "([[:space:]]|$)" { found=1; print; next }
  found && $0 ~ "^##[[:space:]]+" { exit }
  found { print }
' "$notes")"
if [[ -z "$entry" ]]; then
  echo "error: no release-notes entry found for ${normalized} in ${notes}" >&2
  exit 1
fi
printf '%s\n' "$entry"

echo
echo "== Non-CI commits since the previous release tag =="
prev_tag="$(git tag --list 'v*' --sort=-version:refname \
  | awk -v v="$normalized" 'sub(/^v/,"") && $0 < v { print "v"$0; exit }')"
if [[ -n "$prev_tag" ]]; then
  echo "range: ${prev_tag}..HEAD (CI-only commits excluded)"
  non_ci_commits "${prev_tag}..HEAD"
else
  echo "(no earlier v* tag found)"
fi
