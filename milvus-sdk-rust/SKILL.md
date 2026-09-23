---
name: milvus-sdk-rust
description: Analyze and modify the `milvus-io/milvus-sdk-rust` repository, whose preferred local checkout is typically `$HOME/work/git-go/milvus-sdk-rust`, while preserving deprecated V1 compatibility and developing the validated request/response-based ClientV2 API. Use for V1/V2 architecture, ClientV2 API tracing and parity with Milvus C++/Java SDKs, request/response/type design, protobuf conversion boundaries, schema-aware DML validation, DQL/iterator behavior, build/test and CI workflows, examples and standalone tutorials, Cargo/codegen changes, release preparation or publication, and repository-consistent reviews or fixes.
---

# Milvus Rust SDK

Maintain deprecated V1 compatibility and active V2 development as separate API surfaces. Do not add features to V1.

## Repository and references

- Prefer the current checkout when it is already inside `milvus-sdk-rust`; otherwise locate the repository checkout on this machine (for example `$HOME/work/git-go/milvus-sdk-rust`).
- Confirm the root and remotes with `git rev-parse --show-toplevel` and `git remote -v` before relying on a checkout. Upstream is normally `source`.
- When committing, use `git commit -sm '<message>'` so the committer's email address is recorded; every commit in this repository must carry a Signed-off-by trailer.
- When creating a pull request, ensure each PR contains exactly one commit.
- Read only the relevant one-level reference before acting:
  - Architecture, protobuf boundaries, DML/DQL internals: [references/technical-details.md](references/technical-details.md)
  - Build, format, and tests: [references/build-and-test.md](references/build-and-test.md)
  - Examples: [references/examples.md](references/examples.md)
  - Release and packaging: [references/release.md](references/release.md)

## Release-line and API boundaries

- Treat C++/Java `master` as the current reference and their legacy release branch/checkouts as the legacy reference. Compare matching release lines.
- The Rust SDK maintains a legacy compatibility line and the active current line; treat `main` as the active line. The `milvus-proto` submodule is pinned to a current Milvus proto reference so recent messages and RPCs are available; confirm the pin with `git submodule status` before assuming a feature is present or absent. Do not infer unimplemented newer-only APIs, fields, or behavior as legacy-line gaps.
- **Version branch model**: `main` tracks the newest supported Milvus major release (currently 3.0). Each prior major line keeps a maintenance branch (`2.6` for Milvus 2.6, plus `2.5`). When the SDK advances to a newer Milvus major (3.1/4.0), `main` will follow it and a `3.0` branch will be created or frozen to serve Milvus 3.0 users (some other SDKs already carry a `3.0` branch that today tracks their dev line). Always verify the branch-to-Milvus-version mapping from Git rather than assuming a branch name implies a server line.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.
- When a proto bump adds new fields or enum variants to messages used by existing V1/V2 code, keep both surfaces compiling: extend exhaustive proto matches and add `..Default::default()` (or explicit defaults) to proto struct literals. Limit such V1 edits to build fixes that preserve behavior.
- Treat `src/v1` and crate-root modules such as `milvus::client`, `schema`, `query`, `mutate`, and `index` as deprecated compatibility surfaces.
- Limit V1 edits to compatibility preservation, build fixes, security fixes, and critical correctness fixes.
- Put all new API work under `milvus::v2`. Never redirect or remove V1 crate-root exports.
- Do not reuse V1 request, response, schema, data, client, or error types inside V2. Shared generated protobuf infrastructure is allowed as an internal dependency.

## V2 source layout

