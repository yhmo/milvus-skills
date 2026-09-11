---
name: milvus
description: Analyze and modify the `milvus-io/milvus` server repository, whose preferred local checkout is typically `$HOME/work/git-go/milvus`. Use for Milvus architecture and API tracing, coordinator/node behavior, Go/C++/Rust implementation work, streaming/WAL changes, observability, error handling, configuration, protobuf or mock generation, build and test workflows, debugging, behavioral verification, and repository-consistent review or release preparation. Do not use for standalone Milvus SDK repositories such as PyMilvus or milvus-sdk-* when a dedicated SDK skill applies.
---

# Milvus Server

Work from repository evidence. Treat this skill as a workflow and navigation layer, not as a substitute for the checkout's current `AGENTS.md`, documentation, source, or CI configuration.

## Repository

- This skill is for the `milvus-io/milvus` repository.
- Prefer the local checkout at `$HOME/work/git-go/milvus` when it exists on this machine. If the current working directory is already inside that repository, use its root instead.
- Confirm the checkout with `git rev-parse --show-toplevel` and `git remote -v` before relying on it. Do not assume the preferred path exists or is the correct repository without verification.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.

## Start every task

1. Locate and verify the repository root using the repository guidance above, then keep shell commands rooted there unless a module-specific command requires another directory.
2. Read every applicable `AGENTS.md` from the root to the files in scope before explaining or editing code.
3. Inspect `git status --short`; preserve unrelated user changes and generated artifacts.
4. Classify the request as explanation, diagnosis, targeted change, design/cross-component change, generation, or verification. Do not implement a fix for a diagnosis-only request.
5. Read the relevant one-level references:
   - Architecture and trace routes: [references/architecture.md](references/architecture.md)
   - Change constraints and behavioral verification: [references/change-rules.md](references/change-rules.md)
   - Build, test, lint, and generation commands: [references/build-and-test.md](references/build-and-test.md)

Run `scripts/repo-context.sh` when a quick current-checkout snapshot would help. Execute it from any directory inside the Milvus checkout.

## Investigate before acting

1. Find symbols and files with `rg` or `rg --files`; do not infer current paths from this skill.
2. Trace the behavior end to end across its actual boundaries: public/protobuf API, Proxy, coordinator, node, storage/WAL or segcore, response/error projection, tests, and metrics as applicable.
3. Read both callers and callees. Include retry loops, caches, async callbacks, recovery paths, and generated boundaries when they can change the result.
4. For a documented subsystem, follow the checkout's mandatory sequence exactly: read the top-level guide, read all required sub-documents, read their Key Packages, then cross-check documentation against source. For design or cross-component work, read every subsystem sub-document. Stop and ask the user if subsystem docs and source contradict each other.
5. Base conclusions on documentation plus source. Cite concrete paths and distinguish verified behavior from inference.

## Implement changes

- Make the smallest coherent change that preserves component boundaries and established patterns.
- Respect Go module ownership. In particular, run dependency operations for `pkg/` from `pkg/`, for `client/` from `client/`, and for `tests/go_client/` from `tests/go_client/`. Verify the current module path and major version from each `go.mod`.
- Read the repository error-handling guide and casebook before originating, wrapping, or classifying errors. Preserve typed codes and retry semantics deliberately.
- Read the observability guide before changing logs, metrics, or traces. Use the logging package and context policy required by the checkout.
- Never hand-edit generated protobuf or mock files. Change their source and use the repository generator target.
- Keep configuration in the established paramtable/config pipeline and verify the current module import path from source.
- Do not commit, push, publish, start external services, or run destructive integration workflows unless the user authorizes that action.
- When committing, use `git commit -sm '<message>'` so the committer's email address is recorded; every commit in this repository must carry a Signed-off-by trailer.
- When creating a pull request, ensure each PR contains exactly one commit.

## Verify and report

1. Run the narrowest relevant tests first, with the mandatory Milvus Go test tags and gcflags. Expand according to the affected boundary and risk.
2. For behavioral work, audit construction and rewrite sites across the repository, trace each real failure mode to its consumer, and adversarially check untested paths. Passing success-path tests alone is insufficient.
3. Run formatting, lint, generated-file guards, module-wide tests, C++ tests, or integration tests when the contract touched requires them; use [references/build-and-test.md](references/build-and-test.md).
4. Report the outcome first, then changed files, verification performed, and any unverified claims or remaining risks. Never claim a behavior was achieved unless its relevant failure modes were traced or fault-injected end to end.

## Evaluation prompts

Should trigger:

- "Trace how a search request flows through Milvus."
- "Fix this QueryCoord scheduling bug and add tests."
- "Add a WAL message type and update streaming behavior."
- "Classify this segcore error correctly at the Go boundary."
- "How do I build or test the Milvus server?"
- "Review this Milvus change for retry and error-code propagation."

Should not trigger:

- "Add an API to PyMilvus."
- "Prepare a release of milvus-sdk-java."
- "Explain vector databases without using the Milvus repository."
