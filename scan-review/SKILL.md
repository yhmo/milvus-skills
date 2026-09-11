---
name: scan-review
description: Scan repositories in the milvus-io and zilliztech GitHub organizations, excluding milvus-io/milvus-storage, zilliztech/GPTCache, and zilliztech/claude-context, for recent open pull requests; skip closed or merged PRs, bots, and confirmed organization members; then run each eligible external-human PR through an isolated, certificate-validated pr-review workflow before producing a timestamped scan_*.md report. Use for deep batch reviews or recent external-contributor PR scans, with a default lookback of 24 hours.
---

# Scan Review

Scan both GitHub organizations deterministically, then orchestrate a standalone-quality `pr-review` for every eligible PR. Keep discovery/reporting in the scan agent and technical analysis in an isolated per-PR reviewer. Never trade review depth for batch throughput.

## GitHub Comment Language

- Require every GitHub-facing comment and reply produced during the scan to be written in English, including inline comments, fallback or top-level comments, code suggestions, questions, acknowledgements, and overall review messages.
- Apply this rule regardless of the user's language, the PR author's language, or the language already used in the discussion. Preserve only technically necessary code, identifiers, paths, and exact error messages in their original form.
- Pass this English-only requirement explicitly to every isolated or local `pr-review` invocation; do not rely only on inherited context.

## Prerequisites

0. **Locate the skill scripts without assuming a host directory.** Export the absolute path of this skill's base directory — the directory that directly contains both `SKILL.md` and `scripts/` — as `SKILL_DIR`. Most agents expose it when they load the skill (for example as a "Base directory" note); if the host does not, locate that directory yourself and run `export SKILL_DIR=<absolute-path>`. This skill is host-agnostic: never hardcode a `.codex`, `.opencode`, or any other agent-specific prefix. Every helper invocation below uses `"$SKILL_DIR/scripts/<name>"`.
1. Verify `gh`, `python3`, and GNU-compatible `date` are available.
2. Verify `gh auth status` succeeds. Organization membership checks only see memberships visible to the authenticated token; use a token with appropriate organization visibility when private membership must be recognized.
3. Resolve the `pr-review` skill from the available-skills catalog and read its `SKILL.md` completely before reviewing the first PR. Follow that skill exactly for every eligible PR, including posting and timing requirements.
4. Verify `scripts/validate_review_certificate.py` is present. A review without a valid certificate is incomplete and must never be reported as clean.

## Isolation and Completion Contract

- Process PRs sequentially.
- When subagents are available, create a fresh agent for each PR with no inherited conversation turns. Give it only the canonical PR URL, the certificate path, and instructions to use `pr-review` plus the matching repository skill. Instruct it to validate every PR-head code fact with `gh api` at the current head SHA; the local repository checkout (for example `$HOME/work/git-go/<repo>`, when present) is often behind the PR head and must not be trusted for what the current code does. Do not perform the technical review in the scan agent.
- Keep one reviewer assigned to one PR. Resume that reviewer only to finish missing steps or repair an invalid certificate; never give it another PR.
- When subagents are unavailable, run `pr-review` locally but use fresh per-PR notes, ledger, candidate list, and certificate files. State that context isolation was unavailable if the review ultimately fails validation.
- Require the reviewer to persist its changed-file ledger and write a JSON completion certificate after Step 11. Use the schema enforced by `scripts/validate_review_certificate.py`.
- Require the reviewer to read the validator source before starting and write the certificate itself from its persisted evidence. The scan agent must not manufacture or backfill a certificate from the reviewer's final prose.
- The certificate must prove: unchanged head SHA, exact changed/reviewed path equality, matching addition/deletion totals, Steps 1-11 complete, substantive Step 5 comment/doc inspection, a Step 7 behavior-to-evidence map, final severity counts, verified posted comments, and elapsed time.
- A zero-surviving-finding result must also record a completed challenge pass across comments/docs, test coverage, failure modes, concurrency, performance/maintainability, and redundancy.
- Treat elapsed time only as an audit signal. Never impose a minimum duration, but independently re-review a suspicious large clean result as described below.

