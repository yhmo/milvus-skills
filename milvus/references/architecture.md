# Architecture and code tracing

Use this map to choose where to inspect; verify every path against the current checkout.

## Repository layers

| Area | Primary locations | Role |
|---|---|---|
| Process entry and role composition | `cmd/main.go`, `cmd/milvus/`, `cmd/roles/`, `cmd/components/` | Parses roles and constructs deployable components. |
| Component contracts | `internal/types/types.go` | Lifecycle, server, and client interfaces shared by components. |
| User boundary | `internal/distributed/proxy/`, `internal/proxy/` | gRPC/HTTP entry, validation, scheduling, routing, result reduction, and client-facing status. |
| Metadata and scheduling | `internal/rootcoord/`, `internal/datacoord/`, `internal/querycoordv2/` | Metadata, DDL callbacks, indexing/import/compaction, load and query scheduling. |
| Coordinator deployment | `internal/distributed/mixcoord/` | Current combined coordinator server. It composes the separate RootCoord, DataCoord, and QueryCoord packages. |
| Execution nodes | `internal/querynodev2/`, `internal/datanode/`, `internal/streamingnode/` and matching `internal/distributed/*` packages | Query execution, ingestion/index work, and WAL execution. |
| Storage and data lifecycle | `internal/storage/`, `internal/storagev2/`, `internal/flushcommon/`, `internal/compaction/`, `internal/snapshotio/` (master/3.0) | Segment data model/object storage, packed v2 format, shared flush/sync/write-buffer pipelines, compaction helpers, snapshot export/restore I/O. |
| Streaming/WAL | `internal/distributed/streaming/`, `internal/streamingcoord/`, `internal/streamingnode/`, `pkg/streaming/`, `internal/cdc/` | Append/read/broadcast, channel assignment, transactions, recovery, backends, replication. |
| Native execution | `internal/core/` | C++ segcore, storage/index integration, cgo boundary, and Rust/Tantivy bindings. |
| Shared module | `pkg/` | Separate Go module containing protobuf output, merr, mlog, streaming utilities, metrics, config, and common helpers. Module major version is branch-dependent (`pkg/v3` on master/3.0, `pkg/v2` on 2.6) — confirm from `pkg/go.mod`. |
| Go client module | `client/` | Separate Go module embedded in this monorepo. Module major version is branch-dependent (`client/v3` on master/3.0, `client/v2` on 2.6) — confirm from `client/go.mod`. See [branch-differences.md](branch-differences.md). |
| Configuration | `configs/milvus.yaml`, current paramtable packages | Defaults and typed configuration access. |
| Tests | colocated `*_test.go`, `tests/integration/`, `tests/go_client/` | Unit, integration, and client-facing coverage. |

## Runtime composition

- Coordinators own metadata and scheduling; nodes execute work.
- Current master can deploy coordinator responsibilities through `MixCoord`, while logic remains in RootCoord, DataCoord, and `querycoordv2` packages. Do not confuse deployable role composition with source ownership.
- Standalone currently composes MixCoord, Proxy, QueryNode, DataNode, and StreamingNode in one process. Cluster mode deploys roles separately.
- CDC runs as its own role (`cmd/components/cdc.go`, backed by `internal/cdc/` and `internal/distributed/cdc/`); it is not enabled in standalone by default.
- StreamingCoord runs with coordinator responsibilities; StreamingNodes own PChannels and WAL execution. Read the streaming knowledge base before relying on this summary.

## Trace routes

### Public API or RPC

1. Locate the protobuf service or request type and generated server interface.
2. Find the distributed server registration/forwarder under `internal/distributed/<component>/`.
3. Trace the implementation under `internal/proxy/` or the owning coordinator/node package.
4. Follow broker/client interfaces, retries, cache lookups, scheduler tasks, and callback paths.
5. Trace response construction through `merr.Status`, wire status fields, REST projection, and client-visible behavior.
6. Find focused tests plus any integration or compatibility coverage.

### Search and query

Trace Proxy validation/planning/scheduling → QueryCoord routing/target state when relevant → QueryNode task/delegator → cgo/segcore plan execution → reducer/result projection. Include consistency timestamps, shard leaders, retries, and partial-result behavior.

### Insert, delete, flush, and DDL

On current streaming paths, trace Proxy → StreamingClient append or broadcast → StreamingCoord/StreamingNode → WAL interceptors/backend → recovery/flusher and coordinator callbacks. Read every relevant streaming guide and message-semantic document before changing ordering, locks, TimeTick, transactions, channel mapping, or replication.

### Index, import, and compaction

Trace Proxy/coordinator RPC → DataCoord inspectors, schedulers, metadata, and policies → DataNode or worker task → object storage/native indexing → result ingestion and retry/recovery. Include state-machine and restart behavior.

### C++ and cgo

Trace Go call → cgo wrapper → `CStatus`/native status producer → all native construction, throw, catch, and rewrite sites → Go translator → merr/wire projection. A correct boundary mapping is ineffective if upstream native code already flattened the category.

## Source-of-truth rules

- Prefer local `AGENTS.md` and current source over remembered repository structure.
- Treat top-level subsystem pages as indexes, not complete designs.
- Use protobuf definitions and component interfaces to establish contracts, then verify implementation and tests.
- When branch behavior differs, describe the checked-out branch only unless the user asks for a comparison.
