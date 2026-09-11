#!/usr/bin/env bash
set -euo pipefail

if command -v rg >/dev/null 2>&1; then
  search() { rg -q -- "$@"; }
else
  search() { grep -q -- "$@"; }
fi

skill_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

required=(
  "SKILL.md"
  "references/usage.md"
  "references/version-matching.md"
  "references/development.md"
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

if ! search '^name: vectordbbench$' "$skill_dir/SKILL.md"; then
  echo "SKILL.md frontmatter name should be vectordbbench" >&2
  exit 1
fi

for ref in usage version-matching development; do
  if ! search "references/${ref}.md" "$skill_dir/SKILL.md"; then
    echo "SKILL.md does not link references/${ref}.md" >&2
    exit 1
  fi
done

if ! search 'vectordbbench' "$skill_dir/references/usage.md"; then
  echo "usage.md should document the vectordbbench CLI" >&2
  exit 1
fi

if ! search 'init_bench' "$skill_dir/references/usage.md"; then
  echo "usage.md should document the init_bench web UI" >&2
  exit 1
fi

if ! search 'pymilvus' "$skill_dir/references/version-matching.md"; then
  echo "version-matching.md should document the pymilvus pin" >&2
  exit 1
fi

if ! search 'large_topk' "$skill_dir/references/version-matching.md"; then
  echo "version-matching.md should document query_mode=large_topk" >&2
  exit 1
fi

if ! search 'backend/clients' "$skill_dir/references/development.md"; then
  echo "development.md should describe backend/clients structure" >&2
  exit 1
fi

if ! search 'make lint' "$skill_dir/references/development.md"; then
  echo "development.md should document make lint" >&2
  exit 1
fi

echo "skill structure ok: $skill_dir"
