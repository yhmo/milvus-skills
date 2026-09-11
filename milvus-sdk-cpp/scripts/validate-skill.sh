#!/usr/bin/env bash
set -euo pipefail

skill_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

required=(
  "SKILL.md"
  "references/technical-details.md"
  "references/build-and-test.md"
  "references/examples.md"
  "references/release.md"
  "scripts/api-trace.sh"
  "scripts/release-window.sh"
  "scripts/validate-skill.sh"
)

for path in "${required[@]}"; do
  if [[ ! -f "$skill_dir/$path" ]]; then
    echo "missing: $path" >&2
    exit 1
  fi
done

# Quiet search that uses ripgrep when available and falls back to grep otherwise.
search_q() {
  local -a args=()
  local arg
  for arg in "$@"; do
    if [[ "$arg" == "--fixed-strings" ]]; then
      if command -v rg >/dev/null 2>&1; then
        args+=("--fixed-strings")
      else
        args+=("-F")
      fi
    else
      args+=("$arg")
    fi
  done
  if command -v rg >/dev/null 2>&1; then
    rg "${args[@]}"
  else
    grep "${args[@]}"
  fi
}

if ! search_q -q '^---$' "$skill_dir/SKILL.md"; then
  echo "SKILL.md missing YAML frontmatter" >&2
  exit 1
fi

if ! search_q -q '^name: milvus-sdk-cpp$' "$skill_dir/SKILL.md"; then
  echo "SKILL.md frontmatter name should be milvus-sdk-cpp" >&2
  exit 1
fi

for ref in technical-details build-and-test examples release; do
  if ! search_q -q "references/${ref}.md" "$skill_dir/SKILL.md"; then
    echo "SKILL.md does not link references/${ref}.md" >&2
    exit 1
  fi
done

if ! search_q -q -- '-j4' "$skill_dir/references/build-and-test.md"; then
  echo "build-and-test.md should document -j4 build parallelism" >&2
  exit 1
fi

for current_path in \
  'examples/src/v2' \
  'src/impl/utils/cache' \
  'src/impl/MilvusClientV2SessionImpl'; do
  if ! search_q -q --fixed-strings "$current_path" "$skill_dir/references/technical-details.md" \
      "$skill_dir/references/examples.md"; then
    echo "skill references do not describe current path: $current_path" >&2
    exit 1
  fi
done

echo "skill structure ok: $skill_dir"
