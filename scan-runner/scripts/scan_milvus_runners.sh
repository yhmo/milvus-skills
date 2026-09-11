#!/usr/bin/env bash
set -euo pipefail

runner_label="${1:-macos}"
runner_label_lower="${runner_label,,}"
orgs_string="${SCAN_RUNNER_ORGS:-milvus-io zilliztech}"
per_page=100

if [[ "${runner_label}" == "--help" || "${runner_label}" == "-h" ]]; then
  cat <<'EOF'
Usage: scan_milvus_runners.sh [runner-label]

Scan queued and in-progress GitHub Actions jobs in milvus-io and zilliztech.
The runner label is matched case-insensitively as a substring. It defaults to macos.
EOF
  exit 0
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh is required" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "error: gh is not authenticated; run 'gh auth login'" >&2
  exit 1
fi

printf '| URL | State | PR |\n'
printf '|---|---|---|\n'

found=0

resolve_pr_url() {
  local repo="$1"
  local event="$2"
  local api_pr_url="$3"
  local head_owner="$4"
  local head_branch="$5"
  local pr_url="-"

  if [[ "${event}" != "pull_request" && "${event}" != "pull_request_target" ]]; then
    printf '%s\n' "${pr_url}"
    return
  fi

  if [[ "${api_pr_url}" != "-" ]]; then
    printf '%s\n' "${api_pr_url}" \
      | sed -e 's#^https://api.github.com/repos/#https://github.com/#' -e 's#/pulls/#/pull/#'
    return
  fi

  # GitHub sometimes returns an empty workflow_run.pull_requests array even for
  # pull_request runs. Resolve the PR from its exact fork owner and head branch.
  if [[ "${head_owner}" != "-" && "${head_branch}" != "-" ]]; then
    pr_url="$({
      gh api --method GET "/repos/${repo}/pulls" \
        -f state=all \
        -f head="${head_owner}:${head_branch}" \
        -f per_page="${per_page}" \
        --jq 'sort_by(if .state == "open" then 0 else 1 end) | .[0].html_url // empty' \
        </dev/null \
        2>/dev/null || true
    } | head -n 1)"
  fi

  printf '%s\n' "${pr_url:--}"
}

declare -a repositories=()
if [[ -n "${SCAN_RUNNER_REPOS:-}" ]]; then
  read -r -a repositories <<< "${SCAN_RUNNER_REPOS}"
else
  for org in ${orgs_string}; do
    echo "Scanning repositories in ${org}..." >&2
    mapfile -t org_repositories < <(
      gh api --paginate "/orgs/${org}/repos?per_page=100&type=all" \
        --jq '.[].full_name' 2>/dev/null || true
    )
    repositories+=("${org_repositories[@]}")
  done
fi

for repo in "${repositories[@]}"; do
    [[ -z "${repo}" ]] && continue
    echo "Scanning ${repo}..." >&2

    mapfile -t runs < <(
      for state in queued requested in_progress waiting pending; do
        gh api --paginate "/repos/${repo}/actions/runs?status=${state}&per_page=${per_page}" \
          --jq '.workflow_runs[]? | [.id, .event, (.pull_requests[0].url // "-"), (.head_repository.owner.login // "-"), (.head_branch // "-")] | @tsv' \
          </dev/null 2>/dev/null || true
      done | awk '!seen[$0]++'
    )
    for run in "${runs[@]}"; do
      IFS=$'\t' read -r run_id event api_pr_url head_owner head_branch <<< "${run}"
      [[ -z "${run_id}" ]] && continue
      pr_url="$(resolve_pr_url "${repo}" "${event}" "${api_pr_url}" "${head_owner}" "${head_branch}")"

      mapfile -t jobs < <(
        gh api --paginate "/repos/${repo}/actions/runs/${run_id}/jobs?per_page=${per_page}" \
          --jq '.jobs[]? | [.status, .html_url, ((.labels // []) | join(","))] | @tsv' \
          </dev/null 2>/dev/null || true
      )
      for job in "${jobs[@]}"; do
        IFS=$'\t' read -r state job_url labels <<< "${job}"
        [[ -z "${job_url:-}" ]] && continue
        if [[ "${labels,,}" == *"${runner_label_lower}"* ]]; then
          printf '| %s | %s | %s |\n' "${job_url}" "${state}" "${pr_url}"
          found=1
        fi
      done
    done
done

if [[ ${found} -eq 0 ]]; then
  echo "No visible active jobs matched runner label '${runner_label}'." >&2
fi
