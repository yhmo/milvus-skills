---
name: compare-sdk
description: Compare two Milvus SDKs (pymilvus, milvus-sdk-java, milvus-sdk-cpp, milvus-sdk-csharp, milvus-sdk-rust) on a specified branch to find parity gaps: missing MilvusClient/MilvusClientV2 interfaces, missing request/parameter members, missing response/output members, missing input-validation or wire-expressiveness behavior (proto member mappings, data encodings, RPC-issuance short-circuits), missing DataType/IndexType enum values, and missing internal mechanisms (CollectionTsCache for ConsistencyLevel.Session, SchemaCache for describe-collection short-circuiting, and RPC retry policy incl. RateLimit retry), then export a "[sdk1]_[sdk2]_[branch]_gaps.md" report into the opencode session cwd. Use when the user asks to compare SDKs or find SDK gaps/parity, e.g. "compare-sdk java sdk with pymilvus for master branch".
---

# compare-sdk

Compares two Milvus SDKs at a given branch and produces a gap report in the
opencode session's current working directory. This is an orchestration skill:
read `references/sdk-map.md` for per-SDK repo/source-map details and
`references/doc-format.md` for the required output report format.

## Supported SDKs

| Keyword(s) the user may type | Repo | Facade scanned | Type |
|---|---|---|---|
| `pymilvus`, `python` | milvus-io/pymilvus | `MilvusClient` (`pymilvus/milvus_client/milvus_client.py`) | Python, baseline when present |
| `java`, `java-sdk` | milvus-io/milvus-sdk-java | `MilvusClientV2` (`sdk-core/src/main/java/io/milvus/v2/client/MilvusClientV2.java`) | V2 |
| `cpp`, `c++`, `cxx` | milvus-io/milvus-sdk-cpp | `MilvusClientV2` (`src/include/milvus/MilvusClientV2.h`) | V2 |
| `csharp`, `c#`, `cs` | milvus-io/milvus-sdk-csharp | `MilvusClientV2` (`Milvus.Client.V2/MilvusClientV2.cs` + `MilvusClientV2.*.cs` partials) | V2 |
| `rust` | milvus-io/milvus-sdk-rust | V2 client (`src/v2/client.rs` + `src/v2/client/*.rs`) | V2 |

## Input parsing

Input shape is like: `compare-sdk [sdk1] sdk with [sdk2] for [branch] branch`.

- sdk1 = the audited SDK (first named). sdk2 = the baseline SDK (second named).
- Branch: `master`, `main`, `2.6`, `2.5`, `3.0`, ... Default when omitted:
  the dev line of the SDKs (`master`, or `main` for rust).
- When pymilvus is one of the two SDKs, pymilvus `MilvusClient` is always the
  baseline checklist and the other SDK's V2 facade is audited against it.
- Otherwise the SDK named second is the baseline (e.g. `cpp with java`: cpp is
  audited against java; `rust with java`: rust audited against java).
- Report file name: `[sdk1]_[sdk2]_[branch]_gaps_<timestamp>.md` with lowercase
  sdk names, the branch as the user named it, and a timestamp suffix appended
  once per run, e.g. `java_pymilvus_master_gaps_202608313764832.md`,
  `cpp_java_master_gaps_<timestamp>.md`, `rust_java_main_gaps_<timestamp>.md`.
- Timestamp format: `yyyyMMdd` followed by milliseconds-of-day (e.g.
  `202608313764832`), generated once per run so re-runs do not overwrite
  earlier reports. Generate it with:
  `python3 -c 'import time;print(time.strftime("%Y%m%d",time.localtime())+str(int(time.time()%86400*1000)))'`
- Write the report into the opencode session cwd (the directory opencode was
  launched in), NOT the skill directory.

## Workflow

### Step 1 - Ensure the branch codebases

For each of the two SDKs:

1. Resolve the repo root: if the cwd is already inside the SDK repo, use it;
   otherwise use the preferred checkout `$HOME/work/git-go/[repo]` when present on this machine. Verify with
   `git rev-parse --show-toplevel` and `git remote -v`. Do not assume the path
   exists; if it does not, report and ask before cloning.
2. Confirm the upstream remote `source` points to `milvus-io/[repo]`.
3. Map the user's branch keyword to the SDK's actual remote branch per
   `references/sdk-map.md` (e.g. rust `master` maps to `source/main`).
4. Fetch the branch pinned: `git fetch source [branch]:refs/remotes/source/[branch]`.
   If the name is wrong, run `git fetch source --prune`, then `git ls-remote
   source` to find the real branch name and retry with the mapping.
