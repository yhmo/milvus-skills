# RESTful Service Technical Details

Reference for the Milvus RESTful (high-level) API service in `internal/distributed/proxy/httpserver/` of the
`milvus-io/milvus` repository.

## Where the server runs

The RESTful service is an HTTP server hosted inside the Proxy component.

- `internal/distributed/proxy/service.go`:
  - `startHTTPServer` builds the main gin router (h2c/HTTP2-capable, port `proxy.http.port`, default shared with the
    gRPC port). The full middleware chain is applied first:
    `MetricsHandlerFunc` -> `TraceIDHandlerFunc` -> `accesslog.AccessLogMiddleware` -> `LoggerHandlerFunc` +
    `gin.Recovery` -> `RequestHandlerFunc` -> `IdempotencyKeyHandlerFunc` -> `ContextUsername` setter -> optional
    `authenticate` (when `CommonCfg.AuthorizationEnabled`). Then it registers `NewHandlersV1(...).RegisterRoutesToV1(app)`
    under the `/v1` group and `NewHandlersV2(...).RegisterRoutesToV2(appV2)` under the `/v2/vectordb` group
    (`service.go:225-228`).
  - `registerHTTPServer` serves the metrics port (group prefix `apiPathPrefix = "/api/v1"`). It registers
    `NewHandlers(...).RegisterRoutesTo(apiv1)` (the `Handlers` struct in `handler.go`) and then
    `Proxy.RegisterRestRouter(apiv1)` (`internal/proxy/impl.go:6593`) for system/cluster endpoints (cluster info,
    configs, clients, dependencies, slow query, forwarded coordinator metrics, database/collection/partition describe
    endpoints, and the `/health` + `/dummy` routes).
- Auth is `Authorization: Bearer <user:password>`; `authenticate` in `service.go` rejects with HTTP 401 and
  `merr.ErrNeedAuthenticate` when authorization is enabled. `GetAuthorization`/`ParseUsernamePassword` in `utils.go`
  parse the header.

## Three handler types

| Type | File | Prefix | Purpose | Response wrapper |
|---|---|---|---|---|
| `Handlers` | `handler.go` | `/api/v1` (metrics port) | system + low-level ops, `/health`, `/dummy` | `wrapHandler` |
| `HandlersV1` | `handler_v1.go` | `/v1/vector/*` | legacy collection & vector ops (deprecating) | `executeRestRequestInterceptor` + `HTTPReturn` |
| `HandlersV2` | `handler_v2.go` | `/v2/vectordb/*` | recommended high-level API, all endpoints | `wrapperPost` + `HTTPReturn` |

All three wrap `types.ProxyComponent` (concrete `*proxy.Proxy`) and forward to the same gRPC methods the SDKs call.

- `Handlers` (`handler.go`) handlers parse a request, call `h.proxy.<Rpc>(c, req)`, and return `(interface{}, error)`.
  `wrapHandler` maps `errBadRequest` to HTTP 400 and everything else to HTTP 500, negotiating JSON/YAML. It supports
  protobuf-ish request shapes via `WrappedCreateCollectionRequest`/`WrappedInsertRequest` (`wrap_request.go`).
- `HandlersV2` holds, besides `proxy`, a lazy `metaCache` resolver (`getProxyMetaCache`) and a `dqlQueueFull` probe.
  `NewHandlersV2` asserts `var _ interface{ IsDQLQueueFull() bool } = (*proxy.Proxy)(nil)` so a rename of the probe fails
  the build instead of silently disabling admission.

## v2 request flow (the contract-critical path)

1. **Registration** (`RegisterRoutesToV2`, `handler_v2.go:254`): each route is `router.POST(Category+Action, <chain>)`
   where the chain is one of:
   - `dqlAdmission(restfulSizeMiddleware(timeoutMiddleware(wrapperPost(factory, wrapperTraceLog(handler))), observe))`
     for the five DQL routes (query/get/search/advanced_search/hybrid_search),
   - `restfulSizeMiddleware(timeoutMiddleware(wrapperPost(...)), false)` for insert/upsert/delete,
   - `timeoutMiddleware(wrapperPost(...))` for everything else.
   The request factory supplies a default-valued instance (e.g. `QueryReqV2{Limit: 100, OutputFields: ["*"]}`,
   `SearchReqV2{Limit: 100}`), so the handler can distinguish "absent" from defaults.

