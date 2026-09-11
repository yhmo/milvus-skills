---
name: react-review
description: React to the authenticated reviewer's and automated AI-review bots' (GitHub Copilot, OpenAI Codex) unresolved inline threads either on one explicitly supplied open human-authored PR URL (organization membership allowed, no report written) or across recently created open external-human PRs in the milvus-io and zilliztech GitHub organizations, excluding milvus-io/milvus-storage, zilliztech/GPTCache, and zilliztech/claude-context from scan mode. Evaluate PR-author replies, agree and resolve when the author's position is reasonable, rebut unreasonable positions, verify claimed fixes against current code, and inspect every unanswered thread against the current head even when the author never replied. Use for requests such as "react-review https://github.com/milvus-io/milvus-sdk-rust/pull/133", "react-review in the past 48 hours", or "react-review since 2026-08-01".
---

# React Review

Target one external-author PR or scan recent external-author PRs deterministically, evaluate the authenticated GitHub user's and automated AI-review bots' open review threads conservatively, react to author reasoning, inspect unanswered threads against the current head regardless of reply or push evidence, and report cumulative thread status.

## GitHub Reply Language

- Always write every GitHub-facing comment and reply in English. This includes fix acknowledgements, agreements, rebuttals, clarification replies, and any other text posted into a review thread.
- Apply this rule regardless of the user's language, the PR author's language, or the language already used in the thread. Translate non-English draft prose before mutation; preserve only technically necessary code, identifiers, paths, and exact error messages in their original form.
- Require every non-null decision `reply_body` to be English before passing it to `resolve_thread.py`. If it is not English, rewrite it before applying the decision.

## Definitions

- Support two mutually exclusive target modes:
  - **Direct PR mode** when the request contains a canonical `https://github.com/(milvus-io|zilliztech)/REPO/pull/NUMBER` URL. Process only that PR; no creation-time cutoff applies.
  - **Scan mode** otherwise. Scan currently open PRs in `milvus-io` and `zilliztech`, excluding `milvus-io/milvus-storage`, `zilliztech/GPTCache`, and `zilliztech/claude-context`, whose `created_at` is strictly later than the selected cutoff.
- In scan mode, default to a `24 hours` lookback when the user supplies no time window.
- Direct PR mode requires the target to be currently open and authored by a human; organization membership is allowed. Scan mode still targets only external-human PRs.
- Treat an author as external only when they are not a bot and GitHub does not confirm membership in either organization. Internal authors are eligible in direct PR mode only and are excluded from the report.
- Derive the reviewer login from `gh api user --jq .login` at runtime. Do not hardcode or infer it from local Git configuration.
- Treat a review comment as one inline review thread whose root comment was posted by the reviewer login, by `Copilot` / `copilot-pull-request-reviewer`, or by `chatgpt-codex-connector`. Ignore threads initiated by every other account, even when the reviewer later replied.
- Treat a thread whose root comment was posted by `Copilot`, `copilot-pull-request-reviewer`, or `chatgpt-codex-connector` as an automated-review-owned thread. Automated-review-owned threads are evaluated, replied to, and resolved on the same evidence rules as reviewer-owned threads.
- Treat an author response as a later comment in that thread posted by the exact PR author login.
- Treat a top-level PR issue comment posted by the PR author that @-mentions the reviewer login or an automated review bot login as a **unified reply**. A unified reply is a single top-level comment that answers several review threads at once (typically a numbered list of points). The snapshot captures it in `unified_replies` (with URL, body, and creation time); it is not a member of any thread.
- Treat a thread as **addressed by a unified reply** when that comment's content clearly responds to the thread's subject (same path, function, point number, or explicit reference). An addressed thread is evaluated exactly as if the author replied inline; a thread not addressed by any unified reply keeps its no-author-reply treatment.
- Treat a comment as open when its review thread has `isResolved=false`. An outdated thread is still open until resolved.
- Detect code pushed after a comment by comparing the root comment's `originalCommit.oid` with the current PR `headRefOid`. A different non-empty SHA means the head changed after that comment; a missing SHA means the ordering is unknown and must not block inspection. Use `isOutdated` only as additional thread-level evidence.
- `Total comments` is the number of reviewer- or automated-review-initiated inline review threads on the PR at final snapshot time, including already resolved threads.
- `Fixed` is the number of those threads classified `fixed` during this run, whether or not GitHub permitted the reviewer to resolve them.
- `Closed comments` is the number of those threads whose final GitHub state is resolved, including threads resolved before or during the run.
- `Author` is the exact PR author login from the discovery row or final thread snapshot.

