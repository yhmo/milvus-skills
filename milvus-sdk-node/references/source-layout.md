# Source Layout

Use this reference to locate implementation, types, utils, tests, and examples on `source/main`.

## Repository root

```text
package.json              package metadata, scripts, dependencies
tsconfig.json             strict TypeScript config (target ES2015, CommonJS)
build.js                  post-compile build step (generates sdk.json, bundles)
jest.config.js            Jest config (ts-jest)
AGENTS.md / CLAUDE.md     agent and contributor guidance
README.md                 user-facing API documentation
llms.txt                  generated LLM-oriented documentation
Retry.md                  retry mechanism design notes
3.0_change.md             proto 3.0 upgrade notes
proto/                    git submodule: milvus-io/milvus-proto (branch 3.0)
milvus/                   SDK source (no `src/` folder)
test/                     Jest tests
examples/                 standalone example projects
docs/                     VitePress documentation site
.github/workflows/        test.yml (CI), release.yml (npm publish), doc.yml
```

## SDK production code

Base path: `milvus/`

```text
index.ts                  single public entry point; re-exports const/utils/types/telemetry,
                          clients (GrpcClient, MilvusClient, HttpClient), bulkwriter
types.ts                  aggregated type exports
MilvusClient.ts           MilvusClient (high-level API, session()) and MilvusClientSession
HttpClient.ts             HttpBaseClient, HttpError, HttpClient (mixin composition)
grpc/                     gRPC domain modules, chained by inheritance
  BaseClient.ts           configuration, TLS, proto loading, connect status
  Database.ts             database lifecycle
  Collection.ts           collections, schema evolution, load, aliases, snapshots, replicas
  Data.ts                 DML/DQL: insert/upsert/delete/search/hybrid/query/get/count,
                          iterators, flush, segments, import, analyzer, metrics
  MilvusIndex.ts          index lifecycle (class Index)
  Partition.ts            partitions
  Resource.ts             resource groups, replication config
  User.ts                 RBAC users/roles/privileges
  GrpcClient.ts           GRPCClient: channel pool, interceptors, connect, global cluster,
                          telemetry, useDatabase, health/version
http/                     REST domain modules as mixin factories over HttpBaseClient
  HttpBaseClient is defined in milvus/HttpClient.ts
  Vector.ts, Database.ts, Collection.ts, Partition.ts, Alias.ts,
  MilvusIndex.ts, Import.ts, Role.ts, User.ts
types/                    request/response/data types by domain
  Client.ts, Collection.ts, Database.ts, Data.ts, DataTypes.ts, Http.ts,
  Insert.ts, MilvusIndex.ts, Partition.ts, Resource.ts, Response.ts,
  Search.ts, SearchAggregation.ts, Segments.ts, User.ts, GlobalCluster.ts,
  HighLevel.ts, Volume.ts, Common.ts
utils/                    shared conversion and RPC helpers
  Function.ts             promisify, executeCall, failover handler, telemetry wrappers,
                          iterator expr helpers
  Grpc.ts                 getGRPCService, interceptors (meta/retry/request metadata/trace)
  Data.ts                 buildFieldData(Map), processVectorData/scalar/struct
  Bytes.ts                binary/float16/bfloat16/int8/sparse vector encodings, placeholders
  Schema.ts               buildDefaultSchema, formatFieldSchema, formatCollectionSchema
  Search.ts               buildSearchRequest, rerankers, highlighter, result formatting
  SearchAggregation.ts    aggregation request/result conversion
  Format.ts               key-value, time, address, method-name, result helpers
  Validate.ts             error-code checks, isInvalidMessage, isInIgnoreRetryCodes, validation
  Connection.ts           getAuthString
  GlobalTopology.ts       topology fetch, primary resolution, TopologyRefresher
  BloomFilter.ts          client-side Bloom filter blob builder
  RoaringFilter.ts        client-side Roaring bitmap blob builder
  logger.ts               winston logger singleton
  index.ts                utils barrel export
const/                    constants and enums
  milvus.ts               DataType/DataTypeMap, IndexType, MetricType, ConsistencyLevelEnum
  client.ts               METADATA, CONNECT_STATUS, TLS_MODE
  error.ts                ERROR_REASONS, ErrorCode
  highLevel.ts, limits.ts, defaults.ts
proto-json/               generated protobuf.js JSON: milvus.base.ts, schema.base.ts (milvus.ts)
telemetry/                ClientTelemetry.ts, index.ts (ClientTelemetryManager)
bulkwriter/               BulkWriter, ColumnBuffer, JsonFormatter, ParquetFormatter,
                          LocalStorage, VolumeManager
```