- `src/v2/client.rs`: connection setup, interceptor, retry transport, shared state, and connection-wide methods only (including session and telemetry access).
- `src/v2/error.rs`: V2-owned public error/result types and internal server-status decoding.
- `src/v2/bulk_import.rs`: bulk-import configuration and client support.
- `src/v2/client/<area>.rs`: public feature methods for alias, CDC, collection, database, DML, DQL, index, iterator, partition, RBAC, resource group, snapshot, utility, global cluster, session, and telemetry.
- `src/v2/request/<area>.rs`: explicit SDK-owned request DTOs, builders, validation, and request-to-protobuf conversion.
- `src/v2/response/<area>.rs`: explicit SDK-owned response DTOs and protobuf-to-response decoding.
- `src/v2/types/<area>.rs`: reusable SDK-owned enums and value/domain structs. Do not put request or response DTOs here.
- `src/v2/client/internal.rs`: schema-cache lookup and schema-aware DML validation/conversion.
- `src/v2/client/cache.rs`: process-wide endpoint/database/collection-scoped schema and last-DML-timestamp caches, including per-client in-flight schema-load coordination.
- `src/v2/prelude.rs`: convenient exports for all V2 request, response, reusable type, error, client, task, iterator, and bulk-import APIs.
- `src/v2/mod.rs`: declares V2 modules, directly re-exports bulk-import, clients/tasks/iterators plus `types::*` and `utils::*`, and leaves request/response DTOs available through their modules or the prelude.
- `src/v2/utils.rs`: shared V2 conversion helpers re-exported from `milvus::v2`.

## Universal V2 code style

- Start every maintained Rust source file (`.rs`) with the repository's canonical LF AI & Data Foundation Apache License 2.0 header, before module documentation, attributes, imports, or other code. Apply this to library sources, tests, examples, and Rust build/code-generation sources. Maintained executable scripts under `scripts/` use the same header in the language's comment syntax, placed immediately after any required shebang. Do not edit generated build output, vendored dependencies, or submodule contents solely to add the header.
- Define public DTOs and value types explicitly. Do not use macros to generate public request, response, or type declarations.
- Never store or publicly expose generated protobuf messages in SDK-owned public types.
- Put this separator immediately before every V2 struct and enum, including builder structs:

  ```rust
  ///////////////////////////////////////////////////////////////////////////////
  // TypeName
  ///////////////////////////////////////////////////////////////////////////////
  /// Rustdoc description.
  ```

- Keep the separator limited to the type name. Put descriptive prose in `///` rustdoc below it, not inside the separator.
- Put `//!` module documentation at the top of public V2 modules and `///` documentation on public APIs and types.
- Keep each type and its implementations together. For a request, order the DTO and its implementations, then its builder and builder implementations. For an enum, keep inherent and conversion implementations immediately after the enum.
- Mark public request and response DTOs `#[non_exhaustive]`. Mark extensible public enums `#[non_exhaustive]` and require wildcard match arms.
- Preserve unrelated dirty-worktree changes. Never reformat or rewrite V1 incidentally during V2 work.

## Beyond ClientV2: bulk import

`ClientV2` is not the whole SDK. The crate also ships a **standalone bulk-import client**
(`milvus::v2::bulk_import::BulkImport`, re-exported through `milvus::v2::prelude::*`) that calls the Milvus/Zilliz
Cloud **import REST API** directly — no `ClientV2` connection needed. It provides `bulk_import(...)`,
`list_import_jobs(...)`, `get_import_progress(...)` (counterparts of pymilvus `bulk_import` / `get_import_progress`),
with `BulkImportConfig` (url + api_key + TLS options) and builder-based requests
(`BulkImportRequest::builder()...build()?`). There is **no client pool** in the Rust SDK (unlike Java). See
`references/technical-details.md` → "Beyond ClientV2: bulk import". Route bulk-import work to
`bulk_import::BulkImport`, not to `ClientV2`.

## ClientV2 pattern

