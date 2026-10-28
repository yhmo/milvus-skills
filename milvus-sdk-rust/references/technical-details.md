# Technical Details

Use this reference for repository architecture, V1/V2 ownership, API tracing, and protobuf boundaries.

## Contents

- Crate and edition layout
- V2 layout
- V1 compatibility boundary
- Public DTO and protobuf boundary
- Connection and shared state
- V2 error model
- RPC retry machinery
- Schema and timestamp caches
- DML validation and conversion
- DML/DQL timestamps
- MilvusClientV2Session
- Query, search, results, and iterators
- Async and polling behavior
- Generated protobuf workflow
- API tracing

## Crate and edition layout

This is one library crate named `milvus-sdk-rust`, exported as `milvus`.

- `src/lib.rs`: exposes `v1` and `v2`; crate-root feature modules still re-export V1.
- `src/v1/`: legacy implementation and compatibility surface.
- `src/v2/`: request/response-based `ClientV2` implementation.
- `src/error.rs`: compatibility re-export of the V1 error API.
- `src/v1/error.rs`: V1 error/result types and V1 server-status decoding.
- `src/v2/error.rs`: V2 error/result types and V2 server-status decoding.
- `src/proto/mod.rs`: includes Cargo-generated protobuf modules from `OUT_DIR`.
- `build.rs`: compiles the `milvus-proto` submodule with vendored `protoc` when `PROTOC` is unset.

V1 is deprecated and compatibility-only. V2 is additive and opt-in through `milvus::v2`; do not change crate-root exports to point at V2.

## V2 layout

Public entry points:

- `milvus::v2::ClientV2`
- `milvus::v2::{CollectionSchema, FieldSchema, Function, FunctionScore, FieldData}`
- `milvus::v2::request::<area>::*`
- `milvus::v2::response::<area>::*`
- `milvus::v2::prelude::*` for the complete common V2 user surface
- `milvus::v2::{QueryIterator, SearchIterator}` plus session/telemetry/bulk-import entry points

Ownership boundaries:

- `src/v2/client.rs`: transport setup, interceptor, shared client state, and basic connection-wide methods only (including session and telemetry access).
- `src/v2/error.rs`: V2-owned error/result types and server-status decoding.
- `src/v2/bulk_import.rs`: bulk-import configuration and client support.
- `src/v2/client/<area>.rs`: feature APIs for alias, CDC, collection, database, DML, DQL, index, iterator, partition, RBAC, resource group, snapshot, utility, global cluster, session, and telemetry.
- `src/v2/request/<area>.rs`: SDK-owned public request DTOs and crate-private request-to-protobuf conversion.
- `src/v2/response/<area>.rs`: SDK-owned public response DTOs and crate-private protobuf-to-response conversion.
- `src/v2/types/<area>.rs`: V2-only schemas, field data, connection/retry parameters, reusable values, and function types.
- `src/v2/client/internal.rs`: schema-cache lookup, row/column resolution, DML validation, and internal conversion helpers.
- `src/v2/client/cache.rs`: process-global schema and last-DML-timestamp caches keyed by normalized endpoint, database, and collection.
- `src/v2/prelude.rs`: all V2 request/response areas, reusable types, V2 errors, `ClientV2`, tasks, iterators, and bulk-import exports.
- `src/v2/mod.rs`: module declarations plus direct bulk-import/client/task/iterator, `types::*`, and `utils::*` re-exports. Request/response DTOs remain namespaced unless imported through the prelude.
- `src/v2/utils.rs`: shared V2 value-conversion utilities re-exported from `milvus::v2`.

Keep `src/v2/client.rs` short. Add feature methods to the appropriate area module.

## Beyond ClientV2: bulk import

`ClientV2` is the primary API, but the SDK also ships a **standalone bulk-import client** that talks to the
Milvus/Zilliz Cloud import REST API directly — no `ClientV2` connection is needed (counterpart of pymilvus
`bulk_import` / `get_import_progress`):