5. Record the resolved commit: `git rev-parse refs/remotes/source/[branch]`.
6. Read all source pinned to that branch with
   `git show refs/remotes/source/[branch]:[path]` and enumerate files with
   `git ls-tree -r --name-only refs/remotes/source/[branch] [dir]`. Never
   switch or reset a dirty worktree to inspect a branch; if a full checkout is
   ever required, use `git worktree add` with a temp path.

### Step 2 - Interface comparison

- Extract the public facade method list for each SDK pinned to the branch
  (extraction commands in `references/sdk-map.md`).
- Determine the baseline and audited side per the Input parsing rules.
- Map method names across naming conventions (snake_case / camelCase /
  PascalCase; see `references/sdk-map.md`) and build the full API Comparison
  table with one row per interface and a Status of `Implemented`, `Partial`,
  or `Missing`.
- Exclude audited-SDK helper, lifecycle, and deprecated methods from gap counts
  (keep the documented Java exclusion set from `references/sdk-map.md`); mark
  those rows as ignored rather than counting them missing.
- **Deprecated-status comparison (bidirectional):** for every interface mapped
  on BOTH sides, compare the deprecation markers (pymilvus `@deprecated`,
  java `@Deprecated`, cpp `[[deprecated]]`, rust `#[deprecated]`, csharp
  `[Obsolete]`). A divergence in either direction marks the row
  `Partial - deprecated in <sdk> but not in <sdk>` and is reported in Main gaps:
  - baseline interface deprecated but the audited side not yet marked;
  - audited-side interface deprecated but the baseline not yet marked.
  This is symmetric and independent of the parity-target exclusion above: the
  exclusion still applies to audited-SDK helper/lifecycle/deprecated methods
  with no mapped baseline equivalent (the Java exclusion set in
  `references/sdk-map.md`), but a row that maps on both sides with divergent
  deprecation status is always a `Partial` gap. A deprecated plain variant that
  sits under a covering `*V2` variant (e.g. deprecated `searchIterator` under
  `searchIteratorV2`) is legacy-compat, not a deprecation gap.
- Java `*V2` variants are COVERAGE, not exclusions. When java exposes both a
  plain and a `*V2` variant for a baseline interface, prefer the `*V2` variant
  for parity (per `references/sdk-map.md`). If the `*V2` variant expresses the
  full baseline capability, mark the row `Implemented` and add an awareness note
  naming the covering variant; the narrower plain variant is a legacy-compat
  wrapper, not a gap. Only mark `Partial` when NO public variant expresses the
  baseline input/output. This applies to `getLoadState`/`getLoadStateV2`,
  `getServerVersion`/`getServerVersionV2`, `searchIterator`/`searchIteratorV2`,
  and `listCollections`/`listCollectionsV2`.

### Step 3 - Parameter comparison

For each interface row, compare the input surface:

- pymilvus (when baseline): the `MilvusClient` method parameters. Generic
  Python `timeout` and `**kwargs` alone are not gaps; concrete feature
  parameters hidden inside `**kwargs` count when visible in the body.
- java/cpp/csharp/rust: the members of the corresponding request class
  (locations in `references/sdk-map.md`).
- A baseline input that the audited side cannot express marks the row `Partial`
  with a one-line description of the missing parameter.

### Step 4 - Output comparison

For each interface row, compare the output surface:

- pymilvus (when baseline): the dict keys it returns (read the return
  statements).
- java/cpp/csharp/rust: the members/getters of the corresponding response class.
- A missing observable output field marks the row `Partial`. Wrapper-shape
  differences (Python dict/list/scalar vs a typed response object) are NOT
  gaps by themselves.

### Step 5 - Validation comparison

For each interface row, compare client-side input validation on both sides and
count divergences in BOTH directions:

- Enumerate the baseline side's client-side validation rules for the request
  inputs (required/null/empty rejection, range bounds, type/format checks,
  enum membership, cross-field constraints). Read the request class/builder and
  the facade method body, not just the parameter list.
- Numeric-bound rules are MANDATORY to enumerate, not left to auditor
  discretion. For every interface, explicitly check and record each of the
  baseline's numeric/range bounds and its audited-side counterpart: `limit`/
  `topK` > 0, `round_decimal` range, `batch_size`/`batchSize` bounds,
  `dimension` > 0, `target_size`/`targetSize` > 0, `max_capacity` caps, and any
  other range check. A baseline bound that the audited side does not enforce
  (or enforces differently) MUST appear as its own row in the Input Validation
  Comparison table; do not fold several bounds into one generic row.
