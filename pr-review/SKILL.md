---
name: pr-review
description: Exhaustively review GitHub pull requests with complete changed-file and diff-hunk accounting, using gh api for GitHub data and posting dedicated inline comments; loads matching repository skills for supported Milvus-family repositories.
---

# GitHub PR Review

## Overview

Workflow for reviewing GitHub pull requests using `gh api` only to read PR metadata, inspect diffs, and create reviews with code suggestions. **Always use Dedicated Inline Comment**

**Never use `gh pr view` in this skill.** Use `gh api repos/:owner/:repo/pulls/<PR_NUMBER>` for PR metadata and `gh api repos/:owner/:repo/pulls/<PR_NUMBER>/files --paginate` for diff data.

**For Dedicated Inline Comments, post directly after validating anchors.** Do not ask for confirmation before posting review.

**Always write every GitHub-facing review comment and reply in English.** This includes dedicated inline comments, fallback or top-level comments, code suggestions, questions, acknowledgements, and any overall review message posted to the PR. Apply this rule regardless of the user's language, the PR author's language, or the language already used in the thread. Translate any quoted or drafted non-English wording before posting; preserve code, identifiers, paths, and exact error messages when technically necessary.


## When to Use

- Reviewing pull requests
- Adding code suggestions to PRs
- Posting review comments with the gh CLI

Examples:
- `pr-review the pr: https://github.com/foo/bar/pull/123`
- `pr-review this pr: https://github.com/foo/bar/pull/123`
- `pr-review https://github.com/foo/bar/pull/123`

## Prerequisites

**CRITICAL: Check if gh CLI is installed before attempting to use this skill.**

### Locate the skill scripts

Export the absolute path of this skill's base directory — the directory that directly contains both `SKILL.md` and `scripts/` — as `SKILL_DIR`. Most agents expose it when they load the skill (for example as a "Base directory" note); if the host does not, locate that directory yourself and run `export SKILL_DIR=<absolute-path>`. This skill is host-agnostic: never hardcode a `.codex`, `.opencode`, or other agent-specific prefix. Every helper invocation below uses `"$SKILL_DIR/scripts/<name>"`.

### Check for gh CLI

Before starting any PR review workflow, verify the gh CLI is available:

```bash
gh --version
```

**If gh is not installed:**

1. **Stop immediately** - Do not attempt to run gh api commands
2. **Inform the user** with this message:

```
The GitHub CLI (gh) is required for this skill but is not installed.

Please install it from: https://cli.github.com/

Installation options:
- macOS: brew install gh
- Windows: winget install GitHub.cli
- Linux: See https://cli.github.com/ for your distro

After installing, authenticate with:
  gh auth login

Then try your PR review request again.
```

3. **Do not proceed** with the review workflow until gh is installed

### After Installation

Once gh is installed, users must authenticate:
```bash
gh auth login
```

## Milvus Repository Routing

Before Step 1, inspect the PR metadata and try to load the matching repository skill when the PR belongs to a supported Milvus-family repository. This routing is mandatory when the matching skill is available.

1. Read `base.repo.full_name` from `gh api repos/:owner/:repo/pulls/<PR_NUMBER>`; do not infer the repository only from the current directory.
2. Use this mapping:
   - `milvus-io/milvus` -> `milvus`
   - `milvus-io/milvus-sdk-cpp` -> `milvus-sdk-cpp`
   - `milvus-io/milvus-sdk-csharp` -> `milvus-sdk-csharp`
   - `milvus-io/milvus-sdk-node` -> `milvus-sdk-node`
   - `milvus-io/milvus-sdk-java` -> `milvus-sdk-java`
   - `milvus-io/milvus-sdk-rust` -> `milvus-sdk-rust`
   - `milvus-io/pymilvus` -> `pymilvus`
   - `milvus-io/conanfiles` -> `milvus-conanfiles`
   - `milvus-io/milvus-storage` -> `milvus-storage`
   - `milvus-io/birdwatcher` -> `birdwatcher`
   - `zilliztech/milvus-common` -> `milvus-common`
   - `zilliztech/knowhere` -> `knowhere`
   - `zilliztech/cardinal` -> `cardinal`
   - `zilliztech/VectorDBBench` -> `vectordbbench`
3. Resolve the skill from the available-skills catalog and use its declared locator. If it is not listed there, try `<skills-root>/<skill-name>/SKILL.md` as a filesystem fallback, where `<skills-root>` is the directory that directly contains this skill (`$(dirname "$SKILL_DIR")` when `$SKILL_DIR` is the base directory of `pr-review` itself; never hardcode a `.codex`, `.opencode`, or other agent-specific prefix). Read the matching `SKILL.md` completely before technical review actions and follow its repository-specific architecture, compatibility, history, and code-reading guidance.
4. Record which repository skill was loaded. If the mapped skill is unavailable or unreadable, record that briefly and continue with this skill's workflow rather than stopping the review.

For local surrounding-code and history context, prefer the matching checkout when present on this machine (for example, `$HOME/work/git-go/milvus-sdk-cpp`). Confirm it is the expected Git repository before using it.

- Use the local checkout for fast `rg`, file reads, project structure, nearby code, and read-only history inspection. The checkout is frequently behind the GitHub head; use it only for navigation and supporting context, never as the source of truth for the current head.
- Do not fetch, pull, switch branches, reset, clean, or otherwise modify the checkout as part of review.
- Do not assume the checkout matches the PR head or target branch. Fetch every changed file, anchored file, helper, and test at the current head SHA with `gh api` before citing its content in a finding. Validate changed code, line anchors, branch-local symbols, and PR metadata with `gh api`.
- `gh api only` means all GitHub reads and writes must use `gh api`; it does not prohibit read-only inspection of the matching local checkout.
- This `pr-review` skill remains authoritative for the 12-step workflow, COMMENT-only behavior, anchor validation, and posting format. The repository skill supplies domain-specific technical guidance. Do not build or run tests when this skill prohibits them, even if the repository skill documents build/test commands.

## Core Workflow

### Working artifacts and cleanup

- For a standalone review, create one run-specific workspace with `review_run_dir=$(mktemp -d "${TMPDIR:-/tmp}/pr-review.XXXXXX")`. Store the changed-file ledger, review notes, candidate list, fetched metadata/diffs, request payloads, response captures, certificates, and every other non-final artifact inside this directory. Do not create `review*notes*`, `pr*review*`, candidate, ledger, or artifact files in the user's current working directory.
- When an orchestrator such as `scan-review` supplies explicit ledger, notes, or certificate paths, treat those paths as caller-owned. Write only to those paths and do not delete them; the orchestrator performs cleanup after validation.
- After a standalone review completes Step 11, verifies every posted comment, records the end time, and passes the completion check, delete the standalone workspace before sending the final response. Guard deletion so only the directory created from the `pr-review.XXXXXX` template can be removed.
- If the review is interrupted or genuinely incomplete, retain the workspace for resumption and report its absolute path. It is not a successful completed review until the workspace is either cleaned or explicitly handed off for resumption.

Use this guarded cleanup for a successful standalone run:

```bash
python3 "$SKILL_DIR/scripts/cleanup_workspace.py" "$review_run_dir"
```

### Exhaustive coverage contract

Treat every review as exhaustive unless the user explicitly limits the scope. Review duration, PR size, context pressure, and the apparent simplicity of a file are never reasons to sample or stop early.

- Build a changed-file ledger before technical analysis. Record every path, change status, additions, deletions, and review state.
- Inspect every changed file and every changed hunk. For a newly added text file, inspect the complete file. For a deleted file, inspect the deleted content or its base version. For a rename, inspect both the rename relationship and all content changes.
- Read enclosing functions/declarations and direct providers as required below, but keep the dependency graph bounded. Exhaustive coverage applies to the PR diff; it does not require recursively reviewing the entire repository.
- Never infer coverage from a summary, file outline, search result, or risk scan alone. Those tools may prioritize reading, but each ledger entry must also receive direct diff/full-file inspection and a recorded disposition.
- When GitHub omits or truncates a patch, recover the exact content from a checkout whose base/head commits are verified, or fetch base/head file contents with `gh api` and compute/inspect the diff locally. Do not treat a missing API patch as reviewed.
- Generated, vendored, binary, lock, or machine-produced files still require a ledger entry. Inspect the generator/input/provenance and run deterministic structural or integrity checks appropriate to the artifact; record why line-by-line semantic review is not meaningful when applicable.
- Persist the ledger and candidate/open-question lists outside transient model context so a long review can resume without losing coverage state.
- Report progress as `reviewed/total changed files` at module boundaries. Do not claim completion while any path or hunk remains unaccounted for.
- Before Step 9, verify that the reviewed path set exactly equals the current PR changed-file set and that aggregate additions/deletions match the authoritative diff. Resolve renames and refresh the PR head before closing the gate.
- Time is not a stopping condition. Continue across long runs or context compaction until Steps 1-12 and the 100% coverage gate are complete.