- `milvus::v2::bulk_import::BulkImport` (re-exported via `milvus::v2::prelude::*` and `src/v2/mod.rs`).
- Construct with `BulkImport::new(&BulkImportConfig)`. `BulkImportConfig` holds `url` (the platform endpoint, e.g.
  `https://api.cloud.zilliz.com`), `api_key`, `timeout`, TLS options (`verify_tls`, `ca_certificate_path`,
  `client_identity_path`, `client_certificate_path`, `client_private_key_path`).
- Methods are async:
  - `bulk_import(&self, request: BulkImportRequest) -> Result<BulkImportResponse>` — submit a cloud import job.
  - `list_import_jobs(&self, request: ListImportJobsRequest)` — list jobs.
  - `get_import_progress(&self, request: GetImportProgressRequest)` — job progress.
- Requests are builder-based (`BulkImportRequest::builder()...build()?`, `ListImportJobsRequest`, etc.), carrying
  `database_name`, `collection_name`, `files`/`object_urls`, `cluster_id`, `access_key`/`secret_key`, and options.
- Auth is via `Authorization: Bearer <api_key>` (plus a `DB-Name` header when a database is set), so this client does
  not use the gRPC channel, session, or caches of `ClientV2`.

When a task mentions bulk import, route to `milvus::v2::bulk_import::BulkImport` — not to `ClientV2`.

## V1 compatibility boundary

Crate-root imports remain V1, including:

- `milvus::client::Client`
- `milvus::schema::*`
- `milvus::query::*`
- `milvus::mutate::*`
- `milvus::index::*`

V2 work must not remove, rename, or redirect these exports. Do not import V1 domain types into `src/v2`; define V2-owned equivalents.

For meaningful V2 changes, inspect `src/lib.rs` and run at least a compile or targeted V1 test in addition to V2 tests.

## Public DTO and protobuf boundary

Generated protobuf types are transport details, not the V2 public model.

Required pattern:

1. Public request/response structs contain only intentional SDK-owned data.
2. Every public request/response DTO is defined explicitly; do not use macros to generate DTO structs.
3. Request conversion to `crate::proto::*` is `pub(crate)`.
4. Response conversion from `crate::proto::*` is `pub(crate)`.
5. `ClientV2` performs conversion immediately around the RPC call.

Construction rules:

- Requests are constructed only through explicit SDK-owned builders. Request DTOs and builders do not implement `Default`; `build()` validates the complete request before returning it.
- Non-unit request builders own a DTO created by a private `empty()` helper, expose consuming field methods in field order, and finish with `build() -> Result<Request>`.
- Every request provides `into_builder()` so a built request can be modified and validated again.
- Responses are constructed only by RPC decoding. Response DTOs do not implement `Default` and expose no public builder, setter, constructor, or `from_parts` API.
- Response builders may exist only as `#[cfg(test)] pub(crate)` test helpers.
- Request and response fields are private to downstream users. They expose idiomatic `field()`/`is_*()` accessors; reserve `get_*` for keyed or indexed lookup and materializing compatibility helpers.
- Add request members with backward-compatible internal defaults and additive builder methods. Add response members through crate-private decoding and read-only getters.
- Request and response structs are `#[non_exhaustive]`, preventing external struct literals and exhaustive destructuring.
- Extensible public enums are `#[non_exhaustive]`; downstream matches must include a wildcard arm.

Do not add:

- protobuf-holding `inner` members;
- public `as_proto`, `proto_mut`, `from_proto`, or `into_proto` methods;
- raw query/search APIs whose public input is a protobuf message;
- every protobuf field merely because it exists.

## Reusable V2 type construction

Public structs under `src/v2/types` are reusable value/domain objects rather than request/response DTOs.

- Do not add builder structs under `src/v2/types`.
- Give each public type struct a zero-argument `new()` that establishes SDK defaults.
- For each member, keep `field(value) -> Self`, `set_field(&mut self, value) -> &mut Self`, then `get_field()`/`is_field()` adjacent and in field order.
- Return `Copy` members by value and owned members through references, strings, or slices.
- For list members, add a singular consuming `add_item(value) -> Self` helper.
- Do not add `Default` merely as an alias for `new()`; reserve it for established enum/sentinel semantics.

