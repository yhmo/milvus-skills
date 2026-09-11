# Change rules and conventions

Apply these rules to every milvus-common change. Read `references/architecture.md` for component behavior before editing.

## Language and layout

- C++20 is required (`conanfile.py` enforces it; CMake sets `CMAKE_CXX_STANDARD 20`).
- Public headers live under `include/` and are installed wholesale by `CMakeLists.txt`; implementation lives under `src/`. Consumers include headers as `#include "cachinglayer/Utils.h"` with the `include/` root on the include path.
- The library target is `milvus-common` (SHARED). ABI-visible templates (for example `CacheSlot<CellT>`, `Translator<CellT>`, `CellAccessor`, `PinWrapper`) require stable signatures.

## Namespaces

- `milvus` for common utilities (`milvus::tracer`, `milvus::impl`, `milvus::cachinglayer`).
- `milvus::cachinglayer` for public caching-layer types; `milvus::cachinglayer::internal` for `DList` and internals. `LoadingOverheadGroup` is `milvus::cachinglayer` but its implementation is private to `internal::DList`.

## Error handling

- Originate errors through `ThrowInfo(ErrorCode::X, "...", args...)`; assert with `AssertInfo`/`Assert` from `common/EasyAssert.h`.
- `ErrorCode` is an explicit enum in `common/EasyAssert.h`. Add new codes there and keep the numeric space stable. Preserve the pair semantics of `StorageError` (2044, permanent) versus `StorageTransientError` (2045, retriable): a transient object-storage failure must map to `StorageTransientError`, never `StorageError`, or retriable IO becomes non-retriable.
- For cgo boundaries, return `SegcoreError` so `FailureCStatus(const std::exception*)` projects the typed code. Any other exception collapses to `UnexpectedError` and fires the untyped-cgo-exception observer; shrinking that hit rate is the goal when adding classification.
- A zero-byte successful reservation is not a failure: `LoadingResourceReservationResult` carries an explicit `success` flag. Never treat `reserved == 0` as an error sentinel.
- Negative accounting state is an invariant violation: log it and clamp to zero; never let it propagate silently.

## Logging

- Use `LOG_TRACE/DEBUG/INFO/WARN/ERROR/FATAL` from `log/Log.h`. The first argument is a fmt format string; the macros wrap it with `fmt::runtime`, so pass either a literal or a pre-formatted string. Log messages are prefixed with the SERVER module, trace ID, and thread name automatically.
- Do not log sensitive configuration or full cell contents on hot paths.

## Metrics

- Declare families and accessor helpers in the relevant `Metrics.h` (caching layer) or monitor header; define them once in the corresponding `.cpp` with the `DEFINE_PROMETHEUS_*` macros.
- Caching-layer metrics expand over `(CellDataType, StorageType)`; always use the `monitor::cache_xxx(CellDataType, StorageType)` accessor so labels stay consistent.
- Adding a metric family means adding DECLARE + DEFINE + helper in the same change; verify the family name and description match.
- Keep metrics and admission accounting distinct: for example `cache_loading_bytes` must decrement exactly the value it incremented even when a Group policy changes mid-flight.

## Hot-path discipline

The caching layer and tracer are hot-path code; recent work exists specifically to remove per-call refcount bumps and allocations. Before adding work to a frequently called path, read the comments in `CacheSlot::TryBorrowCell`, `RecordAccessEvent`, and `CacheSlot::RunLoad`:

- Do not add a contended `prometheus::Counter::Increment` (single shared `atomic<double>` CAS) to per-access paths; prefer sharded/thread-local counters or aggregated metrics.
- Avoid `shared_from_this()` refcount churn and per-call allocations where a borrow or zero-cost fast path already exists (`skip_pin_`).
- Keep `DList::list_mtx_` critical sections minimal; Group mutations run under this lock by design, but waiter reprocessing and eviction work must stay bounded.

## Caching-layer invariants

Preserve the invariants documented in `docs/design-docs/20260723-loading-overhead-management-and-accounting.md` (Section 12) and `references/architecture.md`:

- Every successful admission receives exactly one paired Release; failed admission leaves no active demand behind.
- Group reservation is aggregate, not per-request; completion order must not change the eventual zero balance.
- Bind, queued-waiter retry, and Unbind use copied `LoadingOverheadConfig` metadata, never later mutations to Translator `Meta`.
- A Handle is issued by and scoped to one DList; membership begins at CacheSlot Bind and ends at CacheSlot Unbind.
- Bounded Budget/Executor policies never operate on a binding without `max_runtime_unit`.
- Group-aware waiter requirements must be recomputed on retry (policy and Group state can change while queued).

## Concurrency and cancellation

- Respect `folly::CancellationToken`; loading and slot-creation paths must check cancellation before starting work and map cancellation to `ErrorCode::FollyCancel`.
- Destroy waiter objects outside `list_mtx_` so cancellation callbacks cannot deadlock.
- `OpContext::trace_span` is a single-threaded parent handoff slot, not a current-span stack. Copy it into per-worker state before nesting spans in parallel work.

## SyncPoint

- Add `TEST_SYNC_POINT("name")` markers only when deterministic interleaving tests need them; they are compiled out unless `ENABLE_SYNCPOINT` is defined. Set up dependencies in the test with `SyncPoint::GetInstance()->LoadDependency(...)` and enable processing first.

## Testing expectations

- Add focused GTest coverage beside the affected test directory (`test/test_cachinglayer/` for caching-layer changes, `test/` for tracer/stream/ptrhash).
- For concurrency, waiting-queue, or policy-reconciliation changes, run the tests under ASan (`make test BUILD_TYPE=Release CONAN_EXTRA='-o \&:with_asan=True'`) and trace the failure modes described in the loading-overhead design doc's test strategy.
- State explicitly when tests were skipped or a real Milvus/Knowhere integration check was required.

## Repository and review rules

- Do not commit, push, or open PRs unless the user asks. When committing, use `git commit -sm '<type>: <subject> (#N)'` so every commit carries a Signed-off-by trailer; conventional subjects in this repo include `enhance:`, `fix:`, and `docs:`.
- Each PR must contain exactly one commit.
- Keep changes scoped: do not mix feature work with release metadata or unrelated formatting. `clang-format` is enforced by pre-commit; format only files you touch.
- Preserve unrelated user changes and generated artifacts; inspect `git status --short` before and after.
