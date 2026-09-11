---
name: scan-runner
description: Scan active GitHub Actions jobs across repositories in the milvus-io and zilliztech organizations and report jobs whose runner labels match a requested platform or label. Use when the user invokes scan-runner with a label or asks to find queued, requested, in-progress, waiting, or pending macOS, Linux, Windows, ARM, GPU, or other GitHub runners and link them to their pull requests.
---

# Scan Runner

Run the bundled scanner with the user's runner label:

```bash
bash scripts/scan_milvus_runners.sh <label>
```

The script intentionally scans repositories one by one and can take several
minutes. Run it as a persistent process. If the command yields a session ID or
otherwise reports that it is still running, keep polling that same session
until the process exits. An output yield is not scan completion. Do not impose
a short external timeout, stop after a partial repository list, or parallelize
repository scans.

Resolve `scripts/` relative to this `SKILL.md`, not the current working directory. Default the label to `macos` only when the user omits it.

Return the script's Markdown table without adding or removing columns. The columns are:

1. `URL`: GitHub Actions job URL.
2. `State`: current job state such as `in_progress`, `queued`, or `waiting`.
3. `PR`: pull request URL, or `-` when the workflow run is not associated with a pull request.

Preserve progress and warnings as diagnostics; do not mix them into the table. If authentication fails, report the script error and ask the user to authenticate `gh`.