### Provider rate-limit concurrency budget

Before starting Step 1, probe the active model provider's per-key request quota and derive a concurrency budget for any subagent delegation. Do this once at the start of the review; reuse the recorded budget if the workflow is resumed.

If the environment variable `PR_REVIEW_CONCURRENCY` is set to a positive integer, use it directly as `N`, record that the budget came from the override, and skip the probe entirely.

1. Resolve the provider base URL and API key from the active agent configuration:
   - codex: read `~/.codex/config.toml` `[model_providers.*]` `base_url` (strip a trailing `/v1`) and `experimental_bearer_token`; if no bearer token is present, read the key from `apiKeys.codexEnvVar` or `OPENAI_API_KEY`.
   - opencode: read `~/.config/opencode/opencode.json` `provider.*.options.baseURL` and `provider.*.options.apiKey`.
   - If the key is not directly readable (e.g. injected via `OPENCODE_CONFIG_CONTENT`), print the masked value and use whatever key is active for the run.
2. Send one minimal probe request and capture response headers:
   ```bash
   curl -sS -D - -o /dev/null --max-time 15 "https://<BASE_URL>/chat/completions" \
     -H "Authorization: Bearer <API_KEY>" -H "Content-Type: application/json" \
     -d '{"model":"<MODEL_ID>","messages":[{"role":"user","content":"hi"}],"max_tokens":4}'
   ```
   Use the actual model ID the review will run with when it is known; otherwise use the provider default.
3. Read the rate-limit headers from the response (case-insensitive). Primary header for this deployment: `x-ratelimit-api_key-remaining-requests`; also read `x-ratelimit-api_key-limit-requests`. Fallbacks if absent: any `x-ratelimit-*-remaining-requests`, then `x-ratelimit-remaining-requests`. If the response is HTTP 429, treat remaining as `0`.
4. Compute the concurrency budget: `N = max(1, min(10, floor(remaining / 4)))`, where `remaining` is the per-key remaining request count.
5. Record `N` in the running review notes, then whenever you delegate work to parallel subagents (e.g. `@general` task fan-out for large PRs), obey this instruction verbatim: **"At most N concurrent subtasks; start the next only after the previous one completes."**, replacing `N` with the computed value.
6. If the provider headers cannot be obtained, default `N = 2` and proceed; do not block the review on the probe.

Example: `x-ratelimit-api_key-remaining-requests: 29` → `N = min(10, floor(29/4)) = 7` → prompt subagents with "At most 7 concurrent subtasks; start the next only after the previous one completes."

### Review timing

- Immediately before starting Step 1, record the review start time as Unix epoch seconds with `date +%s` and keep the value in the running review notes.
- Before starting Step 1, also run the provider rate-limit probe above and record the derived concurrency budget `N` in the running review notes.
- Immediately after Step 11 finishes, including inline-comment attachment verification or the explicit zero-comment outcome, record the end time with `date +%s` and calculate `elapsed_seconds = end_time - start_time`.
- Record the canonical PR URL from the PR metadata `html_url` field for the final completion summary.
- Measure the full wall-clock review duration. Do not estimate the time cost from individual tool-call durations or token usage.
- Format the elapsed time as `Time cost: Xm Ys` in the final review summary. Use `0m Ys` for reviews shorter than one minute. On the immediately following line, print `PR URL: <PR_HTML_URL>` using the canonical URL recorded from PR metadata.
- If a review is resumed after an interruption, retain the original start time when it is available so the reported time reflects the complete review workflow. If it is unavailable, start timing when the review resumes and label the timing line `Time cost after resume: Xm Ys`; still print the `PR URL: <PR_HTML_URL>` line immediately after it.

**Run gates (A-G) — do not skip.** These are wrapper gates around the 12-step Review Workflow below. Gates are lettered, never numbered, so every "Step N" reference in this document unambiguously means the Review Workflow.

- **Gate A — gh CLI ready**: run `gh --version` (see Prerequisites).
- **Gate B — PR metadata fetched**: via `gh api repos/:owner/:repo/pulls/<PR_NUMBER>` (executed at Step 1).
- **Gate C — linked context opened**: directly linked issues, PRs, design documents, specifications, and dependency changes inspected before technical review (see Linked-resource context collection; feeds Step 1).
- **Gate D — repository routed**: for supported Milvus-family repositories, the mapped repository skill and local checkout are loaded (see Milvus Repository Routing; feeds Steps 1-2).
- **Gate E — Review Workflow executed**: Steps 1-12 in order, each with evidence.
- **Gate F — anchors validated**: every `(path, line, side)` confirmed in the current PR diff (part of Step 11 preflight).
- **Gate G — review posted and verified**: threshold applied, comments posted, attachment fields verified (Step 12).

### Review Workflow

The workflow has exactly twelve numbered steps. Steps 1-10 analyze and filter; Step 11 generates and preflights the final comments; Step 12 applies the posting threshold, posts, verifies attachment, and produces the final summary. The review is complete only after Step 12.

Execute the review workflow strictly in order. Do not collapse multiple numbered steps into a single catch-all pass. Complete Step 1 before Step 2, Step 2 before Step 3, and so on through Step 12.

#### Required surrounding-code reads

Do not rely on patch hunks alone for non-trivial files.
For each non-trivial changed source or test file, read at least:
1. the full enclosing function or method for each changed hunk,
2. the nearest declaration/header for changed public or cross-file symbols,
3. at least one directly related helper/provider/sibling implementation when the changed code references newly introduced symbols or helpers.

If the diff adds a new include, helper call, namespace-qualified symbol, singleton accessor, fixture utility, or test-only helper, verify that the provider exists on the PR branch context before concluding the change is valid. For release-branch PRs, do not assume APIs available on `master` exist on the target branch.

These surrounding-code checks are bounded, not recursive. Read the most relevant direct dependencies first and follow dependency edges only one layer deep by default. For each changed file, inspect up to 2-3 directly relevant provider/sibling/declaration files by default unless the PR clearly warrants deeper inspection.

If a provider, header, or symbol cannot be confirmed after those bounded checks, record the uncertainty as evidence and continue; do not keep searching indefinitely. Additional surrounding-code checks strengthen existing review steps, but they do not replace them and must not delay or block later numbered steps once the bounded checks for the current step are complete.