- Missing rule: a rule the baseline enforces that the audited side does not →
  mark the row `Partial` and record the missing validation (the audited side
  accepts input the baseline rejects).
- Extra rule: a rule the audited side enforces that the baseline does not →
  mark the row `Partial` and record the stricter contract (the audited side
  rejects input the baseline accepts). This is a divergence, not a defect.
- Exclusions: server-side-only validation (enforced by Milvus, not the SDK),
  validation ordering, and error-message wording are NOT gaps.
- Required-name emptiness guards are NOT per-row gaps. pymilvus applies uniform
  `check_pass_param` name guards (non-empty `collection_name` / `partition_name`
  / `db_name` / `role_name` / `user_name` / `group_name` / privileges-list
  entries, `timeout` type) across nearly every interface; since the Milvus
  server also rejects empty names, treat these as server-backed presence checks
  and record them ONCE as a cross-cutting note, not as individual `Partial`
  rows. Only count a name guard per-row when the audited side rejects input the
  baseline accepts (Extra direction), never for the routine Missing direction.

### Step 6 - Wire-expressiveness audit (proto-anchored, deep mode)

Catch gaps that are invisible at the facade surface by anchoring on the gRPC
proto definitions and on RPC-issuance behavior. Run this per interface row in
the API Comparison table.

Proto anchor:

- Use ONE canonical proto source pinned to a commit matching the audited
  branches: `milvus-io/milvus-proto`, or, when java, rust, or csharp is
  involved, their vendored submodules (`sdk-core/src/main/milvus-proto` for
  java, `milvus-proto` for rust, `Protos` for csharp). cpp fetches protos via
  CMake at build time (`cmake_build/_deps/milvus_proto-src`). pymilvus does NOT
  vendor `.proto` files - only generated `pymilvus/grpc_gen/*.py` - so never
  look for protos inside the pymilvus repo.
- For each relevant `MilvusService` RPC in `proto/milvus.proto`, enumerate the
  input message members and the output message members.

Member mapping trace:

- For each proto member, trace whether each SDK maps user input to it (search
  for the generated type member: pymilvus `grpc_gen`, java generated protobuf
  classes, cpp/rust generated types). Ignore members with no user mapping on
  either side (server-generated/internal fields such as collection/segment IDs
  and timestamps).
- Distinguish "user-controllable mapping" from "SDK-derived default": if one
  SDK lets the user override a member that the other hard-codes, that is an
  expressiveness gap.
- A baseline-mapped member the audited side cannot map marks the row `Partial`
  with the member named. Compare symmetrically in both directions.

Wire-encoding checks:

- Verify data-payload encodings are equivalent, e.g.:
  - nullable propagation to nested schema elements: struct sub-field
    `FieldSchema.nullable` must inherit the struct's `nullable` (pymilvus does
    this; a missing propagation on the audited side is a gap);
  - null-row encoding through `FieldData.valid_data`;
  - scalar/vector packing and dimension handling.
- A baseline-supported encoding the audited side cannot produce marks the row
  `Partial` with the encoding named.

RPC-issuance behavior:

- Compare whether each SDK short-circuits an edge input client-side (returns a
  synthetic result without issuing the RPC) versus issuing the RPC.
- A divergence is a gap in either direction. Example: pymilvus
  `insert`/`upsert` with an empty `data` list returns `{"insert_count": 0,
  "ids": []}` without an RPC while java sends the RPC - mark `Partial`
  (mismatched RPC-issuance behavior).
- This compares only whether the RPC is issued; retry timing/policy stays out
  of scope (retry behavior itself is audited in Step 7, not here).

### Step 7 - Internal mechanisms audit (deep mode)

Beyond the facade surface, Milvus SDKs share three internal mechanisms that
shape observable behavior. Audit each one on BOTH SDKs pinned to the branch and
record divergences in a dedicated section (source locations in
`references/sdk-map.md` under "Internal mechanisms"). A divergence in either
direction is a gap, reported in the Internal Mechanisms Comparison table.

Mechanism 1 - CollectionTsCache (ConsistencyLevel.Session):

- Check the SDK caches the last DML timestamp per
  (endpoint, db, collection) in a process-wide singleton (pymilvus
  `GlobalCache.collection_ts`, java/cpp `CollectionTsCache::getInstance()`,
  csharp `CollectionTsCache.Instance`, rust `COLLECTION_TS_CACHE`).
