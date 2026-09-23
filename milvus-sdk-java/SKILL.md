---
name: milvus-sdk-java
description: Analyze and modify the `milvus-io/milvus-sdk-java` repository, including the active MilvusClientV2 facade/service/request-response architecture, shared schema and session-timestamp caches, iterators, global-cluster routing, client pools, gRPC/protobuf generation and shading, BulkWriter, tests, examples, benchmarks, releases, and branch-parity work. Use for Java SDK API tracing, bug diagnosis, repository-consistent implementation, build/CI failures, release preparation or publication, and comparisons with Milvus, PyMilvus, or other Milvus SDKs.
---

# Milvus Java SDK

Use this skill only for `milvus-io/milvus-sdk-java`.

## Repository and branch context

- Prefer the current working tree when it is already the Java SDK repository; otherwise locate the repository checkout on this machine (for example `$HOME/work/git-go/milvus-sdk-java`).
- Confirm the checkout with `git rev-parse --show-toplevel`, `git remote -v`, `git branch --show-current`, and `git status --short` before relying on it.
- Use remote `source` as upstream when it points to `milvus-io/milvus-sdk-java`.
- Treat `source/master` as the current design baseline. Treat legacy release branches as maintenance lines whose source layout and supported APIs may differ.
- **Version branch model**: `master` tracks the newest supported Milvus major release (currently 3.0). Each prior major line keeps a maintenance branch (`2.6` for Milvus 2.6). Some SDKs — including Java — already carry a `3.0` branch; today it tracks `master` and is used for 3.0-line stabilization, and it will diverge once the dev branch advances to a newer Milvus major (3.1/4.0). Always verify the branch-to-Milvus-version mapping from Git rather than assuming a branch name implies a server line.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.
- Do not switch, reset, or overwrite a dirty worktree to inspect another branch. Use `git show`, `git ls-tree`, or a clean secondary checkout/worktree.

## Load the relevant reference

Read each selected reference completely before acting:

- Architecture and runtime dataflow: [references/technical-details.md](references/technical-details.md)
- Package and file routing: [references/source-layout.md](references/source-layout.md)
- Build, proto generation, and tests: [references/build-and-test.md](references/build-and-test.md)
- Examples: [references/examples.md](references/examples.md)
- Benchmarks: [references/benchmark.md](references/benchmark.md)
- Releases and publishing: [references/release.md](references/release.md)

For architecture or implementation work, normally read both `technical-details.md` and `source-layout.md`.

## Core workflows

### Trace a V2 API

1. Run `scripts/v2-api-trace.sh METHOD_OR_CLASS` from the repository root.
2. Trace the public method in `MilvusClientV2` through `RpcUtils.retry` (blocking) or `RpcUtils.retryAsync` (async DQL), the owning domain service, request/protobuf conversion, the blocking stub call (`MilvusServiceBlockingStub`) or future stub call (`MilvusServiceFutureStub`), and response conversion.
3. Inspect shared cache, iterator, connection, or global-cluster code when the operation crosses those boundaries.
4. Verify branch-specific behavior from source; do not assume master behavior exists on maintenance branches.

### Diagnose or change code

1. Identify whether the path is V2, legacy V1, shared infrastructure, or BulkWriter.
2. Put new V2 domain behavior in the owning service and its request/response types. Keep connection lifecycle and facade orchestration in `MilvusClientV2`.
3. Preserve the existing endpoint/database/collection cache scope through every path, including iterators and aliases/renames.
4. Update focused tests beside the affected package. Use integration tests only when real server behavior is required.
5. Keep changes minimal and branch-consistent. Do not mix feature implementation with release metadata.

### Prepare a release

1. Read `references/release.md`.
2. Run `scripts/release-window.sh VERSION` from the repository root.
3. Derive user-visible notes from `CHANGELOG.md` and implementation commits, not only `Prepare for vX.Y.Z` markers.
4. Do not publish, tag, or push without explicit authorization.

## Cache machinery

- Keep schema and session-timestamp cache identity scoped by endpoint, effective database, and collection or alias.
- Resolve an empty request database to the connected database when one is configured; otherwise keep it empty for the RPC so serverless deployments do not receive a synthetic `default` database name.
- Pass the resolved RPC database into cache operations. `CollectionCacheKey` normalizes an empty database name to `default`, so wire behavior and cache identity intentionally differ in the empty/empty case.
- Preserve the following database-resolution behavior:

| Connected DB | Request target DB | DB name passed into API | DB name in SchemaCache key |
|---|---|---|---|
| Empty | Empty | Empty | `default` |
| Empty | Explicit DB | Request target DB | Request target DB |
| Explicit DB | Empty | Connected DB | Connected DB |
| Explicit DB | Explicit DB | Request target DB | Request target DB |

## Compatibility rules

- V2 is the active API. V1 is retained for compatibility and should receive only requested maintenance or critical fixes.
- `MilvusClientV2` does not implement the legacy `MilvusClient` interface.
- Public classes under legacy/internal-looking packages may still be binary API; check compatibility before removing or changing signatures.
- Preserve Java 8 source/target compatibility unless the branch explicitly changes it.
- For a class named `XXX`, name its builder `XXXBuilder`.
- New Java files require the Apache 2.0 license header.
- Do not update `CHANGELOG.md` for ordinary feature or bug-fix work unless the user requests release preparation.
- When committing, use `git commit -sm 'message'` so the committer's email address is recorded; every commit in this repository must carry a Signed-off-by trailer.
- When creating a pull request, ensure each PR contains exactly one commit.

## Beyond MilvusClientV2: separate capabilities

`MilvusClientV2` is not the whole SDK. Two capabilities live outside the facade and are easy to miss when tracing
APIs:

- **Client pools** — `io.milvus.pool.MilvusClientV2Pool` / `MilvusClientV1Pool` (in `sdk-core`), for pooling clients
  keyed by `ConnectConfig`. Not methods on `MilvusClientV2`.
- **BulkWriter / bulk import** — the separate **`io.milvus:milvus-sdk-java-bulkwriter`** artifact
  (`io.milvus.bulkwriter`): local/remote/volume writers, plus **cloud REST import** via
  `restful.BulkImportUtils.bulkImport(...)` / `getImportProgress(...)` / `listImportJobs(...)` / `commitImport(...)` /
  `abortImport(...)` (counterparts of pymilvus `bulk_import` / `get_import_progress`). Requests under
  `io.milvus.bulkwriter.request.*`.

See `references/technical-details.md` → "Beyond MilvusClientV2". Route bulk-import work to `bulkwriter`, pooling work
to `io.milvus.pool` — not to `MilvusClientV2`.

## Validation

- Prefer the narrowest relevant test first.
- State explicitly when tests were skipped or a local Milvus/storage service was required.
- Run `scripts/validate-skill.sh` after changing this skill package.
- Prefer `path:line` references in technical explanations.

## Related repositories

Local checkout paths follow the author's machine layout; on other machines the repos may live elsewhere or be absent, so confirm with `git rev-parse --show-toplevel` before relying on them:

- PyMilvus: `$HOME/work/git-go/pymilvus`
- Milvus server: `$HOME/work/git-go/milvus`
- C++ SDK: `$HOME/work/git-go/milvus-sdk-cpp`
- Rust SDK: `$HOME/work/git-go/milvus-sdk-rust`
