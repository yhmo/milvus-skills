# SDK map and extraction commands

Source of truth for locating each SDK repo, pinning a branch, and extracting
the facade/request/response/enum surfaces used by `compare-sdk`. All reads are
pinned with `git show` / `git ls-tree` on `refs/remotes/source/<branch>` and
never mutate a worktree.

## Repos, remotes, and dev branches

| SDK | Repo | Preferred checkout | Upstream remote | Dev line branch ref |
|---|---|---|---|---|
| pymilvus | milvus-io/pymilvus | `$HOME/work/git-go/pymilvus` | `source` | `source/master` |
| java | milvus-io/milvus-sdk-java | `$HOME/work/git-go/milvus-sdk-java` | `source` | `source/master` |
| cpp | milvus-io/milvus-sdk-cpp | `$HOME/work/git-go/milvus-sdk-cpp` | `source` | `source/master` |
| csharp | milvus-io/milvus-sdk-csharp | `$HOME/work/git-go/milvus-sdk-csharp` | `source` | `source/main` |
| rust | milvus-io/milvus-sdk-rust | `$HOME/work/git-go/milvus-sdk-rust` | `source` | `source/main` |

All five upstream remotes use the same `source` remote name pointing at
`milvus-io/<repo>`. Confirm with `git remote -v` before relying on it.

The `Preferred checkout` paths are this author's machine layout and are only
examples; on other machines the checkouts may live elsewhere or be absent. Always
resolve the actual repo root with `git rev-parse --show-toplevel` first, and
report and ask before cloning when no checkout exists.

> **csharp V2 availability**: the C# `MilvusClientV2` implementation lives under
> `Milvus.Client.V2/` and is merged to upstream. It ships as the first stable
> V2 release **v2.6.0** (2026-10-16) from the `source/2.6` branch; `main`
> continues the V2 development line. Request/Response DTOs mirror the
> Java/C++/Rust V2 SDKs. Audit pinned to `source/main` or `source/2.6` directly;
> do NOT pin to a PR head.

## Branch keyword mapping

Map the user's branch keyword to the actual remote branch ref:

| Keyword | pymilvus | java | cpp | csharp | rust |
|---|---|---|---|---|---|
| `master` | `source/master` | `source/master` | `source/master` | `source/main` (dev line) | `source/main` (dev line; some docs call it `master`) |
| `main` | `source/master` | `source/master` | `source/main` | `source/main` | `source/main` |
| `3.0` | `source/3.0` | `source/3.0` | `source/master` (no dedicated `3.0` branch) | `source/main` | `source/main` (no dedicated `3.0` branch) |
| `2.6` | `source/2.6` | `source/2.6` | `source/2.6` | `source/2.6` | `source/2.6` |
| `2.5` | `source/2.5` | `source/2.5` | `source/2.5` | — | `source/2.5` |

Rust `2.5` predates the V2 client surface listed in this map. If a comparison
targets that line, report that the V2 facade is unavailable instead of trying to
read the later `src/v2/...` paths from that ref.

Branch model across the V2 SDKs (csharp/java/cpp/rust): absent a dedicated
major-version branch, the dev line (`master` for java/cpp, `main` for
csharp/rust) is also the release branch for the newest supported Milvus major —
`x.y.z` releases are cut directly from it (cpp/rust have no `3.0` branch yet;
csharp's `main` is planned as the Milvus 3.0 dev/release branch; java already
carries a `3.0` branch that tracks `master`). When a newer major arrives, the
current major's branch (e.g. `3.0`) is forked from the dev line and the dev
line follows the new major. Always verify the actual branch set from Git.

Fetch pinned with:

```bash
git -C <repo> fetch --force source +refs/heads/<branch>:refs/remotes/source/<branch>
git -C <repo> rev-parse refs/remotes/source/<branch>
```

## Source paths per SDK