Operational requirements for explicit step-by-step execution:
- Create one task for each major step or sub-phase you actually perform, and keep task status current.
- Before each numbered step, write a short progress update naming that step.
- After each numbered step, briefly record the outcome: no findings, candidate findings added, or candidate findings discarded.
- Execute and report every numbered step from Step 1 through Step 12 even when the final result is `no inline comments to post`.
- Do not stop the workflow early just because the candidate list is empty or all candidates were discarded; instead, explicitly continue through the remaining steps and record why they ended with no surviving comments.
- When there are no surviving findings, Steps 8-12 must still be visible in the run history: Step 8 should state whether any redundant-change candidates were found, Step 9 should state that zero findings survived confidence/dedup, Step 11 should state that zero final comments were generated, and Step 12 should state that zero comments met the posting threshold.
- The final conclusion `no inline comments to post` is allowed only after the workflow has explicitly completed Step 12.
- Maintain a shared candidate issue list throughout Steps 2-8.
- Maintain a separate running notes / open-questions list during Steps 1-8. Use it to capture confusions, hypotheses, edge cases, and test questions that may be resolved later. Only promote an item from this notes list into the candidate issue list once it survives later inspection and is concrete enough to defend publicly.
- Across Steps 3-9, explicitly accumulate evidence from all three review levels: local code quality, system integration impact, and long-term maintainability. In each step note, record which of those levels the step materially exercised and why the others were less relevant for that step. Before closing Step 9, confirm that all three levels were covered somewhere in the review, or explicitly state why one was genuinely not applicable to this PR.
- Treat concrete performance and maintainability issues as first-class review findings, not merely optional polish, when they are specific, actionable, and tied to changed lines.
- In Step 1 and again before closing Step 9, record one explicit macro conclusion and one explicit micro conclusion. The macro conclusion must address intent, flow, and scope; the micro conclusion must address implementation correctness, readability, and internal consistency.
- For non-trivial PRs, record the planned pass order at the end of Step 1 using these labels: `architecture/design fit`, `implementation correctness`, and `polish/tests/docs`. If you depart from that order, state why in the next step note.
- Carefully execute every rule under Steps 1-9. Treat each bullet in those steps as required unless it is genuinely not applicable to the current PR, and when it is not applicable, explicitly say why.
- Treat Steps 3-9 as independent review lenses, not as a single rolling confirmation pass. A later step must make a fresh attempt to surface findings from its own angle even when earlier candidates were discarded.
- Never let the collapse of one candidate reduce scrutiny in later steps. If an early hypothesis is disproved, reset and continue the remaining steps at full depth.
- For every Step 3-9 completion note, include concrete evidence of work performed: files, functions, tests, history, comments, or examples inspected from that step's perspective. A step is not complete just because it produced zero findings.
- Small, single-file, example-only, or seemingly low-risk PRs still require each Step 3-9 lens to be applied. Size may affect ordering, but never changed-file, changed-hunk, or review-lens coverage.
- Do not conclude that a PR is clean merely because no correctness bug survived. Performance, maintainability, docs/comments, failure modes, test coverage, and redundancy must each receive explicit consideration before Step 9. Before closing Step 9, explicitly list the disposition of each of those non-correctness categories as `survived as finding`, `checked and discarded on evidence`, or `not applicable`.
- Do not post any GitHub comment until Steps 9-11 are complete.
- Do not send a user-facing review conclusion, finding summary, or "I found X" result before Steps 11 and 12 are complete. A surviving candidate in Step 9 is not a finished review.
- Treat Step 11 as the only valid stopping point for a completed `pr-review` run. If the workflow is interrupted after analysis, resume at the next incomplete numbered step rather than reporting partial results as the final outcome.
- Use the task list as a hard completion gate: if any Step 11 or Step 12 task is still `pending` or `in_progress`, continue the workflow instead of concluding the review.
- Before any final user-facing completion message, run an explicit completion check: confirm Steps 1-12 are complete, confirm Step 11 generated the final comment set (or explicitly recorded zero generated comments), and confirm Step 12 posted and verified every surviving comment (or explicitly recorded zero posted comments).
- For standalone runs, confirm the run-specific temporary workspace was deleted after all evidence was consumed. For orchestrated runs, confirm artifact ownership was handed back to the caller instead of deleting caller-owned paths.
- If a step does not apply, explicitly say why it does not apply instead of silently skipping it.
- At the end of Step 1, record risk-priority triage based on size, public API impact, module sensitivity, data/compatibility risk, and reversibility of mistakes. Triage controls review order and where extra surrounding-context depth is spent; it never permits a light pass, sampling, or reduced diff coverage.
- Use question-oriented probing during analysis: explicitly ask what assumptions the code is making, what would happen if an input or dependency is empty/stale/malformed, and whether the surrounding tests actually prove the intended behavior. In each of Steps 3-8, write down at least one explicit probe question from that step’s lens and record the answer or unresolved status.
- Before marking Steps 3-8 complete, record one sentence beginning with `This step specifically tried to falsify/confirm:`. That sentence should name a concrete behavior, file, function, test, history artifact, or scenario that this step examined from its own lens; if the step did not surface a materially new target, say so explicitly and state why the step still produced useful confirmation rather than silently stalling.
- Before declaring Step 9 complete, ask: "Did I keep at least one independent maintainability/performance/docs/tests/failure-modes line of inquiry alive long enough to rule it in or out on evidence, rather than on momentum from earlier steps?"

#### Linked-resource context collection

Perform this during Step 1, after fetching PR metadata and before summarizing intent or beginning technical review.

- Extract directly linked resources from the PR title and body, including full GitHub URLs, same-repository references such as `#123`, cross-repository references such as `owner/repo#123`, closing references, design documents, specifications, dependency upgrades, and implementation PRs.
- Query GitHub relationship data when available to find issues explicitly linked or closed by the PR instead of relying only on text parsing.
- Open each relevant directly linked GitHub issue or PR with `gh api`. If an `/issues/<number>` response contains `pull_request`, fetch the corresponding pull metadata and files/discussion needed to understand it as a PR.
- For linked PRs, inspect at least the title, body, state, base/head context, changed-file summary, and relevant discussion or diff portions. For linked issues, inspect at least the title, body, state, labels, and relevant comments.
- For linked design documents, specifications, or source files, read the sections that define the changed behavior, wire/API contract, compatibility requirements, limitations, or testing expectations.
- Follow links one level deep by default. Do not recursively browse tangential references. Prioritize the closing issue, stated design/specification, server or counterpart implementation, and dependency/proto change that the PR relies on.
- Treat generated session links, generic home pages, badges, and unrelated references as non-review context unless the PR explicitly makes them part of the implementation contract.
- Use `gh api` for every GitHub read. For a relevant non-GitHub link, use an available read-only fetch mechanism; if none is available, record it as inaccessible rather than silently skipping it.
- Record every linked resource inspected, the concrete motivation/acceptance criteria/compatibility constraint it contributed, and every relevant resource that was inaccessible or intentionally skipped with a reason.
- If linked context contradicts the PR description or changed code, add the discrepancy to the candidate issue list before proceeding.
- Do not let a large number of links stall the review. After the directly relevant one-hop resources are covered, record the remaining links as lower priority and continue the numbered workflow.

#### Review Steps

