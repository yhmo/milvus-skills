# Architecture and code tracing

Use this map to choose where to inspect; verify every path against the current checkout.

## Repository layers

| Area | Primary locations | Role |
|---|---|---|
| Caching layer | `include/cachinglayer/`, `src/cachinglayer/` | Tiered cache: cell pin/load/evict, DList LRU, resource reservation, loading-overhead groups, Prometheus metrics. |
| Common utilities | `include/common/`, `src/common/` | Error codes and assertions, `OpContext`, OpenTelemetry tracing, monitor/Prometheus registry, typed storage tracking, C status helpers. |
| File manager | `include/filemanager/`, `src/filemanager/` | Cloud-like file client abstraction (load/add/remove/open streams) with local and memory implementations. |
| Knowhere bridge | `include/knowhere/`, `src/knowhere/` | Global build/search/fetch thread pools with OMP/OpenBLAS control, and the aio context pool. |
| Log module | `include/log/Log.h`, `src/log/Log.cpp` | glog-based `LOG_*` macros that prefix trace ID, thread name, and module. |
| SyncPoint | `include/syncpoint/`, `src/syncpoint/` | RocksDB-derived deterministic test sync points, compiled out unless `ENABLE_SYNCPOINT`. |
| Hash tables | `include/flat_hash_map/`, `include/ptrhash/` | Vendored flat hash maps used by the caching layer. |
| Design docs | `docs/design-docs/` | Design documents for major subsystems (for example loading-overhead groups). |

## Caching layer

The caching layer is the most active subsystem. Public types live in `milvus::cachinglayer`; the LRU core lives in the `milvus::cachinglayer::internal` sub-namespace.

### Core types

- `ResourceUsage` (`cachinglayer/Utils.h`): the {memory_bytes, file_bytes} accounting unit used everywhere; supports `+`, `-`, scaling by `double`, atomics, and `ToString()`. Also defines `StorageType`, `CellDataType`, `CellIdMappingMode`, `CacheWarmupPolicies`, `CacheLimit`, `EvictionConfig`, and system-info helpers.
- `Translator<CellT>` (`cachinglayer/Translator.h`): per-slot abstraction for cell count, uid→cid mapping, conservative `estimated_byte_size_of_cell()` returning `{loaded_usage, loading_overhead}`, storage byte sizes, bonus-cell strategy, and `get_cells()`. `Meta` carries storage/data type, mapping mode, warmup policy, eviction support, `loading_overhead_config`, and optional `MetricAttribution` (shard label).
- `CacheSlot<CellT>` (`cachinglayer/CacheSlot.h`): owns one slot's `CacheCell` vector (each a `ListNode`). Entry points are `Warmup`, `PinAllCells`, `PinCells`, `PinOneCellDirect`, `PinCellsDirect`, `TryBorrowCell`, `ManualEvict(All)`, `IsCached`. `CellAccessor` holds the pins; `PinWrapper` keeps a pin alive around a value. `RunLoad()` computes essential+bonus estimates, reserves through `DList`, falls back to essential-only on bonus failure, loads, and releases through an RAII guard.
- `Manager` (`cachinglayer/Manager.h`): process-wide singleton. `ConfigureTieredStorage` (once, before any slot), `UpdateConfig`, `CreateCacheSlot`, `CreateLoadingOverheadGroup`, `UpdateLoadingOverheadGroup`, and manual reserve/release/charge/refund helpers. Owns the `DList` and prefetch pool.
- `DList` (`cachinglayer/lrucache/DList.h`): the LRU list plus admission accounting. Holds `list_mtx_`, watermarks/max limits, evictable/total loading/total loaded sizes, the timeout waiting queue, background eviction loop, and all loading-overhead Group mutations. Public API includes `ReserveLoadingResourceWithTimeout` (bool and Group-aware variants), `ReleaseLoadingResource`, `ChargeLoadedResource`, `RefundLoadedResource`, `UpdateMaxLimit`/watermarks, `touchItem`/`removeItem`/`freezeItem`, and Group `Bind`/`Unbind`/`Create`/`Update`.
- Loading overhead (`cachinglayer/LoadingOverhead.h`): immutable `LoadingOverheadPolicy` (`Passthrough`, `Budget(capacity)`, `Executor(workers)`), `LoadingOverheadDimension` (memory/file), opaque `LoadingOverheadGroup` handle, `LoadingOverheadGroupBinding` (+ optional `max_runtime_unit`), `LoadingOverheadConfig`, and `LoadingOverheadUpdateResult` (`kApplied`/`kIncompatiblePolicy`/`kInvalidArgument`).
- `TieredStorageConfig` (`cachinglayer/TieredStorageConfig.h`): runtime-updatable config singleton (snapshot reads, atomic bulk `UpdateAll`); init-only fields live in `Manager`.
- `Metrics` (`cachinglayer/Metrics.h`, `src/cachinglayer/Metrics.cpp`): macro-expanded Prometheus families per `(CellDataType, StorageType)` for capacity/watermarks, slot/cell counts, loaded/loading bytes, access hit/miss counters, load latency histograms, eviction counters, cell lifetime, and the dynamic shard-disk-usage series (`CacheShardDiskUsageMetricHandle`).

### Resource accounting flow

