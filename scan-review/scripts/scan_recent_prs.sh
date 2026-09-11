#!/usr/bin/env bash
set -euo pipefail

lookback="24 hours"
output_file="-"
per_page=100
declare -a orgs=("milvus-io" "zilliztech")
declare -a excluded_repos=(
  "milvus-io/milvus-storage"
  "zilliztech/GPTCache"
  "zilliztech/claude-context"
)
declare -A known_automation_authors=(
  ["pymilvus-bot"]=1
)

usage() {
  echo "usage: $0 [--lookback '24 hours'] [--output FILE]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lookback)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      lookback="$2"
      shift 2
      ;;
    --output)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      output_file="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

for command_name in gh python3 date; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "error: ${command_name} is required" >&2
    exit 1
  fi
done

if ! gh auth status >/dev/null 2>&1; then
  echo "error: gh is not authenticated" >&2
  exit 1
fi

if [[ "${lookback}" =~ ^[0-9]+$ ]]; then
  lookback="${lookback} hours"
fi

lookback_without_ago="${lookback% ago}"
if ! cutoff_iso=$(date -u -d "${lookback_without_ago} ago" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null); then
  echo "error: invalid lookback '${lookback}'" >&2
  exit 2
fi
cutoff_epoch=$(date -u -d "${cutoff_iso}" +%s)

work_dir=$(mktemp -d)
trap 'rm -rf "${work_dir}"' EXIT
repos_file="${work_dir}/repos.txt"
recent_file="${work_dir}/recent.tsv"
filtered_file="${work_dir}/filtered.tsv"
: > "${repos_file}"
: > "${recent_file}"

api_to_file() {
  local endpoint="$1"
  local destination="$2"
  local attempt
  for attempt in 1 2 3; do
    if gh api "${endpoint}" > "${destination}"; then
      return 0
    fi
    echo "warning: GitHub API attempt ${attempt}/3 failed: ${endpoint}" >&2
    if [[ ${attempt} -lt 3 ]]; then
      sleep "${attempt}"
    fi
  done
  return 1
}

for org in "${orgs[@]}"; do
  echo "enumerating repositories in ${org} ..." >&2
  if ! gh api --paginate "/orgs/${org}/repos?per_page=${per_page}&type=all" --jq '.[].full_name' >> "${repos_file}"; then
    echo "error: failed to enumerate repositories in ${org}" >&2
    exit 1
  fi
done

sort -u -o "${repos_file}" "${repos_file}"
for excluded_repo in "${excluded_repos[@]}"; do
  sed -i "\|^${excluded_repo}$|d" "${repos_file}"
  echo "excluding repository ${excluded_repo}" >&2
done
repo_count=$(wc -l < "${repos_file}" | tr -d ' ')
repo_index=0
failed_repos=0

while IFS= read -r repo; do
  [[ -n "${repo}" ]] || continue
  repo_index=$((repo_index + 1))
  echo "scanning ${repo} (${repo_index}/${repo_count}) ..." >&2
  page=1

  while true; do
    page_json="${work_dir}/page.json"
    endpoint="/repos/${repo}/pulls?state=open&sort=created&direction=desc&per_page=${per_page}&page=${page}"
    if ! api_to_file "${endpoint}" "${page_json}"; then
      echo "error: failed to scan ${repo}" >&2
      failed_repos=$((failed_repos + 1))
      break
    fi

    page_meta=$(python3 - "${page_json}" "${cutoff_epoch}" "${recent_file}" <<'PY'
import json
import sys
from datetime import datetime

page_path = sys.argv[1]
cutoff = int(sys.argv[2])
recent_path = sys.argv[3]
with open(page_path, encoding="utf-8") as handle:
    pulls = json.load(handle)

oldest = None
with open(recent_path, "a", encoding="utf-8") as recent:
    for pr in pulls:
        created_at = pr["created_at"]
        created_epoch = int(datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp())
        oldest = created_epoch if oldest is None else min(oldest, created_epoch)
        if created_epoch < cutoff:
            continue
        values = [
            pr["html_url"],
            (pr.get("user") or {}).get("login") or "",
            (pr.get("user") or {}).get("type") or "",
            created_at,
            (pr.get("base") or {}).get("repo", {}).get("full_name") or "",
            pr.get("state") or "",
            (pr.get("title") or "").replace("\t", " ").replace("\r", " ").replace("\n", " "),
        ]
        recent.write("\t".join(values) + "\n")

print(f"{len(pulls)}\t{oldest if oldest is not None else 0}")
PY
    )

    IFS=$'\t' read -r page_count oldest_epoch <<< "${page_meta}"
    if [[ "${page_count}" -lt "${per_page}" || "${oldest_epoch}" -lt "${cutoff_epoch}" ]]; then
      break
    fi
    page=$((page + 1))
  done
done < "${repos_file}"

if [[ ${failed_repos} -gt 0 ]]; then
  echo "error: ${failed_repos} repositories could not be scanned completely" >&2
  exit 1
fi

declare -A membership_cache=()
is_bot_author() {
  local author="$1"
  local author_type="$2"
  local normalized_author="${author,,}"

  [[ "${author_type}" == "Bot" ]] ||
    [[ "${normalized_author}" == *"[bot]" ]] ||
    [[ -n "${known_automation_authors[${normalized_author}]+x}" ]]
}

is_internal_author() {
  local author="$1"
  local cache_value
  if [[ -z "${author}" ]]; then
    return 1
  fi
  if [[ -n "${membership_cache[${author}]+x}" ]]; then
    cache_value="${membership_cache[${author}]}"
    [[ "${cache_value}" == "internal" ]]
    return
  fi

  local org
  for org in "${orgs[@]}"; do
    if gh api --silent "/orgs/${org}/members/${author}" >/dev/null 2>&1; then
      membership_cache["${author}"]="internal"
      return 0
    fi
  done
  membership_cache["${author}"]="external"
  return 1
}

printf 'pr_url\tauthor\tcreated_at\trepo\tstate\ttitle\n' > "${filtered_file}"
recent_count=0
eligible_count=0
internal_skipped_count=0
bot_skipped_count=0
while IFS=$'\t' read -r pr_url author author_type created_at repo state title; do
  [[ -n "${pr_url}" ]] || continue
  recent_count=$((recent_count + 1))
  if is_bot_author "${author}" "${author_type}"; then
    bot_skipped_count=$((bot_skipped_count + 1))
    echo "skipping bot author ${author}: ${pr_url}" >&2
    continue
  fi
  if is_internal_author "${author}"; then
    internal_skipped_count=$((internal_skipped_count + 1))
    echo "skipping organization member ${author}: ${pr_url}" >&2
    continue
  fi
  eligible_count=$((eligible_count + 1))
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${pr_url}" "${author}" "${created_at}" "${repo}" "${state}" "${title}" >> "${filtered_file}"
done < <(sort -t $'\t' -k4,4r -k1,1 "${recent_file}")

if [[ "${output_file}" == "-" ]]; then
  cat "${filtered_file}"
else
  mkdir -p "$(dirname "${output_file}")"
  cp "${filtered_file}" "${output_file}"
fi

echo "Scanned ${repo_count} repositories since ${cutoff_iso}: ${recent_count} recent PRs, ${bot_skipped_count} bot-authored PRs skipped, ${internal_skipped_count} internal-author PRs skipped, ${eligible_count} eligible PRs." >&2