- Trace where DML responses feed the cache (insert/upsert/delete timestamps)
  and where the cached ts is read to build the `guarantee_timestamp` for
  `ConsistencyLevel.Session` searches/queries (and the default-consistency
  path). Compare:
  - singleton vs per-client scoping;
  - key granularity (endpoint + db + collection; empty db normalized to
    "default");
  - monotonic update (a newer ts must not be overwritten by an older one);
  - eviction/`clear` behavior and cache capacity (pymilvus/rust LRU-capacity
    differences, java/cpp/csharp unbounded map);
  - rename/alias propagation (`move`/`copy` on rename and create-alias) and
    invalidation on drop/rename/alias-drop;
  - fallback value when the cache is empty for a Session/guarantee-ts lookup
    (pymilvus falls back to eventually-ts; rust falls back to 1).
- A baseline behavior the audited side lacks marks the row `Partial`.

Mechanism 2 - SchemaCache (describe-collection short-circuit):

- Check the SDK caches the collection schema/`DescribeCollectionResponse` per
  (endpoint, db, collection) in a process-wide singleton and consults it before
  issuing `DescribeCollection` (pymilvus `GlobalCache.schema` + `_get_schema`,
  java `SchemaCache.getInstance().getOrLoad`, cpp
  `SchemaCache::GetInstance().GetOrLoad`, csharp `SchemaCache.Instance`
  `GetOrLoadAsync`, rust `SCHEMA_CACHE.get_or_load`).
- Compare:
  - cache-hit fast path: schema-bearing operations (insert/upsert/delete/
    query/search/partition ops/iterator) reuse the cached schema instead of an
    RPC, and `get_collection_stats`/similar skip DescribeCollection;
  - loader coalescing: concurrent cache-miss loads are coalesced so one RPC
    serves many waiters (java/cpp/rust/csharp coalesce within a per-client load
    scope; pymilvus does not coalesce - plain get/set);
  - invalidation coverage: every schema-mutating API (drop, alter, rename,
    create index, load schema-driven calls, insert schema-mismatch retry) must
    invalidate the cache on both sync and async paths;
  - cache capacity/LRU eviction and thread-safety;
  - force-refresh path (`force_update` / `getOrLoad(forceUpdate)`).
- A baseline caching/invalidation behavior the audited side lacks marks the row
  `Partial`.

Mechanism 3 - Retry policy (RPC failure handling):

- Check the SDK applies a uniform retry loop around RPC issuance with a
  configurable policy (pymilvus `retry_on_rpc_failure` decorator, java
  `RpcUtils.retry`/`RetryConfig`, cpp `Retry()`/`RetryParam`, csharp
  `RetryPolicy`/`RetryConfig`, rust `retry_call`/`RetryConfig`).
- Compare:
  - default policy: max retry times/attempts, initial/max backoff, backoff
    multiplier, and whether an overall retry timeout exists;
  - RateLimit handling: server RateLimit errors are retried by default
    (`retry_on_rate_limit`), gated on the server error code in both legacy
    (49/RateLimit) and current (8) encodings;
  - gRPC-level no-retry codes (DEADLINE_EXCEEDED, PERMISSION_DENIED,
    UNAUTHENTICATED, INVALID_ARGUMENT, ALREADY_EXISTS, RESOURCE_EXHAUSTED,
    UNIMPLEMENTED) are not retried;
  - idempotency-aware retry: does the SDK refuse to retry non-idempotent DML
    or retry only idempotent RPCs (rust `RetrySemantics`)?;
  - schema-mismatch retry: on SchemaMismatch, invalidate the schema cache and
    retry once (pymilvus `retry_on_schema_mismatch`);
  - API to configure the policy per client (java `withRetry`/`retryConfig`,
    cpp `SetRetryParam`, csharp `ConnectConfig`/`RetryConfig`, rust
    `set_retry_param`, pymilvus per-call
    `retry_times`/`retry_on_rate_limit` kwargs);
  - where retry is applied: uniformly across DML/DQL and admin calls or only on
    some paths.
- A baseline retry behavior the audited side lacks marks the row `Partial`.
  Retry is a mechanism gap here, distinct from the RPC-issuance short-circuit
  comparison in Step 6 (which compares whether an RPC is issued at all).

### Step 8 - DataType / IndexType enum comparison

- Only when NEITHER SDK is pymilvus (java/cpp/rust/csharp pairs). When pymilvus
  is involved, skip this step entirely (pymilvus has no comparable DataType /
  IndexType enum surface for this comparison).
- Compare enum values by public name; numeric codes may differ between SDKs.
- List every value present on the baseline but missing on the audited side as
  a `Missing` row in the Data Type and Index Type comparison tables.

### Step 9 - Export the report

