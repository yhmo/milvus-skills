# Gap report content format

The report `[sdk1]_[sdk2]_[branch]_gaps_<timestamp>.md` must follow this
structure. `report.py` generates the timestamp in UTC as `yyyyMMddHHmmss` plus
six fractional-second digits and appends a numeric suffix if the path collides.
This format is derived from the existing gap docs (author-machine notes under
`/home/myh/Videos`; treat the structure here as authoritative):

- `/home/myh/Videos/java_sdk_lack_30.md`
- `/home/myh/Videos/cpp_sdk_lack_30.md`
- `/home/myh/Videos/rust_sdk_lack_30.md`

## Status definitions

| Status | Meaning |
|---|---|
| Implemented | The audited SDK exposes an equivalent facade or request API with the same core capability. |
| Partial | The audited SDK has the underlying capability but is missing a baseline input parameter/default/coercion behavior or an observable output value/behavior, or input-validation semantics diverge in either direction (see Input Validation Comparison), or wire-expressiveness diverges - proto member mapping, data encoding, or RPC-issuance short-circuit mismatch (see Wire-expressiveness audit), or an internal mechanism diverges - CollectionTsCache / SchemaCache / Retry / client telemetry / client session behavior mismatch (see Client Session Comparison and Internal Mechanisms Comparison), or deprecation status diverges - the interface is marked deprecated on one side but not the other (bidirectional, see Main gaps and API Comparison). |
| **Missing** | No equivalent audited-SDK facade/request API was found. |
| Ignored / excluded | Helper, lifecycle, config, deprecated, or legacy-V1 surface not treated as a parity target. |

## Counting conventions

- For java/cpp/rust/csharp, count ONLY the V2 implementation (`MilvusClientV2`,
  or the rust V2 client). Legacy V1, legacy ORM helpers, and generated protobuf
  RPCs are not coverage.
- The baseline is the checklist: pymilvus `MilvusClient` when present;
  otherwise the SDK named second (e.g. java for `cpp with java`).
- Generic Python `timeout` and `**kwargs` are not gaps by themselves; concrete
  feature parameters hidden in `**kwargs` are counted when visible.
- Wrapper-shape differences (Python dict/list/scalar vs a typed response
  object) do not count as parity gaps by themselves.
- Java `*V2` variants provide coverage: if the full baseline capability is
  reachable only through a `*V2` variant (e.g. `getLoadStateV2`,
  `getServerVersionV2`, `searchIteratorV2`, `listCollectionsV2`), the
  corresponding interface row is `Implemented` with an awareness note naming
  the covering variant. The narrower plain variant is a legacy-compat wrapper
  and is not a gap by itself.
- Distinguish true facade gaps from lower-level equivalents: if the audited
  SDK exposes the underlying capability but not the same convenience wrapper,
  mark `Partial` rather than `Missing`.
- The actionable bar is content/semantic alignment: only missing content,
  mismatched semantics, missing input expressiveness, or missing observable
  output values count as gaps.
- Default/coercion divergences count as `Partial` when the same unset input
  resolves to materially different proto values or observable behavior.
- Input-validation divergences count as `Partial` in both directions: a
  baseline validation rule absent on the audited side (weaker contract), and
  an audited-side validation rule absent from the baseline (stricter contract).
  Validation order and error-message wording are not gaps.
- Required-name emptiness guards (`collection_name` / `partition_name` /
  `db_name` / `role_name` / `user_name` / `group_name` / privileges-list
  entries) are server-backed presence checks: record them ONCE as a
  cross-cutting note, not as individual `Partial` rows, unless the audited side
  rejects input the baseline accepts (Extra direction, which still counts
  per-row).
- Numeric/range bounds must be enumerated per bound, one row each, and are not
  left to auditor discretion: `limit`/`topK` > 0, `round_decimal` range,
  `batch_size` bounds, `dimension` > 0, `target_size` > 0, `max_capacity` caps,
  and any other range check. A baseline bound the audited side does not enforce
  (or enforces differently) MUST appear as a `Partial` row naming the exact
  bound and its allowed range.
