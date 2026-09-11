# Technical Details

Use this reference for repository architecture, V1/V2 ownership, API tracing, protobuf boundaries, and the cache/retry mechanisms.

## Contents

- Solution and project layout
- V2 architecture
- Public DTO and protobuf boundary
- Connection and shared state
- V2 error model
- RPC retry machinery
- Schema and timestamp caches
- DML/DQL conversion and consistency
- Query, search, and iterators
- Generated protobuf workflow
- API tracing

## Solution and project layout

The repository is a .NET solution (`Milvus.Client.sln`) with four projects plus an examples console app:

- `Milvus.Client` — legacy V1 SDK (`MilvusClient`/`MilvusCollection`, gRPC-based).
- `Milvus.Client.Tests` — V1 xunit tests.
- `Milvus.Client.V2` — active V2 SDK (`MilvusClientV2`, request/response DTOs).
- `Milvus.Client.V2.Tests` — V2 unit/mock-integration/system tests.
- `examples/` — standalone console project referencing `Milvus.Client.V2`.

`Directory.Build.props` enables nullable, `LangVersion=latest`, `TreatWarningsAsErrors`, and
`AnalysisLevel=latest`. `Version.props` carries the package version. `Directory.Packages.props`
centralizes NuGet package versions.

## V2 architecture

`MilvusClientV2` is a `sealed` partial class split across per-area facade files:

- `MilvusClientV2.cs` — connection/utility/infrastructure: constructor, `ConnectAsync`, `HealthAsync`,
  `CheckHealthAsync`, `GetServerVersionAsync`, `Dispose`, and the internal `InvokeAsync` RPC path.
- `MilvusClientV2.Alias.cs`, `.BulkImport.cs`, `.Collection.cs`, `.Database.cs`, `.Dml.cs`, `.Dql.cs`,
  `.Index.cs`, `.Partition.cs`, `.Rbac.cs`, `.ResourceGroup.cs`, `.Utility.cs` — one partial file per domain.

Each facade method follows the pattern:

```text
verify request -> ToGrpc*() conversion -> InvokeAsync (RPC + retry + status) -> FromGrpc() response conversion
```

The `Request/<area>/*Req.cs` and `Response/<area>/*Resp.cs` DTOs own the proto↔DTO conversion
(`internal ToGrpc*()` / `internal FromGrpc()`). The facade orchestrates; it also owns cache
reads/writes and Session-consistency timestamp lookup.

V1 mirrors this split with `MilvusClient` partial files (`MilvusClient.Collection.cs`,
`MilvusClient.Dml.cs`, etc.) and `MilvusCollection` partial files; both remain gRPC-stub oriented and
do not use the V2 DTO layer.

## Public DTO and protobuf boundary

Generated protobuf/gRPC classes live in namespace `Milvus.Client.Grpc` and are generated with
`Access="internal"` in both `Milvus.Client.csproj` and `Milvus.Client.V2.csproj`. Users never see them.

Required pattern:

1. Public request/response DTOs contain only SDK-owned data (object-initializer style properties).
2. `*Req` classes expose an `internal ToGrpc*()` conversion; `*Resp` classes expose an
   `internal FromGrpc()` conversion.
3. `InvokeAsync` performs the RPC and status check; conversion happens immediately around it.
4. Never expose `Milvus.Client.Grpc.*` types, raw protobuf messages, or generated stubs in public APIs.

Request DTOs use settable properties with sensible defaults (for example
`CreateCollectionReq.CollectionName`, `Schema`, `ConsistencyLevel`, `ShardsNum`). Responses are
read-only DTOs populated by `FromGrpc()`.

## Connection and shared state

- `Types/ConnectConfig.cs` mirrors C++ `ConnectParam` / Java `ConnectConfig`: `Uri`, `Username`/
  `Password`, `ApiKey`, `Database`, `ConnectTimeout`, `LoggerFactory`, `ChannelOptions`, `Retry`.
- `MilvusClientV2(ConnectConfig)` builds the gRPC channel and stub eagerly but performs no network
  I/O. `ConnectAsync` (or the lazy first-call fallback) sends the Milvus `Connect` RPC and registers
  client info; call it to surface connection/auth failures up front.
- Client state (channel, stub, authorization metadata, selected database) is shared by the facade
  methods; call `UseDatabaseAsync` to switch the default database.
- `Dispose` releases the channel and resources.

## V2 error model

- `MilvusErrorCode` — public enum mirroring server error codes (`Success`, `UnexpectedError`,
  `RateLimit`, `ForceDeny`, `CollectionNotFound`, `SegmentInfo`, `IndexNotFound`, ...).
