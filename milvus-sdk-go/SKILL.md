---
name: milvus-sdk-go
description: Analyze and modify the Go Milvus SDK, which lives at `client/` inside the `milvus-io/milvus` repository as its own Go module `github.com/milvus-io/milvus/client/v3`. Use for Go SDK architecture and API tracing, the milvusclient option-pattern API surface, entity/column/index data-model packages, gRPC connection and retry behavior, schema and session-timestamp caches, DML/DQL and iterators, client telemetry, error handling (client/internal/merr), build/test/lint workflows, proto-version bumps, release tagging (`client/vX.Y.Z`), and repository-consistent reviews or fixes. Do not use for other Milvus SDKs (PyMilvus, Java, C++, Rust) or for the Milvus server internals outside `client/`.
---

# Milvus Go SDK

Work in the Go SDK that lives at `client/` inside the `milvus-io/milvus` repository. Unlike the other Milvus language SDKs,
this is not a standalone repository: it is a dedicated Go module nested in the server repo. Do not use this skill for another
language SDK or for server-side `internal/` packages.

## Start every task

1. Resolve the repository with the bundled helper:

   ```bash
   python3 "$SKILL_DIR/scripts/resolve_repo.py" --sdk go
   ```

   It prefers a matching `milvus-io/milvus` repository at the current cwd, then
   checks preset locations (`$HOME/work/git-go`, `$HOME/work`, a cwd
   child/sibling, and the temporary area). If none is valid, it automatically
   clones the repository to `${TMPDIR:-/tmp}/milvus-skills/milvus` with remote
   `source`. The automatic clone is depth-1 by default; pass `--full` only when
   complete history is required. `--branch` accepts a branch or tag; a depth-1
   clone can still fetch another known ref later with an explicit refspec. Use
   the returned `path` and `upstream_remote`;
   pass `--no-clone`
   when network access must not be used.
2. Confirm the Go SDK root at `$ROOT/client` and that `client/go.mod` declares module `github.com/milvus-io/milvus/client/v3`.
3. Check `git branch --show-current`, `git status --short`, and the relevant upstream branch before assuming API parity.
4. Preserve unrelated user changes. Use focused edits; never hand-edit generated files (see Repository rules).
5. Search with `rg`, or run `scripts/api-trace.sh`; do not infer an API path from filenames alone.

## Load the relevant reference

- Read [references/technical-details.md](references/technical-details.md) for architecture, source layout, the option-pattern
  API, connection/retry behavior, caches, DML/DQL, iterators, telemetry, and protobuf conversion.
- Read [references/build-and-test.md](references/build-and-test.md) before building, testing, linting, or debugging CI.
- Read [references/branch-2.6.md](references/branch-2.6.md) when working on the `2.6` maintenance branch, in addition
  to the baseline references.
- Read [references/examples.md](references/examples.md) before changing, building, or running examples.
- Read [references/release.md](references/release.md) for version preparation, `client/vX.Y.Z` tags, and proto-version bumps.

## Module and branch context

- The SDK is Go module `github.com/milvus-io/milvus/client/v3` rooted at `client/` in the milvus repo. Dependencies are added
  from `client/` (`go get`, `go mod tidy`), never from the repo root.
- The SDK must depend only on the public API protobuf module `github.com/milvus-io/milvus-proto/go-api/v3`, plus ordinary
  third-party libraries. It must NOT import the server-side `github.com/milvus-io/milvus/pkg/v3` or `internal/` packages; the
  `client/internal/merr`, `retry`, `conc`, `typeutil`, and `crypto` packages exist specifically to keep that dependency out.
- `master` is the active development line (Milvus 3.0). Older released SDK versions are tagged `client/v2.5.x`, `client/v2.6.x`;
  `client/v2.6.x` corresponds to the 2.6 server line. Confirm branch/tag boundaries from Git rather than assuming.
