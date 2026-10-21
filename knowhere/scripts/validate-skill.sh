#!/usr/bin/env bash
set -euo pipefail

skill_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

required=(
  "SKILL.md"
  "references/technical-details.md"
  "references/build-and-test.md"
  "scripts/api-trace.sh"
  "scripts/validate-skill.sh"
)

for ref in technical-details.md build-and-test.md branch-differences.md; do
  if [[ ! -f "$skill_dir/references/$ref" ]]; then
    echo "error: required reference is missing: references/$ref" >&2
    exit 1
  fi
  if ! grep -F "references/$ref" "$skill_dir/SKILL.md" >/dev/null; then
    echo "error: SKILL.md does not link references/$ref" >&2
    exit 1
  fi
done

for path in "${required[@]}"; do
  if [[ ! -f "$skill_dir/$path" ]]; then
    echo "missing: $path" >&2
    exit 1
  fi
done

has() {
  if command -v rg >/dev/null 2>&1; then
    rg -q "$@"
  else
    grep -q "$@"
  fi
}

if ! has '^---$' "$skill_dir/SKILL.md"; then
  echo "SKILL.md missing YAML frontmatter" >&2
  exit 1
fi

if ! has '^name: knowhere$' "$skill_dir/SKILL.md"; then
  echo "SKILL.md frontmatter name should be knowhere" >&2
  exit 1
fi

for ref in technical-details build-and-test; do
  if ! has "references/${ref}.md" "$skill_dir/SKILL.md"; then
    echo "SKILL.md does not link references/${ref}.md" >&2
    exit 1
  fi
done

if ! has 'WITH_UT=True' "$skill_dir/references/build-and-test.md"; then
  echo "build-and-test.md should document the WITH_UT=True unit-test build" >&2
  exit 1
fi

for current_path in \
  'src/index/index_factory.cc' \
  'include/knowhere/index/index_factory.h' \
  'tests/ut/knowhere_tests'; do
  if ! has -F "$current_path" "$skill_dir/references/technical-details.md" \
      "$skill_dir/references/build-and-test.md"; then
    echo "skill references do not describe current path: $current_path" >&2
    exit 1
  fi
done

echo "skill structure ok: $skill_dir"
