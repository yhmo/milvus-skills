---
name: knowhere
description: Analyze and modify the `zilliztech/knowhere` repository, whose preferred local checkout is typically `$HOME/work/git-go/knowhere`. Use for Knowhere C++ ANN engine architecture, index implementations (Flat, HNSW, IVF/SCANN, DISKANN/AISAQ, Sparse, MinHash, GPU/cuVS), the index factory and config systems, data types and metrics, third-party libraries (faiss, hnswlib, DiskANN, Cardinal), C++/Conan/CMake builds, Catch2 unit tests, SIMD kernels, Python wheel packaging, pre-commit code quality, and repository-consistent reviews or fixes.
---

# Knowhere

Work from repository evidence. Treat this skill as a workflow and navigation layer, not as a substitute for the checkout's current `CLAUDE.md`, documentation, source, or CI configuration.

## Repository

- This skill is for the `zilliztech/knowhere` repository (C++ vector search engine, the ANN core of Milvus).
- Upstream remote is normally `source`; `origin` is usually the user's fork.
- Resolve the repository with the bundled helper before relying on a path:

  ```bash
  python3 "$SKILL_DIR/scripts/resolve_repo.py"
  ```

  The helper prefers a matching repository at the current cwd, then checks preset
  locations (`$HOME/work/git-go`, `$HOME/work`, a cwd child/sibling, and the
  temporary area). If none is valid, it automatically clones
  `zilliztech/knowhere` to
  `${TMPDIR:-/tmp}/milvus-skills/knowhere` with remote `source`. The automatic
  clone is depth-1 by default; pass `--full` only when complete history is
  required. `--branch` accepts a branch or tag and guarantees the returned checkout is on
  that ref: a fresh clone checks the ref out directly, and an existing checkout
  is fetched (depth 1) and switched automatically — no manual fetch/checkout
  step. Switching is refused while the worktree is dirty; commit, stash, or
  clean first. Use the returned `path`, `upstream_remote`, `ref_type`, and
  `ref_action`; pass `--no-clone` when network access must not be used.
  Confirm the returned checkout with `git rev-parse --show-toplevel` and
  `git remote -v` before relying on it.
- **Version branch model**: `main` is the active development line; `3.0` and `2.6` are the current released maintenance lines. The branches differ significantly in index coverage: `main` adds the sparse inverted-index rewrite (codec/searcher/SINDI), SVS index, faiss direct integration, emb-list strategies, MRL index, clustering kmeans, build scheduler, and SIMD LSX/LASX — most of which are absent from maintenance branches. See [references/branch-differences.md](references/branch-differences.md) for the full comparison.
- **Branch overlay**: the other references describe the `main` baseline. If `git branch --show-current` returns `3.0` or `2.6`, you MUST read [references/branch-differences.md](references/branch-differences.md) before applying any knowledge from the baseline references. On `3.0`/`2.6`, these baseline items do **not** exist:
  sparse codec (`src/index/sparse/codec/`) · sparse searcher (`src/index/sparse/searcher/`) · SINDI variants · SVS index · `src/index/faiss/` · emb-list strategies · MRL index (`mrl_index_node`) · clustering kmeans · `build_scheduler` · `cancellation` · SIMD LSX/LASX.
  `2.6` additionally lacks the HNSW/IVF RaBitQ wrappers present on `3.0`.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.

## Start every task

1. Locate and verify the repository root using the repository guidance above, then keep shell commands rooted there unless a module-specific command requires another directory.
2. Read `CLAUDE.md` and any applicable project skill docs (`.claude/skills/`: architecture, building, testing, code-quality, git-workflow) before explaining or editing code.
3. Inspect `git branch --show-current` and `git status --short`; preserve unrelated user changes.
4. Classify the request as explanation, diagnosis, targeted change, design/cross-component change, or verification. Do not implement a fix for a diagnosis-only request.
5. Read the relevant one-level reference:
   - Architecture, source layout, index types, and dependencies: [references/technical-details.md](references/technical-details.md)
   - Build, test, lint, and wheel commands: [references/build-and-test.md](references/build-and-test.md)
   - Branch differences (2.6 vs 3.0 vs main): [references/branch-differences.md](references/branch-differences.md)

## Investigate before acting

1. Find symbols and files with `rg` or run `scripts/api-trace.sh`; do not infer an implementation path from index names or filenames alone.
2. Trace behavior across its actual boundaries: index factory registration, config validation, data type conversion, third-party boundaries (faiss/hnswlib/DiskANN/Cardinal), SIMD kernels, and the tests that exercise them.
3. Read both callers and callees. Include refiner wrappers (SCANN, IVF_RABITQ, DataViewRefiner), the thread-pool and data-mock node wrappers, interrupt handling, and result post-processing when they can change the result.
4. Base conclusions on source evidence; cite concrete paths and distinguish verified behavior from inference.

## Implement changes

- Make the smallest coherent change that preserves established patterns and index boundaries.
- Register new index types through the factory pattern in `src/index/index_factory.cc` with the `KNOWHERE_SIMPLE_REGISTER_GLOBAL` macro; keep public headers, config validation, and tests synchronized.
- Never hand-edit generated files or third-party fork sources as a workaround; change the wrapper or inputs and rebuild.
- Run pre-commit on changed files before committing: `pre-commit run --files <changed-files>`.
- When committing, use `git commit -s -m '<type>: <description>'` so every commit carries a Signed-off-by trailer (DCO). Commit types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
- Do not commit, push, publish, or run destructive build/test workflows unless the user authorizes that action.

## Verify and report

1. Build the narrowest relevant configuration first and run focused Catch2 tests; use [references/build-and-test.md](references/build-and-test.md).
2. For behavioral work (distances, metrics, top-k, quantization, iteration), audit construction and rewrite sites and adversarially check edge cases such as empty sets, low cardinality, and out-of-range params.
3. Report the outcome first, then changed files, verification performed, and any unverified claims or remaining risks.

## Helpers

Run bundled helpers from the skill directory. `$SKILL_DIR` is this skill's base directory — the directory that directly contains both `SKILL.md` and `scripts/` — as exposed by the host agent that loaded the skill (or locate it yourself); never hardcode a `.codex`, `.opencode`, or other agent-specific prefix.

```bash
"$SKILL_DIR/scripts/api-trace.sh" SYMBOL
"$SKILL_DIR/scripts/validate-skill.sh"
```

## Evaluation prompts

Should trigger:

- "Trace how the search result is refined for SCANN or IVF_RABITQ."
- "Fix this HNSW recall regression and add a unit test."
- "Add a new index type through the index factory."
- "How do I build knowhere with GPU/ASAN or run a focused Catch2 test?"
- "Why is `knowhere::expected` returning a specific status here?"
- "Review this knowhere change for config validation and metric handling."

Should not trigger:

- "Add an API to PyMilvus or milvus-sdk-*."
- "Prepare a release of the Milvus server."
- "Explain vector databases without using the knowhere repository."
