---
name: cardinal
description: Analyze and modify the private `zilliztech/cardinal` repository (Milvus ANN index library), whose preferred local checkout is typically `$HOME/work/git-go/cardinal`. Use for C++20/23 ANN index architecture and API tracing, MemGraph/DiskGraph/IVF search and build, quantization (SQ4/SQ8, RBQ, SAQ), DataSet/VecLoader/compute, graph serialization, storage backends (memory/disk/mmap), the `know/` Knowhere adapter layer, Conan/Makefile build and Catch2 unit test workflows, compatibility and debug work, and repository-consistent reviews or fixes. Do not use for the Milvus server, Knowhere, or standalone SDK repositories such as milvus-sdk-*.
---

# Cardinal

Work from repository evidence. Treat this skill as a workflow and navigation layer, not as a substitute for the checkout's current `CLAUDE.md`, documentation, source, or CI configuration.

## Repository

- This skill is for the private `zilliztech/cardinal` repository (fork `yhmo/cardinal`), an ANN vector index library integrated into Milvus/Knowhere.
- Locate the repository checkout in this order:
  1. `$HOME/work/git-go/cardinal` when it exists on this machine;
  2. a directory named `cardinal` among the parent directories of the current working directory;
  3. `/home/runner/work/cardinal/cardinal` (GitHub Actions runner `$GITHUB_WORKSPACE`).
- Confirm the checkout with `git rev-parse --show-toplevel` and `git remote -v` before relying on it. `source` is normally the upstream `zilliztech/cardinal` remote; `origin` is usually the user's fork. Do not assume the preferred path exists or is the correct repository without verification.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.

## Start every task

1. Resolve the repository root; keep shell commands rooted there unless a module-specific command requires another directory.
2. Read `CLAUDE.md` and every applicable `AGENTS.md` from the root to the files in scope before explaining or editing code.
3. Inspect `git branch --show-current` and `git status --short`; preserve unrelated user changes and generated artifacts.
4. Classify the request as explanation, diagnosis, targeted change, design/cross-component change, generation, or verification. Do not implement a fix for a diagnosis-only request.
5. Read the relevant one-level references:
   - Architecture, layers, source layout, and change patterns: [references/technical-details.md](references/technical-details.md)
   - Build, test, lint, and generation commands: [references/build-and-test.md](references/build-and-test.md)

Run `scripts/repo-context.sh` when a quick current-checkout snapshot would help.

## Investigate before acting

1. Find symbols and files with `rg` or `rg --files`; do not infer current paths from this skill or from filenames alone.
2. Trace the behavior end to end across its actual boundaries: DataSet/VecLoader, Computer, Graph/IVF build, Searcher pipeline, Quant encode/decode, Serialization, and the `know/` adapter, plus tests and metrics as applicable.
3. Read both callers and callees. Include composed builders/searchers, async build paths, mmap/disk IO, prefetch/refine stages, and serialization compatibility code when they can change the result.
4. Base conclusions on source plus `docs/design.md`. Cite concrete paths and distinguish verified behavior from inference. If documentation and source contradict each other, treat current code as authoritative and stop to ask the user when a design decision is at stake.
5. For cross-layer changes, respect the three-layer rule: objects in a lower layer (Storage) must not manipulate objects of an upper layer (Data, Algorithm).

## Implement changes

- Make the smallest coherent change that preserves component boundaries and established patterns.
- Follow the code conventions: owner types are move-only and own resources; view types are copyable and used transiently; constrain template types with C++20 concepts; pass move-only types by value; use RAII for every resource acquisition; never store view types as class members.
- Files under `/include` must compile with C++17 for downstream consumers and may only include files also under `/include`.
- Metrics, quantization types, and index/search configurations are declared in `cardinal/` headers (`metric.h`, `quantization_config.h`, `*_params.h`); keep runtime/config changes consistent with the compile-time pruning (`ENABLE_COMPILE_PRUNE`) path.
- Never hand-edit generated or serialized-format code that affects on-disk compatibility. Index versions carry serialization compatibility guarantees (e.g. nullable id-map v10/v11); audit version-gated paths before touching format code.
- Do not commit, push, publish, start external services, or run destructive integration workflows unless the user authorizes that action.
- Run `pre-commit` before committing. When committing, use `git commit -sm '<message>'` so the committer's email address is recorded; every commit in this repository must carry a Signed-off-by trailer.

## Verify and report

1. Run the narrowest relevant Catch2 test first (tag or name filter on `test_cardinal`), then expand to the full unit test set. Follow [references/build-and-test.md](references/build-and-test.md) for exact commands.
2. For behavioral work, audit construction and rewrite sites across the repository, trace each real failure mode to its consumer, and adversarially check untested paths. Passing success-path tests alone is insufficient. When touching quantized or compressed data paths, compare against a brute-force reference where feasible.
3. Run clang-format and the pre-commit hooks when the contract touched requires them; use the repository's `.clang-format` (v18) and `.clang-tidy`/`.clang-tidy-ignore` as configured.
4. Report the outcome first, then changed files, verification performed, and any unverified claims or remaining risks.

## Evaluation prompts

Should trigger:

- "Trace how a query flows through Cardinal from DataSet to search result."
- "Add or fix an index builder/searcher path (MemGraph, DiskGraph, IVF)."
- "Implement or fix a quantization encode/decode or its distance computation."
- "Change serialization and preserve compatibility with index version N."
- "How do I build or run Cardinal unit tests?"
- "Review this Cardinal change for the know/ adapter or for correctness under mmap/disk IO."

Should not trigger:

- "Trace the Milvus QueryCoord scheduling path." (Milvus server)
- "Fix this bug in milvus-sdk-cpp." (SDK)
- "Explain ANN search without using the Cardinal repository."