- Wire-expressiveness divergences count as `Partial` in both directions: a
  proto member the baseline maps from user input but the audited side cannot
  map, a data encoding the baseline produces but the audited side cannot
  (e.g. struct sub-field nullable propagation, null-row `valid_data`), and an
  RPC-issuance short-circuit mismatch (one side returns a synthetic result
  without issuing the RPC, the other issues the RPC - e.g. empty-data
  `insert`/`upsert`). SDK-derived-only fields with no user mapping are ignored.
- Internal-mechanism divergences count as `Partial` in both directions (see
  Internal Mechanisms Comparison): CollectionTsCache, SchemaCache, Retry,
  client telemetry, or client-session behavior the baseline has that the
  audited side lacks (or vice versa).
  Singleton-vs-per-client scoping and cache-key normalization (empty db ->
  "default", endpoint normalization) are NOT gaps by themselves. Missing
  monotonic ts updates, missing invalidation coverage on schema/DML-mutating
  APIs, missing `guarantee_timestamp` wiring for `ConsistencyLevel.Session`,
  missing RateLimit retry (legacy 49 / current 8), and missing
  schema-mismatch single retry ARE gaps.
- Deprecated-status divergences count as `Partial` in BOTH directions: the
  interface is marked deprecated on the baseline but not on the audited side,
  OR marked deprecated on the audited side but not on the baseline. Report each
  in Main gaps and mark the API Comparison row
  `Partial - deprecated in <sdk> but not in <sdk>`. Deprecation markers per SDK:
  pymilvus `@deprecated`, java `@Deprecated`, cpp `[[deprecated]]`, rust
  `#[deprecated]`, csharp `[Obsolete]`. A deprecated audited-side method with no
  mapped baseline equivalent stays in the helper/deprecated exclusion (Ignored),
  not a gap; a deprecated plain variant under a covering `*V2` variant is
  legacy-compat, not a gap.
- DataType/IndexType enum comparison is included only when neither SDK is
  pymilvus; when pymilvus is involved, omit those sections entirely.

## Document structure