- Construct clients with `ClientV2::new(&ConnectConfig)`. Keep the lower-level `connect(ConnectConfig)` private.
- Keep `ConnectConfig` and `RetryConfig` as V2 value types using their established `new()` and fluent/setter/getter APIs. Preserve URI/token/database, connect and RPC timeouts, keepalive, retry, TLS server-name override, custom CA, and paired client-certificate/private-key support.
- Keep only connection-wide methods (such as `new`, `set_rpc_deadline`, `set_retry_param`, `session`, and `telemetry`) in `client.rs`; put feature RPCs in `client/<area>.rs`.
- Public feature methods accept an owned validated request DTO and return `crate::v2::error::Result<Response>`, `Result<()>`, a stream, task, or iterator as appropriate.
- Do not use `Option` to represent RPC, validation, conversion, or decoding failure. Use `Option` only for genuine absence and propagate errors with `Result`.
- Convert request DTOs to protobuf immediately before transport and protobuf responses to SDK responses immediately after status validation.
- Route ordinary RPCs through the centralized retry helpers and choose `RetrySemantics` explicitly. Recreate requests for retries so each attempt receives its own deadline.
- Do not apply the ordinary unary deadline to intentionally long-lived streams such as unbounded CDC dump streams.
- Client clones share the channel, selected database, RPC settings, and one schema-load scope. Completed schemas are stored process-wide in a bounded LRU; last-DML timestamps are stored process-wide in an unbounded max-timestamp map aligned with C++/Java. Both caches are keyed by normalized endpoint URI, database, and collection. Independently constructed clients share completed entries but do not join one another's in-flight schema loads.
- Invalidate collection cache and GTS state after lifecycle/schema operations when required by server semantics.

## Request DTO pattern

- Requests are validated construction objects. Users must construct them through `Request::builder()...build()?`.
- Do not implement `Default` for request DTOs or request builders. A public default request bypasses required-field validation.
- Keep request fields private to downstream users; `pub(crate)` is allowed internally.
- Give non-unit requests a private `empty()` constructor containing the SDK defaults. `builder()` owns this value.
- Expose a public explicit `RequestBuilder`; do not derive or macro-generate builders.
- Make builder field methods consuming and chainable: `field(value) -> Self`.
- Make `build(self) -> Result<Request>` validate required fields, ranges, mutually exclusive inputs, and cross-field constraints before returning the request.
- Provide `into_builder(self)` on every request so users can modify an already-built request and re-run validation.
- Give request fields idiomatic read-only accessors named `field()`. Use natural predicates such as `is_*`, `has_*`, `should_*`, or `exists()` for boolean state. Reserve `get_*` for lookup methods that take a key or index, and use `to_*` for owned or materializing conversions. Return copied values for `Copy` fields and references/slices for owned data.
- Keep methods ordered as `builder()`, `into_builder()`, accessors in field order, then crate-private helpers and protobuf conversion. Keep builder methods in request-field order and `build()` last; builder setters remain `field(value) -> Self`.
- Keep request-to-protobuf conversion `pub(crate)` and adjacent to the owning request. Never expose raw `as_proto`, `proto_mut`, or public protobuf request methods.
- Keep user-omitted `database_name` as `None`; `None` or an empty database name means use the selected/default database.
- Add future fields with backward-compatible internal defaults and additive builder methods, while preserving builder validation.

Example:

```rust
let request = QueryRequest::builder()
    .collection_name("books")
    .filter("id > 0")
    .build()?;
```

## Response DTO pattern

- Responses are RPC output objects. Users obtain them from `ClientV2` methods; they do not construct them.
- Do not implement `Default` for response DTOs.
- Do not expose public response constructors, setters, builders, `from_parts`, or protobuf escape hatches.
- Keep response fields private to downstream users and expose idiomatic read-only `field()` accessors. Use natural predicates such as `is_*`, `has_*`, `should_*`, or `exists()` for boolean state. Reserve `get_*` for lookup methods that take a key or index, and use `to_*` for owned or materializing conversions.
- Keep protobuf decoding in `pub(crate) fn from_proto(...) -> Self` when infallible or `-> Result<Self>` when decoding can fail.
- Propagate malformed JSON, missing substantive payloads, mismatched parallel arrays, invalid dimensions/ranges, incompatible protobuf type tags, unsupported field types, and other decode errors as typed V2 errors. Never fabricate defaults or silently drop malformed response fields.
- Response builders may exist only as `#[cfg(test)] pub(crate)` helpers for unit tests. They are not part of the user API and do not implement `Default`.
- A response's private `empty()` helper, when needed, is test-only.

## Reusable types pattern