1. **Summarize the PR**
Fetch PR metadata with `gh api repos/:owner/:repo/pulls/<PR_NUMBER>` and summarize the changed files, overall intent, intended user/business flow, and risk areas before deeper review.
- Fetch the commit list with `gh api repos/:owner/:repo/pulls/<PR_NUMBER>/commits`. For Milvus-family repositories, apply the commit-hygiene rule: each PR must contain exactly one commit, and every commit must carry a `Signed-off-by:` trailer. For other repositories, check the repository's own `CONTRIBUTING.md`, DCO configuration, or commit-convention docs, and apply its stated commit conventions when they exist. Add a `Low` candidate when a stated convention is violated, unless the user explicitly scoped the review away from commit hygiene.
- Fetch CI context with `gh api repos/:owner/:repo/commits/<HEAD_SHA>/check-runs` plus `.../status`. Record failing or pending checks as review context; when a red check maps to changed files, name it in the risk-priority triage. Do not treat green CI as evidence of correctness.
- For draft PRs, proceed with the review normally: record the draft status in the Step 1 summary and in the final review message, and phrase findings as early feedback rather than merge-blocking when the draft clearly indicates ongoing work.
- Run the generated-file heuristic on the changed-file list before deep review: intersect it with the repository's committed generated-output locations — pymilvus `pymilvus/grpc_gen/*_pb2*.py` and `*.pyi`; milvus `internal/mocks/` and `mock_*.go`; milvus `client/milvusclient/mock_milvus_server_test.go`; milvus-sdk-node `milvus/proto-json/*.ts`; generic patterns such as `*_pb2.py`, `*.pb.go`, `mock_*.go`, and `gen*/` or `generated*/` directories; plus any path the loaded repository skill, `AGENTS.md`, or `CLAUDE.md` marks as generated. Add a candidate finding for hand-edits to generated files unless the PR also changes the generator inputs or explicitly regenerates output; when a generic-pattern match is uncertain for the repository, phrase the candidate as a question rather than a bug. Verify through the repository's regeneration workflow instead.
- Before writing the summary, complete the linked-resource context collection above and list the resources inspected. If the PR has no directly relevant linked resources, state that explicitly.
- Incorporate linked-resource evidence into the motivation, intended flow, acceptance criteria, compatibility requirements, known limitations, and review-risk summary. Do not summarize intent from the PR body alone when linked context is available.
- Explicitly compare the PR title/body and changed code against the linked closing issue or design specification. Record whether the implementation appears to cover the requested scope and whether any acceptance criterion is missing, ambiguous, or contradicted.
- Explicitly check whether the PR description, title, and changed code make the motivation and intended flow clear enough to review confidently.
- If the intended flow is unclear, inconsistent, or missing from the PR context, treat that as an early review concern and note it before moving deeper into code details.
- Explicitly decide whether the PR appears appropriately scoped for review. If it mixes unrelated changes, or mixes broad refactoring with behavior changes in a way that makes correctness hard to isolate, add a candidate finding that the PR should be split before detailed review feedback can be trusted.
- Summarize whether the change appears to fit existing architectural patterns, module boundaries, and overall system fit, or whether it seems to introduce scope or design risk that should guide later review.
- Summarize any obvious user-impact or validation concerns visible from the PR context, especially for UI-, API-, example-, and operator-facing changes.
- If the PR affects UI or visible behavior and the code alone is insufficient to validate the change, note that additional evidence such as screenshots, GIFs, or explicit behavior notes would help later review.
- Clarity of intent does not reduce the obligation to execute later review steps exhaustively. Do not use a clear title, description, or apparent flow as justification to compress Steps 3-9.
- Explicitly record risk-priority triage at the end of this step. Cite the factors that determine inspection order and extra surrounding-context depth: size, public API impact, module sensitivity, data/compatibility risk, and reversibility of mistakes. Name at least two factors unless only one is genuinely relevant. The review remains exhaustive at every priority level.
- In Step 1, record one explicit macro conclusion and one explicit micro conclusion. The macro conclusion must address intent, flow, and scope; the micro conclusion must address implementation correctness, readability, and internal consistency.
- For non-trivial PRs, record the planned pass order using these labels: `architecture/design fit`, `implementation correctness`, and `polish/tests/docs`. If you depart from that order, state why in the next step note.
- Do not unilaterally convert an exhaustive PR review into a partial review. Limit coverage only when the user explicitly asks for limited scope; otherwise inspect every changed path and hunk and apply every required review lens.
- If the user explicitly requested limited scope, say so in progress notes and the final outcome summary rather than implying full review coverage.
- Optimize for reviewable scope and team throughput by deciding what to inspect first, not by skipping required steps or weakening selected review lenses. Triage may change ordering and the number of examples or sibling files inspected first, but it must not remove required sub-checks within a step or reduce the minimum evidence needed to complete that step.
- Treat review as evaluation against project constraints and code health, not against a single preferred implementation; multiple valid solutions may exist. Do not use that fact to dismiss a concrete maintainability, performance, documentation, or failure-mode concern before it is fully evaluated on evidence. When discarding such a concern, cite the evidence that ruled it out: specific code paths, tests, history, docs, or runtime semantics.
- Before closing Step 9, record one explicit macro conclusion and one explicit micro conclusion. The macro conclusion must address intent, flow, and scope; the micro conclusion must address implementation correctness, readability, and internal consistency.

2. **Gather project guidance and review constraints**
Read relevant `CLAUDE.md` files from the repo root and any changed-file directories. Also read targeted project docs when they are relevant to the changed code, especially:
- `README.md`
- `CODE_REVIEW.md`
- `CONTRIBUTING.md`
- nearby subsystem docs adjacent to changed files

Prefer focused guidance documents over reading all markdown files in the repo, but use an objective minimum: read repo-root guidance docs plus any docs adjacent to touched code that plausibly govern the changed behavior, API, example, or subsystem. Use these documents as review constraints and intent/context sources, not posting constraints. Do not use this rule to skip nearby docs that are directly relevant to the changed path. Add any violations or ambiguities to the candidate issue list.

Carry forward requirements learned from linked issues, PRs, design documents, specifications, and dependency changes as explicit review constraints in this step. When repository guidance and linked-resource requirements differ, record the conflict and determine which contract governs the changed behavior before continuing.

3. **Run multi-depth scans**
Execute each sub-pass in order as an independent lens. A sub-pass is complete only when its own evidence line records the files/functions inspected from that lens and the findings added or explicitly ruled out. Do not collapse sub-passes into one general read-through, do not stop after the first promising candidate collapses, and do not treat later sub-passes as already covered by an earlier one.

Load applicable checklists before starting, based on the PR classification from Step 1 and the repository routing above, and enumerate them in the Step 3 evidence ledger:
- Any PR that adds or modifies a public API surface — SDK repositories (pymilvus, milvus-sdk-*, or the `client/` module inside milvus) AND public modules/headers in other repos (milvus `pkg/`, milvus-common `include/`, knowhere `include/knowhere/`, milvus-storage FFI): load [references/checklists/sdk-public-api.md](references/checklists/sdk-public-api.md)
- Changed code contains parsing, regex, or pattern-matching: load [references/checklists/parsing.md](references/checklists/parsing.md)
- milvus server / milvus-common / milvus-storage PR, or any PR touching auth, credentials, networking, file paths, or external input: load [references/checklists/security.md](references/checklists/security.md)
- Changed code involves async execution, concurrency, or shared mutable state (any repository): load [references/checklists/concurrency.md](references/checklists/concurrency.md)
- The diff changes proto definitions, a proto submodule pin, shared error-code definitions, storage/segment formats, or any wire contract consumed by sibling repositories: load [references/checklists/cross-repo.md](references/checklists/cross-repo.md)

A checklist that exists and applies but was not loaded requires a one-line justification in the ledger.

Language-specific examples in this workflow are illustrative, not exhaustive: translate each pattern to the PR's actual language. For example, an unhandled promise rejection in TypeScript corresponds to an unchecked error return plus an unrecovered goroutine panic in Go, an `unwrap` on `None` in Rust, or a swallowed checked exception in Java.

**3a. Correctness pass** — exercise each lens below deliberately:
- Surface: typos, wrong variable names, missing returns, copy-paste errors
- Micro: local correctness issues, line-level readability, obvious implementation mistakes
- Logic: trace through conditionals and loops with concrete example inputs
- Failure: for each operation ask "what if this fails?" — null returns, exceptions, promise rejections
- Edge cases: empty inputs, boundary values, malformed data, single-item collections
- Partial-mutation failure: for every new or modified error-return path, ask what state was already mutated before the return, whether it is rolled back or left partially consumed, and what destructor, cleanup, retry, flush, or close paths will observe afterward
- Refactor consistency: for reorganizations, cache rewrites, plumbing moves, and shared-state refactors, ask whether the new implementation preserves the old invariants across clients, databases, collections, threads, and request paths
- Naming clarity: treat unclear, misleading, or overly generic naming as a signal to inspect the underlying logic, ownership, or abstraction more deeply rather than dismissing it as cosmetic
- Compile surface: for C/C++ changes, inspect newly added includes, namespace-qualified symbols, declaration/definition pairing, and obvious target/source discovery patterns to catch likely branch-local compile failures without building; for any language, check whether the change could break the project's compile environment or settings
- Dependency verification: when a changed line introduces a new helper or provider, follow that dependency to its declaration or definition and verify it exists in the PR branch context

**3b. Design pass** — use SOLID as a diagnostic lens for high cohesion and low coupling, not as a reason to demand abstractions or preferred styles. Apply each applicable probe to changed classes, interfaces, modules, and cross-component state flows:
- Single Responsibility: does the change give one unit multiple independent reasons to change, mix policy with mechanism, or split one invariant across owners so fixes can drift?
- Open/Closed: does adding the next likely variant require editing repeated conditionals or switches across stable code instead of extending one existing boundary? Do not require an extension point for a speculative or one-off variation.
- Liskov Substitution: can every implementation still honor the base contract's inputs, outputs, errors, lifecycle, concurrency, and state invariants, or does a subtype add stronger preconditions or weaker guarantees?
- Interface Segregation: does the changed interface force clients or implementations to depend on unrelated methods, dummy implementations, broader permissions, or dependencies they do not use?
- Dependency Inversion: has high-level policy become coupled to a concrete transport, storage engine, singleton/global, clock, filesystem, or constructor path in a way that blocks testing, replacement, or reuse where an established abstraction already exists?
- Cohesion/coupling synthesis: trace ownership of shared mutable state and persisted representations across components. Ask whether one logical invariant now has multiple authorities or whether unrelated modules must change together.

