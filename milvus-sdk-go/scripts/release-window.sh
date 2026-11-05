#!/usr/bin/env bash
set -euo pipefail

version="${1:-}"
if [[ -z "$version" ]]; then
  echo "usage: $0 <client-tag>" >&2
  echo "example: $0 v2.6.4" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -f "$repo_root/client/go.mod" ]]; then
  echo "error: run this from the milvus repository root" >&2
  exit 1
fi

cd "$repo_root"

normalized="${version#v}"
if ! git tag -l "client/v${normalized}" | grep -q .; then
  echo "error: no tag client/v${normalized} found" >&2
  exit 1
fi

tag="client/v${normalized}"

# CI-only commits (dependency-bot subjects) are excluded from the user-visible
# change window. The paths are already scoped to client/ and tests/go_client/,
# so only the subject pattern needs filtering here.
ci_subject_re='^(ci|build\(deps\)|chore\(deps\)|dependabot):'
non_ci_log() {
  git log --format='%h %ad %s' --date=short "$@" 2>/dev/null | grep -vE "$ci_subject_re" || true
}

echo "== SDK release markers =="
git log --grep "client" --date=short --format='%h %ad %s' -- client/ | head -3 || true

echo
echo "== Changes to client/ since ${tag} (CI-only commits excluded) =="
client_log="$(non_ci_log "${tag}..HEAD" -- client/ || true)"
if [[ -n "$client_log" ]]; then
  printf '%s\n' "$client_log"
else
  echo "(none)"
fi

echo
echo "== Changes to tests/go_client/ since ${tag} (CI-only commits excluded) =="
go_client_log="$(non_ci_log "${tag}..HEAD" -- tests/go_client/ || true)"
if [[ -n "$go_client_log" ]]; then
  printf '%s\n' "$go_client_log"
else
  echo "(none)"
fi
