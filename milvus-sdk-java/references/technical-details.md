# Technical Design

Use this reference for architecture, runtime dataflow, cache behavior, and API implementation decisions on `source/master`.

## Deliverables and compatibility boundary

The root Maven reactor publishes two artifacts:

- `sdk-core` → `io.milvus:milvus-sdk-java`
- `sdk-bulkwriter` → `io.milvus:milvus-sdk-java-bulkwriter`

`sdk-core` contains both API generations:

- V2 under `io.milvus.v2` is the active request/response API.
- V1 under `io.milvus.client`, `io.milvus.param`, and `io.milvus.response` remains for compatibility.

Do not describe `MilvusClientV2` as implementing `MilvusClient`.

## V2 facade and RPC flow

`MilvusClientV2` owns the connection and orchestration layer:

- `ManagedChannel`, `MilvusServiceBlockingStub`, and `MilvusServiceFutureStub`
- `ConnectConfig`, `ClientUtils`, and `RpcUtils`
- one service instance for database, collection, index, vector, partition, RBAC, resource group, snapshot, utility, and CDC operations
- optional `GlobalStub` for global-cluster routing
- a logical cache endpoint propagated to services and iterators

Normal call flow:

```text
MilvusClientV2 public method
  -> getRpcStub() applies the per-call deadline
  -> RpcUtils.retry(...)
  -> owning BaseService subclass
  -> request validation/conversion
  -> MilvusServiceBlockingStub RPC
  -> RpcUtils.handleResponse(...)
  -> V2 response conversion
```

Async DQL flow (`queryAsync`, `searchAsync`, `hybridSearchAsync`) uses the same services with a `CompletableFuture` contract:

```text
MilvusClientV2 async method
  -> getFutureRpcStub() applies deadline and captures the client request id as a CallOption
  -> VectorService.<op>Async(...)
  -> validation/conversion; schema is loaded through SchemaCache.getOrLoadAsync when needed
  -> RpcUtils.retryAsync(...) with a Supplier<CompletableFuture<...>>
  -> MilvusServiceFutureStub RPC wrapped via ListenableFuture -> CompletableFuture
  -> RpcUtils.handleResponse(...) inside the future conversion
```

Async validation failures return exceptionally completed futures; retry backoff runs on a dedicated daemon `ScheduledThreadPoolExecutor` and never blocks a caller thread, and cancelling the returned future propagates to the in-flight RPC or scheduled retry.

Keep public facade methods thin. Domain validation and protobuf mapping belong in services or V2 utility classes. Cross-service orchestration such as `optimize()` may remain in the facade.

## Connection and retry behavior

`ClientUtils` builds channels and configures authorization metadata, request identifiers, TLS, authority override, proxy routing, keepalive, message limits, and prechecks. `MilvusClientV2.connect()` performs the Milvus connect handshake and installs the returned identifier interceptor on later RPCs.

`RpcUtils` maps gRPC and server failures to `MilvusClientException`, applies `RetryConfig`, retries eligible transport/rate-limit failures, and triggers global-cluster refresh on routing or availability failures. It exposes both `retry(Callable)` for blocking RPCs and `retryAsync(Supplier<CompletableFuture<T>>)` for async RPCs; the two share the same retry policy, classification, and timeout logic. `RetryConfig` validates non-negative backoffs (`initialBackOffMs`/`maxBackOffMs`) and a `backOffMultiplier` of at least 1 at construction and via setters.

`MilvusClientV2` is safe for concurrent RPCs only while connection and database state remain unchanged. Serialize `useDatabase`, `close`, password-reset reconnection, and lifecycle/schema DDL against affected DML/DQL operations.

## Client telemetry

Client telemetry is part of the 3.0/master line only and is absent from 2.6. Do not reference it, or
add compatibility shims for it, in 2.6 work.

The implementation is under `io.milvus.telemetry`:

- `TelemetryConfig`: enabled, heartbeat interval, sampling rate, error capacity, and optional stable
  client ID.
