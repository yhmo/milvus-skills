#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "not inside a git repository" >&2
  exit 1
}

cd "$root"

echo "repo_root=$root"
echo "branch=$(git branch --show-current)"
echo "head=$(git rev-parse --short HEAD)"

echo "remotes:"
git remote -v

echo "guidance_files:"
find . -name 'AGENTS.md' -o -name 'CLAUDE.md' 2>/dev/null | grep -v -e '/.git/' -e '/third_party/' -e '/build/' | sort

echo "working_tree:"
git status --short

echo "changed_top_level_areas:"
git status --short | awk '{print $2}' | sed 's#^"##; s#"$##; s#/.*##' | sort -u

echo "build_configuration:"
grep -E '^(BUILD_TYPE|WITH_UT|WITH_ASAN|WITH_COMPILE_PRUNE)\s*=' Makefile 2>/dev/null || true

echo "ci_workflows:"
ls .github/workflows 2>/dev/null || true
