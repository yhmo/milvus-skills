---
name: milvus-sdk-csharp
description: Analyze and modify the `milvus-io/milvus-sdk-csharp` repository, whose preferred local checkout is typically `$HOME/work/git-go/milvus-sdk-csharp`. Use for the .NET Milvus SDK architecture, MilvusClient (V1) or MilvusClientV2 (V2) implementation, request/response DTO design, protobuf/gRPC codegen, SchemaCache/CollectionTsCache and retry machinery, xunit test workflows, examples, NuGet packaging, releases, and repository-consistent reviews or fixes.
---

# Milvus C# SDK

Use this skill only for `milvus-io/milvus-sdk-csharp`.

## Repository and branch context

- Locate the repository checkout in this order: `$HOME/work/git-go/milvus-sdk-csharp` when it exists on this machine; a directory named `milvus-sdk-csharp` among the parent directories of the current working directory; `/home/runner/work/milvus-sdk-csharp/milvus-sdk-csharp` (GitHub Actions runner `$GITHUB_WORKSPACE`).
- Confirm the checkout with `git rev-parse --show-toplevel`, `git remote -v`, `git branch --show-current`, and `git status --short` before relying on it.
- Upstream is normally `source` (`milvus-io/milvus-sdk-csharp`); `origin` is usually the user's fork.
- The active development line is `main`/`master`. Legacy release lines are maintained separately. Confirm the current branch set from Git before assuming API parity.
- **Version branch model**: `main` tracks the newest supported Milvus major release (currently 3.0). The general model is that each prior major line keeps a maintenance branch (`2.6` for Milvus 2.6), and when the SDK advances to a newer Milvus major (3.1/4.0) the dev branch follows it while a `3.0` branch is created or frozen for Milvus 3.0 users. Note that the C# SDK's upstream currently maintains a smaller branch set (for example `develop`, `2.2`, `release/2.3`; no `2.6` branch yet), so always verify the actual branch-to-Milvus-version mapping from Git rather than assuming a branch name implies a server line.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.
- Do not switch, reset, or overwrite a dirty worktree to inspect another branch. Use `git show`, `git ls-tree`, or a clean secondary worktree.

## Load the relevant reference

Read each selected reference completely before acting:

- Architecture and runtime dataflow: [references/technical-details.md](references/technical-details.md)
- Project and file routing: [references/source-layout.md](references/source-layout.md)
- Build, proto generation, and tests: [references/build-and-test.md](references/build-and-test.md)
- Examples: [references/examples.md](references/examples.md)
- Releases and publishing: [references/release.md](references/release.md)

For architecture or implementation work, normally read both `technical-details.md` and `source-layout.md`.

## Core workflows

### Trace a V2 API

1. Run `scripts/api-trace.sh SYMBOL` from the repository root.
2. Trace the public method in `MilvusClientV2` (in `Milvus.Client.V2/MilvusClientV2.*.cs`, one partial file per area) through its `*Req`/`*Resp` DTOs, `ToGrpc*()`/`FromGrpc()` conversion, the `InvokeAsync` path, and cache/retry hooks.
3. Inspect shared `Types/` and `Utils/` code when the operation crosses cache, retry, or iterator boundaries.
4. Verify branch-specific behavior from source; do not assume current-line behavior exists on maintenance branches.

### Diagnose or change code

1. Identify whether the path is V2 (`Milvus.Client.V2`), legacy V1 (`Milvus.Client`), or shared infrastructure.
2. Put new V2 domain behavior in the owning facade partial file and its request/response DTOs under `Request/` and `Response/` per domain.
3. Keep the public surface free of generated protobuf types; all proto↔DTO conversion stays `internal`.
4. Update focused tests beside the affected project. Use in-process mock tests before server-backed tests.
5. Keep changes minimal and branch-consistent. Do not mix feature implementation with release metadata.

## V2 API conventions