| Surface | pymilvus | java | cpp | csharp | rust |
|---|---|---|---|---|---|
| V2 facade | `pymilvus/milvus_client/milvus_client.py` (class `MilvusClient`) | `sdk-core/src/main/java/io/milvus/v2/client/MilvusClientV2.java` | `src/include/milvus/MilvusClientV2.h` | `Milvus.Client.V2/MilvusClientV2.cs` + `Milvus.Client.V2/MilvusClientV2.*.cs` partials (class `MilvusClientV2`) | `src/v2/client.rs` + `src/v2/client/*.rs` |
| Request classes | (function parameters in the facade) | `sdk-core/src/main/java/io/milvus/v2/service/**/request/*.java` | `src/include/milvus/request/*.h` | `Milvus.Client.V2/Request/**/*Req.cs` | `src/v2/request/*.rs` |
| Response classes | (dict keys in the return statements) | `sdk-core/src/main/java/io/milvus/v2/service/**/response/*.java` | `src/include/milvus/response/*.h` | `Milvus.Client.V2/Response/**/*Resp.cs` | `src/v2/response/*.rs` |
| DataType enum | skipped (see Step 8) | `sdk-core/src/main/java/io/milvus/v2/common/DataType.java` | `src/include/milvus/types/DataType.h` | `Milvus.Client.V2/Types/DataType.cs` | `src/v2/types/common.rs` |
| IndexType enum | skipped (see Step 8) | `sdk-core/src/main/java/io/milvus/param/IndexType.java` | `src/include/milvus/types/IndexType.h` | `Milvus.Client.V2/Types/IndexType.cs` | `src/v2/types/index.rs` |
| Proto anchor (Step 6) | no vendored `.proto`; use generated `pymilvus/grpc_gen/*.py` descriptors | submodule `sdk-core/src/main/milvus-proto` (`proto/milvus.proto`) | `cmake/MilvusProtoGen.cmake` `PROTO_COMMIT` -> `milvus-io/milvus-proto` | submodule `Protos` (`proto/milvus.proto`) | submodule `milvus-proto` (`proto/milvus.proto`) |

## Internal mechanisms (Step 7)

Source of truth for auditing the four cross-SDK internal mechanisms. Read the
listed files pinned to the branch with `git show refs/remotes/source/<branch>:[path]`.
Line numbers are approximate, taken from the dev-line checkouts; always search
by symbol, not line, on the pinned branch.

### CollectionTsCache - last-DML-timestamp cache for ConsistencyLevel.Session

| SDK | Cache class / singleton | Cache-key | ts read for Session guarantee-ts |
|---|---|---|---|
| pymilvus | `pymilvus/client/cache.py` (`CollectionTsCache`, `GlobalCache.collection_ts`) | (endpoint, db, collection), db empty -> "default" | `pymilvus/client/ts_utils.py` (`construct_guarantee_ts`, `update_collection_ts`, `get_collection_ts`) |
| java | `sdk-core/src/main/java/io/milvus/common/utils/cache/CollectionTsCache.java` (`getInstance()`) | `CollectionCacheKey` (endpoint, db, collection) | `sdk-core/src/main/java/io/milvus/v2/utils/VectorUtils.java` (`CollectionTsCache.getInstance().get` for Session/DML); set via `v2/service/BaseService.java` (`updateTsCache`) called from DML/iterator paths |
| cpp | `src/impl/utils/cache/CollectionTsCache.h/.cpp` (`GetInstance()`) | `CollectionCacheKey` (endpoint, db, collection) | `src/impl/utils/DqlUtils.cpp` (`Get`/`Set` around search/query) |
| csharp | `Milvus.Client.V2/Utils/CollectionTsCache.cs` (`CollectionTsCache.Instance`) | `Milvus.Client.V2/Utils/CollectionCacheKey.cs` (endpoint normalized lower-case host:port, db empty -> "default") | `Milvus.Client.V2/Utils/MilvusTimestampUtils.cs` / DML+query paths building `guaranteeTimestamp` for Session |
| rust | `src/v2/client/cache.rs` (`CollectionTsCache`, `COLLECTION_TS_CACHE`) | (endpoint, db, collection), endpoint normalized, db empty -> "default" | `src/v2/client/cache.rs` (`guarantee_timestamp`) |

Key behaviors to compare: monotonic `set` (never overwrite with an older ts),
`invalidate`/`invalidate_db` on drop/rename/alias-drop, `move`/`copy` on
rename/alias, `clear`/capacity, empty-cache fallback for Session.

### SchemaCache - describe-collection short-circuit cache