## Prerequisites

0. **Locate the skill scripts without assuming a host directory.** Export the absolute path of this skill's base directory — the directory that directly contains both `SKILL.md` and `scripts/` — as `SKILL_DIR`. Most agents expose it when they load the skill (for example as a "Base directory" note); if the host does not, locate that directory yourself and run `export SKILL_DIR=<absolute-path>`. This skill is host-agnostic: never hardcode a `.codex`, `.opencode`, or any other agent-specific prefix. Every helper invocation below uses `"$SKILL_DIR/scripts/<name>"`.
1. Verify `gh`, `python3`, GNU-compatible `date`, and GNU-compatible shell tools are available.
2. Verify `gh auth status` succeeds.
3. Run `reviewer=$(gh api user --jq .login)` and require a non-empty result. Use this exact login for discovery snapshots, thread ownership, acknowledgement replies, and live mutation guards. Automated review bots (Copilot / `copilot-pull-request-reviewer` / `chatgpt-codex-connector`) are additional accounts whose threads are in scope.
4. Use only `gh api` for GitHub reads and mutations.
5. Resolve and read the matching repository skill before evaluating a supported Milvus-family repository. Use `pr-review`'s repository routing table when available.

## Target Selection

Choose the target mode before creating snapshots or evaluating threads.

### Direct PR mode

When the request contains one canonical supported PR URL, do not enumerate organizations and do not apply the default lookback. Create the run workspace and resolve the URL into the same one-row candidate TSV shape used by scan mode:

```bash
react_run_dir=$(mktemp -d "${TMPDIR:-/tmp}/react-review.XXXXXX")
candidates_file="$react_run_dir/candidates.tsv"
python3 "$SKILL_DIR/scripts/direct_pr_candidate.py" \
  --url "$pr_url" \
  --output "$candidates_file"
```

The resolver rejects malformed or unsupported URLs, closed PRs, and bots/automation. It accepts any open human-authored PR regardless of organization membership and emits an `internal` column (`1` when the author is confirmed as a member of milvus-io or zilliztech, `0` otherwise). Internal-author PRs are processed, replied to, and resolved exactly like external ones, but they are never written into a report. Create the report only when the run contains at least one external candidate (`internal=0`); for an internal-only run leave `report_path` empty. Treat resolver failure as a target-selection failure; do not fall back to a broad scan.

If the user supplies both a PR URL and a time phrase, the explicit URL is authoritative and the time phrase is inapplicable because only that PR is targeted. Never add other PRs.

The repository exclusion applies to both scan mode and direct PR mode. Reject explicitly supplied PRs from `milvus-io/milvus-storage`, `zilliztech/GPTCache`, and `zilliztech/claude-context` during target resolution.

### Scan mode

Interpret the requested time constraint before discovery:

- For relative requests such as `react-review in the past 48 hours`, normalize the duration to `48 hours` and pass `--lookback "48 hours"`.
- For explicit cutoff requests such as `react-review since 2026-08-01 09:00`, pass `--since "2026-08-01 09:00"`. Timestamps without an explicit timezone are interpreted by GNU `date` in the local environment timezone.
- When the user supplies no time constraint, pass `--lookback "24 hours"`.
- Never widen or omit the requested cutoff. PRs created at or before the cutoff are out of scope and must not receive thread snapshots, semantic evaluation, mutations, or report rows.

Create one run-specific temporary workspace, create the final report, and scan the time-bounded set of currently open external-human PRs. The report is the only retained artifact:

```bash
react_run_dir=$(mktemp -d "${TMPDIR:-/tmp}/react-review.XXXXXX")
report_path=$(python3 "$SKILL_DIR/scripts/report.py" new)
candidates_file="$react_run_dir/candidates.tsv"
"$SKILL_DIR/scripts/scan_open_prs.sh" \
  --lookback "24 hours" \
  --output "$candidates_file"
```

Use `--since "$cutoff"` instead of `--lookback` for an explicit time point. The options are mutually exclusive.

