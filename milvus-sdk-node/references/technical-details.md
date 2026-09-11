# Technical Design

Use this reference for architecture, runtime dataflow, cache behavior, connection/retry behavior, and API implementation decisions on `source/main`.

## Deliverables and compatibility boundary

The package `@zilliz/milvus2-sdk-node` publishes a single compiled bundle in `dist/` (CommonJS + declarations). Source lives in `milvus/`. The `main` line targets Milvus 3.0 (`milvusVersion` in `package.json`); older `2.x`/`v1.x` branches target older servers.

Two public client surfaces are exposed from `milvus/index.ts`:

- `MilvusClient` — full gRPC client, `extends GRPCClient`.
- `HttpClient` — REST client built by mixing `milvus/http` factories over `HttpBaseClient`.

Keep data-operation APIs aligned between the two where the server REST endpoints support them.

## gRPC client inheritance chain

Classes in `milvus/grpc/` are chained so every public method inherits down to `MilvusClient`:

```text
BaseClient          configuration, proto loading, TLS, connect status, timeout, global-cluster state
Database  extends BaseClient        database lifecycle + properties
Collection extends Database        collection/schema lifecycle, load state, aliases, snapshot, resource,
                                    replica, compaction, schema evolution (AlterCollectionSchema)
Data      extends Collection        insert/upsert/delete, search/hybrid search, query/get/count,
                                    iterators, flush, segments, import, metric, analyzer
Index     extends Data              index lifecycle and properties (MilvusIndex module)
Partition extends Index             partition lifecycle, load, statistics
Resource  extends Partition         resource groups, replication configuration
User      extends Resource          RBAC (users, roles, privileges)
GRPCClient extends User             channel pool, interceptors, connect/reconnect, global-cluster,
                                    telemetry, useDatabase, health/version
MilvusClient extends GRPCClient     high-level API (createCollection simple form), session(), sdkInfo
```

All RPCs ultimately reach `promisify(pool, 'RpcName', params, timeout, requestMetadata)` in `milvus/utils/Function.ts`, which:

1. acquires a `Client` from the `generic-pool` channel pool,
2. extracts an optional `client-request-id`/`client_request_id` from params into gRPC metadata,
3. invokes the unary call with a per-call deadline,
4. on `UNAVAILABLE` after interceptor retries, consults the pool's failover handler for global cluster.

## Connection and channel pool

`BaseClient` (constructor) sets up:

- TLS mode detection (`TLS_MODE.DISABLED/ONE_WAY/TWO_WAY/UNAUTHORIZED`) and `ChannelCredentials` from `config.tls`.
- gRPC channel options: unlimited max send/receive message length, keepalive pings every 10s, `grpc.enable_retries: 1`, plus user `channelOptions`.
- Timeout from `config.timeout` (number ms or string token parsed by `parseTimeToken`), default `DEFAULT_CONNECT_TIMEOUT`.
- Loads `milvus/proto-json/milvus.base.ts` and `schema.base.ts` into protobuf.js `Root` objects.

`GRPCClient` builds `_MilvusService` (and a separate `ClientTelemetryService`) via `getGRPCService` using `@grpc/proto-loader` `fromJSON` on the generated proto JSON, then creates a `generic-pool` of gRPC service clients (`createChannelPool`, defaults `min=2 max=10`, configurable via `config.pool`). Interceptors applied in order:

1. `getMetaInterceptor` — injects client metadata (`dbname`, `authorization`, `identifier`).
2. `getRequestMetadataInterceptor` — adds `client-request-unixmsec`.
3. `getTraceInterceptor` (only when `config.trace`) — OpenTelemetry `traceparent`/`tracestate` injection.
4. `getRetryInterceptor` — retry with exponential backoff (see Retry below).

`connect(sdkVersion)` performs the Milvus `Connect` handshake, stores the returned server `identifier`, and starts telemetry. `use({ db_name })` (alias `useDatabase`) changes the active database for subsequent RPCs.

## Retry behavior

`getRetryInterceptor` in `milvus/utils/Grpc.ts` wraps every gRPC call:

- Retries when the response message is invalid (`isInvalidMessage`) or the gRPC status code is not in the ignore list (`isInIgnoreRetryCodes`, `milvus/utils/Validate.ts`).
- Non-retryable codes: OK, DEADLINE_EXCEEDED, PERMISSION_DENIED, UNAUTHENTICATED, INVALID_ARGUMENT, ALREADY_EXISTS, RESOURCE_EXHAUSTED, UNIMPLEMENTED.
- Delay formula: `2^retryCount * retryDelay` (base default 10ms), `maxRetries` default 3. Each attempt resets the deadline so the original timeout is preserved.
- Compat shim: legacy RPCs that return UNIMPLEMENTED are coerced to OK (except `AlterCollectionSchema` and `ClientHeartbeat`, which must observe it).
- On final failure, the error message is enriched with `(retried N times, Xms)`.

`promisify` itself handles global-cluster failover on `UNAVAILABLE` after the interceptor gives up: it calls the pool's failover handler which refreshes topology and calls `reconnectToPrimary`, then retries the same call once on the new pool.

## Global cluster

Detected when `config.isGlobal` is true or `isGlobalEndpoint(config.address)` matches a global endpoint. Flow (`GRPCClient`):

