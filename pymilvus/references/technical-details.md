# Technical details

Use this when tracing PyMilvus APIs or deciding where repo-consistent code belongs.

## Package layout

Core package root: `pymilvus/`.

Important directories:

- `pymilvus/__init__.py` — public import surface. Re-exports `MilvusClient`, `AsyncMilvusClient`, legacy ORM APIs, schema/types, exceptions, search results, rankers, function chains, bloom filters, and utilities.
- `pymilvus/milvus_client/` — newer high-level SDK layer centered on `MilvusClient` and `AsyncMilvusClient`, plus optimize-task helpers.
- `pymilvus/client/` — low-level transport, connection management, request preparation, response parsing, gRPC handlers, search result/iterator types, bloom filter, field ops, and shared client utilities.
- `pymilvus/orm/` — legacy object-oriented API surface such as `Collection`, `connections`, `utility`, `Index`, `Partition`, `Role`, and `db`.
- `pymilvus/grpc_gen/` — generated protobuf/gRPC Python output and proto generation script.
- `pymilvus/function_chain/` — function-chain API (`FunctionChain`, `FunctionChainStage`).
- `pymilvus/bulk_writer/` — bulk writer functionality (local/remote/volume) and optional dependencies.
- `pymilvus/model/` — model integrations and optional `pymilvus.model` extension integration (`dense/`, `hybrid/`, `sparse/`).

## Public API entry points

Start from `pymilvus/__init__.py` when investigating user-facing APIs. It imports and exports:

- New client APIs: `MilvusClient`, `AsyncMilvusClient`
- Legacy ORM APIs: `Collection`, `Connections`, `connections`, `db`, `utility`, `Index`, `Partition`, `Role`, `MutationFuture`, `SearchFuture`
- Schema/types: `CollectionSchema`, `FieldSchema`, `StructFieldSchema`, `DataType`, `Function`, `FunctionScore`, `FunctionType`, `IndexType`, `Group`, `Replica`, `Shard`, `Status`, `BulkInsertState`, `ResourceGroupInfo`
- Function chains and fields: `FunctionChain`, `FunctionChainStage`, `FieldOp`, `FieldOpType`, `BloomFilterBuilder`, `build_bloom_filter`
- Filter-predicate blobs: `RoaringBitmapBuilder`, `build_roaring_bitmap` — build client-side MRB1-wrapped portable Roaring64 blobs for the `roaring_match` filter expression
- Search helpers: `AnnSearchRequest`, `RRFRanker`, `WeightedRanker`, `SearchResult`, `Hit`, `Hits`, `SearchAggregation`, `AggregationBucket`, `AggregationHit`, `TopHits`, `LexicalHighlighter`, `SemanticHighlighter`
- Config and exceptions: `DefaultConfig` (alias of `Config` from `pymilvus/settings.py`), `PyMilvusDeprecationWarning`, `MilvusException`, `MilvusUnavailableException`, `ExceptionsMessage`
- Low-level surface: `Prepare`

If adding or changing public API exports, update `__all__` consistently and add tests for the import surface when appropriate.

## New MilvusClient layer

Main files:

- `pymilvus/milvus_client/milvus_client.py` — synchronous `MilvusClient`.
- `pymilvus/milvus_client/async_milvus_client.py` — async `AsyncMilvusClient`; marked experimental and partial. Also hosts `AsyncMilvusClientSession`, an async DQL session bound to a cluster id and backed by a parent client.
- `pymilvus/milvus_client/base.py` — shared helpers for schema/field creation, index params, call context, and primary-key expression packing.
- `pymilvus/milvus_client/index.py` — `IndexParam` and `IndexParams` helpers.
- `pymilvus/milvus_client/check.py` — parameter validation helpers.
- `pymilvus/milvus_client/_utils.py` — shared client-side helpers.
- `pymilvus/milvus_client/optimize_task.py` and `pymilvus/milvus_client/async_optimize_task.py` — optimize-task request helpers.

`MilvusClient` is the preferred layer for new high-level user-facing SDK features. It uses `ConnectionConfig` and `ConnectionManager` to obtain a handler, then delegates lower-level RPC work to the handler.

`AsyncMilvusClient` should mirror sync client behavior where possible, but do not assume every sync method exists asynchronously. Check current method coverage before adding async changes.

## Connection and transport layer

Main files:

