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
        author_login = (pr.get("user") or {}).get("login") or ""
        if not author_login:
            raise SystemExit(f"error: {pr.get('html_url', '<unknown PR>')} has no author login")
        values = [
            pr["html_url"],
            author_login,
            (pr.get("user") or {}).get("type") or "",
            pr.get("author_association") or "",
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

check_org_membership() {
  local org="$1"
  local author="$2"
  local status_file="$3"
  local attempt
  local gh_status
  local status_line=""
  local http_status=""

  for attempt in 1 2 3; do
    : >"${status_file}"
    set +e
    gh api --include "/orgs/${org}/members/${author}" >"${status_file}" 2>/dev/null
    gh_status=$?
    set -e

    IFS= read -r status_line <"${status_file}" || status_line=""
    if [[ "${status_line}" =~ ^HTTP/[0-9.]+[[:space:]]+([0-9]{3}) ]]; then
      http_status="${BASH_REMATCH[1]}"
    else
      http_status=""
    fi

    # GitHub returns 204 for a visible member.  Accepting any explicit 2xx
    # keeps this robust if GitHub ever changes the successful no-content code.
    if [[ ${gh_status} -eq 0 && "${http_status}" == 2* ]]; then
      return 0
    fi

    # Only an explicit 404 is a negative membership answer.  Do not treat an
    # empty/malformed response, permission failure, rate limit, transport error,
    # redirect, or server error as "not a member".
    if [[ "${http_status}" == "404" ]]; then
      return 1
    fi

    echo "warning: membership check for ${author} in ${org}, attempt ${attempt}/3, returned HTTP ${http_status:-unknown}" >&2
    if [[ ${attempt} -lt 3 ]]; then
      sleep "${attempt}"
    fi
  done

  echo "error: membership check for ${author} in ${org} could not establish a definitive answer" >&2
  return 125
}

is_internal_author() {
  local author="$1"
  local author_association="$2"
  local cache_value
  local normalized_author="${author,,}"

  if [[ -z "${author}" ]]; then
    echo "error: PR author login is empty; membership cannot be established" >&2
    return 125
  fi

  # OWNER and MEMBER are repository/org membership facts supplied by GitHub.
  if [[ "${author_association}" == "OWNER" || "${author_association}" == "MEMBER" ]]; then
    return 0
  fi
  if [[ -n "${membership_cache[${normalized_author}]+x}" ]]; then
    cache_value="${membership_cache[${normalized_author}]}"
    [[ "${cache_value}" == "internal" ]]
    return
  fi

  local org
  local status_file="${work_dir}/membership_status"
  for org in "${orgs[@]}"; do
    local membership_status=0
    check_org_membership "${org}" "${author}" "${status_file}" || membership_status=$?
    if [[ ${membership_status} -eq 0 ]]; then
      membership_cache["${normalized_author}"]="internal"
      return 0
    fi

    if [[ ${membership_status} -eq 1 ]]; then
      continue
    fi

    # 125 means indeterminate.  It must abort discovery rather than classify a
    # possibly internal author as external.
    if [[ ${membership_status} -ne 125 ]]; then
      echo "error: invalid membership check return status ${membership_status}" >&2
      return 125
    fi
    return 125
  done
  membership_cache["${normalized_author}"]="external"
  return 1
}

printf 'pr_url\tauthor\tcreated_at\trepo\tstate\ttitle\n' > "${filtered_file}"
recent_count=0
eligible_count=0
internal_skipped_count=0
bot_skipped_count=0
while IFS=$'\t' read -r pr_url author author_type author_association created_at repo state title; do
  [[ -n "${pr_url}" ]] || continue
  recent_count=$((recent_count + 1))
  if is_bot_author "${author}" "${author_type}"; then
    bot_skipped_count=$((bot_skipped_count + 1))
    echo "skipping bot author ${author}: ${pr_url}" >&2
    continue
  fi
  internal_status=0
  is_internal_author "${author}" "${author_association}" || internal_status=$?
  if [[ ${internal_status} -gt 1 ]]; then
    echo "error: organization membership discovery cannot continue safely" >&2
    exit 2
  fi
  if [[ ${internal_status} -eq 0 ]]; then
    internal_skipped_count=$((internal_skipped_count + 1))
    echo "skipping organization member ${author}: ${pr_url}" >&2
    continue
  fi
  eligible_count=$((eligible_count + 1))
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${pr_url}" "${author}" "${created_at}" "${repo}" "${state}" "${title}" >> "${filtered_file}"
done < <(sort -t $'\t' -k5,5r -k1,1 "${recent_file}")

if [[ "${output_file}" == "-" ]]; then
  cat "${filtered_file}"
else
  mkdir -p "$(dirname "${output_file}")"
  cp "${filtered_file}" "${output_file}"
fi

echo "Scanned ${repo_count} repositories since ${cutoff_iso}: ${recent_count} recent PRs, ${bot_skipped_count} bot-authored PRs skipped, ${internal_skipped_count} internal-author PRs skipped, ${eligible_count} eligible PRs." >&2