Use the matching public headers under `milvus-sdk-cpp/src/include/milvus/request` and `response` to identify user-facing fields. Internal protobuf members such as message bases, status objects, channels, and transport bookkeeping usually remain invisible.

## Connection and shared state

`ClientV2` clones share tonic channel state, selected database, RPC timeout/retry settings, and one
in-flight schema-load scope. Completed collection descriptions and DML timestamps are process-wide
and endpoint/database/collection scoped.

- `ClientV2::new(&ConnectConfig)` performs initial connection validation through the Milvus Connect RPC and honors `connect_timeout`.
- The interceptor adds authorization and selected-database metadata.
- tonic `Channel` has no explicit close API; dropping all client/channel clones releases it.
- `set_rpc_deadline` controls per-RPC timeout. Do not confuse it with operation-level polling timeouts.
- `ConnectConfig` supports URI/token/database, connect and RPC timeouts, keepalive, retry settings, TLS server-name override, custom CA PEM path, and paired client certificate/private-key PEM paths.
- Normal HTTPS uses native roots. A custom CA replaces native roots. Supplying any TLS option for an HTTP URI upgrades the transport to HTTPS internally. Reject unpaired client certificate/key configuration.

## MilvusClientV2Session

`ClientV2::session` is **Zilliz Cloud only** and returns a cluster-scoped, DQL-only view in
`src/v2/client/session.rs`. It is a lightweight routing view, not a separate connection: every
session clone shares the parent client's channel, selected database, RPC settings, schema/timestamp
caches, telemetry, and global-cluster failover state.

- The session binds one non-empty `cluster_id`; `session("")` returns `Error::Validation`.
- It exposes only DQL entry points: `search`, `hybrid_search`, `query`, `get`, `query_iterator`,
  and `search_iterator`. It intentionally does not expose schema, DML, collection administration,
  RBAC, resource-group, snapshot, or other management APIs.
- The DQL internals call `set_cluster_param` after protobuf conversion and before the RPC to inject
  the session's authoritative `cluster_id`. This removes and replaces any user-supplied `cluster_id`
  param on a session call. On the plain `ClientV2` path, `cluster_id` remains empty and any
  user-supplied param is preserved.
- `MilvusClientV2Session` is `Clone`. Clones share one `Arc<AtomicBool>` closed flag; `close()` on
  any clone rejects all subsequent session calls and does not disconnect the parent client.
- Query and search iterators created through a session are bound to the same closed flag, so closing
  the session also stops later pages of iterators created before the close.
- Do not turn this view into a general scoped client. Add a method only for a DQL operation that is
  represented by an existing request/response DTO and route it through the matching
  `*_with_cluster` internal API.

## V2 error model

Keep V1 and V2 errors independent. `src/error.rs` only preserves the crate-root V1 compatibility export.

V2 exposes:

- `ServerError { code, legacy_code, reason }` for Milvus status failures. Do not expose transport-oriented `retriable`, `detail`, or `extra_info` as public fields.
- `ConversionError::{ProtobufEncode, ProtobufDecode, Json, Value}` for representation conversion failures.
- `ValidationError { parameter, reason }` for invalid local request/value input.
- `Error::{Grpc, Server, Conversion, Validation, Timeout, MalformedResponse, Cancelled, RetryExhausted, Unexpected}`.

Preserve these categories through tasks, caches, retries, polling, and response constructors. Use `MalformedResponse` when a nominally successful protobuf response is missing required payloads, contains incompatible type tags, malformed JSON, or misaligned parallel arrays. Avoid nested `Result<Result<T>>` and avoid reducing typed errors to strings.

## RPC retry machinery

V2 routes RPCs through the centralized async retry executor in `src/v2/client.rs`.

