# Source Layout

Use this reference to locate implementation and tests on `source/master`.

## Repository root

```text
pom.xml                  root reactor, shared versions/plugins
sdk-core/                main SDK artifact
sdk-bulkwriter/          separate BulkWriter artifact
examples/                standalone Maven examples project
benchmark/               standalone Maven benchmark project
tests/                   standalone legacy/TestNG projects
doc/                     generated Javadocs
.github/workflows/       CI and release automation
```

Only `sdk-core` and `sdk-bulkwriter` are root reactor modules.

## V2 production code

Base path: `sdk-core/src/main/java/io/milvus/v2`

```text
client/
  ConnectConfig.java
  MilvusClientV2.java
  MilvusClientV2Session.java
  RetryConfig.java
  globalcluster/         topology discovery, refresh, primary swap
common/                  V2 data types, consistency, index/compaction models
exception/               V2 exception and error-code model
service/
  BaseService.java
  collection/            service plus request/response models
  database/
  index/
  partition/
  rbac/
  resourcegroup/
  snapshot/
  utility/
  vector/                DML/DQL, iterators, analyzer, vector/ranker/highlighter/aggregation models
  cdc/
utils/
  ClientUtils.java       channel construction and connection checks
  ConvertUtils.java      common protobuf/model conversions
  DataUtils.java         schema-aware row validation and DML data conversion
  RpcUtils.java          retries and exception mapping
  SchemaUtils.java       schema conversion helpers
  VectorUtils.java       DQL request/response conversion
```

For a V2 API, start at `client/MilvusClientV2.java`, then follow the matching `service/<domain>` method and its request/response class. Async DQL (`queryAsync`, `searchAsync`, `hybridSearchAsync`) is also on `MilvusClientV2`/`MilvusClientV2Session` and routes through the same services using `MilvusServiceFutureStub` and `RpcUtils.retryAsync`.

## Cross-cutting shared code

Base path: `sdk-core/src/main/java/io/milvus`

```text
common/utils/cache/      CollectionCacheKey, SchemaCache, CollectionTsCache
orm/iterator/            V1/V2 query and search iterators, iterator cache, RpcStubWrapper
pool/                    V1/V2 client pools
common/interceptor/      gRPC metadata/identifier interceptors
common/utils/            JSON, binary/vector, redaction, and general helpers
```

Inspect these packages whenever a V2 operation involves schema loading, SESSION consistency, aliases/renames, iterators, pooling, or diagnostic logging.

## Legacy V1 code

```text
client/                  MilvusClient, AbstractMilvusGrpcClient, concrete clients
param/                   V1 request parameters and ParamUtils conversion
response/                V1 response wrappers
connection/              legacy multi-service monitoring/listeners
exception/               legacy exception hierarchy
```

V1 and V2 share generated protobuf classes, caches, iterators, and some common utilities. A cross-cutting fix may require both paths even when the public API work starts in V2.

## Generated protobuf code

Proto submodule:

```text
sdk-core/src/main/milvus-proto/proto
```

Generated build outputs:

```text
sdk-core/target/generated-sources/protobuf/java
sdk-core/target/generated-sources/protobuf/grpc-java
```

Do not edit generated files. Update the submodule/proto source or conversion code as appropriate.

## BulkWriter

Base path: `sdk-bulkwriter/src/main/java/io/milvus/bulkwriter`

```text
BulkWriter.java and *BulkWriterParam.java
writer/                  CSV, JSON, Parquet format writers
storage/client/          storage implementations
connect/                 S3/Azure/storage configuration
restful/                 import and volume REST clients
request/, response/      REST request/response models
resolver/                endpoint resolution
```

BulkWriter tests are under `sdk-bulkwriter/src/test/java/io/milvus/bulkwriter`.

## Tests

Primary tests:

```text
sdk-core/src/test
sdk-bulkwriter/src/test
```

### Pre-v3.0.9 layout (mirrored `io.milvus.*` production packages)

For versions before v3.0.9, `sdk-core` tests were laid out mirroring the production
packages under `sdk-core/src/test/java/io/milvus`:

```text
sdk-core/src/test/java/io/milvus/v2/service/<domain>/
sdk-core/src/test/java/io/milvus/v2/client/
sdk-core/src/test/java/io/milvus/common/utils/cache/
sdk-core/src/test/java/io/milvus/orm/iterator/
sdk-core/src/test/java/io/milvus/client/
sdk-bulkwriter/src/test/java/
```

Names ending in `DockerTest` were integration tests even though they ran through
Maven Surefire. On master they auto-launched a local Milvus server via
`TestUtils.startMilvusStandalone` and `docker compose`; on maintenance branches they
used `org.testcontainers.milvus.MilvusContainer`. See `build-and-test.md`.

### v3.0.9+ layout (unit/integration/system × v1/v2/common × domain)

Starting with v3.0.9, `sdk-core` tests are grouped by test type, then by SDK API
generation, then by business domain:

```text
sdk-core/src/test/java/io/milvus/
├── support/                      # TestUtils, BaseTest (V2 fixture), MockMilvusServer,
│                                 # Docker test base classes (shared Milvus lifecycle)
├── unit/                         # class/method-level tests, @Tag("unit")
│   ├── v1/        param/ client/ orm/ response/
│   ├── v2/        utils/ service/<domain>/ client/
│   └── common/    utils/ cache/ interceptor/ iterator/ telemetry/
├── integration/                  # facade-level tests over mock stubs / in-process servers,
│   │                             # @Tag("integration")
│   ├── v1/        client/
│   ├── v2/        client/ service/<domain>/
│   └── common/    telemetry/
└── system/                       # end-to-end tests against a real Milvus server, @Tag("system")
    ├── v1/        client/
    ├── v2/        client/ service/<domain>/
    └── common/    telemetry/
sdk-bulkwriter/src/test/java/
```

Notes:

- Every test class carries `@Tag("unit" | "integration" | "system")`. Surefire runs
  only `unit` tests by default; `-Pintegration` adds integration tests and `-Psystem`
  runs the full suite. See `build-and-test.md`.
- `*DockerTest` classes are system tests that auto-launch a local Milvus server via
  `TestUtils.startMilvusStandalone` and `docker compose` (master/current) or use
  `org.testcontainers.milvus.MilvusContainer` (maintenance branches).
- White-box tests that need access to package-private production members stay in the
  original production package even though the surrounding tree is type-grouped
  (for example `io.milvus.v2.client.globalcluster.*` and `io.milvus.telemetry.*`).
- Docker system tests extend shared base classes under `support/`
  (`MilvusV2DockerTestBase`, `MilvusV1DockerTestBase`, `MilvusMultiDockerTestBase`)
  whose `@BeforeAll`/`@AfterAll` use reference counting so split test classes share a
  single Milvus start/stop.
- `docker-compose.yml` / `docker-compose-multi.yml` live under
  `sdk-core/src/test/resources/docker/` (moved from `src/test/java/io/milvus` in v3.0.9).

## Routing examples

- Insert validation: `MilvusClientV2` → `VectorService` → `DataUtils` → `DataUtilsTest`/`MilvusClientV2DockerTest`
- SESSION query timestamp: `VectorService`/`VectorUtils` → `CollectionTsCache`; iterator paths also use `RpcStubWrapper`
- Collection schema invalidation: `CollectionService` or `UtilityService` → `BaseService` cache helpers → cache tests
- Connection failure/retry: `MilvusClientV2` → `ClientUtils`/`RpcUtils`; global endpoints also involve `globalcluster/`
- V1 DML: `MilvusServiceClient` → `AbstractMilvusGrpcClient` → `ParamUtils` and shared caches