2. **`dqlAdmission`** (`handler_v2.go:94`): when `HTTPCfg.DQLAdmissionEnabled` and `h.dqlQueueFull()` are true, aborts
   before decoding with HTTP 429 + `merr.WrapErrTooManyRequests` and a `Retry-After: 1` header (exposed via
   `Access-Control-Expose-Headers` for browsers). It records `metrics.ProxyFunctionCall` itself because it aborts before
   `wrapperPost`'s metric site runs.

3. **`restfulSizeMiddleware`** (`handler_v2.go:533`): wraps the context with `metrics.WrapRestfulContext` carrying
   `ContentLength`, and after the handler runs records in/outbound payload sizes via
   `metrics.RecordRestfulMetrics` (`pkg/metrics/restful_middleware.go`). `observeOutbound` is true only for DQL.

4. **`timeoutMiddleware`** (`timeout_middleware.go:235`): applies `HTTPCfg.RequestTimeoutMs` (or a `Request-Timeout`
   header, seconds), runs the handler in a goroutine against a buffered `timeoutResponseRecorder`, and on expiry writes
   HTTP 408 with `{code: merr.TimeoutCode, message: "request timeout"}`. `timeoutContextKeysToPropagate` carries
   `code`/`message`/`request`/`response`/`traceID` from the child context back to the caller.

5. **`wrapperPost`** (`handler_v2.go:437`):
   - Creates `req := newReq()`, `gCtx.ShouldBindBodyWith(req, binding.JSON)`.
   - Binding/validation failures: validator `ValidationErrors` -> `merr.ErrMissingRequiredParameters`; `io.EOF` ->
     `ErrIncorrectParameterFormat` ("request body should be nil, however {} is valid"); other parse errors ->
     `ErrIncorrectParameterFormat`.
   - Resolves `dbName`: `req.(requestutil.DBNameGetter).GetDbName()` -> `DB-Name` header -> `DefaultDbName` ("default").
     Collection name via `requestutil.CollectionNameGetter`. Every v2 request type implements these interfaces
     (`request_v2.go`), so the handler can rely on them.
   - Builds `ctx = proxy.NewContextWithMetadata(ctx, username, dbName)`.
   - Calls the handler `v2(ctx, gCtx, req, dbName)`.
   - Records `metrics.ProxyFunctionCall` twice (total + result) using `routeToMethod[gCtx.FullPath()]`
     (`handler_v2.go:124`) and `requestutil.ParseMetricLabel(resp, err)`.
   - Logs failed requests by `error_type` (input errors at Info, system errors at Warn).

6. **Handler**: builds the `milvuspb` request, calls `h.proxy.<Rpc>(ctx, req)`, checks `merr.Error(resp.GetStatus())`,
   converts the protobuf result, and ships the envelope.

## Response envelope

Successful and failed v2 responses both use the JSON envelope keys from `constant.go`:

```
{ "code": <merr code, 0 on success>, "message": "...", "data": <result>, "cost": <ms>, ... }
```

Extra top-level keys include `recalls`/`topks`/`aggTopks` (search), `loadState`/`loadProgress`, `has`, `rowCount`,
`insertCount`/`insertIds`, `upsertCount`/`upsertIds`, `deleteCount`, `compactionID`. Senders:

- `HTTPReturn(c, httpStatus, gin.H{...})` (`utils.go:66`) — sets `code`/`message` gin keys, sets the trace-ID header,
  writes JSON.
- `HTTPAbortReturn` (`utils.go:86`) — same but aborts (used by early rejects like DQL admission).
- `HTTPReturnStream` (`utils.go:77`) — same but renders via the custom `jsonRender` (`json_render.go`) for large bodies;
  still buffered when wrapped in `timeoutMiddleware`.
- Errors: `merr.Code(err)` -> `code`, `err.Error()` -> `message`. HTTP status stays 200 for the vast majority of
  REST-mapped errors; HTTP 400/408/429/401/500 are reserved for transport-level conditions (see `api-surface.md`).

## Result conversion (`utils.go`)

`utils.go` (~5,600 lines) holds the JSON<->protobuf conversion:

- `parseSearchResult`/`handleSearchResult`-style helpers turn `schemapb.FieldData` rows into `[]interface{}` rows for
  query/get/search results, honoring wildcard `*`, dynamic `$meta`, struct arrays, and nulls.
- Rendering switches, driven by `proxy.http.*` params: int64 as string when `AcceptTypeAllowInt64` is off
  (`formatInt64`), JSON fields as native documents when `NativeJSONResponse` on, Array fields as native arrays unless
  `LegacyArrayResponse` on, and lenient insert value handling when `CompatibilityMode` on (pre-REST-validation releases).