Both target modes produce TSV fields `pr_url`, `author`, `created_at`, `repo`, `number`, `state`, `title`, and `internal` (scan mode always emits `0`). Scan discovery must skip `milvus-io/milvus-storage`, `zilliztech/GPTCache`, and `zilliztech/claude-context` before requesting their PRs. If discovery fails for any included repository, fix or retry it before evaluating threads; never claim complete coverage from a partial scan.

Store every thread snapshot, decision JSON, failure note, and other working artifact under `$react_run_dir`. Do not create `react_*_candidates.tsv`, `react_*_artifacts`, decision files, or review notes in the user's current working directory.

## Major Per-PR Workflow

Process PRs sequentially in TSV order. Direct PR mode has exactly one candidate and should be announced as `1/1`.

1. Announce progress as `current/total` and the canonical PR URL.
2. Capture a complete paginated thread snapshot:

   ```bash
   python3 "$SKILL_DIR/scripts/thread_snapshot.py" \
     --repo "$repo" \
     --number "$number" \
     --output "$snapshot_path"
   ```

   The snapshot also carries `unified_replies`: top-level issue comments posted by the PR author that @-mention the reviewer login or an automated review bot login. Every open thread must be checked against these before deciding whether the author replied.

3. Count all snapshot threads for `Total comments`. The snapshot already excludes threads rooted by neither the reviewer nor an automated review bot.
4. Skip the PR immediately when `Total comments == 0` or every reviewer- or automated-review-owned thread is already resolved.
5. Process every unresolved reviewer- or automated-review-owned thread against the snapshot head SHA. When subagents are available, use one fresh context per PR with no inherited conclusions. Give it the snapshot path, PR URL, and instructions to load the matching repository skill. Instruct it that PR-head code is read only from GitHub with `gh api` at the snapshot head SHA; the local repository checkout (for example `$HOME/work/git-go/<repo>`, when present) is often behind the PR head and must not be used to establish what the current code does. Keep all threads from one PR with the same evaluator so related changes are understood together. Instruct the evaluator to read the snapshot's `unified_replies` and treat every thread addressed by one as if the author replied inline.
6. Inspect, for every open thread:
   - the exact original comment (by the reviewer or an automated review bot) and every later PR-author reply, including any unified reply in `unified_replies` that addresses the thread;
   - the current diff and current version of the anchored file, fetched from GitHub at the snapshot head SHA (never from a local checkout);
   - enclosing functions plus directly relevant helpers, tests, commits, and linked issue/spec context;
   - whether the reply describes committed code or merely promises future work;
   - whether the current head actually removes the core correctness, compatibility, safety, performance, or maintainability risk.
7. Choose the branch below.

### Author replied

Read the exact PR-author reply and independently check its reasoning. This includes a unified reply that addresses the thread: read its body from `unified_replies` and treat it as the author's response to every thread it addresses.

- If the author says the issue is fixed, inspect the latest code. Use `fixed` only when the core issue is actually removed; a promise, separate PR, or partial symptom fix is insufficient.
- If the author argues that it is not a bug or does not need a change, trace the behavior and relevant contract:
  - Use `author_reasonable` when the author's position is sound. Post agreement and resolve the thread when permitted.
  - Use `author_unreasonable` when the position is unsound. Post a concise, evidence-backed rebuttal that explains the remaining concrete failure and leave the thread unresolved.
- If the author claims a fix but the latest code still permits the original failure, use `author_unreasonable`, explain the current-code evidence, and leave it unresolved.
- If the response only promises future work or points to an unmerged separate PR, leave the thread unresolved. Reply only when clarification is needed; do not classify it as fixed.

### No author reply

Inspect every open unanswered thread against the current head instead of skipping it based on reply state.

- A thread **addressed by a unified reply is not unanswered**: evaluate it under the "Author replied" branch using the unified reply as the author's response, even though the reply lives in a top-level comment rather than in the thread. Only threads not addressed by any unified reply follow the rules below.
- If the root comment's `originalCommit` SHA is present and equals the current head SHA, the reviewed code is unchanged, so a fix cannot be confirmed; leave the thread open and post nothing.
- Otherwise inspect the latest corresponding code at the snapshot head SHA, even when `head_changed_since_comment=false` or `isOutdated=false`. A missing `originalCommit` SHA must not block this inspection.
  - Use `fixed` and close the thread when the current head removes the core issue.
  - Otherwise leave the thread open and post nothing.

