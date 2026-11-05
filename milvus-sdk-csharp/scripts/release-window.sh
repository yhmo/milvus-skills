#!/usr/bin/env bash
set -euo pipefail

version="${1:-}"
if [[ -z "$version" ]]; then
  echo "usage: $0 <version>" >&2
  echo "example: $0 3.0.0" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -f "$repo_root/CHANGELOG.md" || ! -f "$repo_root/Version.props" ]]; then
  echo "error: run this from the milvus-sdk-csharp git repository" >&2
  exit 1
fi

cd "$repo_root"
normalized="${version#v}"

# --- CI-related commit predicate ---------------------------------------------
# A commit is CI-only (excluded from release notes) when its subject is a pure
# CI/dependency-bot marker or every path it touches is under .github/ (workflow
# config). Subject patterns follow the repo's conventional-commit prefixes.
ci_subject_re='^(ci|build\(deps\)|chore\(deps\)|dependabot):'
ci_only_path() {
  # non-zero exit when ALL changed paths are CI/ops-only (no SDK source)
  local sha="$1" paths
  paths="$(git diff-tree --no-commit-id --name-only -r "$sha")"
  [[ -z "$paths" ]] && return 1
  # treat any touched SDK/test/docs source as user-visible
  if grep -qE '^(Milvus\.Client|Milvus\.Client\.V2|CHANGELOG\.md|README\.md|tutorials?|examples?)/' <<<"$paths"; then
    return 1
  fi
  # otherwise CI-only iff nothing outside .github/ (workflow) is touched
  grep -qvE '^\.github/' <<<"$paths" && return 1
  return 0
}

# --- non-CI commits in a release window --------------------------------------
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
echo "== Release markers (Prepare ... vX.Y.Z) =="
git log --grep '^Prepare.* v' --date=short --format='%h %ad %s' | grep "${normalized}" || true

echo
echo "== CHANGELOG section header =="
grep -nE "^## milvus-sdk-csharp ${normalized}(\b|$| \(|$)" CHANGELOG.md || true

echo
echo "== Changelog entry for ${normalized} =="
entry="$(awk -v version="$normalized" '
  $0 ~ "^##[[:space:]]+.*milvus-sdk-csharp[[:space:]]+" version "([[:space:]]|$|\\()" { found=1; print; next }
  found && $0 ~ "^##[[:space:]]+" { exit }
  found { print }
' CHANGELOG.md)"
if [[ -z "$entry" ]]; then
  echo "error: no CHANGELOG.md entry found for ${normalized}" >&2
  exit 1
fi
printf '%s\n' "$entry"

echo
echo "== Non-CI commits since the previous release tag =="
# find the most recent v* tag strictly below the requested version
prev_tag="$(git tag --list 'v*' --sort=-version:refname \
  | awk -v v="$normalized" 'sub(/^v/,"") && $0 < v { print "v"$0; exit }')"
if [[ -n "$prev_tag" ]]; then
  echo "range: ${prev_tag}..HEAD (CI-only commits excluded)"
  non_ci_commits "${prev_tag}..HEAD"
else
  echo "(no earlier v* tag found)"
fi