| SDK | Cache class / singleton | Loader / coalescing | Read path |
|---|---|---|---|
| pymilvus | `pymilvus/client/cache.py` (`SchemaCache`, `GlobalCache.schema`) | plain `get`/`set`, no coalescing | `pymilvus/client/grpc_handler.py` `_get_schema` (~line 1019) and `async_grpc_handler.py` `_get_schema` (~line 685); invalidate via `_invalidate_schema` / `_invalidate_db_schemas` |
| java | `sdk-core/src/main/java/io/milvus/common/utils/cache/SchemaCache.java` (`getInstance()`, `getOrLoad`/`getOrLoadAsync` with load-scope coalescing) | `v2/service/BaseService.java` (`invalidateSchemaCache`), `v2/service/vector/VectorService.java` (`getCollectionSchema` caches) | `sdk-core/src/main/java/io/milvus/common/utils/cache/CollectionCacheKey.java` |
| cpp | `src/impl/utils/cache/SchemaCache.h/.cpp` (`GetInstance()`, `GetOrLoad` with load-scope coalescing) | `src/impl/MilvusClientV2Impl.cpp` (`SchemaCache::GetInstance().Invalidate` in every schema-mutating API; insert schema-mismatch retry at ~line 1878) | `src/include/milvus/types/CollectionDesc.h` |
| csharp | `Milvus.Client.V2/Utils/SchemaCache.cs` (`SchemaCache.Instance`, `GetOrLoadAsync` with single-flight coalescing) | invalidation via `SchemaCache.Instance.Invalidate` / `InvalidateDb` in `MilvusClientV2.Collection.cs` and other schema-mutating APIs | `MilvusClientV2.Collection.cs` (`DescribeCollection` caches via `GetOrLoadAsync`) |
| rust | `src/v2/client/cache.rs` (`SchemaCache`, `SCHEMA_CACHE`, `get_or_load` with load-scope coalescing) | invalidation in `src/v2/client/*.rs` on schema-mutating APIs | `src/v2/client/cache.rs` |

Key behaviors to compare: cache-hit fast path skipping `DescribeCollection`
RPC, loader coalescing (java/cpp/rust/csharp) vs plain get/set (pymilvus),
invalidation coverage on drop/alter/rename/create-index/insert-schema-mismatch
for both sync and async paths, `force_update`/`forceUpdate` refresh, capacity
and eviction.

### Retry policy - RPC failure handling incl. RateLimit

| SDK | Retry engine | Default policy | RateLimit gate | Schema-mismatch retry |
|---|---|---|---|---|
| pymilvus | `pymilvus/decorators.py` (`retry_on_rpc_failure`, `retry_on_schema_mismatch`) | 75 retries, initial 0.01s, max 3s, multiplier 3, no overall timeout; `retry_on_rate_limit` default True | `ErrorCode.RATE_LIMIT` or `common_pb2.RateLimit` (49); gRPC no-retry codes in `IGNORE_RETRY_CODES` | `retry_on_schema_mismatch` invalidates schema cache, retries once |
| java | `sdk-core/src/main/java/io/milvus/v2/utils/RpcUtils.java` (`retry`/`retryAsync`), config `sdk-core/src/main/java/io/milvus/v2/client/RetryConfig.java` | 75, initial 10ms, max 3000ms, multiplier 3, `maxRetryTimeoutMs` 0, `retryOnRateLimit` True | `io.milvus.grpc.ErrorCode.RateLimit` (49) or current code 8; gRPC no-retry codes | schema-mismatch handled via SchemaCache invalidation + retry in service layer |
| cpp | `src/impl/utils/RpcUtils.cpp` (`Retry`), config `src/include/milvus/types/RetryParam.h` | 75, initial 10ms, max 3000ms, multiplier 3, `max_retry_timeout_ms` 0, `retry_on_ratelimit_` True | `proto::common::ErrorCode::RateLimit` (legacy 49) or `ServerCode() == 8`; gRPC no-retry codes | insert/upsert `SchemaMismatch` -> invalidate SchemaCache + retry (`MilvusClientV2Impl.cpp`) |
| csharp | `Milvus.Client.V2/Utils/RetryPolicy.cs` (`RetryPolicy.ExecuteAsync`/`IsRetryable`), config `Milvus.Client.V2/Types/RetryConfig.cs` | 75, initial 10ms, max 3000ms, multiplier 3, `MaxRetryTimeout` null (no overall cap), `RetryOnRateLimit` True | `MilvusErrorCode.RateLimit` (legacy 49) or current code 8 (`MilvusErrorCode.cs`); gRPC no-retry codes in `RetryPolicy.NonRetryableRpcCodes` | via SchemaCache invalidation + retry in service layer |
| rust | `src/v2/client.rs` (`retry_call`, `retry_rpc`, `retry_transport`, `RetrySemantics`), config `src/v2/types/common.rs` (`RetryConfig`) | 75 attempts, initial 10ms, max 3000ms, multiplier 3, `max_retry_timeout` 0, `retry_on_rate_limit` True; idempotent vs non-idempotent semantics | `is_rate_limit` in `src/v2/client.rs` (`ErrorCode::RateLimit` or `status.code == 8`) | `src/v2/client/dml.rs` (`is_schema_mismatch` -> `remove_collection_description` + retry once) |