8. Persist one version-2 decision JSON for each action. Do not create a decision for skipped or still-open unanswered threads. Use this exact schema:

   ```json
   {
     "version": 2,
     "pr_url": "https://github.com/OWNER/REPO/pull/123",
     "thread_id": "PRRT_...",
     "head_sha": "...",
     "decision": "fixed",
     "trigger_kind": "author_reply",
     "trigger_url": "https://github.com/...#discussion_r...",
     "root_original_commit_sha": "...",
     "reply_body": null,
     "evidence": "Concrete explanation of the current-code evidence",
     "inspected_paths": ["path/to/file.py", "tests/path/test_file.py"]
   }
   ```

   Allowed combinations:

   - `fixed` + `author_reply`: verified fix claimed or described by the author.
   - `fixed` + `head_update`: verified fix found in the current head for an unanswered comment; set `trigger_url` to `null`.
   - `author_reasonable` + `author_reply`: sound explanation that no change is required.
   - `author_unreasonable` + `author_reply`: unsound explanation or false fix claim; put the concise evidence-backed rebuttal in `reply_body`.

   For an `author_reply` trigger, `trigger_url` may be either a thread-inline author reply URL or a unified-reply top-level comment URL from `unified_replies`; `resolve_thread.py` accepts both and re-verifies the unified reply live before mutating.

   Set `reply_body` to `null` except for `author_unreasonable`. Write every non-null `reply_body` in English. Never put insults, speculation about intent, or generic demands in a rebuttal.

9. Apply the decision through the guarded mutation helper. Do not ask for per-thread confirmation after the evidence gate passes:

   ```bash
   python3 "$SKILL_DIR/scripts/resolve_thread.py" \
     --snapshot "$snapshot_path" \
     --decision "$decision_path"
   ```

   The helper rechecks the authenticated viewer, `viewerCanReply`, `viewerCanResolve`, PR head, root owner (the reviewer or an automated review bot), exact PR-author reply, and unresolved state immediately before mutation.

   - `fixed`: post `The issue is confirmed fixed. Resolving this conversation.` and resolve when permitted; otherwise post `The issue is confirmed fixed.` when replying is permitted.
   - `author_reasonable`: post `Thanks for the clarification. I agree that no change is needed here. Resolving this conversation.` and resolve when permitted; otherwise omit the final resolving sentence.
   - `author_unreasonable`: post the exact evidence-backed `reply_body` and never resolve.
   - When `viewerCanReply=false`, post nothing. A false `viewerCanResolve` blocks only resolution, not a permitted reply.

   All actions are idempotent for the same trigger. If the helper rejects the decision, do not bypass it with manual mutations.
10. After all candidate threads on the PR are processed, fetch a new snapshot. Compute `Total comments` and `Closed comments` from this final snapshot. Compute `Fixed` by counting the version-2 decision JSONs for this PR whose `decision` is `fixed`; include fixed decisions even when `viewerCanResolve=false` left the thread open. Append the row only when the PR is external (`internal=0`), the report exists, and the initial snapshot contained at least one unresolved reviewer- or automated-review-owned thread. Omit internal PRs (`internal=1`), PRs that had no reviewer- or automated-review-owned comments, and PRs whose reviewer- or automated-review-owned comments were already all resolved before this run:

    ```bash
    python3 "$SKILL_DIR/scripts/report.py" add \
      --report "$report_path" \
      --url "$pr_url" \
      --author "$author" \
      --total-comments "$total_comments" \
      --fixed-comments "$fixed_comments" \
      --closed-comments "$closed_comments"
    ```

11. Continue after an individual thread evaluation or resolution failure. Leave that thread unresolved and keep the failure in the working notes; never count a failed mutation as closed.

## Evidence and Mutation Rules

