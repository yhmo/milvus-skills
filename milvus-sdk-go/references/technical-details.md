# Go SDK Technical Details

Reference for the Go Milvus SDK (`client/` inside the milvus repo, module `github.com/milvus-io/milvus/client/v3`).

## Source layout

```
client/
├── go.mod                      # module github.com/milvus-io/milvus/client/v3
├── Makefile                    # generate-mockery, lint (stub), unittest (stub)
├── .golangci.yml               # golangci-lint v2 config (gci, gofumpt, depguard, revive, ...)
├── common/                     # SDKVersion, param key constants (dim, max_length, ttl, mmap, ...)
├── entity/                     # typed metadata: Schema, Field, Collection, FieldType, vectors, index params, RBAC, resource groups
├── column/                     # columnar data: Column interface + typed columns, FieldData <-> column conversion, ID columns, dynamic $meta
├── index/                      # typed index builders: FLAT, IVF*, HNSW, DISKANN, SCANN, GPU, AUTOINDEX, scalar/json/rtree/minhash/sparse
├── row/                        # row-based bridge: reflect-based unmarshal receivers (GetReceiverCandidate)
├── milvusclient/               # public API: Client, option types, request building, results, iterators, interceptors, telemetry
├── bulkwriter/                 # bulk import writer
├── roaringfilter/              # RoaringBitmap + sbbf bloom filter builders for requests
├── sbbf/                       # scaled bloom filter construction
├── internal/
│   ├── merr/                   # client-side RPC error handling (RPCError, CheckRPCCall, Code)
│   ├── retry/                  # schema-refresh retry (maxAttempts=10, exponential backoff 200ms..3s)
│   ├── conc/                   # Singleflight
│   ├── crypto/                 # Base64 (auth header encoding)
│   └── typeutil/               # ConcurrentMap, Set, vector-type helpers
└── ruleguard/                  # gocritic ruleguard rules for lint
```

## Public API design (`milvusclient`)

- `Client` wraps one `*grpc.ClientConn` + `milvuspb.MilvusServiceClient` (+ a `ClientTelemetryServiceClient`). Created by
  `milvusclient.New(ctx, &ClientConfig{...})` which parses config, dials, runs the `Connect` handshake, seeds the collection
  cache, and starts telemetry.
- **Option pattern**: every operation is `func (c *Client) Op(ctx, option OpOption, callOptions ...grpc.CallOption) (Result, error)`.
  Option types are interfaces (`Request()`, `CollectionName()`, `InsertRequest(schema)`, `WriteBackPKs(...)` etc.) so request
  building is decoupled from transport and is testable without a server. Options live in `*_options.go` files.
- Result types are SDK-owned and typed: `ResultSet` (search/query), `InsertResult`/`UpsertResult`/`DeleteResult`,
  `IndexDescription`, `CreateIndexTask`, `LoadTask`, `FlushTask`, etc.

## Connection and auth

- `ClientConfig.parse()` normalizes the address (`localhost:19530`, `https://...`), extracts the DBName from the URL path,
  and forces TLS for `https` schemes (`:443` default port).
- `Client.dialOptions()` applies `DefaultGrpcOpts` (WithBlock, keepalive 5s/10s, backoff, MaxCallRecvMsgSize 2GB), then
  user `DialOptions`, then a grpc_retry unary interceptor (max 6 attempts, exponential backoff `60ms * 3^attempt` on
  `Unavailable`/`ResourceExhausted`), then `MetadataUnaryInterceptor()`.
- Auth: username/password (`base64(user:pass)`) or APIKey overrides it; both set the `authorization` metadata header.
- `MetadataUnaryInterceptor` appends `authorization`, `dbname`, `identifier`, `client-request-unixmsec`, and an opt-in
  `client_request_id` (a 32-char lowercase hex OTel TraceID) header. See `WithClientRequestID`/`NewClientRequestID`.
- `connectInternal` calls the `Connect` RPC; if the server returns `Unimplemented` (old server), feature flags
  (`disableDatabase`, `disableJSON`, `disableDynamicSchema`, `disableParitionKey`) are set so the client degrades gracefully.

## Schema cache and retries

- `CollectionCache` (common.go) caches `entity.Collection` per collection name: a concurrent map guarded by
  `conc.Singleflight`. `GetCollection`, `Evict(name)`, `Reset()`.
- Write paths (`Insert`, `Upsert`) use `retryIfSchemaError`: on `ErrCollectionSchemaMismatch` they evict the cache and retry
  when the collection `UpdateTimestamp` changed, so a stale client schema is refreshed automatically.
- The client-side `internal/retry.Handle` backs this with up to 10 attempts and exponential backoff.

## Error handling (`internal/merr`)

- Deliberately depends only on `milvus-proto/go-api/v3` so the SDK never imports server `milvus/pkg`.
- `RPCError` carries `code` (modern Milvus code), `legacyCode` (commonpb.ErrorCode), `retriable`, `input` flags, `message`, and
  `detail`. `errors.Is` matches on the numeric code via `RPCError.Is`.