```
# <Title>

Title examples:
- "PyMilvus `MilvusClient` vs Java SDK `MilvusClientV2` - <branch>"
- "<SDK1> <branch>: Missing Interfaces Compared to <SDK2>"

Source files compared:

- <SDK1> <branch> (<commit>): <absolute path to facade file>
- <SDK2> <branch> (<commit>): <absolute path to facade file>
- <SDK2> request/response classes under <absolute directory paths>

Scope:

- bullets stating the methodology used for this run:
  - which facade was counted on each side and the baseline/audited roles
  - raw method counts observed on both sides
  - what was not counted (inherited helpers, Java helper/lifecycle/deprecated
    set, V1 legacy surface, generated RPCs)
  - parameter and output counting conventions
  - behavior-artifact scope: facade parameters, request/builder fields and
    defaults, concrete kwargs, validation-signal entry points, response
    members/accessors, Python return paths, and nested observable types
  - input-validation comparison in both directions (missing baseline rules and
    extra audited-side rules) and what is excluded (server-side-only checks,
    validation order, error wording)
  - wire-expressiveness audit scope (proto anchor and its commit, per-RPC
    member mappings traced, encoding checks, RPC-issuance short-circuits) and
    what is ignored (members with no user mapping on either side)
  - internal-mechanisms audit scope (CollectionTsCache for
    `ConsistencyLevel.Session`, SchemaCache describe-collection short-circuit,
    Retry policy incl. RateLimit retry, client telemetry, and client
    session/global-cluster routing) and what is
    ignored (singleton-vs-client
    scoping, cache-key normalization)
  - deprecated-status comparison in both directions (interface marked
    deprecated on one side but not the other) and what is ignored (audited-side
    deprecated methods with no mapped baseline equivalent, deprecated plain
    variants under a covering `*V2` variant)
  - wrapper-shape and enum conventions

## Summary

| Status | Count | Meaning |
|---|---|---:|---|
| Implemented | N | ... |
| Partial | N | ... |
| **Missing** | N | ... |
| Total | N | Total baseline interfaces checked. |

## Main gaps

- Missing API: <none>, or a table of the missing interfaces.
- Partial parameter or output gaps: table with columns `Method` and `Gap`.
- Deprecated-status divergences: one bullet (or small table) per interface whose
  deprecation status differs between the two SDKs, in both directions, e.g.
  `searchIteratorV2: deprecated in java but not in pymilvus`,
  `list_collections: deprecated in pymilvus but not in java`.

Minor behavioral nuances (counted as Implemented, noted for awareness):
- one bullet per nuance (e.g. None-vs-exception, missing page timestamp).

## Coverage validation

State that `validate_coverage.py` passed and record the baseline/audited surface
SHA-256 values and method counts. Name any audited-only methods carried as
`scope=extra` rows and any check marked not applicable with its reason.

```text
Coverage validation: PASS
Baseline surface SHA-256: ...
Audited surface SHA-256: ...
Baseline behavior SHA-256: ...
Audited behavior SHA-256: ...
Baseline telemetry SHA-256: ...
Audited telemetry SHA-256: ...
Telemetry comparison SHA-256: ...
Baseline session SHA-256: ...
Audited session SHA-256: ...
Session comparison SHA-256: ...
```

The validator must report version 2 and all seven per-method checks (`facade`,
`parameters`, `defaults`, `outputs`, `validation`, `wire`, `deprecated`) plus
all five global checks (`collection_ts_cache`, `schema_cache`, `retry`,
`client_telemetry`, `client_session`).

## API Comparison

| <SDK1 API> | <SDK2 API> | Status |
|---|---|---|
| `search_iterator` | `searchIteratorV2` | Partial - deprecated in java but not in pymilvus |

One row per interface. Status is `Implemented`, `Partial - <reason>`,
`**Missing**`, or a note like `Ignored helper API`. A deprecation-status
divergence is marked `Partial - deprecated in <sdk> but not in <sdk>`
(bidirectional). Order the rows by domain
grouping (session/config, collection/schema, partition, index, DML/DQL,
database, alias, RBAC, resource group, snapshot, CDC, utility).

## Defaults and Coercion Comparison

| Interface | Input/output value | Baseline default/coercion | Audited default/coercion | Observable effect | Status |
|---|---|---|---|---|---|

One row for each materially different unset-value resolution, implicit default,
unit normalization, coercion, truncation, clamping, or empty/null fallback that
changes an RPC value or an observable result. Equivalent spellings such as
`10_000`, `10000`, and a ten-second duration are not gaps. Rows must reconcile
with `Partial` API rows.

## Input Validation Comparison

| Interface | Baseline rule | Audited side | Direction | Status |
|---|---|---|---|---|

One row per validation rule (an interface may have several rows) with a
divergence, in both directions:
- Missing: baseline validates, audited side does not (audited accepts input
  the baseline rejects) - weaker contract.
- Extra: audited side validates, baseline does not (audited rejects input the
  baseline accepts) - stricter contract, a divergence not a defect.
Each numeric/range bound is its own row (e.g. separate rows for `limit > 0`
and `round_decimal` range on `search`).
Excluded: server-side-only validation (enforced by Milvus), validation order,
and error-message wording. Every row must name the specific rule; rows here
reconcile with the `Partial` rows in the API Comparison table.

## Wire-expressiveness audit

| Interface | Proto member / encoding / behavior | Baseline | Audited side | Direction | Status |
|---|---|---|---|---|---|

One row per wire-expressiveness divergence found in Step 6, in both
directions:
- Member mapping: baseline maps a proto member from user input, audited side
  cannot (or vice versa); SDK-derived-only members with no user mapping on
  either side are ignored.
- Encoding: baseline produces a data encoding the audited side cannot (or vice
  versa), e.g. struct sub-field `nullable` propagation, null-row
  `valid_data`, scalar/vector packing.
- RPC issuance: baseline short-circuits an edge input without issuing the RPC
  while the audited side issues it (or vice versa), e.g. empty-data
  `insert`/`upsert`.
Excluded: retry timing/policy. Every row must name the specific member,
encoding, or short-circuit; rows here reconcile with the `Partial` rows in the
API Comparison table.

## Client Telemetry Comparison

| Aspect | Baseline | Audited side | Direction | Status |
|---|---|---|---|---|
| Availability/default enablement | ... | ... | ... | ... |
| Configuration fields and defaults | ... | ... | ... | ... |
| Metrics and heartbeat | ... | ... | ... | ... |
| Server-pushed commands | ... | ... | ... | ... |
| Lifecycle and handoff | ... | ... | ... | ... |
| Failure isolation and privacy | ... | ... | ... | ... |

Use the `extract_telemetry.py` capability map as the minimum checklist, then
trace every claimed capability to pinned source. Report an explicit
`**Missing**`/unavailable row for SDKs without a client-side implementation;
do not omit telemetry merely because it is not in the baseline facade.

## Client Session Comparison

| Aspect | Baseline | Audited side | Direction | Status |
|---|---|---|---|---|
| Availability / session type | ... | ... | ... | ... |
| Factory and cluster-ID validation | ... | ... | ... | ... |
| DQL method surface | ... | ... | ... | ... |
| DML/admin exclusion | ... | ... | ... | ... |
| Cluster-ID injection/override | ... | ... | ... | ... |
| Parent client sharing | ... | ... | ... | ... |
| Close/clone/iterator lifecycle | ... | ... | ... | ... |

Use the `extract_session.py` capability map as the minimum checklist, then
trace every claimed capability to pinned source. Report an explicit
`**Missing**`/unavailable row for SDKs without a client-session
implementation; do not omit the section merely because session is absent from
the baseline facade. The factory itself is lifecycle/config API; the comparison
must cover the returned session object and routing semantics.

## Internal Mechanisms Comparison

| Mechanism | Aspect | Baseline | Audited side | Direction | Status |
|---|---|---|---|---|---|
| CollectionTsCache | ... | ... | ... | ... | ... |
| SchemaCache | ... | ... | ... | ... | ... |
| Retry | ... | ... | ... | ... | ... |
| Client telemetry | ... | ... | ... | ... | ... |
| Client session | ... | ... | ... | ... | ... |

One row per mechanism/aspect divergence found in Step 7, in both directions.
Every row must name the specific aspect and the observed behavior on each side.
Covered aspects (see `references/sdk-map.md`):

- CollectionTsCache: process-wide singleton presence, (endpoint, db,
  collection) key granularity, monotonic ts update (older ts never overwrites a
  newer one), write path (DML responses feed the cache) and read path
  (`guarantee_timestamp` built for `ConsistencyLevel.Session` and the
  default-consistency path), invalidation on drop/rename/alias-drop,
  move/copy on rename and create-alias, capacity/eviction/clear, and the
  empty-cache fallback value.
- SchemaCache: singleton presence, cache-hit fast path that skips the
  `DescribeCollection` RPC, loader coalescing of concurrent cache-miss loads
  (java/cpp/rust/csharp load-scope coalescing vs pymilvus plain get/set),
  invalidation
  coverage across every schema-mutating API (drop/alter/rename/create-index/
  insert-schema-mismatch) on sync and async paths, `force_update` refresh,
  capacity/LRU eviction, thread-safety.
- Retry: default policy (max attempts, initial/max backoff, multiplier, overall
  timeout), RateLimit retry gate in both legacy (49/RateLimit) and current (8)
  encodings and its default on/off, gRPC no-retry code set, idempotency-aware
  retry (rust `RetrySemantics`), schema-mismatch single retry with cache
  invalidation, per-client configurability (`withRetry`, `SetRetryParam`,
  `set_retry_param`, csharp `RetryConfig`, per-call
  `retry_times`/`retry_on_rate_limit`), and retry
  application breadth (uniform across DML/DQL/admin vs selective).
- Client telemetry: default enablement/config, metrics and heartbeat,
  server-pushed commands, lifecycle handoff, shutdown, and failure isolation;
  use the Client Telemetry Comparison table for the detailed rows.
- Client session: factory availability, empty `cluster_id` validation, returned
  session type, DQL-only surface, cluster-ID accessor/injection/override,
  parent-client sharing, and close/clone/iterator lifecycle; use the Client
  Session Comparison table for the detailed rows.

Not gaps: singleton-vs-per-client scoping and cache-key normalization (empty db
-> "default", endpoint normalization). Rows here reconcile with the `Partial`
rows in the API Comparison table.

## Data Type Comparison (only when neither SDK is pymilvus)

| <SDK1 DataType> | <SDK2 DataType> | Code | Status | Notes |
|---|---|---|---|---|

Compare by public name; numeric codes may differ. Mark values present on the
baseline but missing on the audited side as `**Missing**`.

## Index Type Comparison (only when neither SDK is pymilvus)

| <SDK1 IndexType> | <SDK2 IndexType> | Status |
|---|---|---|

## Response audit (optional)

Bullets for output surfaces still missing on the audited side (response class
members absent, dict keys absent).

## Behavioral / intentional differences (optional)

Bullets describing deliberate differences (iterator semantics, error-wrapping
shape, default-consistency default values) that do not count as gaps. Validation
existence/absence, default/coercion behavior, RPC-issuance short-circuit
mismatches, and internal-mechanism
divergences are NOT covered here; they are counted under Input Validation
Comparison, Wire-expressiveness audit, and Internal Mechanisms Comparison
respectively.

## Reproducibility

The exact pinned `extract_surface.py`, `map_surface.py`, and
`extract_behavior.py` commands; surface/behavior SHA-256 values; commit hashes;
and a note to re-audit each baseline method's parameters and defaults against
the audited SDK's request class, its output against the audited SDK's response
class/accessors, and its client-side input validation against the audited SDK's
request builder/facade checks. For the wire-expressiveness audit,
record the `resolve_proto.py` command and resulting anchor (submodule gitlink,
C++ `PROTO_COMMIT`, or pymilvus generated descriptors) and commit; note that
pymilvus vendors no `.proto` files. Record both `extract_telemetry.py`
commands/digests, the `compare_telemetry.py` command/digest, and the pinned
source files read per SDK for
CollectionTsCache, SchemaCache, Retry, client telemetry, and client session
(from `references/sdk-map.md`), plus both `extract_session.py`
commands/digests and the `compare_session.py` command/digest, so the mechanism
rows can be re-verified at the same commits.

## Update policy

One line: keep the Summary counts, API table, and Main-gap bullets aligned
whenever the pinned branches change.
```

## Consistency rules

- The Summary counts MUST equal the number of table rows that are not marked
  Ignored/excluded, and MUST reconcile with the Main gaps section.
- Record both repos' branch and commit hash in `Source files compared` and in
  `Reproducibility`.
- Every `Partial` row must name the specific missing parameter or output field.
- Every default/coercion gap must name the baseline and audited resolved
  values, including units where applicable.
- Telemetry gaps must name direction and whether the feature is entirely
  unavailable or present with reduced capability.
- Do not leave `TODO` placeholders in the exported report; unresolved rows must
  carry the `Partial` status with the observed gap described, or be resolved
  before export.