- `_initGlobalConnection`: `fetchTopology(globalEndpoint, token)` → `getPrimaryCluster(topology)` → set `config.address` to the primary endpoint → `createChannelPool(primary)` → start `TopologyRefresher` (default 5-minute refresh, `milvus/utils/GlobalTopology.ts`) → connect to primary.
- On primary change, `reconnectToPrimary` builds a complete candidate pool/telemetry client/refresher, validates against the candidate, then publishes atomically: bumps `telemetryEndpointEpoch`, swaps `config.address`, pool, telemetry client, and refresher, drains the old pool, and starts the new refresher. Failover is serialized via `reconnectingPromise`.
- `closeConnection` fences publication with `lifecycleGeneration`/`closed` so late async candidate work cannot resurrect a closed client.

## Client telemetry

`milvus/telemetry/ClientTelemetry.ts` implements heartbeats over the `ClientTelemetryService` (enabled by default). `GRPCClient` owns a `ClientTelemetryManager`, a dedicated telemetry channel (no retry interceptor, own backoff), and a `telemetryEndpointEpoch` so stale responses from a pre-failover endpoint are discarded. Telemetry RPCs never use the ordinary retry burst path.

## DML/DQL conversion

`milvus/grpc/Data.ts` is the schema-aware core:

- `insert`/`upsert`: converts row objects into protobuf `FieldData` via `buildFieldDataMap`/`buildFieldData` (`milvus/utils/Data.ts`), with `processVectorData` (dense/binary/float16/bfloat16/int8/sparse), `processScalarData`, and `processStructArraysData`. Sparse vectors accept dict, array (dense), coo, or csr forms; encodings live in `milvus/utils/Bytes.ts` (including `buildPlaceholderGroupBytes` for search placeholders).
- `search`/`hybridSearch`: `buildSearchRequest` (`milvus/utils/Search.ts`) constructs `SearchRequest`/`HybridSearchRequest`, placeholder groups, rerankers (`RRFRanker`, `WeightedRanker`), highlighter, function score, aggregation (`buildSearchAggregation`, `milvus/utils/SearchAggregation.ts`); responses are decoded by `formatSearchResult`/`formatSearchData` including validity bitmaps, element indices, and group-by values.
- `query`: uses scalar `filter`/`expr` with optional `output_fields`, aggregation via output field functions (`count`, `min`, `max`, `sum`, `avg`), and `group_by_fields`.
- `delete`: accepts `filter` or primary-key `ids`; both route through `deleteEntities`.

`promisify` and `withTelemetryLogicalOperation` (both in `milvus/utils/Function.ts`) wrap DML/DQL RPCs so telemetry records exactly one logical operation per public call. Internal iterator machinery uses `withTelemetrySuppressed`.

## Iterators

`searchIterator`/`queryIterator` return async-iterable objects (see `milvus/grpc/Data.ts`):

- `searchIterator` pages using the server token/bound with a per-page search.
- `queryIterator` advances with a primary-key cursor built by `getQueryIteratorExpr`/`getPKFieldExpr` (`milvus/utils/Function.ts`) rather than an ever-growing offset; VarChar primary keys compare against string bounds, integer keys against numeric bounds.
- Both support `batchSize`, `limit`, `filter`/`expr`, and `output_fields`.

## Sessions

`MilvusClient.session(clusterId)` returns a `MilvusClientSession` (in `milvus/MilvusClient.ts`) that reuses the parent client's connection and injects `cluster_id` into search/query/get/iterator request params. Closing the session only prevents future session calls; it does not close the parent.

## High-level API

`MilvusClient.createCollection` supports three input shapes (`CreateColReq`, `CreateColWithSchemaAndIndexParamsReq`, `CreateCollectionReq`) and, for the simple form, auto-builds a default schema (`buildDefaultSchema`), creates indexes, and loads the collection synchronously. `sdkInfo` is baked from `sdk.json` during build.

## BulkWriter

`milvus/bulkwriter/` generates import files offline:

- `BulkWriter` appends rows and produces chunked batch files (`JSON`/`Parquet` via `JsonFormatter`/`ParquetFormatter`), with columnar buffering in `ColumnBuffer`, local storage via `LocalStorage`, and optional cloud volume upload via `VolumeManager`.
- Server-side import is separate: `bulkInsert`, `getImportState`, `listImportTasks` in `milvus/grpc/Data.ts`.

## Generated protobuf code

- Proto sources are a git submodule at `proto/` (branch `3.0` of `milvus-io/milvus-proto`).
- `yarn pre` copies the descriptor proto into `proto/proto/google/protobuf/descriptor.proto`.
- `yarn proto:json` runs `test/utils/ProtoJson.spec.ts` which regenerates `milvus/proto-json/milvus.base.ts` and `milvus/proto-json/schema.base.ts` (plus `milvus/proto-json/milvus.ts` in the loader path) as protobuf.js JSON.
- Do not hand-edit generated proto JSON; change the submodule/proto input or conversion code instead. `3.0_change.md` documents feature deltas after proto bumps (external collections, snapshots, AlterCollectionSchema, client telemetry, molecular data, partial array upsert, element-level results).