- Types under `src/v2/types` are SDK value/domain objects, not request/response DTOs.
- Do not add builder structs under `src/v2/types`.
- Every public struct under `src/v2/types` uses a zero-argument `new()` that establishes its SDK defaults. Set required/configurable values through fluent methods.
- Do not add `Default` to type structs merely as an alias for `new()`. Keep `Default` only where an existing enum/sentinel semantic genuinely requires it.
- For each member, keep the method family adjacent and ordered:
  1. `field(value) -> Self` for consuming fluent construction.
  2. `set_field(&mut self, value) -> &mut Self` for in-place mutation.
  3. `get_field(&self)` or a natural boolean `is_field(&self)` for reading.
- Return values by copy when the field type is `Copy`; return `&str`, slices, or references for owned fields.
- For list/array/vector members, also provide a singular consuming `add_item(value) -> Self` method. Keep it after the full member method family.
- Prefer typed methods such as `dimension`, `max_length`, `enable_analyzer`, and `analyzer_params` over asking users to manipulate raw parameter maps.
- Keep enum/protobuf conversions crate-private unless the conversion is intentionally part of the SDK API.
- Keep `FieldData` SDK-owned and schema-aware. Vector data does not store a separate public dimension; infer and validate dimensions from values and schema.

Example:

```rust
let field = FieldSchema::new()
    .name("embedding")
    .data_type(DataType::FloatVector)
    .dimension(128);

let mut schema = CollectionSchema::new();
schema.set_enable_dynamic_field(false).set_description("books");
```

## DML, DQL, iterator, and timestamp invariants

- Keep column and row input directly on `InsertRequest`/`UpsertRequest` as `Vec<FieldData>` and `Vec<EntityRow>`. Builders accept JSON through `row(...)` and `rows(...)`, then validate and convert objects in `build()`. Do not reintroduce a public input-wrapper enum.
- Require exactly one non-empty input representation. Validate names, required fields, row counts, data types, dimensions, nullability/defaults, and partial-upsert rules before protobuf conversion.
- Validate and convert by reference where possible. Avoid cloning large row/vector payloads; clone only for a stale-schema retry when necessary.
- Pass `RetrySemantics::Idempotent` or `RetrySemantics::NonIdempotent` into the shared retry machinery instead of creating operation-specific retry implementations. Treat insert, upsert, delete, truncate, credential mutations, resource-group transfer deltas, and snapshot mutations (`create_snapshot`, `drop_snapshot`, `restore_snapshot`, `pin_snapshot_data`, `unpin_snapshot_data`) as non-idempotent after dispatch. Do not replay them after ambiguous transport failures or generic `status.retriable`; the server may already have committed the mutation. Explicit rate-limit and stale-schema mutation retries remain allowed when the server response proves the first attempt was rejected. Do not retry `dump_messages` or transparently restart delivered streams.
- Successful insert, upsert, and delete update the process-wide, endpoint-scoped timestamp cache. Query, get, search, hybrid search, and iterators deduce guarantees from the same endpoint/database/collection entry. Schema-aware operations use the process-wide schema cache with the identical key and invalidate it after collection, alias, or schema lifecycle changes.
- Resolve aliases to the canonical collection name before timestamp updates/lookups. Preserve, copy, move, or invalidate schema/timestamp entries according to the matching Java/C++ lifecycle semantics; in particular, identical-schema create may preserve an existing timestamp and rename uses timestamp move semantics.
- Query iterators advance with a primary-key cursor/filter rather than an ever-growing protobuf offset.
- Search iterators preserve the server token/bound and one MVCC session timestamp. Treat iterator `limit(0)` as an immediately finished iterator.
- Decode search/query fields with effective row ranges and validity bitmaps; do not retain and clone the entire decoded payload when direct range decoding is possible.
- Prefer `ResultRowIter<'_>` and `ResultRow<'_>` for allocation-free query/search row traversal. Use `ResultValue<'_>` for generic typed values; use `get_output_row(s)` only when owned JSON maps or indexed materialization are needed. Search rows expose ID, score, output fields, and optional element offset.

## Examples and tests

