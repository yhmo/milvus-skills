---
name: milvus-sdk-node
description: Analyze and modify the `milvus-io/milvus-sdk-node` repository, whose preferred local checkout is typically `$HOME/work/git-go/milvus-sdk-node`. Use for the Node.js/TypeScript Milvus SDK architecture, MilvusClient (gRPC) or HttpClient (REST) implementation, request/response type design, proto-json generation from the `proto` submodule, channel-pool and retry machinery, global-cluster failover, client telemetry, DML/DQL and iterators, BulkWriter, Jest test workflows, examples, releases, and repository-consistent reviews or fixes. Do not use for other Milvus SDKs (PyMilvus, Java, C++, Rust, C#, Go) or for the Milvus server internals.
---

# Milvus Node.js SDK

Use this skill only for `milvus-io/milvus-sdk-node` (npm package `@zilliz/milvus2-sdk-node`).

## Repository and branch context

- Locate the repository checkout in this order: `$HOME/work/git-go/milvus-sdk-node` when it exists on this machine; a directory named `milvus-sdk-node` among the parent directories of the current working directory; `/home/runner/work/milvus-sdk-node/milvus-sdk-node` (GitHub Actions runner `$GITHUB_WORKSPACE`).
- Confirm the checkout with `git rev-parse --show-toplevel`, `git remote -v`, `git branch --show-current`, and `git status --short` before relying on it.
- Upstream is normally `source` (`milvus-io/milvus-sdk-node`); `origin` is usually the user's fork.
- `main` is the active development line targeting Milvus 3.0; legacy release lines `2.4`, `2.5`, `2.6`, and `v1.x` are maintained separately. Confirm the branch set from Git before assuming API parity with `main`.
- **Version branch model**: the dev branch (`main`) tracks the newest supported Milvus major release (currently 3.0). Each prior major line keeps a maintenance branch (`2.6` for Milvus 2.6, and older lines like `2.5`/`2.4`). When the SDK advances to a newer Milvus major (3.1/4.0), the dev branch will follow it and a `3.0` branch will be created or frozen to serve Milvus 3.0 users (some other SDKs already carry a `3.0` branch that today tracks their dev line). Always verify the branch-to-Milvus-version mapping from Git rather than assuming a branch name implies a server line.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.
- Do not switch, reset, or overwrite a dirty worktree to inspect another branch. Use `git show`, `git ls-tree`, or a clean secondary worktree.
- The `proto` git submodule tracks the `3.0` branch of `milvus-io/milvus-proto`; check `git submodule status` before assuming a proto feature is present. It may be uninitialized (`-` prefix); initialize with `git submodule update --init --recursive`.

## Load the relevant reference

Read each selected reference completely before acting:

- Architecture and runtime dataflow: [references/technical-details.md](references/technical-details.md)
- Package and file routing: [references/source-layout.md](references/source-layout.md)
- Build, proto generation, and tests: [references/build-and-test.md](references/build-and-test.md)
- Examples: [references/examples.md](references/examples.md)
- Releases and publishing: [references/release.md](references/release.md)

For architecture or implementation work, normally read both `technical-details.md` and `source-layout.md`.

## Core workflows

### Trace an API

1. Run `scripts/api-trace.sh SYMBOL` from the repository root.
2. Trace the public method in `MilvusClient` (`milvus/MilvusClient.ts`) or a domain module under `milvus/grpc/` through validation, protobuf conversion, and the `promisify` RPC dispatch (`milvus/utils/Function.ts`) that acquires a client from the `generic-pool` channel pool.
3. Note where retry (`getRetryInterceptor`), global-cluster failover (`setPoolFailoverHandler`), and telemetry (`withTelemetryLogicalOperation`) wrap the call.
4. For HTTP paths, trace the equivalent factory method in the relevant `milvus/http/<Domain>.ts` module (per-entity files such as `Collection.ts`, `Database.ts`, `Vector.ts`) which calls `POST`/`GET` on `HttpBaseClient`.
5. Verify branch-specific behavior from source; do not assume `main` behavior exists on maintenance branches.

### Diagnose or change code

1. Identify whether the path is the gRPC `MilvusClient` hierarchy, the HTTP `HttpClient` mixin, shared utils/types, BulkWriter, or telemetry.
2. Put domain behavior in the owning `milvus/grpc/<Domain>.ts` module (per-class files; classes are chained by inheritance, e.g. the `Index` class lives in `MilvusIndex.ts`) or a `milvus/http/<Domain>.ts` factory mixin (functions are mixed into `HttpClient`).
3. Keep request/response TypeScript types in `milvus/types/` and shared conversion helpers in `milvus/utils/`.
4. Do not hand-edit `milvus/proto-json/*.ts`; regenerate them when `proto/` changes.
5. Update focused tests beside the affected area (`test/grpc`, `test/http`, `test/utils`). Use server-backed tests only when real Milvus behavior is required.
6. Keep changes minimal and branch-consistent. Do not mix feature implementation with release metadata.

## Compatibility and API rules

- There is no separate V1/V2 split like other Milvus SDKs; `MilvusClient` (gRPC) and `HttpClient` (REST) are the two public client surfaces and should stay API-aligned for data operations.
- Public entry points re-export through `milvus/index.ts`; every new public type/method intended for users must be reachable from it.
- `MilvusClient` extends `GRPCClient` which extends the domain hierarchy `User → Resource → Partition → Index → Data → Collection → Database → BaseClient`. Put new RPCs in the most appropriate domain class so they inherit into `MilvusClient`.
- `HttpClient` is built by mixing `milvus/http` factory functions over `HttpBaseClient` in `milvus/HttpClient.ts`; add a new domain by writing a factory mixin and adding it to the composition.
- Keep the public surface free of raw `@grpc/grpc-js` types except where already exposed (e.g. `ChannelOptions`).
- Check results against `ErrorCode.SUCCESS` and throw `Error` with `reason`/`ERROR_REASONS` when validation fails, matching existing style.
- New source files follow the repository style: 2-space indent, single quotes, semicolons, ES5 trailing commas, strict TypeScript (`strict: true`). Run prettier on changed files.
- Do not update package version, changelog docs, or release metadata for ordinary feature/bug-fix work unless the user requests release preparation.

## Conventions for committing and PRs

- When committing, use `git commit -sm 'message'` so the committer's email address is recorded; commits in this repository must carry a Signed-off-by trailer.
- When creating a pull request, ensure each PR contains exactly one commit.

## Validation

- Prefer the narrowest relevant test first (unit, then server-backed integration).
- State explicitly when tests were skipped or a local Milvus server was required.
- Run `scripts/validate-skill.sh` after changing this skill package.
- Prefer `path:line` references in technical explanations.

## Scripts

Run helpers from the SDK repository root. `$SKILL_DIR` is this skill's base directory — the directory that directly contains both `SKILL.md` and `scripts/` — as exposed by the host agent that loaded the skill (or locate it yourself); never hardcode a `.opencode` or other agent-specific prefix.

```bash
"$SKILL_DIR/scripts/api-trace.sh" search
"$SKILL_DIR/scripts/validate-skill.sh"
```

## Related repositories

Local checkout paths follow the author's machine layout; on other machines the repos may live elsewhere or be absent, so confirm with `git rev-parse --show-toplevel` before relying on them:

- PyMilvus: `$HOME/work/git-go/pymilvus`
- Milvus server: `$HOME/work/git-go/milvus`
- C++ SDK: `$HOME/work/git-go/milvus-sdk-cpp`
- Java SDK: `$HOME/work/git-go/milvus-sdk-java`
- Rust SDK: `$HOME/work/git-go/milvus-sdk-rust`
- C# SDK: `$HOME/work/git-go/milvus-sdk-csharp`
- Go SDK: `$HOME/work/git-go/milvus` (`client/` module)
