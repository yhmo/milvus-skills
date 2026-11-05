#!/usr/bin/env bash
set -euo pipefail

version="${1:-}"
if [[ -z "$version" ]]; then
  echo "usage: $0 <version>" >&2
  echo "example: $0 3.0.2" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -f "$repo_root/pyproject.toml" || ! -d "$repo_root/pymilvus" ]]; then
  echo "error: run this from the pymilvus git repository" >&2
  exit 1
fi

cd "$repo_root"
normalized="${version#v}"

# --- CI-related commit predicate ---------------------------------------------
# PyMilvus uses conventional-commit prefixes; CI/ops-only subjects and commits
# that touch only .github/ (workflow) are excluded from user-visible notes.
ci_subject_re='^(ci|chore\(deps\)|build\(deps\)|dependabot):'
ci_only_path() {
  local sha="$1" paths
  paths="$(git diff-tree --no-commit-id --name-only -r "$sha")"
  [[ -z "$paths" ]] && return 1
  # SDK source, tests, docs, and packaging metadata are user-visible.
  if grep -qE '^(pymilvus/|tests/|docs/|README|pyproject\.toml|requirements|setup\.py)' <<<"$paths"; then
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
echo "== Dynamic version at HEAD =="
make version 2>/dev/null || echo "(make version unavailable; run `hatchling version` manually)"

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

echo
echo "== Recent release markers (GitHub Releases use tags; no top-level CHANGELOG) =="
git log --oneline --decorate --max-count=10 --simplify-by-decoration