Promote a SOLID concern only when it is tied to changed lines and has a concrete consequence: incorrect substitution, inconsistent state, duplicated change sites, hard-to-test behavior, architectural boundary erosion, or disproportionate future change cost. Record preference-only or premature-abstraction observations in notes and discard them before posting.

**3c. Performance pass** — look for avoidable allocations, unnecessary copies, repeated serialization work, redundant traversals, and other inefficiencies that occur in hot paths, per-row/per-item loops, or otherwise scaled execution paths. For any concern kept alive, name the repeated path, the concrete extra work introduced, and the scale dimension that makes it matter.

**3d. Maintainability pass** — look for newly duplicated logic, drift-prone sibling implementations, awkward ownership boundaries, or other concrete structure problems that are likely to make the next bug fix or feature change error-prone.

**3e. Security pass** — apply [references/checklists/security.md](references/checklists/security.md): secrets, injection, authorization gaps, unsafe deserialization, credential handling, transport safety, and protocol-safety of user-controlled values reaching logs, metrics, or the wire.

**3f. Concurrency pass** — apply [references/checklists/concurrency.md](references/checklists/concurrency.md) and translate its patterns to the PR's language: leak, race, deadlock/lock order, atomicity of compound operations, cancellation/timeout, callback thread-safety, and shutdown for every async boundary or shared mutable state the diff touches.

**3g. Cross-repository consistency pass (conditional)** — activate only when the diff changes proto definitions, a proto submodule pin, shared error-code definitions, storage/segment formats, or any wire contract consumed by sibling repositories. Apply [references/checklists/cross-repo.md](references/checklists/cross-repo.md): name the changed contract, map its consumers, determine the dependency direction, check whether synchronized changes or sibling PRs exist or are required, and record the conclusion in the evidence ledger.

**Closing question pass** — keep asking the running open questions from Step 1 and the current diff: what assumption is being made, what would happen if the input is empty/stale/malformed, and does the test suite actually demonstrate the intended behavior?

Completion gate for Step 3 — all of the following:
- Every sub-pass 3a-3f has its own evidence line: the files, functions, or scenarios inspected from that sub-pass's lens, plus findings added or an explicit ruled-out rationale.
- Sub-pass 3g was either activated with its own evidence line or explicitly ruled out with the condition that did not apply.
- The step explicitly addressed local code quality, system integration impact where it reveals a concrete bug, concrete performance regressions or avoidable costs, concrete maintainability risks from duplication or structure drift, and concrete SOLID/cohesion/coupling violations whose runtime, testability, ownership, or future-change cost can be demonstrated from repository evidence.
- Loaded checklists are enumerated, with justification for any applicable-but-unloaded checklist.
- At least one concrete falsification attempt was made beyond the first discovered candidate.
- Surrounding files, headers, declarations, or helper providers inspected beyond the patch hunk are named.

Add every plausible issue from these passes to the candidate issue list, even if confidence is still low.

4. **Review historical and surrounding context**
Read git blame and history of modified code, then inspect related files that might be affected by the changes.
Treat this as a fresh pass, not as confirmation of Step 3. The goal here is to surface findings that only become visible once you compare the change against prior versions, sibling files, and surrounding patterns.
- Identify bugs in light of historical context
- Check what patterns existed before and if changes break them
- Check for patterns in sibling files that should be followed
- Look for inconsistencies with existing code
- For release-branch or non-default-branch PRs, explicitly verify that newly referenced helpers, headers, fixtures, and utility APIs are actually available on the target branch rather than assuming default-branch parity
- When the diff introduces a new symbol or include, inspect the nearest provider file or declaration as part of surrounding-context review, not only the changed file itself
- If a changed test or implementation depends on adjacent infrastructure (filesystem helpers, test utilities, singleton accessors, build-visible headers), verify that dependency in the surrounding branch context before closing this step
- For refactors and reorganizations, compare the old and new dataflow explicitly: what state used to be per-request, per-client, per-db, or per-collection, and did the new code accidentally widen or narrow that scope?
- Check whether related request paths that used to share behavior still derive flags, defaults, cache keys, and compatibility params the same way after the refactor
- Re-evaluate any early "please split this PR" concern using the actual changed-file structure and history: if mixed-purpose changes materially reduce review confidence, keep the split-PR finding alive into Step 9 instead of treating it as a stylistic preference
- Revisit relevant linked issue/PR discussion, review comments, design decisions, or dependency history when Step 3 raises an ambiguity. Use this as a focused historical follow-up, not as the first time the linked resources are opened.

Inspect history and sibling context first, then add new candidates from this context pass or materially revise existing candidates based on new contextual evidence. Do not use this step only to re-score Step 3 findings; cite at least one history artifact or sibling file before marking this step complete.

5. **Check code comments and existing documentation in touched code**
Read code comments in modified files and ensure the changed code still matches them.
Do not satisfy this step with a quick glance. Explicitly enumerate the touched comment/doc surfaces you inspected and make a real attempt to find drift, stale rationale, misleading examples, or missing updates.
- Enumerate every touched documentation-bearing artifact in the diff before judging coverage: function/method/type doc comments, block comments, inline comments, TODOs/FIXMEs, and nearby docs sections directly referenced by the touched code.
- For each touched function, method, type, or public API with a doc comment, compare the comment claim-by-claim against the implementation. Verify any described control flow, fallback path, panic/recover behavior, error handling, state/caching scope, concurrency assumption, and performance claim still matches the code.
- When a touched comment explains an invariant, precondition, postcondition, or "why", verify the code still preserves that statement after the change rather than assuming the comment remains true.
- Compare top-level doc comments with nearby inline comments inside the same symbol. If they describe different mechanisms, assumptions, or failure behavior, treat that as a candidate inconsistency even when runtime behavior appears correct.
- Check TODOs and FIXMEs in touched code for three things: they still describe the current code, they are still actionable, and the PR did not silently obsolete or satisfy them without updating the text.
- Look for places where the code now contradicts nearby comments, documented assumptions, examples, or usage notes in touched documentation.
- Check for typos, stale names, stale copy-pasted wording, or references to removed mechanisms in touched comments and documentation.
- If the PR changes architecture, workflow, public behavior, operational expectations, or other shared understanding, check whether touched comments or nearby documentation were updated so the new behavior is discoverable from the codebase, not only from the PR description or discussion.
- When a PR adds closely related public APIs with different destructive scope or lifecycle behavior, verify that the touched comments and docstrings distinguish them clearly enough that a caller would not confuse their effects.
- Do not treat comment/doc drift as automatically cosmetic: if a future maintainer could implement, debug, or modify the code incorrectly by trusting the touched comment, keep it as a real candidate finding. When a touched comment or doc appears stale, explicitly state the maintainer risk: what incorrect implementation, debugging step, or follow-up change a future reader could make by trusting the text.
- Record the result of this step explicitly: either no mismatches found, or a concrete list of mismatched comments/docs with the affected symbol or file.
- If no mismatches are found, still list which touched comments/docs were inspected so this step shows inspection breadth, not just a conclusion.

Add any real comment or documentation mismatches to the candidate issue list.
- A missing doc update is a valid candidate finding when the change alters information future developers or operators would reasonably need.
- A contradiction between touched comments and code is a valid candidate finding even if tests still pass and runtime behavior is otherwise correct.