- `MilvusClientV2` is `sealed` and constructed with `new MilvusClientV2(ConnectConfig)`. Call `ConnectAsync` to surface connection/auth failures up front; otherwise the first API call connects lazily.
- Requests and responses are plain C# DTOs (`*Req`/`*Resp`) under `Request/` and `Response/` per domain (for example `Milvus.Client.V2.Requests.Collection` and `Milvus.Client.V2.Responses.Dml`). They are configured via object-initializer properties, not builders.
- Requests convert to protobuf in `internal ToGrpc*()`; responses convert from protobuf in `internal FromGrpc()`. Never expose generated `Milvus.Client.Grpc` types publicly.
- The generated proto namespace is `Milvus.Client.Grpc`; both V1 and V2 generate from the shared `Protos/` submodule with `Access="internal"`.
- The centralized `InvokeAsync` path (in `MilvusClientV2.cs`) applies retry and maps non-success status to `MilvusException`; transport `RpcException` is wrapped into `MilvusException`.
- `ConnectConfig`/`RetryConfig` live in `Types/`. Preserve their established property surface when extending them.

## Cache and consistency

- `Utils/SchemaCache.cs` and `Utils/CollectionTsCache.cs` are process-wide, keyed by `CollectionCacheKey` (normalized endpoint + database + collection). Empty database normalizes to `default`.
- `SchemaCache` single-flights concurrent `DescribeCollection` loads. Facade lifecycle operations invalidate/move/copy entries as appropriate (rename uses `Move`, alias uses `Copy`, drop invalidates).
- `CollectionTsCache` records the last successful DML timestamp; `ConsistencyLevel.Session` queries read it to build the `guaranteeTimestamp` (read-your-writes). Strong/Eventually/BoundedStaleness map to fixed guarantee timestamps matching the Java/C++ SDKs.
- Cache reads/writes belong in the facade orchestration methods, not in conversion helpers or `InvokeAsync`.

## Retry

- `Utils/RetryPolicy.cs` retries inside `InvokeAsync` with exponential backoff governed by `RetryConfig`.
- Do not retry the 7 blacklisted gRPC status codes (deadline exceeded, permission denied, unauthenticated, invalid argument, already exists, resource exhausted, unimplemented).
- Retry server `RateLimit` errors only when `RetryOnRateLimit` is enabled.
- The explicit `ConnectAsync` (and lazy fallback) is not retried; connection/auth failures surface immediately.

## Compatibility rules

- V2 is the active API. V1 (`MilvusClient`/`MilvusCollection`) is retained for compatibility and should receive only requested maintenance or critical fixes.
- Preserve multi-targeting (`net8.0;netstandard2.0;net462`). Guard net8.0-only APIs (for example `Half` in FP16/BF16 paths) with `#if NET8_0_OR_GREATER`.
- New source files should follow the repository's style and analyzers; `TreatWarningsAsErrors` and `AnalysisLevel=latest` are enabled at the directory level.
- Do not update `Changelog.md` for ordinary feature or bug-fix work unless the user requests release preparation.

## Validation

- Prefer the narrowest relevant test first (unit, then in-process mock integration, then server-backed system).
- State explicitly when tests were skipped or a local Milvus/storage service was required.
- Run `scripts/validate-skill.sh` after changing this skill package.
- Prefer `path:line` references in technical explanations.

## Contribution conventions

- Use `git commit -sm '<message>'` so the committer's email address is recorded; commits in this repository must carry a Signed-off-by trailer.
- When creating a pull request, ensure each PR contains exactly one commit.

## Related repositories

Local checkout paths follow the author's machine layout; on other machines the repos may live elsewhere or be absent, so confirm with `git rev-parse --show-toplevel` before relying on them:

- PyMilvus: `$HOME/work/git-go/pymilvus`
- Milvus server: `$HOME/work/git-go/milvus`
- C++ SDK: `$HOME/work/git-go/milvus-sdk-cpp`
- Java SDK: `$HOME/work/git-go/milvus-sdk-java`
- Rust SDK: `$HOME/work/git-go/milvus-sdk-rust`
