#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scan_weekly_prs.sh "<t1_utc>" "<t2_utc>" "<github_account>"

Example:
  scan_weekly_prs.sh "2026-05-23T15:00:00Z" "2026-05-30T15:00:00Z" "yhmo"

Notes:
  - t1 and t2 must be UTC datetime strings parseable by Python's ISO-8601 parser.
  - Date-only input is treated as 00:00:00 UTC on that date.
  - The script keeps all OPEN PRs for the account, plus PRs merged in [t1, t2].
  - PRs that are closed without being merged are excluded.
  - Requires: gh, python3
EOF
}

if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 3 ]]; then
  echo "Error: expected exactly 3 arguments: t1, t2, github_account." >&2
  usage >&2
  exit 1
fi

t1_raw="$1"
t2_raw="$2"
github_account="$3"

if [[ -z "$github_account" ]]; then
  echo "Error: github_account cannot be empty." >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: gh is not installed. Please install GitHub CLI: https://cli.github.com/" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required by this script." >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Error: gh is not authenticated. Please run: gh auth login" >&2
  exit 1
fi

parse_utc_to_epoch() {
  python3 - "$1" <<'PY'
import sys
from datetime import datetime, timezone

raw = sys.argv[1].strip()

try:
    if raw.endswith('Z'):
        dt = datetime.fromisoformat(raw[:-1] + '+00:00')
    elif 'T' in raw or '+' in raw:
        dt = datetime.fromisoformat(raw)
    else:
        dt = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
except Exception:
    sys.exit(1)

print(int(dt.timestamp()))
PY
}

format_epoch_to_utc() {
  python3 - "$1" <<'PY'
import sys
from datetime import datetime, timezone
print(datetime.fromtimestamp(int(sys.argv[1]), tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
PY
}

if ! t1_epoch=$(parse_utc_to_epoch "$t1_raw"); then
  echo "Error: invalid t1 UTC datetime: $t1_raw" >&2
  exit 1
fi

if ! t2_epoch=$(parse_utc_to_epoch "$t2_raw"); then
  echo "Error: invalid t2 UTC datetime: $t2_raw" >&2
  exit 1
fi

if (( t1_epoch > t2_epoch )); then
  echo "Error: t1 must be <= t2." >&2
  exit 1
fi

T1_UTC=$(format_epoch_to_utc "$t1_epoch")
T2_UTC=$(format_epoch_to_utc "$t2_epoch")

echo "t1=$T1_UTC"
echo "t2=$T2_UTC"
echo "github_account=$github_account"

ORGS=("milvus-io" "zilliztech")

echo "Scanning repositories under organizations: ${ORGS[*]}"
for org in "${ORGS[@]}"; do
  echo "== $org =="

  repo_list=$(gh api --paginate "orgs/${org}/repos?per_page=100" \
    --jq 'if type == "array" then .[]?.full_name else empty end' 2>/dev/null || true)

  if [[ -z "$repo_list" ]]; then
    echo "Warning: unable to list repositories for org '$org' (check gh auth scope or rate limits)." >&2
    continue
  fi

  while IFS= read -r repo; do
    [[ -z "$repo" ]] && continue

    rows=$(gh pr list --repo "$repo" --author "$github_account" --state all --limit 200 \
      --json number,title,url,state,baseRefName,createdAt,mergedAt \
      --jq '.[] | [.number, .title, .url, .state, .baseRefName, .createdAt, (.mergedAt // "")] | @tsv')

    if [[ -z "$rows" ]]; then
      continue
    fi

    filtered=$(ROWS="$rows" python3 - "$t1_epoch" "$t2_epoch" <<'PY'
import os
import sys
from datetime import datetime, timezone

start = int(sys.argv[1])
end = int(sys.argv[2])
rows = os.environ.get('ROWS', '')


def to_epoch(value: str):
    value = value.strip()
    if not value:
        return None
    if value.endswith('Z'):
        dt = datetime.fromisoformat(value[:-1] + '+00:00')
    else:
        dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.astimezone(timezone.utc).timestamp())

for raw in rows.splitlines():
    raw = raw.rstrip('\n')
    if not raw:
        continue
    parts = raw.split('\t')
    if len(parts) < 7:
        continue
    num, title, url, state, base_ref, created, merged = parts[:7]
    merged_epoch = to_epoch(merged)
    in_merged = merged_epoch is not None and start <= merged_epoch <= end
    is_open = state.lower() == 'open'
    if is_open or in_merged:
        print('\t'.join([num, title, url, state, base_ref]))
PY
)

    if [[ -n "$filtered" ]]; then
      echo "repo=$repo"
      printf '%s\n' "$filtered"
    fi
  done <<< "$repo_list"
done
