# Source Layout

Use this reference to locate implementation and tests on the current development line.

## Repository root

```text
Milvus.Client.sln            solution: V1, V1.Tests, V2, V2.Tests
Milvus.Client/               legacy V1 SDK project
Milvus.Client.Tests/         V1 tests
Milvus.Client.V2/            active V2 SDK project
Milvus.Client.V2.Tests/      V2 tests (Unit / Integration / System)
examples/                    standalone console examples project
Protos/                      milvus-proto submodule (proto sources)
docs/                        design doc (docs/design/v2_design.md), v1/v2 docs
Directory.Build.props        shared build props (nullable, analyzers, warnings-as-errors)
Directory.Packages.props     centralized NuGet package versions
Version.props                package version
Changelog.md                 user-facing release history
.github/workflows/           CI and NuGet publishing workflows
```

## V2 production code (`Milvus.Client.V2/`)

```text
MilvusClientV2.cs                 connection/utility/infrastructure + internal InvokeAsync
MilvusClientV2.<Area>.cs          facade partial files: Alias, BulkImport, Collection, Database,
                                  Dml, Dql, Index, Partition, Rbac, ResourceGroup, Utility
MilvusErrorCode.cs                server error-code enum
MilvusException.cs                SDK exception
Request/<area>/*Req.cs            public request DTOs + internal ToGrpc*() conversion
Response/<area>/*Resp.cs          public response DTOs + internal FromGrpc() conversion
Types/                            ConnectConfig, RetryConfig, FieldSchema, CollectionSchema,
                                  DataType, IndexType, SimilarityMetricType, FieldData,
                                  Float16Utils, iterators, consistency level, sparse vectors, ...
Utils/                            CollectionCacheKey, SchemaCache, CollectionTsCache, RetryPolicy,
                                  DqlConversions, TypeMappings, MilvusTimestampUtils, Verify, ...
```

Namespaces:

- `Milvus.Client.V2` — facade, error model, `Float16Utils`.
- `Milvus.Client.V2.Requests.<Area>` — request DTOs.
- `Milvus.Client.V2.Responses.<Area>` — response DTOs.
- `Milvus.Client.V2.Types` — reusable config/data types.
- `Milvus.Client.V2.Utils` — internal helpers (caches, retry, conversion).
- `Milvus.Client.Grpc` — generated protobuf/gRPC classes (internal).

For a V2 API, start at the matching `MilvusClientV2.<Area>.cs` facade file, then follow its
`Request/<area>/*Req.cs` / `Response/<area>/*Resp.cs` DTOs and the internal `InvokeAsync` path.

## V1 legacy code (`Milvus.Client/`)

```text
MilvusClient.cs                     V1 client (sealed partial class)
MilvusClient.<Area>.cs              partial files: Alias, Collection, Compaction, Database,
                                    Entity, Metrics, ResourceGroup, Role, User
MilvusCollection.cs + partials      collection handle (Collection, Entity, Index, Partition, Rows)
MilvusPartition.cs                  partition handle
FieldData*.cs, *VectorFieldData.cs  field-data model
CollectionSchema.cs, FieldSchema.cs schema model
SearchResults.cs, SearchParameters.cs, QueryParameters.cs, HybridSearchParameters.cs  DQL models
MilvusException.cs, MilvusErrorCode.cs  error model
Utils.cs, MilvusTimestampUtils.cs   helpers
```

V1 targets the same protobuf submodule with `Access="internal"` and shares the generated
`Milvus.Client.Grpc` namespace. Do not port V2 DTO patterns back into V1.

## Tests

V1 (`Milvus.Client.Tests/`):

```text
MilvusFixture.cs              Testcontainers.Milvus fixture (MILVUS_IMAGE override)
*.cs                         per-feature test classes (Collection, Data, Index, Search, RBAC, ...)
```

V2 (`Milvus.Client.V2.Tests/`):

```text
Unit/                         DTO→proto conversion, validation, timestamp/FP16 utilities
Integration/                  in-process mock gRPC server (MockMilvusServer via ASP.NET TestHost),
                              facade connectivity, retry, error mapping
System/                       real Milvus container (milvus_container.py), end-to-end tests
MilvusTestContainer.cs        manages the Milvus container lifecycle
```

See `build-and-test.md` for the exact run commands.
