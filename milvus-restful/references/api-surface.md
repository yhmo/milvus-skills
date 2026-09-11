# API Surface and Wire Contract

Catalog of the RESTful endpoints and their wire behavior, verified against `constant.go`, `handler_v2.go`
(`RegisterRoutesToV2` and `routeToMethod`), `handler_v1.go`, and `handler.go`. Documentation mirror:
https://milvus.io/api-reference/restful/v3.0.x/ (v2) and v2.6.x/v2.5.x for maintenance branches.

## Base URLs

- v2 (recommended): `http://<host>:<port>/v2/vectordb/<category>/<action>` — every endpoint is `POST`, JSON body.
- v1 (legacy, deprecating): `http://<host>:<port>/v1/vector/<operation>` — GET/POST mix, query params or JSON body.
- System/metrics port: `http://<host>:<metrics-port>/api/v1/...` (`/health`, `/dummy`, `/metrics`, cluster endpoints).

## Authentication

- `Authorization: Bearer <user>:<password>` (e.g. `root:milvus`) when `CommonCfg.AuthorizationEnabled` is on.
  Invalid/missing credentials -> HTTP 401 with `merr.ErrNeedAuthenticate`.
- Database selection: `dbName` in body, else `DB-Name` header, else `"default"`.

## Headers

- `Request-Timeout: <seconds>` overrides `proxy.http.requestTimeoutMs` (default 30000 ms); expiry -> HTTP 408
  `{code: merr.TimeoutCode, message: "request timeout"}`.
- `Accept-Type-Allow-Int64` drives int64 rendering; `Idempotency-Key` for idempotent retries (DML); `X-Milvus-Trace-Id`
  returned for trace correlation; `Retry-After: 1` on DQL-admission 429.

## v2 endpoints by category

Collections (`/collections/`): `list`, `has`, `describe`, `get_stats`, `get_load_state`, `create`, `drop`, `truncate`,
`rename`, `load`, `refresh_load`, `release`, `alter_properties`, `drop_properties`, `add_function`, `alter_function`,
`drop_function`, `add_function_field`, `drop_function_field`, `compact`, `get_compaction_state`, `flush`.
Fields: `/collections/fields/alter_properties`, `/collections/fields/add`, `/collections/fields/drop`,
`/collections/struct_fields/add`.

Databases (`/databases/`): `create`, `drop`, `drop_properties`, `list`, `describe`, `alter`, `alter_properties`.

Entities (`/entities/`): `query`, `get`, `delete`, `insert`, `upsert`, `search`, `advanced_search`, `hybrid_search`.
DQL admission (HTTP 429 when the proxy DQL queue is full) and restful-size accounting apply to `query`/`get`/`search`/
`advanced_search`/`hybrid_search`; restful-size (inbound only) applies to `insert`/`upsert`/`delete`.

Partitions (`/partitions/`): `list`, `has`, `get_stats`, `create`, `drop`, `load`, `release`.

Users (`/users/`): `list`, `describe`, `create`, `update_password`, `drop`, `grant_role`, `revoke_role`.
Roles (`/roles/`): `list`, `describe`, `create`, `alter`, `drop`, `grant_privilege`, `revoke_privilege`,
`grant_privilege_v2`, `revoke_privilege_v2`.
Privilege groups (`/privilege_groups/`): `create`, `drop`, `list`, `add_privileges_to_group`, `remove_privileges_from_group`.

Indexes (`/indexes/`): `list`, `describe`, `create`, `drop`, `alter_properties`, `drop_properties`.
Aliases (`/aliases/`): `list`, `describe`, `create`, `drop`, `alter`.

Jobs (`/jobs/import/`): `list`, `create`, `get_progress`, `describe`, `commit`, `abort`.
Jobs (`/jobs/snapshot/`): `restore_external`, `export`, `export/describe`, `describe`, `list`.
Jobs (`/jobs/external_collection/`): `refresh`, `describe`, `list`.

Snapshots (`/snapshots/`): `create`, `drop`, `list`, `describe`, `restore`, `pin`, `unpin`.

Resource groups (`/resource_groups/`): `create`, `drop`, `alter`, `describe`, `list`, `transfer_replica`.
File resources (`/file_resources/`): `add`, `remove`, `list`.
Others: `/segments/describe`, `/quotacenter/describe`, `/common/run_analyzer`.

`routeToMethod` (`handler_v2.go:124`) maps every full path to the underlying gRPC method name used for
`metrics.ProxyFunctionCall` and error-type logging; keep it in sync when routes change.

## v1 endpoints

`/v1/vector/collections` (GET list), `/v1/vector/collections/create` (POST), `/v1/vector/collections/describe` (GET),
`/v1/vector/collections/drop` (POST), `/v1/vector/insert` (POST), `/v1/vector/upsert` (POST), `/v1/vector/delete`
(POST), `/v1/vector/search` (POST), `/v1/vector/query` (POST), `/v1/vector/get` (POST). Deprecating; do not extend.

## System/metrics-port endpoints (`Handlers` + `RegisterRestRouter`)

`GET /health`, `POST /dummy`, collection/partition/alias/index CRUD and describe, load/release, `GET /metrics`,
`POST /load-balance`, compaction, import, credential management (`/credential*`), and the cluster/system endpoints
(`/cluster/info`, `/cluster/configs`, `/cluster/clients`, `/cluster/dependencies`, `/slow_query`, forwarded
coordinator metrics, database/collection/partition describe). These are diagnostics; the v2 surface is the user contract.

## Response envelope

```json
{ "code": 0, "message": "Success", "data": <result>, "cost": "<ms>", ... }
```

- `code` uses `merr` codes; `0` on success. `message` carries the merr message. `cost` appears on data-plane calls.
- Search responses add `recalls`, `topks` (and `aggTopks` for aggregation). `get_load_state` adds `loadState`/
  `loadProgress`. Insert/upsert return `insertCount`/`insertIds` or `upsertCount`/`upsertIds`. Delete returns
  `deleteCount`.
- HTTP status is 200 for almost all business outcomes (errors ride in `code`); non-200 statuses are reserved:
  400 bad body (`Handlers` path), 401 unauthenticated, 408 request timeout, 429 DQL admission, 500 internal panic/wrap.

## Rendering switches (`proxy.http.*`)

- `acceptTypeAllowInt64` (default true): when off, int64 values render as strings anywhere (including inside arrays).
- `nativeJSONResponse` (default true): JSON fields render as native documents; when off, as escaped strings.
- `legacyArrayResponse` (default false): Array fields render wrapped in the protobuf `ScalarField` shape when on.
- `compatibilityMode` (default false): restores pre-REST-validation lenient insert value handling (escape hatch only).
- `maxExprParamsDepth` (default 100): bounds expression-template recursion; requests beyond are rejected.

## Breaking-change notes

- v2 request structs use `binding:"required"` where fields are mandatory; a missing field returns
  `ErrMissingRequiredParameters`. An empty/`nil` body returns `ErrIncorrectParameterFormat`.
- A null in a search vector, an id list, or a base64 vector is rejected (`FloatVectorQuery`/`Int64ListQuery`/
  `Base64VectorQuery`), never silently treated as 0/empty.
- Get/delete by id builds `` pk in {__pk_ids} `` with the ids as a `TemplateValue`; never interpolate caller ids into
  expression text.