6. **Analyze failure modes explicitly**
Review the changed paths with a failure-focused pass.
Treat this as an adversarial pass. Assume the happy path is already understood and try to break the changed behavior with realistic bad inputs, missing dependencies, partial state, and production-scale conditions. In Step 6, record at least one attempted break scenario from each applicable category: invalid input, missing dependency, partial state, and production-scale condition.
- For async operations: Is rejection/error handled? Could this cause unhandled promise rejection?
- For external calls/APIs: What happens on timeout, network failure, or unexpected response?
- For parsing code: What happens with malformed, truncated, or unexpected input?
- For resource acquisition: Are resources properly released on error paths?
- For each newly added or modified failure path, explicitly record whether any counters, builders, buffers, ownership handles, or partially produced outputs were already mutated before the error was returned.
- If mutable state changes before failure, inspect the destructor, retry path, cleanup path, and close/flush/finalize path to determine whether later code observes inconsistent state. Check at least one post-failure invariant or cleanup interaction for each materially changed error path introduced or modified by the diff; do not expand to untouched historical error paths unless the diff strongly suggests shared-state coupling.
- For public SDK entrypoints: What happens if the caller passes an invalid-but-type-correct value, leaves an optional field empty, or provides an empty callback/function object?
- For string-to-enum or string-to-identifier conversions: Does parse/lookup failure return an explicit error, or does the code silently send a default/zero value?
- For callback invocation: Is the callable checked before invocation, or can an empty callback crash/throw at runtime?
- For APIs whose work may continue over time or across many results: Do timeout, deadline, retry, or buffering rules still make sense for that lifecycle, or do they convert healthy operation into premature termination?
- For non-atomic or progressive APIs: Would expiry/failure in the middle cause silent truncation, partial output, or non-obvious data loss rather than a clean and explicit stop?
- For request/response features: Could the request succeed yet still fail to deliver the advertised user-visible result because response parsing, result propagation, or public accessors are missing?
- For string serialization on protocol boundaries: Could locale, formatting, or precision differences make otherwise-valid values fail server-side parsing or change semantics on the wire?
- Check whether newly added or modified logs would actually help diagnose failures or trace execution, and whether the PR adds noisy, redundant, or unnecessarily expensive logging.
- Ask whether the change emits useful signals for monitoring and operations, such as errors, throughput, latency, availability, or processed volume when those signals are relevant to the changed path. When the changed path is operationally relevant, record which of those signals are applicable and whether the code emits enough information, emits noisy/redundant information, or does not expose a useful signal.
- For data-heavy, distributed, or production-sensitive code paths, ask whether the implementation is safe for real runtime conditions: memory/CPU usage, DB/query load, large result sets, pagination, resource contention, or other production-scale constraints.
- For changes that introduce operational behavior, background work, request processing, or production-sensitive data paths, review whether logging is useful but not excessive, whether monitoring/metrics signals are sufficient for operating the feature, and whether runtime and infrastructure assumptions remain safe at production scale.
- Ask: "If I were trying to break this code, what input would I use?"

Add any concrete failure-path problems to the candidate issue list. Before closing this step, name at least one attempted break scenario for the changed code and make sure the pass explicitly considered invalid input, missing dependency, partial state, and production-scale assumptions where relevant.

7. **Check test coverage gaps**
Inspect whether the PR includes or should include tests for the changed behavior.
This step must independently answer whether the current evidence is strong enough for the changed behavior, not merely whether earlier steps already failed to find a bug. In Step 7, map the material changed behaviors to their current evidence surface: direct test, indirect test, docs/example evidence, code reasoning only, or no evidence. Use that map to identify concrete coverage risks, not to stall the review: if some behaviors remain only code-reasoned or unsupported, record them as explicit risks or justify why they are acceptable before moving to Step 8.
- Use changed tests early in this step as an understanding aid: ask what behavior the author seems to think they changed, what cases they considered important, and which open questions from earlier steps remain unanswered by the tests.
- Check testability, not just test presence: ask whether the design itself is reasonably testable, or whether coupling, globals/statics, hidden dependencies, or missing seams make meaningful tests harder than they should be.
- For new code paths: Is there a test that exercises this specific path?
- For conditional branches: Are both/all branches tested?
- For error handling code: Are error paths tested, not just happy paths?
- For edge cases in the code: Is there a corresponding test case?
- For parsing/regex: Are all input format variations tested?
- For public API additions: Are malformed-but-type-valid inputs tested, not just happy-path setters/getters?
- For changed test files, verify not only behavioral coverage but also test dependency validity: newly added headers, helpers, fixtures, constants, and utility APIs must exist on the target branch and be plausibly available to that test target.
- If the production change fixes a failure-path bug, confirm that at least one test exercises a failure path rather than only asserting the OK path or idempotent path.
- For callbacks: Is an empty / null / unset callback tested when the API accepts an optional callable?
- For string-to-enum conversions: Is the invalid-string path tested to prove the API rejects it instead of silently defaulting?
- For APIs with incremental, paginated, streaming, watch-like, or otherwise long-lived behavior: Is there a test for non-default timeout/deadline behavior or other shared client policies that could stop healthy work early?
- For APIs that can produce partial progress: Is there a test proving the implementation fails explicitly rather than silently truncating or dropping output when limits are hit mid-operation?
- For serialization-heavy features: Do tests assert exact keys and representative values on the wire rather than only counts, sizes, or presence of containers?
- For request/response features: Is there at least one test that proves user-visible output comes back through the public result type, not just that request fields were set?
- For examples and docs that teach a caller pattern: Do tests validate that the demonstrated values and flows are actually accepted by the real server contract?
- For multi-item or multi-query mapping code: Is there a coverage case where the index/offset actually advances, rather than only single-item inputs that leave mapping logic unexercised?
- For refactors that preserve public APIs: Is there a test that old caller patterns still work, especially explicit opt-outs, raw params, deprecated setters, and compatibility helpers?
- For caches and shared-state rewrites: Is there a test that isolates state across two clients / sessions / databases / collections so cross-scope leakage would be caught?
- If the PR affects UI or visible behavior, check whether the available tests and evidence are sufficient to validate the changed behavior.

Add missing-test findings to the candidate issue list only when the missing coverage corresponds to a concrete risk in the changed behavior.
- Before concluding there is no concrete coverage risk, state which changed behaviors do or do not have direct evidence and map them to the expected test or validation surfaces.
- If a user-impact concern is only unsupported by tests or evidence, keep it here as a coverage/validation gap rather than as a separate product-level review track.

8. **Check for redundant changes**
Look for unnecessary churn in the PR.
Treat redundancy as its own review target. Even when the behavior is correct, make a deliberate pass for avoidable duplication, needless conversions, dead helpers, copy-paste drift, and repeated-path work that the PR may have introduced.
- Are there any redundant changes added?
- Are there any redundant dependencies were added?
- For C/C++ changes, check whether newly added headers are actually needed by the touched translation unit or header; treat unnecessary includes as redundant dependency churn and as a potential maintainability/build-cost finding when they widen compile surface without need.
- For Java changes, check whether newly added imports are actually used by the touched class; treat unnecessary imports as redundant dependency churn and remove-only noise when they add no behavior or documentation value.
- For Python changes, check whether newly added imports are actually used by the touched module; treat unnecessary imports as redundant dependency churn and remove-only noise when they add no behavior or documentation value.
- For Rust changes, check whether newly added `use` imports are actually used by the touched module; treat unnecessary imports as redundant dependency churn, and as a potential build/lint issue when the repo denies `unused_imports` or warnings.
- Are there any redundant comments were added?
- Did the refactor leave behind dead compatibility helpers, unused functions, or duplicate flag-derivation paths that no longer match the new control flow?
- Did the PR introduce sibling implementations of the same new logic that now have to be kept in sync manually? Treat byte-for-byte or near-duplicate new helpers in touched files as a candidate maintainability finding when extracting shared code would materially reduce drift risk.
- For every new helper or wrapper introduced by the PR, trace whether an existing layer, shared utility, or surrounding call path already performs the same transformation, validation, normalization, or conversion on the same inputs; if yes, treat the new helper or call site as redundant unless it adds a distinct contract, scope boundary, or behavior.
- Did the PR introduce avoidable work in a repeated path, such as always copying unchanged collections, rebuilding equivalent objects, or normalizing the same structure multiple times? Treat those as candidate performance findings when the cost is concrete even if the code remains functionally correct.
- For touched text files, treat `\ No newline at end of file` as a `Low` candidate finding unless the repository clearly ignores that formatting issue or the file type intentionally omits trailing newlines.

Add any unnecessary or misleading changes to the candidate issue list. Before closing this step, explicitly state which redundancy categories were checked: duplicate helpers, repeated conversions, dead code, drift-prone sibling logic, repeated-path work, and unnecessary comments or dependencies. Record a redundancy checklist outcome for each category as `none found`, `candidate found`, or `not applicable`.