Use a task shaped like this for each isolated reviewer:

```text
Use the pr-review skill to exhaustively review <PR_URL>. Start with no prior scan context.
Read the matching repository skill. Persist the changed-file ledger at <LEDGER_PATH>
and review notes at <NOTES_PATH>. Read $SKILL_DIR/scripts/validate_review_certificate.py,
then after Step 11 write its version-1 JSON certificate to <CERTIFICATE_PATH>.
Write every GitHub-facing review comment and reply in English.
Validate every PR-head code fact (changed files, hunks, helpers, tests) via gh api at the
current head SHA; do not rely on the local `$HOME/work/git-go` checkout when present, which may be behind
the PR head and mislead the review.
Do not return a clean result unless every changed path/hunk and Steps 1-11 are complete,
the zero-finding challenge is recorded when applicable, and posted comments are verified.
```

## Workflow

1. Interpret the requested time span. Default to `24 hours`. Accept values understood by GNU `date`, such as `90 minutes`, `2 days`, or `1 week`.
2. Create one run-specific temporary workspace and the final report. The report is the only scan artifact retained in the current working directory:

   ```bash
   scan_run_dir=$(mktemp -d "${TMPDIR:-/tmp}/scan-review.XXXXXX")
   report_path=$(python3 "$SKILL_DIR/scripts/report.py" new --output-dir "$PWD")
   ```

3. Discover eligible PRs:

   ```bash
   candidates_file="$scan_run_dir/candidates.tsv"
   "$SKILL_DIR/scripts/scan_recent_prs.sh" \
     --lookback "24 hours" \
     --output "$candidates_file"
   ```

   Replace `24 hours` with the user-provided span. The TSV output contains `pr_url`, `author`, `created_at`, `repo`, `state`, and `title`. The scanner enumerates visible repositories in `milvus-io` and `zilliztech`, skips `milvus-io/milvus-storage`, `zilliztech/GPTCache`, and `zilliztech/claude-context` before requesting their PRs, requests only currently open PRs from the remaining repositories, and excludes:
   - GitHub accounts whose PR author type is `Bot`.
   - Bot-style GitHub App logins ending in `[bot]`.
   - Known automation accounts implemented as normal GitHub users, currently `pymilvus-bot`.
   - Authors confirmed as members of either organization.

4. If scanning returns nonzero, do not claim complete organization coverage. Fix or retry the failed GitHub calls before starting reviews. Preserve the candidate and report files while retrying.
5. Process candidates in TSV order, one PR at a time. For each candidate:
   - Announce the canonical PR URL and progress as `current/total`.
   - Carry the candidate's `author` field through the review and report workflow. Use the exact GitHub login from the discovery TSV; do not derive a display name or omit the author when a review fails.
   - Immediately before reviewing, run `gh pr view "$pr_url" --json state --jq .state`. If the result is not `OPEN`, skip the PR without invoking `pr-review`; this catches PRs closed or merged after discovery.
   - Fetch the current PR metadata and paginated files with `gh api`; save the authoritative files JSON and head SHA for certificate validation.
   - Create a unique per-PR subdirectory under `$scan_run_dir`. Store the review ledger, notes, completion certificate, fetched metadata/files, diffs, payloads, response captures, timestamps, and all other working artifacts there. Never create these files or an `*_artifacts` directory in the user's current working directory.
   - Invoke `pr-review` in the isolated reviewer described above. Do not replace it with a shortened review, a custom batch review, or a summary-only task. The reviewer must visibly execute all numbered steps and inspect every changed path and hunk.
   - Let `pr-review` post its dedicated inline comments as required by its own workflow.
   - Refresh the PR metadata/files after the reviewer finishes, then validate the certificate against the refreshed head and files:

     ```bash
     python3 "$SKILL_DIR/scripts/validate_review_certificate.py" \
       --certificate "$certificate_path" \
       --files-json "$current_files_json" \
       --head-sha "$current_head_sha" \
       --pr-url "$pr_url"
     ```

   - If validation fails, do not accept or summarize the review. Give the same reviewer one bounded continuation to complete missing work and regenerate the certificate, then validate again. If it still fails, record `Failed: incomplete pr-review coverage` and continue to the next PR.
   - If the validated certificate reports zero surviving findings and the PR changes more than 5 files or more than 300 total lines, run one second independent `pr-review` in another fresh context. Validate its separate certificate too. This clean-result verification is mandatory; it is not a sampling pass. Combine newly posted findings and total wall-clock time across both passes.
   - Condense only validated outcomes into one table-cell-safe result, for example `No inline comments to post`, `No new inline comments; active threads cover the findings`, or `Posted 3 comments: High 1, Medium 2, Low 0`.
   - Use full scan-side wall-clock time for the PR, including retries and independent clean-result verification. If the review fails before a valid certificate exists, prefix the result with `Failed:`.
   - Append the row immediately:

     ```bash
     python3 "$SKILL_DIR/scripts/report.py" add \
       --report "$report_path" \
       --url "$pr_url" \
       --author "$author" \
       --result "$review_result" \
       --time-cost "$time_cost"
     ```