Key behaviors to compare: default policy numbers, per-client configurability
(java `withRetry`, cpp `SetRetryParam`, rust `set_retry_param`, pymilvus per-call
`retry_times`/`retry_on_rate_limit` kwargs, csharp `ConnectConfig.RetryConfig`),
gRPC no-retry code set, RateLimit
retry gating in both legacy (49) and current (8) encodings, idempotency-aware
retry (rust `RetrySemantics`), and schema-mismatch-triggered single retry.
`retryAsync`/async coverage on the java and pymilvus async paths.

### Client telemetry - metrics, heartbeat, and server-pushed commands

Run `scripts/extract_telemetry.py` for both SDKs, run
`scripts/compare_telemetry.py` on the two artifacts, then verify every reported
capability against these pinned source paths. The artifacts are the
completeness checklist; they are not a semantic parity verdict.

| SDK | Availability / config | Manager and public API | Lifecycle / wire integration |
|---|---|---|---|
| pymilvus | No client-side telemetry manager on current dev branches; generated `pymilvus/grpc_gen` code only shows the server contract | unavailable | unavailable; report explicitly instead of treating generated proto types as an SDK feature |
| java | `sdk-core/src/main/java/io/milvus/telemetry/TelemetryConfig.java` (`enabled=true`, `heartbeatIntervalMs=10_000`, `samplingRate=1.0`, `errorMaxCount=100`, `clientId=""`) | `ClientTelemetryManager.java`; facade `startTelemetry` / `getTelemetry` in `MilvusClientV2.java` | `TelemetryInterceptor.java`, `ClientTelemetryService`, heartbeat/config commands, global-cluster and use-database handoff in `MilvusClientV2.java` / global-cluster tests |
| cpp | `src/include/milvus/types/TelemetryConfig.h` (`enabled=true`, `heartbeat_interval_ms=10000`, `sampling_rate=1.0`, `error_max_count=100`, empty generated `client_id`) | `src/include/milvus/ClientTelemetry.h` and `src/impl/ClientTelemetry.cpp`; facade inline virtual `GetTelemetry()` in `MilvusClientV2.h` | `ConnectParam::Telemetry`, `MilvusConnection.cpp` handshake/transport rebound, `MilvusClientV2Impl.cpp` connection and close paths, `TelemetryUtils.h` proto conversion |
| csharp | No client-side telemetry implementation found in `Milvus.Client.V2`; generated `Protos` types do not count as an SDK feature | unavailable | unavailable on current mapped branches |
| rust | `src/v2/types/common.rs` `TelemetryConfig` (`enabled=true`, 10-second heartbeat, sampling 1.0, 100 errors, empty generated/pinned client ID) | `src/v2/client/telemetry.rs` `ClientTelemetry`; facade `telemetry()` in `src/v2/client.rs` | `ClientTelemetryService`, command handlers/acks, heartbeat task, use-database/username update, transport rebound/global-cluster integration |

Key behaviors to compare: default enablement and opt-out; config fields, units,
and validation/clamping; stable client IDs; manager accessibility; operation
latency/error/global/per-collection metrics; heartbeat and stale-window
semantics; dynamic enable/disable and other server commands; command ack and
unknown-command behavior; connection/use-database/username/global-cluster/
transport-rebound handoff; shutdown; and whether telemetry failures affect
business RPCs.


## Facade method extraction (pinned to the branch)

Run each from anywhere; replace `<branch>` with the mapped remote branch name
(use `master` / `main` as appropriate).

pymilvus (public `MilvusClient` methods):