- `CheckRPCCall(resp, err)` folds transport errors and the embedded `commonpb.Status` into a single error.
- `Code(err)`, `IsRetryableErr(err)`, `Error(status)`, `Status(err)`, `Ok(status)`, `Success()` and the `Err*` sentinels
  (`ErrCollectionNotFound` 100, `ErrCollectionSchemaMismatch` 109, `ErrIndexNotFound` 700, `ErrParameterInvalid` 1100, ...) plus
  `WrapErr*` helpers are available. Code families mirror the server `merr` partition table.

## DML / DQL flow

- **Insert/Upsert** (write.go): `retryIfSchemaError` -> `getCollection` -> `option.InsertRequest(collection)` (validates fields
  and builds `milvuspb.InsertRequest`, converting columns/rows) -> `service.Insert` -> `column.IDColumns(schema, resp.IDs, ...)`
  builds the returned ID column, then `option.WriteBackPKs` writes auto-generated PKs back into the caller's structs.
- **Search/HybridSearch** (read.go): `getCollection` -> `service.Search/HybridSearch` -> `handleSearchResult`, which:
  - detects aggregation results (`AggTopks`/`AggBuckets`) and group-by values,
  - handles whole-result parsing when all topks are non-negative,
  - produces one `ResultSet` per query vector (`nq`), each with `Scores`, `IDs`, `Fields`, `GroupByValue`, `AggregationBuckets`,
    `Recall`, and per-row `Err`.
- **Query/Get**: `service.Query` -> `parseSearchResult` builds columns from `FieldData`, honoring wildcard `*`, dynamic `$meta`,
  struct-array output selections, and partial-load missing columns.
- `expandWildcard` turns `*` into the schema field list plus explicitly requested dynamic fields.

## Result handling and unmarshal (`results.go`)

- `ResultSet` is columnar: `GetColumn(name)`, `Len()`, `Slice(start,end)`, `Unmarshal(receiver)` where `receiver` is
  `[]*T`. `DataSet.Unmarshal` uses `row.GetReceiverCandidate` reflection to fill struct fields; pointer fields support nulls.
- `fillPKEntry` writes the returned IDs back into the PK field of each row (search only, when IDs present).

## Iterators (`iterator.go`)

- `SearchIterator`/`QueryIterator` interfaces expose `Next(ctx) (ResultSet, error)`, returning `io.EOF` at the end.
- Search iterators use server-side iterator keys (`iterator`, `iterator_session_ts`, `search_iter_v2`, `search_iter_batch_size`,
  `search_iter_last_bound`, `search_iter_id`, `collection_id`) and a `limit` (or `Unlimited` = -1).
- Query iterators advance with a PK cursor filter; `limit(0)` finishes immediately. If the server does not support the iterator
  mode, `ErrServerVersionIncompatible` is returned.

## Telemetry (`telemetry.go`)

- `ClientTelemetryManager` collects per-operation metrics (counts, latency, p99, errors) sampled at `SamplingRate`, sends
  heartbeats every `HeartbeatInterval` (default 10s) to `ClientTelemetryServiceClient`, and handles server commands
  (`ClientCommand`/`CommandReply`) such as `client:<id>` scoped queries and config replies.
- `TelemetryConfig` (enabled, heartbeat interval, sampling rate, error max count, stable `ClientID`) is configured via
  `ClientConfig.TelemetryConfig`; `DefaultTelemetryConfig()` enables it. Metrics can be read back and dynamically adjusted.

## Index package (`index/`)

- `Index` interface (`Name()`, `Params() map[string]string`, `IndexType()`); concrete types `autoIndex`, `flatIndex`,
  `ivfIndex`, `hnswIndex`, `diskAnnIndex`, `scannIndex`, `gpuIndex`, plus scalar (inverted/bitmap), JSON, rtree, minhash,
  and sparse variants. Metric types (`L2`, `IP`, `COSINE`, `HAMMING`, `JACCARD`) via `index.MetricType`.
- Vector ANN search params use `AnnParam` builders (`hnsw.NewHNSWSearchParam(ef)` etc.); the `milvusclient` read options accept
  these alongside scalar filters and output fields.

## Tests

- Unit/mocked tests use mockery-generated `milvusclient/mock_milvus_server_test.go` (a `milvuspb.MilvusServiceServer` mock) and
  `github.com/bytedance/mockey` for monkey patching. Run tests with
  `go test -tags dynamic,test -gcflags="all=-N -l" -count=1 ./...` from `client/`.
- Example tests (`*_example_test.go`) are compile/run-named examples for `pkg.go.dev`; they connect to `127.0.0.1:19530` and are
  gated by `// nolint`. E2E lives in `tests/go_client` (separate module, `replace` back to `../../client`).