- Write `[sdk1]_[sdk2]_[branch]_gaps_<timestamp>.md` into the opencode session
  cwd, with the timestamp generated once per run per the Input parsing rules.
- Follow `references/doc-format.md` exactly: header block, Scope, Summary,
  Main gaps, API Comparison, Input Validation Comparison, Wire-expressiveness
  audit, Internal Mechanisms Comparison, enum tables (when applicable), and
  Reproducibility sections.
- Keep the Summary counts, Main-gap bullets, and API table consistent with each
  other and with the audited source. Record the branch and commit hash of both
  repos in the report.
- Finish with a concise summary to the user of the counts and headline gaps.

## Rules

- For java/cpp/rust/csharp scan ONLY the V2 implementation. Legacy V1 facades,
  legacy ORM helpers, and generated protobuf RPCs do not count as V2 coverage.
- Status definitions are fixed: `Implemented` = equivalent facade/request API
  with the same core capability; `Partial` = capability exists but a baseline
  input parameter or observable output value is missing, or input-validation
  semantics diverge in either direction (see Step 5), or wire-expressiveness
  diverges (proto member mapping, data encoding, or RPC-issuance short-circuit
  mismatch, see Step 6); `Missing` = no equivalent facade/request API. If the
  underlying capability exists but not the same convenience wrapper, mark
  `Partial`, not `Missing`. If the capability is reachable only through a
  `*V2` variant (e.g. `getLoadStateV2`), the row is `Implemented` with an
  awareness note (see Step 2), not `Partial`.
- Validation comparison is symmetric: a baseline rule absent on the audited
  side and an audited-side rule absent from the baseline are both recorded as
  `Partial` with the rule named. Validation order and error-message wording
  are never gaps.
- Deprecated-status comparison is symmetric: an interface deprecated on the
  baseline but not on the audited side, and one deprecated on the audited side
  but not on the baseline, are both recorded as `Partial - deprecated in <sdk>
  but not in <sdk>` and listed in Main gaps. Detection markers per SDK:
  pymilvus `@deprecated`, java `@Deprecated`, cpp `[[deprecated]]`, rust
  `#[deprecated]`, csharp `[Obsolete]`. Audited-side deprecated methods with no
  mapped baseline equivalent remain in the helper/deprecated exclusion
  (Ignored), and deprecated plain variants under a covering `*V2` variant
  remain legacy-compat (not gaps).
- Required-name emptiness guards are recorded once as a cross-cutting note, not
  per-row `Partial`s (see Step 5); the server backs them, so the routine
  Missing direction is not a gap. The Extra direction (audited side rejects
  input the baseline accepts) still counts per-row.
- Wire-expressiveness comparison is symmetric and counts in both directions: a
  baseline proto-member mapping, data encoding, or RPC-issuance short-circuit
  that the audited side does not share is a `Partial` gap. RPC short-circuit
  mismatches (one side returns a synthetic result without issuing the RPC, the
  other issues the RPC) are gaps, in either direction.
- Internal-mechanisms comparison (Step 7) is symmetric and counts in both
  directions: a CollectionTsCache, SchemaCache, or Retry behavior the baseline
  has that the audited side lacks (or vice versa) is a `Partial` gap, reported
  in the Internal Mechanisms Comparison table. Single-instance singletons and
  cache-key normalization are not gaps by themselves; missing monotonicity,
  missing invalidation coverage on schema/DML-mutating APIs, missing
  guarantee-ts wiring for `ConsistencyLevel.Session`, missing rate-limit
  retry, or missing schema-mismatch retry are gaps.
- Proto anchor: use `milvus-io/milvus-proto` (or the java/rust/csharp
  submodules)
  pinned to a commit matching the audited branches. pymilvus vendors no
  `.proto` files; only generated `pymilvus/grpc_gen/*.py`.
- Do not mutate any repository worktree; all reads must be pinned via
  `git show`/`git ls-tree` on `refs/remotes/source/[branch]`.
- Verify every path before using it; when the two SDKs are resolved, also load
  the matching per-SDK skills (pymilvus, milvus-sdk-java, milvus-sdk-cpp,
  milvus-sdk-csharp, milvus-sdk-rust) for repo-specific detail, but trust
  `references/sdk-map.md` here as the source of truth for this comparison.
- Do not invent SDKs or branches. If the user names a branch that does not
  exist, report it and ask.

## References

- [references/sdk-map.md](references/sdk-map.md) - per-SDK repo locations,
  branch mapping, source paths, extraction commands, and naming conventions.
- [references/doc-format.md](references/doc-format.md) - the required content
  format of the exported gap report.
