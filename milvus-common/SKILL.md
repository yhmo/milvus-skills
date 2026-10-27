---
name: milvus-common
description: Analyze and modify the `zilliztech/milvus-common` C++ library, which bridges Milvus and Knowhere and is consumed as a submodule by `milvus-io/milvus` internal/core. Use for the caching layer (Manager/CacheSlot/Translator/DList/loading-overhead groups), common utilities (EasyAssert error codes, OpContext, OpenTelemetry Tracer), filemanager, knowhere thread pools/aio, glog logging, SyncPoint testing, flat_hash_map/ptrhash, CMake/Conan builds, GTest unit tests, CI, and repository-consistent reviews or fixes. Do not use for the `milvus-io/milvus` server repository or for standalone SDK repositories when a dedicated skill applies.
---

# Milvus Common

Work from repository evidence. This skill is a workflow and navigation layer, not a substitute for the checkout's source, documentation, or CI configuration.

## Repository

- This skill is for the `zilliztech/milvus-common` repository; the user's fork is `yhmo/milvus-common` (remote `origin`), with `source` pointing to upstream.
- Resolve the repository with the bundled helper before relying on a path:

  ```bash
  python3 "$SKILL_DIR/scripts/resolve_repo.py"
  ```

  The helper prefers a matching repository at the current cwd, then checks preset
  locations (`$HOME/work/git-go`, `$HOME/work`, a cwd child/sibling, and the
  temporary area). If none is valid, it automatically clones
  `zilliztech/milvus-common` to
  `${TMPDIR:-/tmp}/milvus-skills/milvus-common` with remote `source`. The automatic
  clone is depth-1 by default; pass `--full` only when complete history is
  required. `--branch` accepts a branch or tag and guarantees the returned checkout is on
  that ref: a fresh clone checks the ref out directly, and an existing checkout
  is fetched (depth 1) and switched automatically — no manual fetch/checkout
  step. Switching is refused while the worktree is dirty; commit, stash, or
  clean first. Use the returned `path`, `upstream_remote`, `ref_type`, and
  `ref_action`; pass `--no-clone` when network access must not be used.
  Confirm the returned checkout with `git rev-parse --show-toplevel` and
  `git remote -v` before relying on it.
- `master` is the active development line. Legacy lines such as `v1.x` or `2.6` are maintained upstream; confirm the target branch from Git rather than assuming it matches `master`.
- **Branch overlay**: the differences between `master` and `2.6` are minimal — `2.6` lacks `src/cachinglayer/LoadingOverhead.cpp`, the top-level `Makefile`, `OWNERS`, and `docs/`. See [references/branch-differences.md](references/branch-differences.md). If `git branch --show-current` returns `2.6`, read that overlay before applying baseline knowledge.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.

## Start every task

1. Locate and verify the repository root using the repository guidance above, then keep shell commands rooted there.
2. Read every applicable `AGENTS.md` from the root to the files in scope before explaining or editing code.
3. Inspect `git status --short`; preserve unrelated user changes and generated artifacts.
4. Classify the request as explanation, diagnosis, targeted change, design/cross-component change, or verification. Do not implement a fix for a diagnosis-only request.
5. Read the relevant one-level references:
   - Component layout and behavior: [references/architecture.md](references/architecture.md)
   - Build, test, lint, and platform quirks: [references/build-and-test.md](references/build-and-test.md)
   - Conventions, error codes, and change rules: [references/change-rules.md](references/change-rules.md)
   - Branch differences (2.6 vs master): [references/branch-differences.md](references/branch-differences.md)

## Investigate before acting

1. Find symbols and files with `rg` or `rg --files`; do not infer current paths from this skill.
2. Trace behavior end to end across its actual boundaries: public header API, `cachinglayer` admission/LRU/eviction state, cgo projection into Milvus segcore, Knowhere consumers, metrics, and tests.
3. Read both callers and callees. Include the waiting queue, background eviction loop, cancellation callbacks, Group policy updates, and RAII release guards when they can change the result.
4. For a documented subsystem such as loading-overhead groups, read the design doc under `docs/design-docs/` and cross-check it against the implementation. Stop and ask the user if docs and source contradict each other.
5. Base conclusions on documentation plus source. Cite concrete paths and distinguish verified behavior from inference.

## Implement changes

- Make the smallest coherent change that preserves component boundaries and established patterns.
- This is a shared library consumed by Milvus and Knowhere. Preserve public API/ABI and header compatibility unless the task explicitly changes the contract.
- Preserve hot-path discipline in the caching layer and tracer: avoid per-access allocations, refcount bumps, and contended atomic counters on fast paths. See `CacheSlot::TryBorrowCell` and `RecordAccessEvent` comments before touching access paths.
- Read [references/change-rules.md](references/change-rules.md) before originating, wrapping, or classifying errors. Preserve typed `ErrorCode` and retriable `StorageTransientError` semantics deliberately.
- Keep metrics definitions and their accessor helpers in sync when adding or changing a metric family.
- Never hand-edit generated or vendored files. Change their source of truth and regenerate.
- Do not commit, push, publish, or run destructive integration workflows unless the user authorizes that action.
- When committing, use `git commit -sm '<message>'` so the committer's email address is recorded; every commit in this repository must carry a Signed-off-by trailer. Use conventional subjects such as `enhance: ... (#N)` or `fix: ... (#N)`.
- When creating a pull request, ensure each PR contains exactly one commit.

## Verify and report

1. Run the narrowest relevant tests first, then expand according to the affected boundary and risk. Use `make test` for the full suite or build the focused binary and run `--gtest_filter`.
2. For concurrency, waiter, or policy-reconciliation work, trace each failure mode end to end and run the tests under ASan when the surrounding build supports it.
3. Run clang-format/pre-commit checks when the touched files require them.
4. Report the outcome first, then changed files, verification performed, and any unverified claims or remaining risks. Never claim a behavior was achieved unless its relevant failure modes were traced or fault-injected.

## Evaluation prompts

Should trigger:

- "Trace how a cell load is reserved, pinned, and evicted in the caching layer."
- "Fix this DList waiting-queue or eviction bug and add tests."
- "Add a loading-overhead Group policy or change the UpdateLoadingOverheadGroup contract."
- "Classify a caching-layer failure with the right ErrorCode at the cgo boundary."
- "How do I build or test milvus-common?"
- "Review this milvus-common change for reservation and error-code propagation."

Should not trigger:

- "Add an API to PyMilvus."
- "Fix a QueryCoord scheduling bug in the Milvus server."
- "Explain vector databases without using this repository."
