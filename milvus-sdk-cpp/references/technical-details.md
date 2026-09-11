# Technical Details

Use this reference for architecture, source placement, API tracing, cache behavior, and repository-consistent changes
on the current `master`/active line.

## Contents

- Architecture layers
- Source layout
- Public API and DTO conventions
- RPC execution and connection lifecycle
- Schema and session timestamp caches
- DML, DQL, iterators, and sessions
- Protobuf and build targets
- Change checklists
- API tracing

## Architecture layers

The main call path is:

```text
MilvusClient or MilvusClientV2 public interface
  -> MilvusClientImpl or MilvusClientV2Impl
  -> validation and SDK/protobuf conversion helpers
  -> ConnectionHandler::Invoke / InvokeWithRpcTimeout
  -> retry policy
  -> MilvusConnection thin gRPC wrapper
  -> generated MilvusService stub
```

`MilvusClientV2SessionImpl` is a cluster-scoped DQL view over a shared `MilvusClientV2Impl`; it forwards Search,
HybridSearch, Query, Get, and iterator requests with a cluster identifier.

## Source layout

Public installed headers:

- `src/include/milvus/MilvusClient.h`: legacy V1 interface, retained for compatibility.
- `src/include/milvus/MilvusClientV2.h`: active request/response interface and aggregate include for V2 consumers.
- `src/include/milvus/MilvusClientV2Session.h`: cluster-scoped V2 DQL session interface.
- `src/include/milvus/Status.h`: SDK status and transport/server error information.
- `src/include/milvus/request/<area>/`: public request DTOs.
- `src/include/milvus/response/<area>/`: public response DTOs.
- `src/include/milvus/types/`: schemas, field data, iterators, search/query arguments, IDs, consistency, and models.
- `src/include/milvus/utils/`: public utility headers such as FP16 conversion.
- `src/include/milvus/thirdparty/nlohmann/`: vendored JSON headers under the SDK namespace to avoid system conflicts.

Implementation:

- `src/impl/MilvusClientImpl.*`: legacy API orchestration.
- `src/impl/MilvusClientV2Impl.*`: active V2 API orchestration and internal overloads used by sessions/iterators.
- `src/impl/MilvusClientV2SessionImpl.*`: session lifetime and cluster-ID forwarding.
- `src/impl/MilvusConnection.*`: channel/stub ownership, connect handshake, status conversion, and one-line RPC wrappers.
- `src/impl/MilvusInterceptor.*`: authorization/database metadata injection.
- `src/impl/request/<area>/`, `response/<area>/`, `types/`: non-inline DTO/model implementations.
- `src/impl/types/QueryIteratorImpl.*`, `SearchIteratorImpl.*`, `SearchIteratorV2Impl.*`: iterator paging state.
- `src/impl/utils/DmlUtils.*`: schema-aware DML validation and field-data conversion.
- `src/impl/utils/DqlUtils.*`: DQL request/result conversion and guarantee timestamp deduction.
- `src/impl/utils/TypeUtils.*`: general protobuf/SDK model conversions.
- `src/impl/utils/ConnectionHandler.*`: synchronized connection state, retry/deadline snapshots, and API pipeline.
- `src/impl/utils/cache/`: `CollectionCacheKey`, `SchemaCache`, and `CollectionTsCache`.

Other important layout:

- `test/ut/{request,response,types,utils}`: server-free unit tests.
- `test/it/mocks`: in-process mocked gRPC service/server.
- `test/it/v1` and `test/it/v2`: mocked API behavior tests.
- `test/st/cases`: real-server system tests; the test environment starts a Milvus Docker container.
- `examples/src/v1` and `examples/src/v2`: example sources; binaries go to `cmake_build/examples/v1|v2`.
- `cmake/`: dependency discovery, protobuf generation, lint integration, and package config templates.
- `scripts/build.sh`: Conan/CMake build orchestrator.
- `conanfile.py`: Conan 2 recipe for building or consuming `milvus-sdk-cpp`.

## Public API and DTO conventions

- New user-facing APIs belong in `MilvusClientV2` unless the task explicitly requires V1.
- `MilvusClientV2.h` intentionally includes the public request, response, and core type headers needed by its methods;
  a user should be able to include that one header.
- Mirror a new virtual method in `MilvusClientV2Impl.h` and implement it in `MilvusClientV2Impl.cpp`.
- Put request and response headers under the matching domain: alias, cdc, collection, database, dml, dql, index,
  partition, rbac, resourcegroup, snapshot, or utility.
