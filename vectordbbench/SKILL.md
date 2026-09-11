---
name: vectordbbench
description: Analyze and modify the `zilliztech/VectorDBBench` repository, whose preferred local checkout is typically `$HOME/work/git-go/VectorDBBench`. Use for the VDBBench benchmark tool: running insertion / vector search / filtered search / full-text search benchmarks through the `vectordbbench` CLI, the Streamlit web UI (`init_bench`), or the Flask REST API (`init_bench_rest`); selecting case types, datasets, index configurations, and payload profiles; Milvus/Zilliz version matching (pinned pymilvus bounds, Milvus server features such as `query_mode=large_topk`, per-index/SQ/GPU capability gates); adding, updating, or debugging vector-database clients (`vectordb_bench/backend/clients/*`) and their CLI commands; and repository-consistent fixes, tests, and reviews. Do not use for the Milvus server or Milvus SDK repositories when a dedicated skill applies.
---

# VectorDBBench (VDBBench)

Work from repository evidence. Treat this skill as a workflow and navigation layer, not as a substitute for the checkout's current `README.md`, `pyproject.toml`, source, tests, or CI configuration.

## Repository

- This skill is for the `zilliztech/VectorDBBench` repository (Python 3.11+ benchmark tool for vector databases and cloud services).
- Upstream remote is normally `origin` (`git@github.com:zilliztech/VectorDBBench.git`); `liqing` may be the user's fork.
- Prefer the local checkout at `$HOME/work/git-go/VectorDBBench` when it exists on this machine. If the current working directory is already inside that repository, use its root instead.
- Confirm the checkout with `git rev-parse --show-toplevel` and `git remote -v` before relying on it. Do not assume the preferred path exists or is the correct repository without verification.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.

## Start every task

1. Locate and verify the repository root using the repository guidance above, then keep shell commands rooted there.
2. Read `README.md` sections relevant to the request (Quick Start, CLI examples, Module/Code Structure, Contribution/Adding New Clients) and any `docs/release/*.md` notes that apply, before explaining or editing code.
3. Inspect `git status --short`; preserve unrelated user changes and generated artifacts (results, dataset downloads, `.env`).
4. Classify the request as explanation, usage help, diagnosis, targeted change, new-client/case work, or verification. Do not implement a fix for a diagnosis-only or usage-only request.
5. Read the relevant one-level reference:
   - Tool usage, CLI, web UI, REST API, datasets, and case types: [references/usage.md](references/usage.md)
   - Milvus/Zilliz client and server version matching: [references/version-matching.md](references/version-matching.md)
   - Code structure, adding clients/cases, tests, and lint: [references/development.md](references/development.md)

## Usage guidance

- Explain and run VDBBench as a tool with the actual entry points: `vectordbbench` (CLI), `init_bench` (Streamlit web UI), and `init_bench_rest` (Flask REST API). See [references/usage.md](references/usage.md).
- Before proposing a run command, check `vectordbbench --help` and `vectordbbench <command> --help` so the case type, dataset, and index parameters match the current checkout. Command names are the lowercase function names registered in `vectordb_bench/cli/vectordbbench.py` and the client `cli.py` modules.
- Version-match Milvus/Zilliz targets deliberately (pymilvus bounds, large TopK, index/SQ/GPU features, FTS). See [references/version-matching.md](references/version-matching.md).

## Investigate before acting

1. Find symbols and files with `rg` or `rg --files`; do not infer paths from the README alone.
2. Trace behavior across its actual boundaries: CLI TypedDict → `cli.py` `run()` → `TaskConfig` → `backend/assembler.py` / `task_runner.py` → the database client in `backend/clients/*` → `result_collector.py` / results JSON.
3. Read both callers and callees. Include case assembly, dataset selection, filter/payload handling, concurrency runners, and result formatting when they can change the outcome.
4. Base conclusions on source evidence; cite concrete paths and distinguish verified behavior from inference.

## Implement changes

- Make the smallest coherent change that preserves established patterns and client boundaries.
- A new client requires the `VectorDB` subclass in `backend/clients/<name>/<name>.py`, `config.py` (`DBConfig` + optional `DBCaseConfig`), registration in the `DB` enum in `backend/clients/__init__.py`, and an optional `cli.py` imported by `vectordb_bench/cli/vectordbbench.py`. Follow [README: Adding New Clients](https://github.com/zilliztech/VectorDBBench#adding-new-clients) and [references/development.md](references/development.md).
- Keep configuration in pydantic models (`DBConfig`, `DBCaseConfig`); use `SecretStr` for credentials. Never log or store connection secrets.
- Do not hand-edit result JSON in `vectordb_bench/results/` as a workaround; results are produced by runs.
- Do not commit, push, publish, or run destructive benchmark loads unless the user authorizes that action.

## Verify and report

1. Run the narrowest relevant test first from the repository root, typically `PYTHONPATH=. python3 -m pytest tests/test_<area>.py -k <name>`; use `make lint` / `make format` for black+ruff. See [references/development.md](references/development.md).
2. For a usage change, verify with `--dry-run` on a CLI command to confirm parameter wiring without executing a load.
3. Report the outcome first, then changed files, verification performed, and any unverified claims or remaining risks.

## Evaluation prompts

Should trigger:

- "How do I run a VectorDBBench benchmark against Milvus/Zilliz (or Qdrant, PgVector, ...) from the CLI?"
- "Which case type and dataset should I pick for a 100M-vector search performance test?"
- "Why does K > 16384 fail for Milvus, and what needs `query_mode=large_topk`?"
- "Add a new client/backend for <database> to VDBBench, including its CLI command."
- "Fix this filtered-search or FTS case result."
- "Review this VDBBench change for version or config compatibility."

Should not trigger:

- "Trace a Milvus query coordinator scheduling bug." (use the milvus skill)
- "Add an API to PyMilvus." (use the pymilvus skill)
- "Explain vector databases without using the VectorDBBench repository."