- `pymilvus/client/connection_manager.py` — newer connection pooling/lifecycle layer for `MilvusClient`. It parses URIs, handles tokens/db names, supports local `.db` Milvus Lite connections, and deduplicates reusable handlers.
- `pymilvus/client/grpc_handler.py` — synchronous gRPC transport layer.
- `pymilvus/client/async_grpc_handler.py` — async gRPC transport using `grpc.aio`.
- `pymilvus/client/prepare.py` and related client utilities — request preparation and conversion helpers.
- `pymilvus/client/search_result.py`, `pymilvus/client/search_iterator.py`, `pymilvus/client/search_aggregation.py`, `pymilvus/client/iterator/` — result and iterator handling.
- `pymilvus/client/bloom_filter.py` — `BloomFilterBuilder` and `build_bloom_filter` (uses the optional `bloom_filter` extra's `xxhash` when installed; the dev group also installs `xxhash` so CI exercises the accelerated path).
- `pymilvus/client/roaring_filter.py` — `RoaringBitmapBuilder` and `build_roaring_bitmap`; client-side portable Roaring64 serialization for `roaring_match`. Not gRPC-generated or wrapper-based; keep its `_plan`/`_serialize` logic synchronized with the server-side Go roaring/v2 encoding.
- `pymilvus/client/field_ops.py`, `field_data_extractors.py`, `global_topology.py`, `embedding_list.py`, `blob.py`, `ts_utils.py`, `type_info.py` — shared conversions and helpers.

Put shared connection/lifecycle changes in `connection_manager.py`. Touch gRPC handlers only when raw RPC behavior, timeout behavior, request invocation, retry, or response parsing requires it.

## Legacy ORM layer

Main files:

- `pymilvus/orm/collection.py` — legacy `Collection` wrapper.
- `pymilvus/orm/connections.py` — legacy singleton alias-based connection manager.
- `pymilvus/orm/utility.py` — legacy utility functions.
- `pymilvus/orm/schema.py` — schema objects and function definitions.
- `pymilvus/orm/db.py`, `future.py`, `mutation.py`, `iterator.py`, `prepare.py`, `types.py`, `role.py`, `partition.py`, `index.py` — supporting legacy surface.

Avoid adding new product logic to `orm/` unless the task explicitly concerns legacy compatibility. If changing behavior shared by new and legacy APIs, trace both paths and add tests for the affected surface.

## Generated protobuf and gRPC files

Generated files live under `pymilvus/grpc_gen/`, including `common_pb2.py`, `schema_pb2.py`, `milvus_pb2.py`, `milvus_pb2_grpc.py`, `feder_pb2.py`, `msg_pb2.py`, `rg_pb2.py`, `.pyi` files, and related proto outputs.

Do not edit generated files manually. The proto source is the `pymilvus/grpc_gen/milvus-proto` submodule. Generation is done by `pymilvus/grpc_gen/python_gen.sh`, normally via:

```bash
git submodule update --init
make gen_proto
make check_proto_product
```

The `codegen` dependency group in `pyproject.toml` pins a specific `grpcio-tools` version and a constrained Python range (`[tool.uv.dependency-groups]`), because generated code embeds a gRPC generated version. Do not regenerate with arbitrary newer tooling unless deliberately updating this compatibility constraint.

## Packaging and optional features

Packaging is in `pyproject.toml` with the `hatchling` build backend. `requires-python` is `>=3.9`. Versioning is dynamic: `[tool.hatch.version]` reads `get_version()` from `pymilvus/_version.py`, which builds on `setuptools_scm` with a custom `rc_version_scheme`.

Core dependencies include grpcio, protobuf, orjson, pandas, cachetools, requests, and python-dotenv. `grpcio` is pinned conditionally by Python version; check `pyproject.toml` for the current constraints. Dependency groups and optional extras include:

- `dev` — pytest, coverage, black, ruff, codegen, benchmark/profiling, and bulk-writer development dependencies.
- `codegen` — pinned grpcio/grpcio-tools for proto generation.
- `release` — `twine` and `check-wheel-contents`.
- `bulk_writer` — minio, pyarrow, azure-storage-blob, requests, urllib3.
- `model` — `pymilvus.model` integration.
- `bloom_filter` — `xxhash` for the accelerated bloom-filter path.
- `milvus_lite` — local `.db` connections, not on Windows.

## Where new logic belongs

- New high-level user feature: `pymilvus/milvus_client/` first.
- Sync API transport, request invocation, or response parsing: `pymilvus/client/grpc_handler.py` and helpers.
- Async equivalent: `pymilvus/milvus_client/async_milvus_client.py` plus `pymilvus/client/async_grpc_handler.py`.
- Connection pooling, URI parsing, local `.db`, or token/db handling: `pymilvus/client/connection_manager.py`.
- Legacy `Collection`/`connections` compatibility: `pymilvus/orm/`.
- Public imports: `pymilvus/__init__.py`.
- Generated proto output: regenerate, do not hand-edit.

## API tracing checklist

1. Start at `pymilvus/__init__.py` for the import surface.
2. Search `pymilvus/milvus_client/` for new client methods.
3. Search `pymilvus/client/` for handler/delegation/conversion behavior.
4. Search `pymilvus/orm/` only if legacy APIs are involved.
5. Search `tests/unit/` for expected delegation, validation, and response parsing patterns.
6. Search `examples/` for user-facing usage patterns.