## Tracing a gRPC API

For a method on `MilvusClient`:

1. Look in the appropriate `milvus/grpc/<Domain>.ts` class (inheritance chain: `MilvusClient → GRPCClient → User → Resource → Partition → Index → Data → Collection → Database → BaseClient`).
2. Request/response types come from `milvus/types/`; conversion helpers from `milvus/utils/`.
3. The RPC call is `promisify(this.channelPool, 'RpcName', {...}, timeout)` in `milvus/utils/Function.ts`.

## Tracing an HTTP API

For a method on `HttpClient`:

1. Find the mixin factory in `milvus/http/<Domain>.ts` and confirm it is included in the composition in `milvus/HttpClient.ts`.
2. The method calls `this.POST/GET(url, params)`; URL paths and base URL come from `HttpBaseClient` (`baseURL` = `${endpoint}/${DEFAULT_HTTP_ENDPOINT_VERSION}`).
3. Response types are in `milvus/types/Http.ts` and `milvus/types/`.

## Tests

Base path: `test/`

```text
test/grpc/            integration tests against a live Milvus server (localhost:19530)
                      one spec per feature: Collection, Data, Insert, Upsert, Search,
                      Query, Iterator, GlobalCluster, ExternalCollection, Snapshot,
                      SearchAggregation, Struct, Text, FullTextSearch, HighLevel, etc.
test/http/            HTTP client tests (client, cloud, fetch, import, node-fetch,
                      serverless)
test/utils/           unit tests for utils (Data, Schema, Search, Grpc, Bytes,
                      BloomFilter, RoaringFilter, Function, Validate, ProtoJson, etc.)
test/build/           build verification tests
test/bulkwriter/      BulkWriter tests
test/telemetry/       telemetry tests
test/tools/           shared test helpers (const.ts, data.ts, utils.ts, ip.ts) and
                      benchmark scripts (bench.ts, bulkwriter-*.ts)
test/cert/            test certificates for TLS
```

- Unit tests run without a server (`NODE_ENV=dev jest test/utils/...`).
- `test/grpc` and most `test/http` specs are server-backed: they connect to a Milvus instance (default `localhost:19530`) and mutate data/collections. Ask before running them unless a server is confirmed available.
- Prefer `test/utils` unit tests for conversion/validation changes, and `test/grpc` for behavioral verification.

## Examples

Base path: `examples/`

```text
examples/milvus/      standalone TypeScript examples (HelloMilvus, Data, DataQuery,
                      Database, DynamicSchema, PartitionKey, QueryIterator, Server,
                      BinarySearch, EntityTTL, HelloSparse, test.ts)
examples/LangChain/   LangChain integration example (own package.json)
examples/nextjs/      Next.js example (own package.json)
```

See `examples.md` for build/run instructions.

## Routing examples

- Insert conversion: `MilvusClient.insert` → `milvus/grpc/Data.ts` → `buildFieldDataMap` (`milvus/utils/Data.ts`) → `promisify`
- Search request: `MilvusClient.search` → `buildSearchRequest` (`milvus/utils/Search.ts`) → placeholder groups (`buildPlaceholderGroupBytes`, `milvus/utils/Bytes.ts`)
- Retry/failover: `promisify` (`milvus/utils/Function.ts`) → `getRetryInterceptor` (`milvus/utils/Grpc.ts`) → `setPoolFailoverHandler`/`reconnectToPrimary`
- Global cluster connect: `GRPCClient.connect` → `_initGlobalConnection` → `fetchTopology`/`getPrimaryCluster` (`milvus/utils/GlobalTopology.ts`)
- Proto bump: edit `proto/` submodule → `yarn pre` → `yarn proto:json` → regenerate `milvus/proto-json/*.ts`
