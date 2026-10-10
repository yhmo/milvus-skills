---
name: pymilvus
description: Analyze and modify the `milvus-io/pymilvus` repository, whose preferred local checkout is typically `$HOME/work/git-go/pymilvus`. Use for PyMilvus architecture, MilvusClient or AsyncMilvusClient implementation, legacy ORM compatibility, gRPC/protobuf codegen, build/test/lint workflows, examples, benchmarks, releases, publishing, or repository-consistent SDK code changes.
---

# PyMilvus SDK

Repo-specific workflows for the Milvus Python SDK. This is not a general Python or Milvus tutorial.

## Repository

- This skill is for the `milvus-io/pymilvus` repository.
- Locate the repository checkout in this order:
  1. `$HOME/work/git-go/pymilvus` when it exists on this machine;
  2. a directory named `pymilvus` among the parent directories of the current working directory;
  3. `/home/runner/work/pymilvus/pymilvus` (GitHub Actions runner `$GITHUB_WORKSPACE`).
- Confirm the checkout with `git rev-parse --show-toplevel` and `git remote -v` before relying on it. Do not assume the preferred path exists or is the correct repository without verification.
- **Version branch model**: `master` is the dev branch and tracks the newest supported Milvus major release (currently 3.0). Each prior major line keeps a maintenance branch (`2.6` for Milvus 2.6, plus older `2.x` lines). PyMilvus already carries a `3.0` branch; today it tracks `master` and is used for 3.0-line stabilization, and it will diverge once the dev branch advances to a newer Milvus major (3.1/4.0). Always verify the branch-to-Milvus-version mapping from Git rather than assuming a branch name implies a server line.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.

## References

Read the relevant one-level reference before acting:

- Technical design: [references/technical-details.md](references/technical-details.md)
- Build and test: [references/build-and-test.md](references/build-and-test.md)
- Examples: [references/examples.md](references/examples.md)
- Benchmarks: [references/benchmark.md](references/benchmark.md)
- Release and publish: [references/release.md](references/release.md)

## Common workflows

- Trace a public API from `pymilvus/__init__.py` into `milvus_client/`, `client/`, `orm/`, tests, and examples.
- Make minimal changes that follow the existing `MilvusClient`, `AsyncMilvusClient`, or legacy ORM pattern.
- Run targeted tests first, then lint/coverage as needed. The repo uses `uv` for dependency management; prefer `make` targets or `uv run --group dev`.
- Regenerate protobuf output only when Milvus proto definitions changed.
- Explain examples or benchmarks without assuming a Milvus server is already running.
- Prepare release or publishing guidance with awareness of the current major release branches (verify with `git branch -a`), and without changing remote release state.

## Scripts

Run bundled scripts from the skill base directory (this skill's own directory), keeping the shell working directory at the PyMilvus repo root for `api-trace.sh`:

```bash
# from the skill directory
scripts/api-trace.sh search
scripts/validate-skill.sh "$(pwd)"
```

`api-trace.sh` locates the repo root itself via `git rev-parse --show-toplevel`; `validate-skill.sh` accepts the skill directory as its first argument and defaults to the script's parent directory.

## Rules

- Verify current files before acting; this skill records repo state observed at authoring time.
- Prefer the new `MilvusClient` layer for new high-level SDK features.
- Touch legacy `orm/` only for compatibility or explicit legacy API work.
- Do not edit generated `pymilvus/grpc_gen/*` files by hand; use the proto generation workflow.
- Prefer targeted tests before full repo tests.
- Ask before running examples or benchmarks that require a Milvus server, external credentials, large data, or destructive cleanup.
- Never publish packages, push tags, create releases, or modify remote release state without explicit confirmation.
- When committing, use `git commit -sm 'message'` so the committer's email address is recorded; every commit in this repository must carry a Signed-off-by trailer.
- When creating a pull request, ensure each PR contains exactly one commit.

## Evaluation prompts

Should trigger:

- “Where is `MilvusClient.search` implemented?”
- “How do I build and test PyMilvus?”
- “Regenerate the protobuf files.”
- “Run the PyMilvus benchmarks.”
- “How does PyMilvus publish to PyPI?”
- “Add a new MilvusClient API with tests.”

Should not trigger:

- “What is Milvus?”
- “Teach me Python packaging from scratch.”
- “Write unrelated Python code.”
