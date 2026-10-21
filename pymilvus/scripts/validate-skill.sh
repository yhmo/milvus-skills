#!/usr/bin/env bash
set -euo pipefail

skill_dir="${1:-$(cd "$(dirname "$0")/.." && pwd)}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

[[ -d "$skill_dir" ]] || fail "Skill directory not found: $skill_dir"
[[ -f "$skill_dir/SKILL.md" ]] || fail "Missing exact file name SKILL.md"
[[ -d "$skill_dir/references" ]] || fail "Missing references/ directory"

base="$(basename "$skill_dir")"
[[ "$base" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || fail "Skill folder must be kebab-case: $base"

if grep -nE '<[^>]+>' "$skill_dir/SKILL.md" >/dev/null; then
  fail "SKILL.md contains XML-like angle bracket tags; remove them"
fi

if ! grep -q '^---$' "$skill_dir/SKILL.md"; then
  fail "SKILL.md missing YAML frontmatter delimiters"
fi

if ! grep -q '^name: pymilvus$' "$skill_dir/SKILL.md"; then
  fail "SKILL.md frontmatter should contain name: pymilvus"
fi

if ! grep -q '^description: ' "$skill_dir/SKILL.md"; then
  fail "SKILL.md frontmatter missing description"
fi

missing=0
for ref in technical-details.md build-and-test.md branch-2.6.md examples.md benchmark.md release.md; do
  if [[ ! -f "$skill_dir/references/$ref" ]]; then
    echo "ERROR: Missing references/$ref" >&2
    missing=1
  fi
  if ! grep -q "references/$ref" "$skill_dir/SKILL.md"; then
    echo "ERROR: SKILL.md does not link references/$ref" >&2
    missing=1
  fi
done

[[ "$missing" -eq 0 ]] || exit 1

echo "Skill validation passed: $skill_dir"