- **Version branch model**: because the Go SDK lives inside the `milvus-io/milvus` repository, its branches follow the server repo's model. `master` is the dev line and tracks the newest supported Milvus major release (currently 3.0); the milvus repo keeps a `2.6` branch (plus older `2.x` branches) for the previous server line, and already carries a `3.0` branch. Go SDK releases are tagged `client/vX.Y.Z`, so the SDK version that ships on a given branch is what matters (`client/v2.6.x` → Milvus 2.6, `client/v3.x` → Milvus 3.0). When the server advances to a newer major (3.1/4.0), `master` will follow it and a `3.0` branch will be maintained for Milvus 3.0. Always verify branch/tag-to-Milvus-version mapping from Git rather than assuming.
- **Branch overlay**: the other references describe the `master` baseline (module `client/v3`, proto `go-api/v3`). If `git branch --show-current` returns `2.6`, you MUST read [references/branch-2.6.md](references/branch-2.6.md) before applying any knowledge from the baseline references. On `2.6`, the module path is `client/v2` (not `v3`) and the proto module is `go-api/v2` (not `v3`) — every `/v3` import must be replaced with `/v2`. Additionally, these baseline items do **not** exist on `2.6`:
  `client/internal/` · `client/membership/` ·
  `milvusclient/snapshot.go` / `snapshot_options.go` / `file_resource.go` / `file_resource_options.go` / `external_table.go` / `external_table_options.go` / `search_aggregation.go` / `search_aggregation_result.go` / `bloom_filter.go` / `roaring_filter.go` / `telemetry.go` / `errors.go` ·
  `entity/external_table.go` / `entity/file_resource.go` ·
  `Client.GetTelemetry()` / `getCurrentDB()` / `recordOperation()`.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.
- `tests/go_client` in the milvus repo is a separate e2e module (`github.com/milvus-io/milvus/tests/go_client`) that uses a
  `replace` directive pointing the `client/v3` module at `../../client`. Changes there exercise the SDK against a real server.
- Parity notes for other SDKs live on the author's machine under `/home/myh/Videos` (e.g. `cpp_sdk_lack_30.md`, `rust_sdk_lack_26.md`); treat the
  checked-out source as authoritative when notes disagree.

## Repository rules

- Preserve the public API shape: `milvusclient` methods take an `XxxOption interface` built by `NewXxxOption(...)` and return
  typed results (`ResultSet`, `InsertResult`, `*CreateIndexTask`, etc.). Do not leak `milvuspb` request/response types from
  public methods; conversion happens inside options and `callService` closures.
- Prefer typed, columnar results (`column.Column`, `entity.*`) over raw protobuf. `ResultSet.Unmarshal`/`DataSet.Unmarshal`
  provide the row-based bridge via the `row` package.
- Keep `client/internal/*` self-contained; they must not reference server packages.
- Error handling uses `github.com/cockroachdb/errors` and `client/internal/merr` (`CheckRPCCall`, `RPCError`, `Code`). The
  stdlib `errors` package and `github.com/pkg/errors` are forbidden by `client/.golangci.yml` depguard.
- Do not hand-edit generated files: `milvusclient/mock_milvus_server_test.go` is regenerated with `make generate-mockery-client`;
  protobuf bindings come from `milvus-proto/go-api/v3` and are bumped with `scripts/update-api-version.sh` (see build-and-test.md).
- Keep changes minimal and branch-consistent. Do not mix feature implementation with release metadata.
- When committing, use `git commit -sm 'message'` so the committer's email address is recorded; every commit in this repository must carry a Signed-off-by trailer.
- When creating a pull request, ensure each PR contains exactly one commit.

## Typical triggers

- Trace or add a `milvusclient` API and its option/result types.
- Diagnose connection, retry, deadline, schema-cache, consistency, iterator, or telemetry behavior.
- Add or change `entity`/`column`/`index`/`row` data-model code.
- Build/test/lint the SDK module, run e2e through `tests/go_client`, or bump the milvus-proto version.
- Prepare a release or review a Go SDK PR.

## Helpers

Run bundled helpers from the milvus repo root (they locate paths themselves). `$SKILL_DIR` is this skill's base directory — the directory that directly contains both `SKILL.md` and `scripts/` — as exposed by the host agent that loaded the skill (or locate it yourself); never hardcode a `.codex`, `.opencode`, or other agent-specific prefix.

```bash
"$SKILL_DIR/scripts/api-trace.sh" Search
"$SKILL_DIR/scripts/release-window.sh" v2.6.4
"$SKILL_DIR/scripts/validate-skill.sh"
```
