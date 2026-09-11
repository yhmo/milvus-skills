#!/usr/bin/env bash
set -euo pipefail

skill_dir="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

[[ -d "$skill_dir" ]] || fail "Skill directory not found: $skill_dir"
[[ -f "$skill_dir/SKILL.md" ]] || fail "Missing exact file name SKILL.md"
[[ -d "$skill_dir/references" ]] || fail "Missing references/ directory"

base="$(basename "$skill_dir")"
[[ "$base" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || fail "Skill folder must be kebab-case: $base"

# Flag raw XML/HTML only outside backtick code spans, so placeholders such as
# `git commit -sm '<message>'` are allowed.
if sed 's/`[^`]*`//g' "$skill_dir/SKILL.md" | grep -nE '<[^>]+>' >/dev/null; then
  fail "SKILL.md contains XML-like angle bracket tags; remove them"
fi

if ! grep -q '^---$' "$skill_dir/SKILL.md"; then
  fail "SKILL.md missing YAML frontmatter delimiters"
fi

if ! grep -q '^name: milvus-storage$' "$skill_dir/SKILL.md"; then
  fail "SKILL.md frontmatter should contain name: milvus-storage"
fi

if ! grep -q '^description: ' "$skill_dir/SKILL.md"; then
  fail "SKILL.md frontmatter missing description"
fi

missing=0
for ref in technical-details.md build-and-test.md examples.md release.md; do
  if [[ ! -f "$skill_dir/references/$ref" ]]; then
    echo "ERROR: Missing references/$ref" >&2
    missing=1
  fi
  if ! grep -q "references/$ref" "$skill_dir/SKILL.md"; then
    echo "ERROR: SKILL.md does not link references/$ref" >&2
    missing=1
  fi
done

for script in api-trace.sh validate-skill.sh; do
  if [[ ! -x "$skill_dir/scripts/$script" ]]; then
    echo "ERROR: scripts/$script missing or not executable" >&2
    missing=1
  fi
done

[[ "$missing" -eq 0 ]] || exit 1

for current_path in \
  'cpp/src/ffi' \
  'cpp/include/milvus-storage/ffi_c.h' \
  'cpp/src/format/bridge/rust' \
  'python/milvus_storage/_ffi.py' \
  'cpp/src/jni' \
  'tests/integration' \
  'scripts/error_handling_baseline.tsv'; do
  if ! grep -q --fixed-strings "$current_path" "$skill_dir/references/technical-details.md" \
      "$skill_dir/references/build-and-test.md"; then
    echo "ERROR: skill references do not describe current path: $current_path" >&2
    exit 1
  fi
done

echo "skill structure ok: $skill_dir"
