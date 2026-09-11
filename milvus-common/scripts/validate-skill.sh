#!/usr/bin/env bash
set -euo pipefail

if command -v rg >/dev/null 2>&1; then
  search() { rg -q -- "$@"; }
else
  search() { grep -q -- "$@"; }
fi
search_fixed() {
  if command -v rg >/dev/null 2>&1; then
    rg -q --fixed-strings -- "$@"
  else
    grep -qF -- "$@"
  fi
}

skill_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

required=(
  "SKILL.md"
  "references/architecture.md"
  "references/build-and-test.md"
  "references/change-rules.md"
  "scripts/validate-skill.sh"
)

for path in "${required[@]}"; do
  if [[ ! -f "$skill_dir/$path" ]]; then
    echo "missing: $path" >&2
    exit 1
  fi
done

if ! search '^---$' "$skill_dir/SKILL.md"; then
  echo "SKILL.md missing YAML frontmatter" >&2
  exit 1
fi

if ! search '^name: milvus-common$' "$skill_dir/SKILL.md"; then
  echo "SKILL.md frontmatter name should be milvus-common" >&2
  exit 1
fi

for ref in architecture build-and-test change-rules; do
  if ! search "references/${ref}.md" "$skill_dir/SKILL.md"; then
    echo "SKILL.md does not link references/${ref}.md" >&2
    exit 1
  fi
done

if ! search '--gtest_filter' "$skill_dir/references/build-and-test.md"; then
  echo "build-and-test.md should document --gtest_filter focused tests" >&2
  exit 1
fi

if ! search 'default-conan-local2' "$skill_dir/references/build-and-test.md"; then
  echo "build-and-test.md should document the default-conan-local2 remote" >&2
  exit 1
fi

for current_path in \
  'cachinglayer/Manager.h' \
  'cachinglayer/lrucache/DList.h' \
  'cachinglayer/LoadingOverhead.h' \
  'common/EasyAssert.h' \
  'common/OpContext.h' \
  'log/Log.h' \
  'docs/design-docs/20260723-loading-overhead-management-and-accounting.md'; do
  if ! search_fixed "$current_path" "$skill_dir/references/architecture.md"; then
    echo "architecture.md does not describe current path: $current_path" >&2
    exit 1
  fi
done

echo "skill structure ok: $skill_dir"
