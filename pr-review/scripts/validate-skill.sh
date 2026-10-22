#!/usr/bin/env bash
set -euo pipefail

skill_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

required=(
  "SKILL.md"
  "scripts/cleanup_workspace.py"
  "scripts/validate-skill.sh"
  "references/checklists/sdk-public-api.md"
  "references/checklists/parsing.md"
  "references/checklists/security.md"
  "references/checklists/concurrency.md"
  "references/checklists/cross-repo.md"
  "references/checklists/examples.md"
)

for path in "${required[@]}"; do
  if [[ ! -f "$skill_dir/$path" ]]; then
    echo "missing: $path" >&2
    exit 1
  fi
done

for script in "$skill_dir"/scripts/*.sh; do
  [[ -e "$script" ]] || continue
  if [[ ! -x "$script" ]]; then
    echo "error: script is not executable: $script" >&2
    exit 1
  fi
done

if ! grep -q '^---$' "$skill_dir/SKILL.md"; then
  echo "SKILL.md missing YAML frontmatter" >&2
  exit 1
fi

if ! grep -q '^name: pr-review$' "$skill_dir/SKILL.md"; then
  echo "SKILL.md frontmatter name should be pr-review" >&2
  exit 1
fi

for checklist in sdk-public-api parsing security concurrency cross-repo examples; do
  if ! grep -F "references/checklists/$checklist.md" "$skill_dir/SKILL.md" >/dev/null; then
    echo "SKILL.md does not link references/checklists/$checklist.md" >&2
    exit 1
  fi
done

if ! grep -q 'Completion gate for Step 3' "$skill_dir/SKILL.md"; then
  echo "SKILL.md is missing the Step 3 completion gate" >&2
  exit 1
fi

if ! grep -q '3g\. Cross-repository consistency pass' "$skill_dir/SKILL.md"; then
  echo "SKILL.md is missing the conditional cross-repository consistency sub-pass" >&2
  exit 1
fi

for repo in milvus-sdk-node milvus-storage birdwatcher milvus-common knowhere cardinal vectordbbench; do
  if ! grep -q "$repo" "$skill_dir/SKILL.md"; then
    echo "routing map is missing repository skill: $repo" >&2
    exit 1
  fi
done

if grep -q '11-step workflow' "$skill_dir/SKILL.md"; then
  echo "off-by-one reference: '11-step workflow' should be '12-step workflow'" >&2
  exit 1
fi

if grep -q 'Steps 1-11' "$skill_dir/SKILL.md"; then
  echo "off-by-one reference: 'Steps 1-11' should be 'Steps 1-12'" >&2
  exit 1
fi

if grep -q 'through Step 11\.' "$skill_dir/SKILL.md"; then
  echo "off-by-one reference: 'through Step 11' should be 'through Step 12'" >&2
  exit 1
fi

if ! grep -q 'Run gates (A-G)' "$skill_dir/SKILL.md"; then
  echo "SKILL.md is missing the lettered run gates" >&2
  exit 1
fi

if ! grep -F 'Any PR that adds or modifies a public API surface' "$skill_dir/SKILL.md" >/dev/null; then
  echo "SKILL.md public-API checklist loading rule is too narrow; it must cover public modules/headers in non-SDK repos too" >&2
  exit 1
fi

if grep -q '最多' "$skill_dir/SKILL.md"; then
  echo "SKILL.md contains a Chinese instruction; keep instructions in English" >&2
  exit 1
fi

if ! grep -q 'PR_REVIEW_CONCURRENCY' "$skill_dir/SKILL.md"; then
  echo "rate-limit budget is missing the PR_REVIEW_CONCURRENCY override" >&2
  exit 1
fi

if ! grep -q 'For draft PRs' "$skill_dir/SKILL.md"; then
  echo "SKILL.md is missing the draft-PR handling rule" >&2
  exit 1
fi

if ! grep -q "For other repositories, check the repository's own" "$skill_dir/SKILL.md"; then
  echo "commit-hygiene rule must cover non-Milvus repositories via their own conventions" >&2
  exit 1
fi

if ! grep -q 'For any other repository, identify its consumers' "$skill_dir/references/checklists/cross-repo.md"; then
  echo "cross-repo checklist consumer map must have a non-Milvus fallback" >&2
  exit 1
fi

echo "skill structure ok: $skill_dir"