- Request classes normally expose `SetX(...)` and fluent `WithX(...)` returning the concrete request type.
- Shared CRTP bases include `CollectionRequestBase<T>`, `DMLRequestBase<T>`, `DQLRequestBase<T>`, and domain-specific
  bases. Empty database names mean the connection database, ultimately normalized to `default` for cache keys.
- Response classes wrap SDK model objects and expose setters plus const getters.
- Preserve naming conventions such as `ID`, `IDs`, `CollectionName`, `DatabaseName`, and `WithCollectionName`.
- Update `MilvusClientV2.h` includes when a public method introduces a new DTO. Add a focused DTO unit test.

## RPC execution and connection lifecycle

Most APIs compose up to five stages:

```text
validate -> pre(request conversion) -> RPC with Retry -> wait_for_status -> post(response conversion/cache update)
```

`ConnectionHandler::apiHandler` snapshots the active `shared_ptr<MilvusConnection>`, retry parameters, and RPC deadline
under its mutex, then releases the mutex before validation, conversion, retry, and the network call. An in-flight normal
RPC therefore retains its connection object even if the handler later changes state; public lifecycle rules still require
`Connect`, `Disconnect`, and `UseDatabase` to be serialized with other operations.

Connection behavior on current master:

- `ConnectionHandler::Connect` serializes the complete candidate handshake with lifecycle/configuration mutations.
- `MilvusConnection::Connect` builds a candidate channel/stub, waits for connectivity, sends the Milvus `Connect` RPC,
  checks both gRPC and protobuf status, and publishes channel/stub/parameters only after success.
- A failed reconnect leaves the existing handler connection intact.
- `UseDatabase` reconnects the same `MilvusConnection` with changed database metadata.
- `SetRpcDeadlineMs` updates the active connection's `ConnectParam`; `SetRetryParam` updates handler retry state.
- `Retry` does not retry definitive gRPC errors such as deadline exceeded, authentication/permission failures, invalid
  arguments, already exists, resource exhaustion, or unimplemented. Server-side retries are limited to rate limiting
  when enabled.

When adding an RPC:

1. Add a thin wrapper declaration/definition to `MilvusConnection` if one does not exist.
2. Build protobuf input in `pre`; convert output in `post`.
3. Use `wait_for_status` only for polling-style operations.
4. Use `InvokeWithRpcTimeout` only when a caller supplies a narrower per-call budget.
5. Keep endpoint/database values used by cache callbacks consistent with the RPC path.

## Schema and session timestamp caches

Both caches are process-wide singletons keyed by `CollectionCacheKey`:

```text
normalized endpoint + resolved database + caller-supplied collection or alias name
```

`CollectionCacheKey::Create` normalizes URI spellings to `host:port`, maps an empty database to `default`, preserves
IPv6 brackets, and falls back to the original endpoint if URI parsing throws.

### SchemaCache

- Stores completed `CollectionDescPtr` entries in a bounded cache with default capacity 4096.
- Uses `std::shared_timed_mutex` for concurrent hits and exclusive mutation.
- Tracks approximate LRU recency with an atomic access sequence.
- `GetOrLoad` coalesces concurrent misses only for the same collection key and the same stable per-client `load_scope`
  (`MilvusClientImpl*` or `MilvusClientV2Impl*`). Different clients do not inherit another client's credentials or RPC
  deadline through an in-flight load.
- A loader performs `DescribeCollection`; exceptions are converted to `Status` and all waiters are completed.
- Invalidation marks and detaches matching in-flight loads so a stale result cannot repopulate the cache.
- `InvalidateDb` removes all schemas for one normalized endpoint/database.

Schema consumers include schema-aware Insert/Upsert validation, delete/query-by-IDs primary-key resolution, compact or
optimize collection-ID lookup, and iterator preparation (collection ID, primary-key schema, and search metric lookup).
DDL that changes collection identity or schema must invalidate the exact keys that callers may have cached. Alias names
are cache keys too; do not assume invalidating only the canonical collection clears alias entries.

### CollectionTsCache

- Stores the greatest observed successful DML timestamp per collection key; `Set` is monotonic and ignores zero.
- Uses `std::shared_timed_mutex` and is intentionally not capacity-evicted, because silently dropping a timestamp would
  weaken SESSION consistency.
- `DqlUtils::DeduceGuaranteeTimestamp` uses the cached value for `SESSION` and for unspecified (`NONE`) consistency,
  falling back to 1 when no timestamp exists. Strong maps to 0, bounded maps to 2, and eventual/other levels map to 1.
