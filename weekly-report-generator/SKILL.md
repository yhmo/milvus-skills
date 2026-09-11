---
name: weekly-report-generator
description: Generates a weekly engineering report / 周报 in Markdown with exactly these sections: Time, Summary, Work items, and Plan for next week. Use when the user asks to draft, update, or polish a weekly report, summarize this week’s work, turn tasks/PRs into a status report, or asks in Chinese for 周报、本周周报、上周周报、工作总结、PR 周报、下周计划.
---

# Weekly Report Generator

## Goal
Produce a concise weekly report in Markdown using this structure:
1. `## Time`
2. `## Summary`
3. `## Work items`
4. `## Plan for next week`

Save the report as a Markdown file:
- Default directory: `/tmp`
- If user provides a path, save to that path instead

Platform support:
- The bundled `scripts/scan_weekly_prs.sh` supports both Linux and macOS.
- Requirements: `gh` and `python3`.

## Output format
Always return Markdown.

Use the same language as the user's request when generating the report. For example, if the user triggers the skill in Chinese, generate the report in Chinese.

Use this exact section order and titles:

```md
## Time
From 2026-06-05 15:00 CST to 2026-06-12 15:00 CST

## Summary
- ...

## Work items
- Project or area name
  - [x] Completed item [link](https://...)
  - [ ] In-progress item [link](https://...)

## Plan for next week
- ...
```

For Chinese reports, format the `## Time` content in Chinese, for example:
- `从 2026年6月5日 15:00 到 2026年6月12日 15:00`

For English reports, format the `## Time` content in English, for example:
- `From 2026-06-05 15:00 CST to 2026-06-12 15:00 CST`

The `## Time` section should contain the actual local-time window used for the report.
Do not show UTC there unless the user explicitly requested UTC.
Keep `## Time` as a plain text line under the heading, not a bullet list.

## Prerequisites

**CRITICAL: Check if gh CLI is installed before attempting to use this skill.**

### Check for gh CLI

Before generate report workflow, verify the gh CLI is available:

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