- `ClientTelemetryManager`: operation metrics, snapshots/errors, heartbeat worker, server-command
  processing, and runtime-state handoff.
- `TelemetryInterceptor`: records selected unary RPCs at the gRPC boundary.

`ConnectConfig` defaults to `TelemetryConfig.defaults()`: enabled, a 10-second heartbeat and metrics
window, full sampling, 100 retained errors, and an empty client ID (a UUID is generated when no
stable ID is set). `MilvusClientV2.connect()` creates the manager before the gRPC channel, attaches
`TelemetryInterceptor` to that channel, sets the telemetry stub after the Milvus `Connect` handshake
returns an identifier, and starts the worker unless `ConnectConfig.deferTelemetryStart(true)` was
used. `startTelemetry()` starts the deferred worker; `getTelemetry()` returns the manager for
diagnostics and custom command handlers, and resolves to the primary inner client under global
cluster routing.

`TelemetryInterceptor` records one logical operation for `Insert`, `Upsert`, `Delete`, `Query`,
`Search`, `HybridSearch`, and `RunAnalyzer`. It suppresses nested calls already inside a logical
operation, derives the collection from the protobuf request, and treats business failure as an error
even when the gRPC status itself is OK. Retries inside one facade call remain one logical operation.
Metrics retain request/success/error counts and mean/p99/max latency globally and per collection.

The manager is thread-safe and `AutoCloseable`. A successful heartbeat flushes pending command
replies and processes server commands for configuration pushes, collection-metric filters, recent
errors/latency history, and config queries. Persistent command hashes are deterministic across SDKs.
Repeated `UNIMPLEMENTED` responses back off and mark the current server unsupported. Global-cluster
failover carries telemetry runtime state, client ID/config hash, command cursor/replies, and metric
filters to the replacement primary client.

Telemetry is best-effort: interceptor and heartbeat failures must be logged/skipped rather than
changing the result of a Milvus business RPC.

## Global-cluster routing

Global endpoints are detected from the configured URI. `GlobalStub` fetches topology, owns an inner client for the current primary, runs `TopologyRefresher`, and swaps the outer client's channel/stub when the primary changes.

Cache identity intentionally remains the logical global endpoint rather than the physical primary endpoint so schema and session state survive primary failover.

## Service domains

All services extend `BaseService`, which owns current-database resolution, endpoint propagation, conversion helpers, and cache helper methods.

- `DatabaseService`: database lifecycle and properties
- `CollectionService`: schema/collection lifecycle, load state, fields, functions, replicas
- `IndexService`: index lifecycle and properties
- `VectorService`: insert, upsert, delete, get, query, search, hybrid search, iterators, analyzer, and async query/search/hybrid search
- `PartitionService`: partition lifecycle, load, and statistics
- `RBACService`: users, roles, privileges, privilege groups
- `ResourceGroupService`: resource-group lifecycle and transfers
- `SnapshotService`: snapshot create/list/restore/pin workflows
- `UtilityService`: aliases, flush, compaction, health, external collections, file resources
- `CDCService`: replication configuration and message dumping

Request and response classes live under each service's `request` and `response` packages. They use explicit `XXXBuilder` builders and often validate required fields during `build()`.

## DML and schema-aware conversion

`VectorService` is the main schema-aware path:

- obtains `DescribeCollectionResponse` through `SchemaCache`
- uses `DataUtils` for row/entity validation and field conversion
- uses `VectorUtils` for search/query/hybrid/iterator protobuf construction and response decoding
- refreshes schema when local conversion indicates stale metadata
- retries insert/upsert once on server `SchemaMismatch`
- records mutation timestamps only after successful writes

Ordinary invalid user data should raise `DataNotMatchException` without broadly invalidating a valid schema cache entry.

## Shared schema and session caches

`SchemaCache` and `CollectionTsCache` are JVM-wide singletons shared by V1 and V2.

Their completed-entry key is:

```text
normalized endpoint + database name + collection/alias name
```

Important details:

