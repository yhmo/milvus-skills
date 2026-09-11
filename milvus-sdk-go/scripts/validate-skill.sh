#!/usr/bin/env bash
set -euo pipefail

skill_dir="$(cd "$(dirname "$0")/.." && pwd)"
skill_file="$skill_dir/SKILL.md"

if [[ ! -f "$skill_file" ]]; then
  echo "error: SKILL.md is missing" >&2
  exit 1
fi

if ! awk 'NR==1 && $0=="---" { ok=1 } END { exit ok ? 0 : 1 }' "$skill_file"; then
  echo "error: SKILL.md must start with YAML frontmatter delimiter ---" >&2
  exit 1
fi

name="$(awk -F': ' '/^name:/ { print $2; exit }' "$skill_file")"
description="$(awk -F': ' '/^description:/ { print $2; exit }' "$skill_file")"

if [[ -z "$name" ]]; then
  echo "error: frontmatter name is missing" >&2
  exit 1
fi

if [[ ! "$name" =~ ^[a-z0-9-]+$ ]]; then
  echo "error: name must use lowercase letters, numbers, and hyphens only: $name" >&2
  exit 1
fi

if [[ -z "$description" ]]; then
  echo "error: frontmatter description is missing" >&2
  exit 1
fi

if grep -nE '<|>' "$skill_file" >/dev/null; then
  echo "error: SKILL.md contains XML angle brackets, which are forbidden in skill frontmatter and risky in instructions" >&2
  exit 1
fi

line_count="$(wc -l < "$skill_file")"
if (( line_count > 500 )); then
  echo "error: SKILL.md has $line_count lines; keep it under 500 lines" >&2
  exit 1
fi

for script in "$skill_dir"/scripts/*.sh; do
  [[ -e "$script" ]] || continue
  if [[ ! -x "$script" ]]; then
    echo "error: script is not executable: $script" >&2
    exit 1
  fi
done

required_references=(
  technical-details.md
  build-and-test.md
  examples.md
  release.md
)

for reference in "${required_references[@]}"; do
  if [[ ! -f "$skill_dir/references/$reference" ]]; then
    echo "error: required reference is missing: references/$reference" >&2
    exit 1
  fi
  if ! grep -F "references/$reference" "$skill_file" >/dev/null; then
    echo "error: SKILL.md does not link references/$reference" >&2
    exit 1
  fi
done

echo "OK: skill package passes basic validation"