- `RetryConfig` controls attempt count, total retry timeout, initial/max backoff, multiplier, and rate-limit retry.
- Retry transient tonic/gRPC failures, but do not retry deadline exceeded, permission denied, unauthenticated, invalid argument, already exists, resource exhausted, or unimplemented errors.
- Honor server `status.retriable` only for idempotent operations. Retry legacy/new rate-limit responses when `retry_on_rate_limit` is enabled, including non-idempotent calls because a rate-limit response establishes rejection before mutation.
- Recreate the tonic request on every attempt so the configured per-RPC deadline applies independently to each call.
- `retry_rpc` receives `RetrySemantics::Idempotent` or `RetrySemantics::NonIdempotent`; require the call site to choose explicitly. Normal reads, iterator page requests, internal polling RPCs, and safe stream establishment use idempotent semantics. Insert, upsert, delete, truncate, password/credential mutations, resource-group transfer deltas, and snapshot mutations (`create_snapshot`, `drop_snapshot`, `restore_snapshot`, `pin_snapshot_data`, `unpin_snapshot_data`) use non-idempotent semantics. Return ambiguous transport failures and generic retriable statuses without replaying such mutations.
- Keep explicit stale-schema DML retry separate from ambiguous transport replay and retain a payload-sized copy only when that retry path requires it.
- `dump_messages` is deliberately not retried. Do not transparently restart any stream after messages have been delivered because that can duplicate data.
- Use `tokio::time::sleep` for backoff; never block an async runtime thread.

## Schema and timestamp caches

`src/v2/client/cache.rs` contains two intentionally different process-wide caches:

- `SchemaCache` stores completed `DescribeCollectionResponse` values in a bounded 4,096-entry LRU (the current `DEFAULT_CAPACITY`) keyed by normalized `(endpoint, database, collection)`.
- In-flight schema loads use `LoadKey { collection key, client scope }`. Clones of one client coalesce loads, but independently constructed clients do not share an in-flight load, so credentials and deadlines cannot leak across clients.
- `SchemaLoadGuard` makes elected loads cancellation-safe: dropping the loader completes/removes its state and wakes waiters. Invalidation also prevents a late in-flight response from repopulating a removed entry.
- `CollectionTsCache` is an unbounded `HashMap`, intentionally aligned with C++/Java rather than the schema LRU. It keeps the maximum timestamp and supports `set`, `get`, `invalidate`, `copy`, `move_ts`, and database invalidation.

Direct user-facing `describe_collection` does not populate `SchemaCache`; internal schema-aware operations do. Apply lifecycle invalidation narrowly and in parity with Java/C++: collection/schema/function changes invalidate descriptions where necessary, collection-property changes invalidate only when schema-dependent behavior such as `allow_insert_auto_id` changes, alias operations copy/invalidate schemas and timestamps as appropriate, rename moves timestamps, and create-collection success preserves an existing timestamp because identical-schema creation may be accepted.

## DML validation and conversion

Insert and upsert accept column-based `FieldData` or row-based JSON objects.

`InsertRequest` and `UpsertRequest` own `columns: Vec<FieldData>` and `rows: Vec<EntityRow>` directly. Their builders expose `row(...)` and generic `rows(...)`; JSON values are converted to object rows and validated in `build()`. Do not expose a wrapper enum: accept exactly one non-empty representation and reject empty columns/rows or requests containing both.

The DML path must:

1. Resolve the effective database and collection.
2. Fetch or reuse `DescribeCollection` from the collection cache.
3. Validate column/row field names, required fields, row counts, data types, vector dimensions, nullability/defaults, and value constraints.
4. Convert to protobuf only after validation.
5. Refresh the cached schema and retry validation when stale schema is plausible.

Validate nested struct-array vector dimensions and all narrowing numeric conversions, including finite/in-range JSON-to-`f32` conversion. Build protobuf field data by borrowing validated SDK data where possible. The normal successful insert/upsert path must not deep-clone payload-sized vectors; rebuild per retry attempt and retain a deep copy only for an explicit stale-schema retry when unavoidable.

## DML/DQL timestamps

Both caches normalize an empty database name to `default` and normalize equivalent endpoint forms. Resolve aliases to their canonical collection name before timestamp access so alias and real-name DML/DQL share session state.