```text
Manager::CreateCacheSlot(translator)
  -> DList configured (ConfigureTieredStorage)
  -> CacheSlot copies Meta::loading_overhead_config and DList::BindLoadingOverheadGroups(config)

PinCells/PinCellsDirect -> PinInternal
  -> cells_[cid]->pin() (hit -> NodePin, miss -> SemiFuture<NodePin>)
  -> RunLoad for missing cids
      -> translator estimates {loaded, overhead}
      -> DList::ReserveLoadingResourceWithTimeout(loaded, overhead, config, timeout, ctx)
      -> on success: RAII release guard + cache_loading_bytes metrics
      -> translator_->get_cells(ctx, cids) -> set_cell -> ChargeLoadedResource + metrics
      -> ReleaseLoadingResource via guard
  -> collect pins into CellAccessor
```

Key properties to preserve: a successful admission gets exactly one paired release; failed admission rolls back Group demand and DList state; reservation success is explicit (`success` flag) because a policy may legitimately reserve zero bytes; `cache_loading_bytes` increments/decrements the same request-local estimate even when Group policy changes mid-flight.

### Loading-overhead Groups

Groups aggregate temporary loading demand per dimension per DList accounting domain. Read `docs/design-docs/20260723-loading-overhead-management-and-accounting.md` before modifying this subsystem. Core model:

- `S` = sum of conservative active demand, `R` = max runtime-unit bound across bindings, `Q` = unscaled amount booked in DList, `T(S,P,R) = min(max(S,0), B(P,R))`.
- Reserve transition adds demand then charges `max(T(S1)-Q0, 0)`; release removes demand and frees `max(Q0-T(S1), 0)`. Release is aggregate, not per-request.
- All Group mutations (bind/unbind/reserve/release/update/waiter retry) are serialized under `DList::list_mtx_`; the Group itself has no lock.
- Handle identity is DList-scoped: create, bind, reserve, release, and unbind must go through the same DList. A handle is not membership; `BindLoadingOverheadGroups()` creates membership, `UnbindLoadingOverheadGroups()` ends it.
- Policy replacement (`UpdateLoadingOverheadGroup`) is eventually reconciled: expansion reconciles on the next successful Reserve, tightening drains on later Releases. The owner must follow the expansion/tightening ordering contract documented in `Manager.h` and the design doc.
- `loading_resource_factor` scaling is applied per-dimension and endpoint-scaled for Groups (`Scale(Q_after)-Scale(Q_before)`, never `Scale(delta)`).

## Common utilities

- `common/EasyAssert.h`: the `milvus::ErrorCode` enum (2xxx space), `AssertInfo`/`Assert`, `ThrowInfo`, `SegcoreError`, `CStatus`/`SuccessCStatus`/`FailureCStatus`, and the untyped-cgo-exception observer hook. `FailureCStatus(const std::exception*)` maps `SegcoreError` to its typed code, otherwise collapses to `UnexpectedError` and fires the observer.
- `common/OpContext.h`: per-operation context carrying cancellation token, `storage_usage` scanning counters, optional `runtime_load_priority`, `coload_fields` coalesced-read hint, type-erased `pinned_segment_state` (+ owner guard), `trace_context`, and the single-threaded `trace_span` parent-handoff slot.
- `common/Tracer.h` / `TracerBase.h`: OpenTelemetry integration. `TraceConfig`, `TraceContext`/`OwnedTraceContext`, span helpers (`AutoSpan`, `NestedSpanGuard`, scope guards), `TRACE_SERVICE_SEGCORE`.
- `common/CommonMonitor.h` / `PrometheusClient.h`: metric registry, exporter setup, and the `DECLARE`/`DEFINE` macros used by the caching layer.
- `common/TrackingStdAllocator.h`: allocator for accounting allocations.
- `common/common_type_c.h`: C ABI `CStatus` and the `CacheWarmupPolicy` C enum.

## File manager, knowhere, and log

- `filemanager/FileManager.h`: virtual `FileManager` (LoadFile/AddFile/AddFileMeta/IsExisted/RemoveFile/OpenInputStream/OpenOutputStream) with `impl/LocalFileManager` and local/memory stream implementations.
- `knowhere/thread_pool.h`: `knowhere::ThreadPool` wrapping `folly::CPUThreadPoolExecutor` (LIFO/FIFO queues, Linux thread priority), global build/search/fetch pools, and `ScopedBuildOmpSetter`/`ScopedSearchOmpSetter` that tune OMP and OpenBLAS threads.
- `knowhere/aio_context_pool.h` / `src/knowhere/aio_context_pool.cc`: Linux aio context pool; only compiled when `find_library(aio)` succeeds.
- `log/Log.h`: glog-backed `LOG_TRACE/DEBUG/INFO/WARN/ERROR/FATAL` macros. First argument is a fmt format string (wrapped with `fmt::runtime`), and output is prefixed with the SERVER module function, trace ID, and thread name.

## SyncPoint and hashing

- `syncpoint/sync_point.h`: `milvus::SyncPoint` singleton with `LoadDependency`, callbacks, blocked points, and `TEST_SYNC_POINT`/`TEST_IDX_SYNC_POINT`/`TEST_SYNC_POINT_CALLBACK`/`INIT_SYNC_POINT_SINGLETONS` macros that are no-ops unless `ENABLE_SYNCPOINT` is defined. Build with `-DENABLE_SYNCPOINT` (CMake `ENABLE_SYNCPOINT` option).
- `flat_hash_map/` and `ptrhash/`: vendored hash-table headers. Prefer these over ad-hoc containers where the caching layer already uses them.

## Downstream consumers

- `milvus-io/milvus` embeds this repository under `internal/core/` as a submodule; segcore calls into the caching layer and common utilities over the cgo boundary, and Knowhere consumes the thread pools, file manager, and hash headers. A public-header or ABI change therefore requires coordinated testing in Milvus and Knowhere.