```bash
git -C "$HOME/work/git-go/pymilvus" show source/<branch>:pymilvus/milvus_client/milvus_client.py | python3 -c '
import ast, sys
mod = ast.parse(sys.stdin.read())
for node in mod.body:
    if isinstance(node, ast.ClassDef) and node.name == "MilvusClient":
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                print(item.name)
'
```

java (public `MilvusClientV2` methods; debugging aid only — use
`scripts/extract_surface.py` for the authoritative surface):

```bash
git -C "$HOME/work/git-go/milvus-sdk-java" show source/<branch>:sdk-core/src/main/java/io/milvus/v2/client/MilvusClientV2.java \
  | grep -nE '^[[:space:]]*public[[:space:]]+(static[[:space:]]+)?[^[:space:]]+[[:space:]]+[A-Za-z_][A-Za-z0-9_]*[[:space:]]*\(' \
  | grep -v 'public class MilvusClientV2' | grep -v 'public MilvusClientV2(' \
  | sed -E 's/^.*[[:space:]]([a-zA-Z][a-zA-Z0-9_]*)\(.*/\1/' | sort -u
```

cpp (public virtual `Status` APIs):

```bash
git -C "$HOME/work/git-go/milvus-sdk-cpp" show source/<branch>:src/include/milvus/MilvusClientV2.h \
  | grep -nA1 '^\s*virtual Status' \
  | grep -E '^[0-9]+-[[:space:]]*[A-Z][a-zA-Z0-9_]+\(' \
  | sed -E 's/^.*-[[:space:]]*([A-Z][a-zA-Z0-9_]+)\(.*/\1/' | sort -u
```

rust (V2 client `pub fn` across the facade and per-domain modules):

```bash
git -C "$HOME/work/git-go/milvus-sdk-rust" show source/<branch>:src/v2/client.rs \
  | grep -nE '^\s*pub (async )?fn ' | sed -E 's/.*pub (async )?fn ([a-zA-Z0-9_]+).*/\2/' | sort -u
git -C "$HOME/work/git-go/milvus-sdk-rust" ls-tree -r --name-only source/<branch> src/v2/client/ | grep '\.rs$'
# then repeat the grep above for each module file
```

csharp (public `MilvusClientV2` methods across the facade and its partials):

```bash
git -C "$HOME/work/git-go/milvus-sdk-csharp" ls-tree -r --name-only source/<branch> Milvus.Client.V2 \
  | grep -E 'MilvusClientV2[^/]*\.cs$' | while read -r f; do
    git -C "$HOME/work/git-go/milvus-sdk-csharp" show source/<branch>:"$f"
  done | python3 -c '
import re, sys
names = set()
for line in sys.stdin:
    m = re.match(r"\s*public\s+(?:async\s+)?(?:static\s+)?[^=;]+?\s([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
    if m and m.group(1) not in ("MilvusClientV2", "Dispose", "ToString", "this"):
        names.add(m.group(1))
for name in sorted(names):
    print(name)
'
```

Method names are PascalCase with an `Async` suffix (e.g. `CreateCollectionAsync`,
`SearchAsync`, `UseDatabaseAsync`); strip the suffix when mapping to other
SDKs' names. The facade class is split into partials (`MilvusClientV2.cs` plus
`MilvusClientV2.Alias.cs`, `.Collection.cs`, `.Database.cs`, `.Dml.cs`,
`.Dql.cs`, `.Index.cs`, `.Partition.cs`, `.Rbac.cs`, `.ResourceGroup.cs`,
`.Utility.cs`), so concatenate all of them for extraction. `BulkImport.cs` is a
standalone REST bulk-import client (`BulkImportConfig` + `BulkImport`), not a
facade partial, and is excluded by the `MilvusClientV2[^/]*\.cs$` match.

## Deprecation markers per SDK (Step 2 deprecated-status comparison)

Detect deprecation status on each SDK pinned to the branch. Marker syntax and
example grep commands:

