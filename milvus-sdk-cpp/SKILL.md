---
name: milvus-sdk-cpp
description: Analyze and modify the `milvus-io/milvus-sdk-cpp` repository, whose preferred local checkout is typically `$HOME/work/git-go/milvus-sdk-cpp`. Use for C++ SDK architecture and API tracing, MilvusClient/MilvusClientV2 request-response work, connection and retry behavior, schema or session-timestamp caches, DML/DQL and iterators, CMake/Conan builds, unit/mocked/system tests, examples, packaging, releases, and repository-consistent reviews or fixes.
---

# Milvus C++ SDK

Work in the standalone `milvus-io/milvus-sdk-cpp` repository. Do not use this skill for the Milvus server or another
language SDK except when comparing behavior.

## Start every task

1. Locate the repository checkout in this order: `$HOME/work/git-go/milvus-sdk-cpp` when it exists on this machine; a directory named `milvus-sdk-cpp` among the parent directories of the current working directory; `/home/runner/work/milvus-sdk-cpp/milvus-sdk-cpp` (GitHub Actions runner `$GITHUB_WORKSPACE`).
2. Confirm it with `git rev-parse --show-toplevel` and `git remote -v`.
3. Check `git branch --show-current`, `git status --short`, and the relevant upstream branch before assuming API parity.
4. Preserve unrelated user changes. Use `apply_patch` for edits.
5. Search with `rg` or run `scripts/api-trace.sh`; do not infer an API path from filenames alone.

## Load the relevant reference

- Read [references/technical-details.md](references/technical-details.md) for architecture, source layout, public API
  changes, connection/retry behavior, caches, DML/DQL, sessions, iterators, and protobuf conversion.
- Read [references/build-and-test.md](references/build-and-test.md) before configuring, building, testing, linting, or
  debugging CI.
- Read [references/branch-2.6.md](references/branch-2.6.md) when working on the `2.6` maintenance branch, in addition
  to the baseline references.
- Read [references/examples.md](references/examples.md) before changing, building, or running examples.
- Read [references/release.md](references/release.md) for version preparation, package metadata, tags, workflows, and
  release-note investigation.

## Branch context

- `source` is normally the upstream `milvus-io/milvus-sdk-cpp` remote; `origin` is usually the user's fork.
- `master` is the active development line; legacy release lines such as `2.6` are maintained separately. Confirm any
  additional release branch from Git rather than assuming it matches `master`.
- **Version branch model**: absent a dedicated major-version branch, `master` is both the development branch and the
  release branch for the newest supported Milvus major — `x.y.z` releases for that major are cut directly from it.
  `master` currently tracks the Milvus 3.0 line (no separate `3.0` branch exists). Each prior major line keeps a
  maintenance branch (`2.6` for Milvus 2.6, plus older lines like `2.5`/`2.4`). When the SDK advances to a newer Milvus
  major (3.1/4.0), `master` will follow it and a `3.0` branch will be created or frozen to serve Milvus 3.0 users (some
  other SDKs already carry a `3.0` branch that today tracks their dev line). Always verify the
  branch-to-Milvus-version mapping from Git rather than assuming a branch name implies a server line.
- **Branch overlay**: the other references describe the `master` baseline. If `git branch --show-current` returns `2.6`,
  you MUST read [references/branch-2.6.md](references/branch-2.6.md) before applying any knowledge from the baseline
  references. On `2.6`, these baseline items do **not** exist:
  `AGENTS.md` · `Doxyfile` · `test/e2e/` · `ClientRequestContext.h` · `ClientTelemetry.h` · `MilvusClientV2Session.h` ·
  `request/import/` · `request/rls/` · `request/snapshot/` ·
  `request/collection/AddCollectionStructFieldRequest` / `AddFunctionFieldRequest` / `DropCollectionFieldRequest` / `DropFunctionFieldRequest` ·
  `request/utility/FileResourceRequest` / `ListCompactionTasksRequest` / `RefreshExternalCollectionRequest` ·
  `response/rls/` · `response/snapshot/` ·
  `types/FunctionChain.h` / `SearchAggregation.h` / `AggregationBucket.h` / `BloomFilter.h` / `RoaringBitmap.h` / `RowPolicy.h` / `TelemetryConfig.h` ·
  `types/FileResourceInfo.h` / `RestoreSnapshotJobInfo.h` / `RefreshExternalCollectionJobInfo.h` / `OrderByField.h` / `IndexParam.h` ·
  examples: `snapshot.cpp` / `rls.cpp` / `function_chain.cpp` / `search_aggregation.cpp` / etc.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs
  are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch —
  `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` —
  where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or
  `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native
  remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before
  editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.
- For Java parity, compare C++ `master` with Java `master`, and the C++ legacy release line with the Java legacy line or
  the user's local equivalent.

## Repository rules

- Prefer `MilvusClientV2` request/response APIs for new features. Keep `MilvusClient` compatible and add V1 features
  only when explicitly requested or needed for a critical fix/parity change.
- Preserve the aggregate-header design: consumers may include only `milvus/MilvusClientV2.h`; add required public DTO
  headers there when exposing a new V2 API.
- Keep public declarations, implementation declarations, DTO headers/implementations, protobuf conversion, examples,
  and tests synchronized.
- For every cache-aware RPC path, use one consistent endpoint, resolved database, collection or alias name, and schema
  load scope. Audit successful DDL mutation callbacks for schema/timestamp invalidation or transfer.
- Do not edit generated protobuf files under the build tree. Change SDK conversion code or dependency/proto inputs.
- Build with at most four jobs. Prefer focused unit or mocked tests before broader test binaries.
- Ask before starting Docker/system tests, running examples that mutate Milvus, installing outside the repository,
  publishing packages, pushing tags, or changing remote release state.
- Do not invent a benchmark workflow; this repository currently has none.
- When committing, use `git commit -sm 'message'` so the committer's email address is recorded; every commit in this repository must carry a Signed-off-by trailer.
- When creating a pull request, ensure each PR contains exactly one commit.

## Beyond MilvusClientV2: separate capabilities

`MilvusClientV2` is not the whole SDK. The client also ships **`milvus::BulkImport`** — a standalone static-utility
class that talks to the Milvus/Zilliz Cloud **import REST API** (no client connection needed): `CreateImportJobs`,
`ListImportJobs`, `GetImportJobProgress`, `CommitImport`, `AbortImport` (counterparts of pymilvus `bulk_import` /
`get_import_progress`). There is **no client pool** in the C++ SDK (unlike Java). See
`references/technical-details.md` → "Beyond MilvusClientV2". Route bulk-import work to `BulkImport`, not
`MilvusClientV2`.

## Helpers

Run bundled helpers from the SDK repository root. `$SKILL_DIR` is this skill's base directory — the directory that directly contains both `SKILL.md` and `scripts/` — as exposed by the host agent that loaded the skill (or locate it yourself); never hardcode a `.codex`, `.opencode`, or other agent-specific prefix.

```bash
"$SKILL_DIR/scripts/api-trace.sh" DescribeCollection
"$SKILL_DIR/scripts/release-window.sh" vX.Y.Z
"$SKILL_DIR/scripts/validate-skill.sh"
```

## Typical triggers

- Trace or add a `MilvusClientV2` API and its request/response types.
- Diagnose connection, retry, deadline, cache, consistency, iterator, or schema-refresh behavior.
- Build/test with CMake or Conan, investigate Linux/macOS/Windows CI, or fix package exports.
- Update examples, prepare a release, summarize a release window, or review a C++ SDK PR.
- Work with bulk import (`milvus::BulkImport` — cloud REST import jobs).