Then try generate your report again.
```

3. **Do not proceed** with the report workflow until gh is installed

### After Installation

Once gh is installed, users must authenticate:
```bash
gh auth login
```

## How to trigger this skill
Use prompts such as:
- "Generate this week's weekly report."
- "Draft a weekly engineering report from my PRs."
- "Create/update my weekly report and save it to /tmp."
- "Use t1=2026-05-23T15:00:00Z, t2=2026-05-30T15:00:00Z, github account yhmo, then generate report."

Chinese prompts can trigger this skill too, for example:
- "帮我生成本周周报。"
- "根据我这周的 PR 生成 weekly report。"
- "总结这周的工作，生成包含 Summary、Work items 和 Plan for next week 的周报。"
- "使用 t1=2026-05-23T15:00:00Z，t2=2026-05-30T15:00:00Z，GitHub 账号 yhmo，生成周报。"

For best auto-trigger matching, include keywords like: `weekly report`, `summarize this week`, `work items`, `plan for next week`, `周报`, `本周工作`, `工作总结`.

If auto-trigger does not happen, explicitly ask:
- "Use weekly-report-generator to generate my weekly report."
- "/weekly-report-generator 帮我生成本周周报。"

## Instructions

### Step 1: Preflight checks
- Read global git identity:
  - `git config --global user.name`
  - `git config --global user.email`
- Check GitHub CLI availability:
  - `command -v gh`
- If `gh` is not installed:
  - Notify the user that GitHub CLI is required for PR scanning.
  - Stop PR-scan workflow and ask user to install `gh`.
- Check GitHub CLI authentication state:
  - `gh auth status`
- If `gh` is logged out or auth check fails:
  - Notify the user that GitHub CLI must be logged in for PR scanning.
  - Stop PR-scan workflow and ask user to run `gh auth login`.

### Step 2: Get Work items from script
- Collect or infer:
  - time range from the user
  - GitHub account (prefer `git config --global user.name` mapping to login, or ask user)
- Accept user time input in local time by default unless the user explicitly says UTC.
- Detect local timezone before conversion:
  - `date +%Z`
  - `date +%z`
  - or use `python3` timezone handling if needed
- Convert the user-provided local time range to `t1_utc` and `t2_utc` before running the script.
- If the user specifies only dates without hour/minute in local time:
  - Set `t1` to the first date at `00:00:00` in local time.
  - Set `t2` to the last date at `24:00:00` in local time (equivalent to next day `00:00:00`).
  - Convert both boundaries to UTC before calling the script.
  - Example: local `2026-05-23` to `2026-05-30` means local `2026-05-23 00:00:00` to local `2026-05-31 00:00:00`, then convert those to UTC.
- If the user specifies hour/minute explicitly in local time, convert the provided local datetimes to UTC.
- If the user explicitly provides UTC timestamps, use them directly without timezone conversion.
- If the user specifies relative phrases like `last week`, follow the skill's default weekly window rules unless the user overrides them.
- If the user specifies relative weekday/time phrases such as `last Friday 3:00 PM`, `上周五下午3点`, `this Monday 10:00 AM`, or `这周一上午10点`:
  - Resolve them in the user's local timezone by calendar week/date first, then apply the clock time.
  - `last Friday` / `上周五` means the Friday in the previous calendar week.
  - `this Friday` / `这周五` means the Friday in the current calendar week.
  - Do not shift the result by an extra week just because the current clock time is before the target clock time on the same weekday.
  - For example, if now is `2026-06-12 14:26 CST`, then `上周五下午3点到现在` must resolve to local start `2026-06-05 15:00 CST`, not `2026-05-29 15:00 CST`.
- When the user says `to now` / `到现在`, resolve `now` as the current local datetime, and resolve the relative start independently using the local calendar rule above.
- Run:
  - `bash ./scripts/scan_weekly_prs.sh "<t1_utc>" "<t2_utc>" "<github_account>"`
- Parse script output and use it as the source for `## Work items`.
- Include only PRs that are currently open or were merged within the report window.
- Exclude closed-but-unmerged PRs, even if they were created or updated within the report window. Determine completion from a non-null `mergedAt` / `merged_at`, not from `state == closed`.
- Preserve the final local-time window used for the report so it can be written into `## Time`.
- Keep both boundaries in local time for display, even if UTC was used to call the script.
- Ensure open PR coverage:
  - If any open PRs by this account exist, they must be represented in `## Work items`.
  - Open PRs still follow deduplication rules; similar-title open PRs can be merged into one deduplicated work item.
  - When deduping open PRs, keep one representative link and preserve meaningful branch context only if needed.
  - Never drop open PR coverage entirely due to deduplication.
- If script returns no rows, keep `## Work items` minimal and ask user whether to add manual items.
- If script returns rows but no open PRs, do a quick sanity check with `gh pr list --author "<github_account>" --state open --limit 200` for relevant repos before finalizing.
- If key inputs are missing, ask focused follow-up questions.


### Step 3: Write `Time`
- Add a `## Time` section before `## Summary`.
- Show the final report time window using the local-time boundaries actually used for the scan.
- Language rules:
  - If the report is in English, use a single plain-text line like: `From 2026-06-05 15:00 CST to 2026-06-12 15:00 CST`.
  - If the report is in Chinese, use a single plain-text line like: `从 2026年6月5日 15:00 到 2026年6月12日 15:00`.
- Do not invent a different time window than the one actually used.
- Do not render the time window as bullets.

### Step 4: Write `Work items`
- Deduplicate PRs before writing items:
  - If multiple PRs have similar titles (for example, same feature/fix on different branches), treat them as one work item.
  - This dedup rule applies to open and merged PRs. Closed-but-unmerged PRs must be excluded before deduplication.
  - Keep one representative link for each deduplicated item (prefer open PR link for in-progress items; otherwise prefer the latest merged PR).
  - Preserve branch details only when branch differences are meaningful to report.
- If both open and merged PRs share similar titles, merge into one item and mark status by latest active state (prefer `[ ]` if any linked PR is still open).
- Group by project/component (for example, `- Milvus Java SDK`).
- For each item, rewrite the raw GitHub PR title into a friendly, human-readable work title.
- Title refinement rules:
  - Remove noisy prefixes/suffixes (for example: `feat:`, `fix:`, `wip`, branch tags, ticket IDs when not essential).
  - Normalize wording to clear action/outcome language.
  - Keep technical accuracy (API names/features) while improving readability.
  - Keep the title concise (prefer one short line).