9. **Confidence, severity, and dedup pass**
Review the full candidate issue list and consolidate it before posting.
Do not use this step only to prune correctness bugs. Re-open the full output of Steps 3-8 and verify that maintainability, performance, docs/comments, failure-mode, coverage, and redundancy concerns were each consciously either kept or discarded on evidence.
- Merge duplicate findings
- Down-rank speculative findings
- Discard findings that are not concrete enough to defend publicly on the PR
- Assign a severity label to every surviving finding:
  - `High` — Highly confident, highly necessary to fix; correctness bug, CI/runtime failure, wrong API behavior, or serious mismatch
  - `Medium` — Moderately confident, should probably fix; likely bug, brittleness, important inconsistency, or meaningful performance/maintainability problem
  - `Low` — Somewhat confident, minor problem or optional improvement; user may ignore it
- Keep only findings that are concrete, actionable, and worth posting publicly on the PR
- Treat maintainability as part of the approval bar, not just correctness: if a change works today but introduces obvious structural debt, hard-to-test design, architectural drift, or disproportionate future change cost, keep that concern alive when it is concrete enough to defend publicly. For every maintainability concern you keep alive past its first mention, name the concrete future cost: which duplicated logic may drift, which design is hard to test, which architectural boundary moved or blurred, or which follow-up change is made more error-prone. Do not block the current step on unresolved confidence: if that future cost cannot yet be explained concretely, record the uncertainty and carry the concern forward to Step 9 as a lower-confidence candidate unless evidence already rules it out.
- For every SOLID-based candidate, name the violated contract or ownership boundary and the observable consequence. Discard comments that only rename a principle, prefer a different abstraction, or predict hypothetical extensibility needs without a concrete repository-supported change path.
- Treat concrete performance regressions and avoidable repeated-path costs as part of the approval bar too: if the new code adds unnecessary per-row, per-item, or otherwise scaled work, keep that concern alive when the cost and fix are both specific enough to explain publicly. For every performance concern kept alive, name the repeated path, the concrete extra work introduced, and the scale dimension that makes it matter (for example per-row, per-item, per-request, per-page, or per-retry). Do not block the current step on unresolved confidence: if the repeated path or extra cost is still uncertain, record the uncertainty and carry the concern forward to Step 9 as a lower-confidence candidate unless evidence already rules it out.
- After a concern has been fully evaluated and evidence-backed, distinguish merge blockers from backlog-worthy suggestions: if a point is valid but not necessary for correctness, compatibility, safety, or completion of this PR, prefer to down-rank it, phrase it as non-blocking, or suggest follow-up tracking instead of treating it like a must-fix review finding. For every surviving finding in Step 9, record both severity and disposition (`blocking`, `non-blocking`, or `follow-up`) and justify the disposition in one sentence by referencing correctness, compatibility, safety, PR completion, or future-maintenance impact.
- Do not use severity or disposition guidance to avoid fully evaluating a plausible maintainability or performance concern.
- Explicitly classify the disposition of each surviving finding as blocking, non-blocking, or informational before writing the final comment.
- For every surviving or discarded candidate that depended on surrounding-code inspection, record which extra files, headers, declarations, or sibling implementations were checked and what evidence ruled the concern in or out. Record the surrounding-code evidence that materially informed the result, but do not perform extra reads solely to populate this note once the bounded required checks are already complete.
- Treat personal style or reviewer-preference points as non-blocking by default unless they violate an explicit project rule or materially affect code health. When posting a style-adjacent comment, explicitly state whether it is grounded in an explicit project rule, a concrete code-health concern, or only reviewer preference. Do not post preference-only comments as blocking findings.
- When a comment rests on judgment rather than objective breakage, confirm that the concern is still strong enough to defend publicly even if another valid implementation choice exists. Record the public-defense rationale in one sentence: what concrete maintenance, readability, performance, testability, or contract risk justifies posting it even though another implementation choice could also be valid.
- For dedupe against existing review feedback, use thread-aware data from `gh api graphql` on `pullRequest.reviewThreads`, not `gh api repos/:owner/:repo/pulls/<PR_NUMBER>/comments`
- Treat a materially same finding in an unresolved, non-outdated thread as active feedback and suppress the candidate as a duplicate.
- Treat a materially same finding in a resolved, non-outdated thread as already reviewed and dispositioned. Suppress the candidate instead of reposting it, even when the reviewer independently disagrees with the resolution.
- Reopen a resolved, non-outdated finding only when the new candidate contains materially new evidence or identifies a distinct consequence that the resolved thread did not cover. Record the new evidence and explain explicitly why this is a justified reopen rather than a duplicate.
- Do not automatically suppress against outdated threads because their code anchor changed. Re-read the current diff and only post when the issue applies to the current code; if the same issue was previously resolved, state what current code change or new evidence makes the new comment necessary.

Explicitly note how many candidate findings were kept, merged, downgraded, or discarded.
- In that summary, be explicit about whether any architecture/design or maintainability concerns survived to the final set, even if no correctness bugs did.

10. **Dedupe Against Existing Review Threads**
When checking whether a finding is already covered on the PR, fetch review threads with GraphQL so you can see thread state.
Use a command shaped like this:

```bash
gh api graphql \
  -F owner='<OWNER>' \
  -F repo='<REPO>' \
  -F number=<PR_NUMBER> \
  -f query='
    query($owner: String!, $repo: String!, $number: Int!) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $number) {
          reviewThreads(first: 100) {
            nodes {
              isResolved
              isOutdated
              path
              line
              comments(first: 20) {
                nodes {
                  author { login }
                  body
                  createdAt
                  url
                }
              }
            }
          }
        }
      }
    }
  '
```

Classify materially matching threads as follows:

- `isResolved == false` and `isOutdated == false`: active feedback; suppress the duplicate candidate.
- `isResolved == true` and `isOutdated == false`: already reviewed and dispositioned; suppress the duplicate candidate unless materially new evidence justifies reopening it.
- `isOutdated == true`: the anchor changed; inspect the current diff before deciding. Do not repost solely because the old thread is outdated.

For every candidate matched to a resolved, non-outdated thread, record `previously dispositioned` in Step 10. If reopening it, record the exact new evidence or distinct consequence and ensure the new comment acknowledges the prior disposition. A reviewer disagreement with the prior resolution is not, by itself, new evidence.

11. **Generate final review comments**
- Convert the surviving findings into review comments with exact `(path, line, side)` anchors
- Write every final comment and any reply in English. Before posting, reject or translate a drafted body whose explanatory prose is not English; preserve only technically necessary code, identifiers, paths, and exact error messages in their original form.
- In every posted comment, explain the reasoning behind the concern, not just the preferred change, so the author can understand the risk, contract, or maintenance issue being pointed out.
- Classify each surviving finding by comment shape before writing it: `bug`, `question`, or `suggestion`
  - `bug` when the reviewer is pointing out a concrete correctness, compatibility, safety, or contract issue
  - `question` when the reviewer needs the author to explain an assumption or intent before deciding whether something is wrong
  - `suggestion` when the point is valid but advisory rather than required for correctness
  - For dynamically typed languages (Python, JavaScript/TypeScript), when a finding depends on cross-file type inference that reading alone cannot confirm, prefer the `question` shape over `bug` unless repository evidence directly proves the incorrect behavior
- Use this comment-shape classification to refine phrasing, but do not let it override severity or blocking disposition
- Treat the comment-body format as mandatory, not advisory: do not post or patch any comment until the body has been checked against this exact two-line shape.
- Format every posted comment body as exactly two logical lines before any optional extra detail:
  - first line: `path/to/file.ext line:123`
  - second line: severity-prefixed message, for example `High ---- ...`
- Do not rely on GitHub's inline anchor metadata or UI to supply the file path or line number; the first line must still be written explicitly in the comment body.
- Prefix every posted comment body with its severity label in plain text on the second line, for example:
  - `test/foo.cpp line:123`
    `High ---- This request now sets the feature flag to true on the happy path, but the surrounding setup still initializes the dependency in disabled mode, so the new branch cannot behave as intended ...`
  - `test/foo.cpp line:123`
    `Medium ---- ...`
  - `test/foo.cpp line:123`
    `Low ---- ...`