- `Move` transfers the maximum source/destination timestamp for collection rename, including cross-database rename.
- `Copy` seeds an alias from its target while retaining the target timestamp.
- `InvalidateDb` clears timestamps after a database drop.

Successful Insert, Upsert, and Delete callbacks update the timestamp for the request name. Collection/alias lifecycle
callbacks invalidate, move, or copy entries according to server-side identity changes. Cache behavior is implemented in
both V1 and V2; keep them aligned when a fix affects shared semantics.

## DML, DQL, iterators, and sessions

### DML

- V2 Insert and Upsert accept row- or column-based data, reject both together, load the collection schema, validate and
  convert fields, and send the schema timestamp.
- A client-side schema mismatch forces one schema refresh. A server `SchemaMismatch` response invalidates and retries
  once.
- Delete supports a filter or IDs, but not both. Delete-by-IDs loads the schema to construct a primary-key expression.
- Successful DML stores the returned mutation timestamp for later SESSION reads.

### DQL

- Search, HybridSearch, Query, and Get conversion lives mainly in `DqlUtils`.
- Resolve endpoint and database before converting the request so guarantee timestamps use the same cache namespace.
- `ConsistencyLevel::NONE` tells the server to use collection default consistency while still carrying the deduced
  timestamp used by current SDK behavior.
- Query-by-IDs is represented by `QueryRequest::IDs`; filter and non-empty IDs are mutually exclusive.

### Iterators

- Iterator requests are mutable during preparation/paging; public entry points may copy them when a const/session API
  must not mutate caller input.
- Preparation loads collection ID and primary-key schema. V2 search iterators may also need cached schema/index data for
  metric behavior.
- Paging must preserve the first-page snapshot/session timestamp and retain overflow rows in the iterator cache.
- Add iterator regressions for first-page guarantee timestamps, oversized server pages, cursor updates, and input
  immutability when touching this code.

### MilvusClientV2Session

- `MilvusClientV2::Session(cluster_id, session)` creates a DQL-only view sharing the parent client.
- The session injects `cluster_id` through internal V2 overloads and holds the parent alive until `Close()`.
- A closed session returns `NOT_CONNECTED`; closing it does not disconnect the parent client.

## Protobuf and build targets

- `cmake/MilvusProtoGen.cmake` generates protobuf/gRPC sources into `${milvus_proto_BINARY_DIR}`, normally
  `cmake_build/_deps/milvus_proto-build`.
- Never edit generated `.pb.h/.pb.cc` files. Check them only to confirm accessor spelling or available RPC fields.
- `src/CMakeLists.txt` recursively collects implementation `.cpp/.cxx/.cc` files into `milvus_sdk_objects`, then builds
  the `milvus_sdk` library.
- Installed CMake consumers use `find_package(milvus_sdk CONFIG REQUIRED)` and
  `milvus_sdk::milvus_sdk`. The library filename is `libmilvus_sdk` (or the platform equivalent).
- Public headers are installed from `src/include`; implementation headers are not installed.
- The default language level is C++14, with C++17/C++20 supported through `CPPSTD` or `CMAKE_CXX_STANDARD`.

## Change checklists

For a new V2 API:

1. Public request/response/model headers and implementation files.
2. `MilvusClientV2.h` aggregate includes and virtual method.
3. `MilvusClientV2Impl.h/.cpp` declaration and orchestration.
4. `MilvusConnection.h/.cpp` RPC wrapper if needed.
5. Conversion helpers in `TypeUtils`, `DmlUtils`, or `DqlUtils` when reusable.
6. DTO unit tests, mocked RPC tests, and a system test only when real-server behavior matters.
7. A V2 example and `examples/README.md` entry for a user-visible workflow.

For cache-aware DDL/DML/DQL changes:

1. Resolve one endpoint/database namespace for all cache access in that API path.
2. Identify collection and alias keys affected before and after mutation.
3. Update SchemaCache and CollectionTsCache only after the mutation outcome warrants it.
4. Preserve monotonic timestamps under concurrent writes and rename/alias transfer.
5. Cover V1 and V2 when both implementations share the behavior.
6. Add unit tests for cache primitives and mocked tests proving callbacks use the intended keys.

## API tracing

Prefer:

```bash
rg -n "DescribeCollection" src/include/milvus src/impl test examples
rg -n "SchemaCache|CollectionTsCache|getCollectionDesc" src/impl test
rg -n "MilvusClientV2Impl::SYMBOL|SYMBOL" src/impl/MilvusClientV2Impl.* src/include/milvus test examples
```

Or run:

```bash
"$SKILL_DIR/scripts/api-trace.sh" DescribeCollection
```
