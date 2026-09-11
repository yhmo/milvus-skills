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

echo "guidance_files:"
find . -name AGENTS.md -not -path './.git/*' -print | sort

echo "go_modules:"
find . -name go.mod -not -path './.git/*' -not -path './vendor/*' -not -path './cmake_build/*' -print | sort

echo "working_tree:"
git status --short

echo "changed_top_level_areas:"
git status --short | awk '{print $2}' | sed 's#^"##; s#"$##; s#/.*##' | sort -u

echo "available_component_test_targets:"
if command -v rg >/dev/null 2>&1; then
  rg -o '^test-[a-z0-9-]+:' Makefile | tr -d ':' | sort
else
  grep -oE '^test-[a-z0-9-]+:' Makefile | tr -d ':' | sort
fi

echo "agent_guide_indexes:"
find docs/agent_guides -type f \( -name README.md -o -name '*system.md' \) -print 2>/dev/null | sort