6. Continue after an individual PR review failure. Record the failure in that PR's row and proceed to the next candidate unless GitHub authentication or another global prerequisite is broken.
7. When no eligible PRs are found, leave the report with only its header and state that zero external-author PRs matched.
8. After all candidates finish and every report row is durable, delete `$scan_run_dir` with the guarded command below. Delete the workspace even when individual PR rows record `Failed:`; those PRs are retried from fresh artifacts on resume. If a global failure prevents completion of the report, retain the workspace temporarily and report its path instead of claiming completion.

   ```bash
   python3 "$SKILL_DIR/scripts/cleanup_workspace.py" "$scan_run_dir"
   ```

9. As the mandatory final terminal action after cleanup, print the complete Markdown table with `cat "$report_path"`, then provide the absolute report path. The report must have exactly these columns in this order: `PR URL`, `Author`, `Review results`, and `Time cost`.

## Resume Rules

- Treat existing rows in the report as completed work. Before resuming, compare candidate URLs with column one and skip URLs already recorded.
- A row whose `Review results` cell begins with `Failed:` is not completed review work. Retry it on resume and replace that row rather than skipping it.
- Recreate fresh per-PR artifacts when retrying a failed row; successful completed scan workspaces are deliberately deleted and are not part of resume state.
- Never append a second row for the same PR unless the user explicitly requests a re-review; if re-reviewing, replace the prior row manually rather than duplicating it.
- Keep failures visible in the final table. A failed review is not a successful review and must not be summarized as clean.

## Retention Contract

- Retain only the timestamped `scan_*.md` report after a completed scan.
- Remove candidate TSVs, ledgers, notes, certificates, metadata snapshots, diffs, payloads, response captures, and artifact directories before the final table is printed.
- Never delete user-provided files or directories. Cleanup applies only to the guarded `$scan_run_dir` created by this workflow.

## Bundled Scripts

- `scripts/scan_recent_prs.sh`: enumerate repositories except `milvus-io/milvus-storage`, `zilliztech/GPTCache`, and `zilliztech/claude-context`, find recently created open PRs, and filter bots plus organization members.
- `scripts/report.py`: create `scan_YYYYmmdd_HHMMSS.md` and safely append report rows.
- `scripts/validate_review_certificate.py`: reject incomplete, stale-head, partial-ledger, shallow-doc/test, or unverified-comment review results.
- `scripts/cleanup_workspace.py`: safely remove only a direct system-temporary-directory child whose name starts with `scan-review.`; reject arbitrary paths and symlinks.
