#!/usr/bin/env bash
set -euo pipefail

output_file="-"
lookback=""
since=""
per_page=100
declare -a orgs=("milvus-io" "zilliztech")
declare -a excluded_repos=(
  "milvus-io/milvus-storage"
  "zilliztech/GPTCache"
  "zilliztech/claude-context"
)
declare -A known_automation_authors=(["pymilvus-bot"]=1)

usage() {
  echo "usage: $0 [--lookback DURATION | --since TIME_POINT] [--output FILE]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lookback)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      lookback="$2"
      shift 2
      ;;
    --since)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      since="$2"
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
  command -v "${command_name}" >/dev/null 2>&1 || {
    echo "error: ${command_name} is required" >&2
    exit 1
  }
done
gh auth status >/dev/null 2>&1 || { echo "error: gh is not authenticated" >&2; exit 1; }

if [[ -n "${lookback}" && -n "${since}" ]]; then
  echo "error: --lookback and --since are mutually exclusive" >&2
  exit 2
fi

if [[ -n "${since}" ]]; then
  if ! cutoff_epoch=$(date -d "${since}" +%s 2>/dev/null); then
    echo "error: invalid --since time point: ${since}" >&2
    exit 2
  fi
else
  lookback="${lookback:-24 hours}"
  if ! cutoff_epoch=$(date -d "${lookback} ago" +%s 2>/dev/null); then
    echo "error: invalid --lookback duration: ${lookback}" >&2
    exit 2
  fi
fi
cutoff_iso=$(date -u -d "@${cutoff_epoch}" +%Y-%m-%dT%H:%M:%SZ)
echo "including PRs created after ${cutoff_iso}" >&2

work_dir=$(mktemp -d)
trap 'rm -rf "${work_dir}"' EXIT
repos_file="${work_dir}/repos.txt"
open_file="${work_dir}/open.tsv"
filtered_file="${work_dir}/filtered.tsv"
: > "${repos_file}"
: > "${open_file}"

api_to_file() {
  local endpoint="$1"
  local destination="$2"
  local attempt
  for attempt in 1 2 3; do
    if gh api "${endpoint}" > "${destination}"; then
      return 0
    fi
    echo "warning: GitHub API attempt ${attempt}/3 failed: ${endpoint}" >&2
  done
  return 1
}

for org in "${orgs[@]}"; do
  echo "enumerating repositories in ${org} ..." >&2
  gh api --paginate "/orgs/${org}/repos?per_page=${per_page}&type=all" --jq '.[].full_name' >> "${repos_file}" || {
    echo "error: failed to enumerate repositories in ${org}" >&2
    exit 1
  }
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
    read -r page_count reached_cutoff < <(python3 - "${page_json}" "${open_file}" "${cutoff_epoch}" <<'PY'
from datetime import datetime
import json
import sys

page_path, output_path, cutoff_text = sys.argv[1:]
cutoff = int(cutoff_text)
with open(page_path, encoding="utf-8") as handle:
    pulls = json.load(handle)
reached_cutoff = False
with open(output_path, "a", encoding="utf-8") as output:
    for pr in pulls:
        created_at = pr["created_at"]
        created_epoch = int(datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp())
        if created_epoch <= cutoff:
            reached_cutoff = True
            continue
        values = [
            pr["html_url"],
            (pr.get("user") or {}).get("login") or "",
            (pr.get("user") or {}).get("type") or "",
            pr["created_at"],
            (pr.get("base") or {}).get("repo", {}).get("full_name") or "",
            str(pr["number"]),
            pr.get("state") or "",
            (pr.get("title") or "").replace("\t", " ").replace("\r", " ").replace("\n", " "),
        ]
        output.write("\t".join(values) + "\n")
print(len(pulls), int(reached_cutoff))
PY
    )
    [[ "${reached_cutoff}" == "1" ]] && break
    [[ "${page_count}" -lt "${per_page}" ]] && break
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
  local normalized="${author,,}"
  [[ "${author_type}" == "Bot" ]] || [[ "${normalized}" == *"[bot]" ]] || [[ -n "${known_automation_authors[${normalized}]+x}" ]]
}

is_internal_author() {
  local author="$1"
  [[ -n "${author}" ]] || return 1
  if [[ -n "${membership_cache[${author}]+x}" ]]; then
    [[ "${membership_cache[${author}]}" == "internal" ]]
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

printf 'pr_url\tauthor\tcreated_at\trepo\tnumber\tstate\ttitle\tinternal\n' > "${filtered_file}"
open_count=0
eligible_count=0
internal_count=0
bot_count=0
while IFS=$'\t' read -r pr_url author author_type created_at repo number state title; do
  [[ -n "${pr_url}" ]] || continue
  open_count=$((open_count + 1))
  if is_bot_author "${author}" "${author_type}"; then
    bot_count=$((bot_count + 1))
    continue
  fi
  if is_internal_author "${author}"; then
    internal_count=$((internal_count + 1))
    continue
  fi
  eligible_count=$((eligible_count + 1))
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${pr_url}" "${author}" "${created_at}" "${repo}" "${number}" "${state}" "${title}" "0" >> "${filtered_file}"
done < <(sort -t $'\t' -k4,4r -k1,1 "${open_file}")

if [[ "${output_file}" == "-" ]]; then
  cat "${filtered_file}"
else
  mkdir -p "$(dirname "${output_file}")"
  cp "${filtered_file}" "${output_file}"
fi

echo "Scanned ${repo_count} repositories for PRs created after ${cutoff_iso}: ${open_count} in-window open PRs, ${bot_count} bot-authored skipped, ${internal_count} internal-author skipped, ${eligible_count} eligible external PRs." >&2