- Prefer current-head code over the prose response when they conflict.
- **Read PR-head code from GitHub, never from a local checkout.** Fetch the current version of every changed file, anchored file, helper, and test with `gh api` (contents/raw at the snapshot head SHA). The local checkout (for example `$HOME/work/git-go/<repo>`, when present) preferred by repository skills is frequently behind the PR head, so code read from it can mislead the decision even when the hunk itself was fetched correctly. You may use the local checkout only for repository-wide navigation aids (package layout, symbol index) that are not facts about the head; any fact that influences a `fixed`/`author_reasonable`/`author_unreasonable` verdict must be verified at the head SHA from GitHub first.
- Treat an outdated anchor as a navigation hint; find the corresponding current code before deciding.
- A passing test claimed in prose is supporting evidence, not proof. Read the test and implementation.
- Do not run builds or tests unless the user explicitly asks. Review through code, commits, tests, and documentation reads.
- Do not post reviews, reactions, top-level comments, or unrelated replies. Responses to a unified reply are still posted inline in the affected thread through `resolve_thread.py`, never as new top-level comments. Mutate only threads owned by the reviewer or an automated review bot through `resolve_thread.py`: acknowledge verified fixes, agree with reasonable author positions, post evidence-backed rebuttals to unreasonable author positions, and resolve only `fixed` or `author_reasonable` decisions when `viewerCanResolve=true`.
- Never resolve on uncertainty. False negatives are safer than closing a still-valid issue.

## Final Report

Internal-author PRs (direct mode) never produce report rows, so a run whose candidates are all internal (`internal=1`) has no report file. Such a run still processes every thread normally; after cleanup, its final terminal action is a concise per-PR summary listing each PR URL and its thread outcomes (processed / fixed / closed) instead of a `cat`.

After every candidate PR is processed and all report rows (for external candidates) are durable, delete `$react_run_dir` with a guard that permits deletion only for the `react-review.XXXXXX` temporary-directory template. Delete it even when individual thread actions failed and were recorded as still open. If a global failure prevents the scan from completing, retain the workspace temporarily and report its absolute path instead of claiming completion.

```bash
python3 "$SKILL_DIR/scripts/cleanup_workspace.py" "$react_run_dir"
```

After the report file has been generated and all processing is complete, the mandatory final terminal action (after cleanup) is to show that report's complete Markdown table directly on the terminal with this exact command:

```bash
cat "$report_path"
```

Do not replace the terminal table with a summary, a separately reconstructed table, or a partial excerpt. The report generator must create the file directly in the current working directory before the final `cat` command runs. Its filename must use the form `react_YYYYmmdd_HHMMSS.md`; if that exact second already exists, append a numeric suffix without changing the `react_` plus timestamp prefix. The report must contain exactly these columns in this order: `PR URL`, `Author`, `Total comments`, `Fixed`, and `Closed comments`. Every data row must represent an external-author PR that had at least one open reviewer- or automated-review-owned comment at the start of the run. If no PR qualifies, print the header-only table, then provide the report's absolute path.

Retain only the timestamped `react_*.md` report after a completed run. Remove candidate TSVs, snapshots, decisions, notes, and artifact directories before printing the final table. Never delete user-provided paths; cleanup applies only to the guarded `$react_run_dir` created by this workflow.

## Bundled Scripts

- `scripts/direct_pr_candidate.py`: validate one canonical supported PR URL, require an open human-authored PR (organization members allowed, bots rejected), emit the standard one-row candidate TSV for direct PR mode with an `internal` column, and reject PRs from excluded repositories.
- `scripts/scan_open_prs.sh`: enumerate both organizations except `milvus-io/milvus-storage`, `zilliztech/GPTCache`, and `zilliztech/claude-context` and filter open PRs by creation cutoff, bot status, and organization membership; accepts mutually exclusive `--lookback` and `--since` options and defaults to `--lookback "24 hours"`.
- `scripts/thread_snapshot.py`: fetch all review threads/comments, root comment commit SHAs, and viewer reply/resolve capabilities with GraphQL pagination; retain only threads initiated by the reviewer or an automated review bot (`Copilot` / `copilot-pull-request-reviewer` / `chatgpt-codex-connector`) and compute `head_changed_since_comment`; also capture the PR author's top-level issue comments that @-mention the reviewer or an automated review bot as `unified_replies`.
- `scripts/resolve_thread.py`: validate a version-2 decision against live GitHub state, post the appropriate idempotent acknowledgement/agreement/rebuttal, and resolve only eligible decisions when permitted; accepts both thread-inline author replies and unified-reply top-level comments as qualifying `author_reply` triggers.
- `scripts/report.py`: create `react_YYYYmmdd_HHMMSS.md` in the current working directory and append qualifying rows to the five-column Markdown report (`PR URL`, `Author`, `Total comments`, `Fixed`, `Closed comments`).
- `scripts/cleanup_workspace.py`: safely remove only a direct system-temporary-directory child whose name starts with `react-review.`; reject arbitrary paths and symlinks.
