#!/usr/bin/env bash
set -euo pipefail

skill_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

required=(
  "SKILL.md"
  "references/technical-details.md"
  "references/build-and-test.md"
  "references/branch-2.6.md"
  "references/examples.md"
  "references/release.md"
  "scripts/api-trace.sh"
  "scripts/release-window.sh"
  "scripts/validate-skill.sh"
  "agents/openai.yaml"
)

for path in "${required[@]}"; do
  if [[ ! -f "$skill_dir/$path" ]]; then
    echo "missing: $path" >&2
    exit 1
  fi
done

if ! grep -q '^---$' "$skill_dir/SKILL.md"; then
  echo "SKILL.md missing YAML frontmatter" >&2
  exit 1
fi

if ! grep -q '^name: milvus-sdk-rust$' "$skill_dir/SKILL.md"; then
  echo "SKILL.md frontmatter name should be milvus-sdk-rust" >&2
  exit 1
fi

for ref in technical-details build-and-test branch-2.6 examples release; do
  if ! grep -q "references/${ref}.md" "$skill_dir/SKILL.md"; then
    echo "SKILL.md does not link references/${ref}.md" >&2
    exit 1
  fi
done

echo "skill structure ok: $skill_dir"
