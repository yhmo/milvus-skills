# Source Layout

Use this reference to locate the RESTful API service code inside the `milvus-io/milvus` repository (`master`).

## Package root

Base path: `internal/distributed/proxy/httpserver/`

```text
constant.go                    route/action constants, HTTP headers, response-key constants, default names
handler.go                     Handlers (system/metrics-port API, /health, /dummy) + wrapHandler
handler_v1.go                  HandlersV1: legacy /v1/vector/* endpoints
handler_v2.go                  HandlersV2: /v2/vectordb/* endpoints, middlewares, wrapperPost, routeToMethod
request.go                     v1 request structs (and shared query-safe types FloatVectorQuery, ...)
request_v2.go                  v2 request structs; DBNameGetter/CollectionNameGetter implementations
wrap_request.go                protobuf-shaped wrapped requests for Handlers (WrappedCreateCollectionRequest, ...)
wrapper.go                     wrapHandler, shouldBind, badRequestf, ErrResponse
timeout_middleware.go          Timeout middleware + timeoutResponseRecorder
json_render.go                 custom jsonRender for large responses
utils.go                       JSON<->protobuf conversion, response envelope senders, vector/field serialization
resource_group_handler_v2.go   v2 resource-group endpoints
file_resource_handler_v2.go    v2 file-resource endpoints
snapshot_handler_v2.go         v2 snapshot endpoints
*_test.go                      unit tests (mockProxyComponent + httptest + gin engine)
```

## Server bootstrap (outside the package)

```text
internal/distributed/proxy/service.go    startHTTPServer (main HTTP server: /v1 + /v2/vectordb),
                                         registerHTTPServer (metrics port: /api/v1), authenticate middleware
internal/proxy/impl.go                   Proxy.RegisterRestRouter: cluster/system endpoints on /api/v1
internal/http/                           shared HTTP helpers (headers, rbac.go, server.go, webui/, healthz/)
pkg/util/paramtable/http_param.go        proxy.http.* configuration items
pkg/metrics/proxy_metrics.go             restful_api_* metrics
pkg/metrics/restful_middleware.go        WrapRestfulContext / RecordRestfulMetrics
pkg/metrics/proxy.go                     ProxyFunctionCall metric
```

## Constants (constant.go)

- v2 categories: `DataBaseCategory`, `CollectionCategory`, `EntityCategory`, `PartitionCategory`, `UserCategory`,
  `RoleCategory`, `IndexCategory`, `AliasCategory`, `ImportJobCategory`, `SnapshotJobCategory`, `SnapshotCategory`,
  `ExternalCollectionJobCategory`, `PrivilegeGroupCategory`, `CollectionFieldCategory`, `CollectionStructFieldCategory`,
  `ResourceGroupCategory`, `FileResourceCategory`, `SegmentCategory`, `QuotaCenterCategory`, `CommonCategory`.
- v2 actions: `ListAction`, `HasAction`, `DescribeAction`, `CreateAction`, `DropAction`, `StatsAction`, `LoadStateAction`,
  `RenameAction`, `LoadAction`, `RefreshLoadAction`, `ReleaseAction`, `QueryAction`, `GetAction`, `DeleteAction`,
  `InsertAction`, `UpsertAction`, `SearchAction`, `AdvancedSearchAction`, `HybridSearchAction`, RBAC/privilege actions,
  `AlterAction`/`AlterPropertiesAction`/`DropPropertiesAction`, function actions, `CompactAction`, `FlushAction`,
  `TruncateAction`, import/snapshot/external-collection actions, `TransferReplicaAction`, `RunAnalyzerAction`, `CommitAction`,
  `AbortAction`.
- v1 paths: `VectorCollectionsPath` etc. (`/vector/collections`, `/vector/insert`, `/vector/search`, ...).
- Headers/response keys: `HTTPHeaderAllowInt64`, `HTTPHeaderDBName`, `HTTPHeaderIdempotencyKey`, `HTTPHeaderRequestTimeout`,
  `HTTPHeaderMilvusTraceID`, `HTTPReturnCode`, `HTTPReturnMessage`, `HTTPReturnData`, `HTTPReturnCost`, `HTTPReturnRecalls`,
  `HTTPReturnTopks`, `HTTPReturnLoadState`, etc. Defaults: `DefaultDbName`, `DefaultIndexName`, `DefaultOutputFields`,
  `DefaultPrimaryFieldName`, `DefaultVectorFieldName`, `DefaultMetricType`.

## Registering a new v2 endpoint (checklist)

1. `constant.go`: add the `Category` + `Action` constants (or reuse existing ones).
2. `handler_v2.go` `RegisterRoutesToV2`: add the `router.POST(Category+Action, ...)` line with the right middleware chain
   and a default-valued request factory.
3. `request_v2.go`: add the request struct implementing `GetDbName()` and (if a collection is involved) `GetCollectionName()`.
4. `handler_v2.go`: add the handler func with signature `func (h *HandlersV2) xxx(ctx context.Context, c *gin.Context, req any, dbName string) (interface{}, error)`.
5. `handler_v2.go` `routeToMethod`: map the full path to the underlying gRPC method name for metrics/logging.
6. Tests: extend `handler_v2_test.go` (or a domain-specific `*_v2_test.go`).

## Tracing an endpoint

1. Route string: `handler_v2.go` registration line (search the `Action` constant or the full path like `/entities/search`).
2. Request type: the `newReq` factory at the registration line.
3. Handler + RPC: the handler body ends with `h.proxy.<Method>(ctx, req)`; `<Method>` is the `types.ProxyComponent` gRPC method.
4. Result conversion: helpers called inside the handler (mostly `utils.go`), then the envelope keys returned.
5. Tests: `handler_v2_test.go` / `utils_test.go` for the endpoint and its conversion.