- `MilvusException` — wraps server `common.Status` (`ErrorCode` + `Reason`); transport-level
  `RpcException` is caught in `InvokeAsync` and wrapped into `MilvusException` for a consistent
  public error surface.

## RPC retry machinery

`Utils/RetryPolicy.cs` applies retry inside `InvokeAsync`, so every facade operation gets retry for
free. `RetryConfig` (`Types/RetryConfig.cs`) controls `MaxRetryTimes`, `InitialBackOff`, `MaxBackOff`,
`BackOffMultiplier`, `RetryOnRateLimit`, and `MaxRetryTimeout`.

Retry decision (matching Java/C++/PyMilvus):

- gRPC `RpcException` — retry unless the status is one of the shared 7-code blacklist: `DeadlineExceeded`,
  `PermissionDenied`, `Unauthenticated`, `InvalidArgument`, `AlreadyExists`, `ResourceExhausted`,
  `Unimplemented`.
- `MilvusException` — retry only on `RateLimit` (8) / legacy `RateLimit` (49) when `RetryOnRateLimit`
  is enabled.
- The explicit `ConnectAsync` (and its lazy fallback) is not retried; it calls the gRPC `Connect`
  directly so connection/auth failures surface immediately.

Backoff is exponential and capped at `MaxBackOff`; `MaxRetryTimeout` bounds the overall retry window.
The same `CancellationToken` flows through every attempt and the backoff delay.

## Schema and timestamp caches

Two process-wide caches in `Utils/`, keyed by `Utils/CollectionCacheKey.cs`
(normalized endpoint + database + collection; empty database → `default`):

- `SchemaCache` — caches `DescribeCollection` results and single-flights concurrent loads per key.
  Used by schema-aware DML/DQL paths; direct user-facing `DescribeCollectionAsync` also routes
  through it.
- `CollectionTsCache` — records the last successful DML timestamp per collection (monotonic
  max-timestamp map, aligned with Java/C++). Backs `ConsistencyLevel.Session` queries.

Cache maintenance happens in the facade: `RenameCollectionAsync` → `Move`, alias create/alter →
`Copy`, `DropCollectionAsync` → `Invalidate`, database drop → `InvalidateDb`. Cache reads/writes
belong in facade methods, not in conversion helpers or `InvokeAsync`.

## DML/DQL conversion and consistency

- `Utils/DqlConversions.cs` and `Utils/TypeMappings.cs` hold shared request/response conversion and
  type mapping helpers for DQL and general conversion.
- Successful insert/upsert/delete records the returned mutation timestamp into `CollectionTsCache`.
- Session consistency: on `SearchAsync`/`QueryAsync` with `ConsistencyLevel.Session`, the facade reads
  the cached timestamp and sends it as the request `guaranteeTimestamp` (`1` when absent). Strong maps
  to `0`, Eventually/unspecified to `1`, BoundedStaleness to `2`, matching Java/C++.

## Query, search, and iterators

- `QueryIterator` / `SearchIterator` (`Types/`) are returned by the iterator APIs and consumed with
  `await foreach` over `IAsyncEnumerable<IReadOnlyList<FieldData>>` pages. They lazily page with
  `batchSize`-sized batches (default 1000, range 1–16384) and preserve the first-page
  snapshot/session timestamp. `offset` is not supported with an iterator.
- Search/query results expose row data through `FieldData` collections; hybrid search combines
  multiple ANN requests with an `IReranker` (`RrfReranker`, `WeightedReranker`).

## Generated protobuf workflow

Proto sources live under the `Protos/` submodule (`Protos/proto/*.proto`). Both `Milvus.Client` and
`Milvus.Client.V2` reference the shared proto files via `<Protobuf>` items (Grpc.Tools) with
`Access="internal"`. Confirm the current submodule pin with `git submodule status` before assuming a
proto feature is present or absent. Never edit generated build output; change proto sources or
conversion code instead.

Generated files land under each project's `obj/` build output (for example
`Milvus.Client.V2/obj/<tfm>/<config>/`). Check them only to confirm accessor spelling or available RPC
fields.

## API tracing

Prefer `rg`:

```bash
rg -n "DescribeCollection|CreateCollectionReq|ToGrpcCreateCollectionRequest|FromGrpc" Milvus.Client.V2
rg -n "InsertAsync|MutationResp|CollectionTsCache" Milvus.Client.V2 Milvus.Client.V2.Tests
rg -n "RetryPolicy|SchemaCache|CollectionCacheKey" Milvus.Client.V2
```

Or run:

```bash
"$SKILL_DIR/scripts/api-trace.sh" SYMBOL
```

When comparing parity, trace the same operation in the matching C++ `MilvusClientV2` / Java
`MilvusClientV2` and PyMilvus `MilvusClient` implementations.