- Before every POST or PATCH request, construct the final comment body as a dedicated string variable and inspect that exact string; never post draft reasoning prose or analysis notes directly.
- Before every POST or PATCH request, do a literal preflight check on the exact body text:
  - line 1 must exactly match `path/to/file.ext line:123`
  - line 2 must start with `High ----`, `Medium ----`, or `Low ----`
  - if the body was copied or adapted from earlier analysis text, rewrite it into the required two-line review format before sending the request
  - if either required line-shape check fails, rewrite the body before sending the request
- In Step 10 notes, record the exact final body text you intend to post so Step 11 can verify the posted comment against the same string rather than a paraphrase.
- Then continue with the normal anchor validation and COMMENT-only posting flow below

If a surviving finding cannot be anchored, explicitly handle it with the fallback rule below instead of silently dropping it.

12. **Posting threshold**
- Always post `High` findings
- Post `Medium` findings
- Post `Low` findings by default unless the user explicitly asks to ignore them. For example, skip low findings if user explicitly says "ignore minor issues" or "ignore low issues".
- Even when zero findings survive to this step, still execute Step 11 explicitly and record that no comments met the posting threshold.
- Step 12 completion is mandatory before any final review response. Never stop after Step 9, Step 10, or Step 11 just because the surviving findings are already clear.
- If there is at least one surviving finding entering Step 11, the workflow must continue through comment generation, inline posting, and post verification before the review is considered complete.
- If a user message arrives mid-review, finish or resume the numbered workflow unless the user explicitly changes the task. Do not convert an in-progress review into a partial-results summary.

At the end, summarize the result in counts: total candidate findings, discarded findings, and posted comments by severity. End the summary with these exact final two-line fields, with no content between or after them:

```text
Time cost: Xm Ys
PR URL: https://github.com/<OWNER>/<REPO>/pull/<PR_NUMBER>
```

Use `Time cost after resume: Xm Ys` for the first line only when the original start time was unavailable. Populate the second line from the PR metadata `html_url` field rather than reconstructing or abbreviating the URL.
- If the final outcome is `no inline comments to post`, say that only after explicitly recording the Step 9 outcome (zero surviving findings), the Step 10 outcome (zero generated comments), and the Step 11 outcome (zero posted comments).
- Before sending the final review summary, perform this literal pre-response checklist:
  - Step 9 completed
  - Step 10 completed
  - Step 11 completed
  - every surviving finding was either posted and attachment-verified, or explicitly discarded with a stated reason
  - no Step 11 or Step 12 task remains `pending` or `in_progress`
  - review end time recorded and elapsed wall-clock seconds calculated from the saved start time
  - canonical PR URL recorded from PR metadata
  - final summary ends with the correctly formatted time-cost line followed immediately by the `PR URL: <PR_HTML_URL>` line

The posting mechanism stays the same; the required change is that the analysis workflow must now be visibly sequential and each step must show evidence of independent, substantive execution. Sequential reporting alone does not satisfy this workflow. Substantive execution means the step names the files, functions, history, docs, tests, or scenarios inspected from that step's own lens, and explains what was ruled in or out from that evidence.

### Severity Guidance

Use these labels consistently:
- `High` — highly necessary to fix before merge.
- `Medium` — better to fix; likely worthwhile and non-trivial
- `Low` — minor issue; acceptable for the author to ignore
- Severity and merge disposition are related but not identical: severity describes how serious the issue is, while blocking vs non-blocking describes whether it must be fixed before this PR merges.
- Decide merge disposition separately for each surviving finding: blocking, non-blocking, or follow-up.
- Default guidance: `High` findings are blocking by default; `Medium` findings block when they affect correctness, compatibility, safety, or completion of the PR; `Low` findings are non-blocking by default unless the user explicitly asks to hold the bar higher.

Do not use numeric severity scores in posted comments unless the user explicitly asks for them.

### Posting Pattern

Do not ask the user for confirmation. Post directly after validating:
- Include file path and line number in the comment body on the first line, formatted exactly as: `path/to/file.ext line:123`
- Put the severity-prefixed review text on the second line, for example: `Medium ---- ...`
- Before every POST request, do a final body-shape check: line 1 must be the explicit `path ... line:...` text and line 2 must start with `High ----`, `Medium ----`, or `Low ----`; if not, fix the body before posting
- Exact comment text, including code suggestions
- Always use Dedicated Inline Comment
- Overall review message

### Posting Technical Approach

Use the **Dedicated Inline Comment** endpoint for every review comment you post.

This is the GitHub API equivalent of clicking **"Add a single comment"** on a changed line in the PR diff.

#### 1. Fetch metadata and validate the anchor first
Before posting any comment:
- Fetch PR metadata:
  - `gh api repos/:owner/:repo/pulls/<PR_NUMBER>`
- Fetch the PR files/patches:
  - `gh api repos/:owner/:repo/pulls/<PR_NUMBER>/files --paginate`
- Confirm the exact `(path, line, side)` exists in the current diff hunk
- Do not assume a local checkout line number is attachable in the PR review API
- Do not use `gh pr view` anywhere in this workflow

#### 2. Post the inline comment directly
Use this endpoint:

```bash
gh api repos/:owner/:repo/pulls/<PR_NUMBER>/comments \
  -X POST \
  -f commit_id="<COMMIT_SHA>" \
  -f path="path/to/file.ts" \
  -F line=<LINE_NUMBER> \
  -f side="RIGHT" \
  -f body=$'path/to/file.ts line:123\nHigh ---- Exact comment body here'
```

For inline comments, the body must still include the path and line on the first line even though GitHub also stores the anchor metadata separately.

#### 3. Verify the comment actually attached
After posting, verify the response contains the expected:
- `path`
- `line`
- `side`
- `html_url`

Do not claim success unless those fields confirm the comment attached to the intended diff line.

#### 4. If posting fails
If the inline comment does not attach as expected:
1. Do not claim success
2. Re-check the anchor against the current PR patch
3. Retry with a nearby valid added line in the same hunk if needed
4. Only if no valid inline anchor exists, fall back to a normal PR comment that explicitly cites `path:line` in the body

Suggested fallback shape:

```text
path/to/file.ts line:123
High ---- Exact comment body here.
```

Use the same two-line format for fallback non-inline comments.

#### 5. Quoting rule
- Prefer single-quoted `-f body='...'` payloads when the comment body contains Markdown code spans or fenced code blocks
- Backticks inside double-quoted shell strings can trigger command substitution in the shell

## Bundled Scripts

- `scripts/cleanup_workspace.py`: safely remove only a direct system-temporary-directory child whose name starts with `pr-review.`; reject arbitrary paths and symlinks.

## Bundled review checklists

- [references/checklists/sdk-public-api.md](references/checklists/sdk-public-api.md): public SDK API review rules — hostile-caller probes, backward compatibility, lifecycle policy, wire serialization, cache scoping.
- [references/checklists/parsing.md](references/checklists/parsing.md): regex/parser/pattern-matching review rules.
- [references/checklists/security.md](references/checklists/security.md): security review rules — secrets, injection, authorization, deserialization, transport, SDK credential handling.
- [references/checklists/concurrency.md](references/checklists/concurrency.md): concurrency review rules with per-language pattern translation.
- [references/checklists/cross-repo.md](references/checklists/cross-repo.md): cross-repository consistency rules — proto bumps, sibling PRs, error-code families, wire/REST contracts, storage formats.

Step 3 loads applicable checklists per PR classification; the Step 3 evidence ledger must enumerate them.

## Notes

- Do not build or typecheck as part of the review, but still perform deep semantic validation through code reading, history, tests, docs, and surrounding context. This rule restricts build/test execution, not review depth.
- Cite each issue with `path:line` in the final reasoning
- Dedupe carefully so the final review removes only genuinely overlapping findings, while distinct concerns remain separate even if they touch related code
- When deduping against existing PR feedback, treat resolved, non-outdated threads as previously reviewed and dispositioned; do not repost materially identical findings without new evidence. Inspect outdated threads against the current diff. Use `reviewThreads` via `gh api graphql` rather than the plain REST review-comments list.
- Posting remains COMMENT-only