- Keep one line per item.
- Include links when provided.
- Under each group, list checklist bullets:
  - `[x]` only for PRs merged within the report window
  - `[ ]` for PRs that are still open
  - Do not create a work item for a PR that is closed without being merged

### Step 5: Write `Summary`
- Derive bullets from `Work items`, not from raw PR titles directly.
- Each bullet must summarize outcomes within the same project and the same class of work.
- Do not merge unrelated projects or repositories into one bullet, even if they are broadly similar (for example, release work in one repo must not be merged with packaging or release-flow work in another repo).
- Concrete counterexamples of invalid merging:
  - Do not merge `Prepare Java SDK 2.6/3.0 releases` with `Refine Rust SDK source code` in one bullet, because they belong to different projects/repos.
  - Do not merge `Reorganize Rust SDK source code for v1` with `Continue closing capability gaps in the C++ SDK` in one bullet, because they are different project tracks with different deliverables.
- Within one project, prefer one bullet per major theme (for example: SDK feature additions, reliability improvements, test/coverage work, release/build updates).
- Merge related repo-level items into a single outcome bullet only when they describe the same initiative in the same project.
- Prioritize completed (`[x]`) outcomes; mention in-progress (`[ ]`) items only if they are important cross-week carryover.
- Emphasize impact and result (what capability improved), not implementation micro-steps.
- Focus on meaningful outcomes, not minor activity logs.
- Use concise, action-oriented language.
- Avoid duplicates between bullets.
- Keep each bullet as one line.
- Do not invent accomplishments not present in `Work items`.
- If `Work items` is empty, keep Summary minimal and explicitly note limited activity data.

### Step 6: Write `Plan for next week`
- 1-5 bullets.
- Derive the plan from in-progress (`[ ]`) items in `Work items`.
- Do not invent uncertain or speculative plans.
- Only include concrete next actions that logically continue current in-progress work.
- Forward-looking and specific.
- Keep each bullet actionable.
- If there are no in-progress items, keep this section minimal and ask user whether to add manual plan items.

### Step 7: Build filename and save file
- Get UTC date from shell:
  - `date -u +%F`
- Build filename exactly as:
  - `weekly-report-[utc date].md`
  - Example: `weekly-report-2026-05-29.md`
- Choose output directory using this rule:
  - If user provides a path, use that path.
  - Otherwise, use `/tmp`.
- Build final output path:
  - `[output directory]/weekly-report-[utc date].md`
- Execute an explicit write-to-file command using heredoc (do not only print text):
  - `cat <<'EOF' > "[final output path]"`
  - `[full report markdown content]`
  - `EOF`
- Verify file was written before claiming success:
  - `test -f "[final output path]"`
  - `ls -l "[final output path]"`
- After saving, include the full report content in the assistant response.
- Report the final file path after the full report content.
- Never say a file is saved unless the verification commands pass.

## Rules
- Keep the four section titles exactly as specified.
- Section order is mandatory: `## Time`, `## Summary`, `## Work items`, `## Plan for next week`.
- Do not invent links, numbers, or accomplishments.
- Never count a closed-but-unmerged PR as completed work or include it as a work item.
- Preserve user-provided product/team naming.
- Keep wording concise and professional.
- Prefer concrete deliverables over vague statements.
- Never overwrite an existing file unless user explicitly asks.
- Filename format is mandatory: `weekly-report-[utc date].md` using UTC date from `date -u +%F`.

## Quality checks before returning
- Section titles and order are correct.
- `Time` is present before `Summary` and shows the actual local-time report window.
- `Summary` is short and outcome-focused.
- `Work items` are grouped and have clear status markers.
- No open PR found by the script is missing from `Work items`.
- No closed-but-unmerged PR appears in `Work items` or `Summary`.
- `Plan for next week` is specific and actionable.
- Markdown is clean and ready to paste.
- Output directory follows default `/tmp` or user-provided override.
- Filename matches `weekly-report-[utc date].md` from `date -u +%F`.
- Final saved file path is included in the response.