- Vector serialization: `vector2Bytes`/`binaryVector2Bytes`/`serializeFloatVectors`/`serializeInt8Vectors`, sparse
  vectors, placeholders. `FloatVectorQuery`/`Int64ListQuery`/`Base64VectorQuery` (`request.go`) refuse null elements via
  custom `UnmarshalJSON` so a null can never silently become 0.
- Expression templates: `exprParams`/`TemplateValue` conversion, bounded by `HTTPCfg.MaxExprParamsDepth`. The get/delete
  id path uses `checkGetPrimaryKey` with `primaryKeyTemplateVar = "__pk_ids"` so ids travel as a template value instead
  of being interpolated into expression text (historically a quote-injection bug).
- Field-schema/collection-schema conversion for create/describe, index params (`indexparamcheck`), functions, external
  collections (`externalspec`), RBAC, resource groups, snapshots, file resources.

## Configuration (`pkg/util/paramtable/http_param.go`)

`proxy.http.*` items: `enabled`, `debug_mode`, `port`, `acceptTypeAllowInt64` (refreshable), `compatibilityMode`
(refreshable), `maxExprParamsDepth` (refreshable, clamp 1..1024), `nativeJSONResponse` (refreshable), `legacyArrayResponse`
(refreshable), `requestTimeoutMs` (refreshable), `dqlAdmissionEnabled` (refreshable), server timeouts
(`readHeaderTimeout`, `readTimeout`, `writeTimeout`, `idleTimeout`, `maxHeaderBytes`), HSTS (`enableHSTS`,
`hstsMaxAge`, `hstsIncludeSubDomains`), `enablePprof`, `enableWebUI`.

## Metrics

- `pkg/metrics/proxy_metrics.go`: `restful_api_req_count`, `restful_api_req_latency`, `restful_api_receive_bytes_count`,
  `restful_api_send_bytes_count` (labeled by method + HTTP status).
- `metrics.ProxyFunctionCall` (milvus_proxy_go_function_call) recorded per-route in `wrapperPost` and `dqlAdmission`
  with the gRPC method name from `routeToMethod`, plus db/collection labels.
- `pkg/metrics/restful_middleware.go`: `WrapRestfulContext`/`RecordRestfulMetrics` feed `ProxyReceiveBytes` and
  `ProxyReadReqSendBytes` from the `restfulSizeMiddleware`.

## Logging

- The `mlog` package only, with a real `ctx` (from the request context). `wrapperTraceLog` (`handler_v2.go:660`)
  redacts sensitive fields per request type (`getTraceLogRequestFieldWithoutSensitiveInfo`): passwords -> username only,
  external specs -> `externalspec.Redact*`, exprParams -> placeholder names with values replaced by `proxy.RedactedValue`.
- Access logs via `internal/proxy/accesslog` middleware; trace-ID propagation via `TraceIDHandlerFunc` and the
  `X-Milvus-Trace-Id` header.

## Tests

- Unit tests build a gin engine with a `mockProxyComponent` (embed `types.ProxyComponent`, stub the exercised RPCs) and
  drive it with `httptest`; see `handler_test.go`, `handler_v1_test.go`, `handler_v2_test.go`, `utils_test.go`,
  `resource_group_handler_v2_test.go`, `file_resource_handler_v2_test.go`, `snapshot_handler_v2_test.go`,
  `handler_v2_admission_test.go`.
- Tests need the Milvus mandatory Go flags: `-tags dynamic,test -gcflags="all=-N -l"`.
- E2E for the RESTful surface lives in the repo's e2e suites and needs a running Milvus; do not run without one.

## Typical routing examples

- v2 search: `POST /v2/vectordb/entities/search` -> `dqlAdmission` -> `restfulSizeMiddleware` -> `timeoutMiddleware` ->
  `wrapperPost(SearchReqV2{Limit:100}, h.search)` -> `h.search` builds `milvuspb.SearchRequest` (incl. placeholder
  groups) -> `h.proxy.Search` -> `parseSearchResult` -> `{code, message, data, cost, recalls, topks}`.
- v2 get/delete: `checkGetPrimaryKey` builds `` pk in {__pk_ids} `` with a `TemplateValue`, avoiding expression-string
  injection (`utils.go:193`).
- v1 search: `POST /v1/vector/search` (`VectorSearchPath`) -> `HandlersV1.search` -> `executeRestRequestInterceptor`
  -> `HTTPReturn`.
- System metrics: `GET /api/v1/metrics` (metrics port) -> `Handlers.handleGetMetrics` -> `Proxy.GetMetrics`.