- Successful insert/upsert/delete updates the last DML timestamp.
- Query, get, search, hybrid search, query iterator, and search iterator deduce guarantee timestamps using the same dictionary.
- Preserve the greatest timestamp for a collection within one endpoint scope.
- Strong and Customized consistency use guarantee timestamp `0`; Eventually uses `1`; Bounded uses `2`; Session uses the cached timestamp or `1` when absent.
- Clones and independently constructed clients using the same endpoint share completed schemas and timestamps; clients connected to different endpoints remain isolated.

## Query, search, results, and iterators

- `QueryRequest` supports either a filter or typed primary-key IDs (`Ids::Int64`/`Ids::VarChar`), never both. ID queries resolve the primary field through schema; query iterators reject ID input.
- `QueryResults::rows()` and `SingleResult::rows()` return borrowing `ResultRowIter<'_>` values. `ResultRow<'_>` exposes typed field getters, generic `get(name) -> Result<ResultValue<'_>>`, row index, and—on element-level search hits—`element_offset()`.
- Query rows contain requested output fields. Search rows additionally expose primary ID and score. `ResultValue<'_>` preserves scalars, arrays, struct arrays, JSON, and all supported vector forms without materializing JSON.
- `get_output_row(s)` are owned JSON convenience/random-access APIs and allocate maps/values. Prefer row iteration for hot paths.
- Decode missing search payloads, incompatible protobuf tags, unequal parallel arrays, malformed index JSON, or missing CDC message IDs as errors. Do not synthesize plausible defaults.
- Query iterators use primary-key cursor pagination, keep the cursor predicate on the left of `and`, and keep a user `element_filter(...)` expression last. SearchIteratorV2 preserves server token/bound and pins one MVCC timestamp. Legacy SearchIteratorV1 uses integer-aware distance steps for HAMMING.
- The response hierarchy is: the search response's `results()` returns `SearchResults`;
  `SearchResults::iter()`/`get_results()` exposes one `SingleResult` per query vector, and each
  `SingleResult` contains that query vector's complete hit list.

## Async and polling behavior

Public network APIs are async and use tonic/Tokio. Use `tokio::time` for waiting; never use blocking sleeps in async client methods.

Some C++ request fields are client-side workflow controls rather than protobuf fields, such as waiting/polling timeouts for load/index operations. Preserve such fields in V2 DTOs and implement polling around RPCs when parity requires it. Bound every poll RPC and sleep by the remaining operation deadline, return immediately after observed success, and preserve typed timeout/cancellation errors. Optimize tasks must be cooperatively cancellable.

## Generated protobuf workflow

Proto sources live under `milvus-proto/proto`. `build.rs` tracks the current set of proto source files and compiles entry files for common, Milvus, and schema protos; imports generate feder, msg, and resource-group modules too. The submodule is pinned to a current Milvus proto reference so recent RPCs and schema messages (snapshots, external collections, newer data types, `external_field`, aggregation, etc.) are available; confirm the pin with `git submodule status` before assuming a proto feature is absent or present.

Generated Rust files are written under Cargo `OUT_DIR`, for example:

```text
target/debug/build/milvus-sdk-rust-*/out/milvus.proto.milvus.rs
```

Only `src/proto/mod.rs` is source-controlled in the current workflow. Do not edit `target/.../out` files. Change proto inputs, `build.rs`, or dependency versions and rebuild.

## API tracing

Prefer `rg`:

```bash
rg -n "pub async fn search|struct SearchRequest|struct SearchResponse" src/v2
rg -n "search\(" src/v2 tests/v2 examples/v2
rg -n "pub async fn search|SearchOptions" src/v1 tests/v1 examples/v1
rg -n "struct SearchRequest|async fn search" target/debug/build/milvus-sdk-rust-*/out
```

Or run:

```bash
"$SKILL_DIR/scripts/api-trace.sh" SYMBOL
```

When comparing parity, trace the same operation in the matching-release C++ `MilvusClientV2Impl.cpp` and public request/response headers. Use Java `MilvusClientV2` only on the matching release line.