- Keep V1 examples under `examples/v1` and V2 examples under `examples/v2`; do not modernize V1 incidentally.
- V2 examples must import `milvus::v2::prelude::*`, use V2 request/type APIs, and explicitly show important create-with-index/load/insert steps rather than hiding them in shared helpers.
- Use uppercase collection names: `RUST_V1_<EXAMPLE_NAME>` for V1 and `RUST_V2_<EXAMPLE_NAME>` for V2.
- Ensure examples and system tests clean up collections/resources they create. Prefer unique collection names in concurrent tests.
- Compile examples without running them when no live Milvus mutation is requested.
- Treat `tutorial/` as eight standalone application crates that pin the published `milvus-sdk-rust` version. The path is `1_quickstart`, collection/schema/index/DML/DQL tutorials, then advanced `7_database` and `8_rbac`. Keep concise comments immediately before SDK calls explaining the API purpose and important request parameters. `scripts/run_tests.sh` compile-checks tutorials against the current checkout with a temporary Cargo patch; `scripts/run_tutorials.sh` resolves the pinned crate from crates.io and runs every tutorial against one standalone Milvus container.
- Keep tutorial READMEs beginner-oriented: show the first-run command, default endpoint/credential
  assumptions, representative output, and concise troubleshooting. Explain that `8_rbac` does not
  require the default server to enable authorization and cannot validate permission denial when it is
  disabled.
- Prefer `cargo test --test v2_ut`, `cargo test --lib`, and `cargo check --all-targets` for V2 changes.
- Treat `tests/v2/st` and most V1 integration tests as server-backed. Ask before starting Docker or running destructive/system tests.
- Run `cargo fmt --all -- --check` and `git diff --check` before handoff. Tutorial crates are outside the root workspace, so format or check each `tutorial/*/Cargo.toml` separately when tutorial Rust files change. Use Clippy when requested or proportionate to the change.

## Release workflow

When preparing or analyzing a release:

1. Read [references/release.md](references/release.md).
2. Run `scripts/release-window.sh VERSION` from the repository root.
3. Treat `CHANGELOG.md` as the source of truth for user-visible release contents and update it for release preparation using the repository's existing format.
4. Bump the SDK version across the versioned files: the root `Cargo.toml` version, every `tutorial/*/Cargo.toml` exact `milvus-sdk-rust = "=X.Y.Z"` dependency, and every tutorial README version reference. Then `git status --short` and confirm only intended version files changed.
5. Use `scripts/run_tutorials.sh` to launch the standalone Milvus test server and validate tutorials after the published crate is available.
6. Derive changelog entries from implementation commits since the preceding release, not only version-bump or `Prepare for vX.Y.Z` marker commits.
7. Keep ordinary feature and bug-fix work out of `CHANGELOG.md` unless the user explicitly asks for release preparation or a changelog update.
8. Do not publish, tag, push, or modify remote release state without explicit authorization.

## Generated code and safety

- Generated protobuf bindings live in Cargo `OUT_DIR` and are included through `src/proto/mod.rs`. Never patch generated build output.
- Change proto sources, `build.rs`, or dependency inputs and rebuild when generated behavior must change.
- Ask before starting/recreating containers, running examples that mutate server data, publishing crates, pushing branches/tags, or changing remote release state.

## Scripts

Run helpers from the repository root. `$SKILL_DIR` is this skill's base directory — the directory that directly contains both `SKILL.md` and `scripts/` — as exposed by the host agent that loaded the skill (or locate it yourself); never hardcode a `.codex`, `.opencode`, or other agent-specific prefix.

```bash
"$SKILL_DIR/scripts/api-trace.sh" SYMBOL
"$SKILL_DIR/scripts/release-window.sh" VERSION
"$SKILL_DIR/scripts/validate-skill.sh"

# Repository helper
./scripts/run_tutorials.sh
```

## Evaluation prompts

Should trigger this skill:

- "Where is ClientV2 search implemented?"
- "Add a Rust V2 API matching the C++ SDK current API."
- "Does this V2 change impact old V1 client code?"
- "Review the request builder validation."
- "Why is a protobuf type exposed by this response?"
- "How are DML timestamps used by query and search?"
- "Run the V2 unit tests or compile V2 examples."
- "Prepare a Rust SDK release."

Should not trigger this skill:

- "What is Milvus?"
- "Explain Rust ownership generally."
- "Write unrelated Rust code."