- Empty database names normalize to `default`.
- Endpoint normalization supplies default ports and canonicalizes host casing.
- `SchemaCache` has a default capacity of 4096 and evicts the least-recently accessed entry.
- Completed schemas are shared across clients with the same key.
- In-flight schema loads additionally include an identity-based service/client scope so one caller's credentials or deadline do not control another caller's load.
- Invalidation marks in-flight loads before removing completed entries so stale loaders cannot republish after DDL invalidation.
- `CollectionTsCache.set` is monotonic and backs SESSION guarantee timestamps.
- Rename uses timestamp `move`; create/alter alias uses timestamp `copy`.

Pass the same endpoint, effective database, and collection name through every cache access. Iterators receive endpoint/database context via `RpcStubWrapper`.

## Iterators

V2 iterator entry points are exposed by `MilvusClientV2` but implementations remain under the shared `io.milvus.orm.iterator` package:

- `QueryIterator`
- `SearchIterator`
- `SearchIteratorV2`
- `IteratorCache`
- `RpcStubWrapper`

`RpcStubWrapper` recreates deadline-bearing stubs per page and carries cache endpoint/database identity. Iterator result caches drain consumed rows and release completed state to avoid retention.

## Sessions, pools, and utility models

`MilvusClientV2Session` is a lightweight cluster-ID wrapper for DQL, async DQL, get, and iterator requests; closing it does not close the parent client. Session calls inject the session `clusterId` into the request params, replacing any conflicting user-supplied value so a single authoritative `cluster_id` reaches the wire on every sync/async path.

`MilvusClientV2Pool` and `MilvusClientV1Pool` live under `io.milvus.pool` and reuse clients through the common pool implementation.

Common V2 enums and schema/index types live under `io.milvus.v2.common`. Vector request subpackages contain typed vectors, rankers, highlighters, and aggregation models.

## Packaging

The build generates Java protobuf and gRPC sources from `sdk-core/src/main/milvus-proto/proto`. `sdk-core` shades and relocates gRPC into `io.milvus.shaded...`; do not assume runtime stack traces or downstream dependency trees use unshaded gRPC packages.

BulkWriter is separate because it adds Parquet/Hadoop and cloud-storage dependencies. Its design supports local, remote, and volume writers plus storage clients and REST import/volume APIs.

## Beyond MilvusClientV2: separate capabilities

The SDK is more than the `MilvusClientV2` facade. Two capabilities live outside `sdk-core` / `io.milvus.v2` and are
easy to miss when tracing APIs:

- **Client pools** — `io.milvus.pool.MilvusClientV2Pool` and `MilvusClientV1Pool` reuse clients through a common pool
  implementation (keyed by `ConnectConfig`), for applications that need many short-lived client instances. They are part
  of `sdk-core` but are NOT methods on `MilvusClientV2`.
- **BulkWriter / bulk import** — shipped as the separate **`io.milvus:milvus-sdk-java-bulkwriter`** artifact
  (`sdk-bulkwriter` module, package `io.milvus.bulkwriter`). It writes CSV/JSON/Parquet data via `LocalBulkWriter` /
  `RemoteBulkWriter` / `VolumeBulkWriter`/`VolumeManager`, AND it exposes **cloud REST import** — you do NOT need a
  MilvusClientV2 to submit an import job against Milvus/Zilliz Cloud:
  - `io.milvus.bulkwriter.restful.BulkImportUtils.bulkImport(url, BaseImportRequest)` — submit a cloud import job
    (counterpart of pymilvus `bulk_import`).
  - `BulkImportUtils.getImportProgress(...)`, `listImportJobs(...)`, `commitImport(...)`, `abortImport(...)`.
  - Request models under `io.milvus.bulkwriter.request.*` (e.g. `import_.CloudImportRequest` /
    `import_.MilvusImportRequest` / `import_.VolumeImportRequest` — each a `BaseImportRequest` carrying
    `collectionName`, `files`/`objectUrl`, `accessKey`/`secretKey`, `clusterId`, etc.).

When a task mentions bulk writing/import or client pooling, route to these modules — not to `MilvusClientV2`.