| SDK | Marker | Detection on the pinned branch |
|---|---|---|
| pymilvus | `@deprecated` decorator (from `pymilvus.decorators`) | `git -C "$HOME/work/git-go/pymilvus" show source/<branch>:pymilvus/milvus_client/milvus_client.py \| grep -nA2 '@deprecated'` |
| java | `@Deprecated` annotation | `git -C "$HOME/work/git-go/milvus-sdk-java" show source/<branch>:sdk-core/src/main/java/io/milvus/v2/client/MilvusClientV2.java \| grep -nB1 '@Deprecated'` |
| cpp | `[[deprecated(...)]]` attribute | `git -C "$HOME/work/git-go/milvus-sdk-cpp" show source/<branch>:src/include/milvus/MilvusClientV2.h \| grep -nB1 'deprecated'` |
| rust | `#[deprecated(...)]` attribute | `git -C "$HOME/work/git-go/milvus-sdk-rust" show source/<branch>:src/v2/client.rs \| grep -nA1 '#\[deprecated'` (repeat per `src/v2/client/*.rs`) |
| csharp | `[Obsolete]` attribute | `git -C "$HOME/work/git-go/milvus-sdk-csharp" show source/<branch>:<MilvusClientV2.cs or partial> \| grep -nB1 'Obsolete'` |

Match the deprecation marker to the method it annotates (it precedes the
declaration). A deprecated plain variant that has a covering `*V2` variant is
legacy-compat, not a deprecation gap (see SKILL.md Step 2).

## Naming convention mapping

Use `scripts/map_surface.py` to generate mapping candidates. Ordinary
snake_case/camelCase/PascalCase names map automatically; C# `Async` is a
language suffix and is removed for matching. Semantic `V2` suffixes (for
example `grant_privilege_v2`) are preserved. The script also carries the
documented nontrivial aliases, including:

| pymilvus | java | cpp | csharp | rust |
|---|---|---|---|---|
| `using_database` / `use_database` | `useDatabase` | `UseDatabase` | `UseDatabaseAsync` | `use_database` |
| `list_loaded_segments` | `getQuerySegmentInfo` | `ListQuerySegments` | `GetQuerySegmentInfoAsync` | `list_query_segments` |
| `list_persistent_segments` / `list_segments` | `getPersistentSegmentInfo` | `ListPersistentSegments` | `GetPersistentSegmentInfoAsync` | `list_persistent_segments` |
| `get_partition_stats` | `getPartitionStats` | `GetPartitionStatistics` | `GetPartitionStatsAsync` | `get_partition_stats` |
| `close` | `close` | `Disconnect` | `Dispose` | `close` |

The mapper's candidates are not parity verdicts: read both implementations
before deciding which candidate covers the baseline. When java exposes both a
plain and a known covering `*V2` variant, prefer the `*V2` variant for parity;
do not collapse an unrelated semantic `V2` API (such as
`grant_privilege_v2`) into its plain variant.

## Java helper/lifecycle/deprecated exclusions

These are NOT parity targets; do not count them as missing. Source:
`/home/myh/Videos/java_sdk_lack_30.md` (an author-machine note; the list below is the content).

`withRetry`, `withTimeout`, `currentUsedDatabase`, `batchDescribeCollection`,
`transferNode`, `checkHealth`, `clientIsReady`, `retryConfig`,
`setBlockingStub`, `setFutureStub`, `getAsync`, `queryAsync`, `searchAsync`,
`hybridSearchAsync`, `getLoadStateV2`, `getServerVersionV2`,
`listCollectionsV2`, `searchIteratorV2`, and deprecated helpers `alterDatabase`,
`alterCollection`, `alterIndex`, `createSchema`, `CreateSchema`.

Coverage note: `getLoadStateV2`, `getServerVersionV2`, `searchIteratorV2`, and
`listCollectionsV2` DO provide the pymilvus-equivalent capability for their
corresponding interface rows. They are excluded as independent parity rows, but
when they cover the baseline surface the row is `Implemented` with an awareness
note (see SKILL.md Step 2), not `Partial`.

C++ config/helper style equivalents of the above (`SetRetryParam`,
`SetRpcDeadlineMs`, `CheckHealth`, `session`, `Disconnect`) are config or
lifecycle equivalents, not missing server-capability APIs.

## Related reference docs

Existing parity/gap notes that these SDKs maintain on the author's machine under `/home/myh/Videos`
(these paths will not exist on other machines; treat them as optional background):

- `java_sdk_lack_30.md` - PyMilvus MilvusClient vs Java MilvusClientV2.
- `cpp_sdk_lack_30.md` - C++ vs Java.
- `rust_sdk_lack_30.md` - C++/Java vs Rust V2.
- `rust_sdk_lack_26.md` - 2.6 line Rust coverage.

Treat the checked-out/pinned source as authoritative when these notes disagree.
