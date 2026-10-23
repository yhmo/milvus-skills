# Build and Test

Build, test, lint, and CI context for the RESTful API service in `internal/distributed/proxy/httpserver/`.

## Environment

- Go module: the root `github.com/milvus-io/milvus` module (no CGO/C++ core needed for the Go HTTP layer alone).
- Dependencies: `gin-gonic/gin`, `cockroachdb/errors`, `tidwall/gjson`, `spf13/cast`, `go-playground/validator`,
  `samber/lo`, OpenTelemetry, the `milvus-proto/go-api/v3` module, and internal `milvus/pkg/v3` packages.

## Build

```bash
go build ./internal/distributed/proxy/...
```

## Unit tests

Milvus requires the mandatory Go flags for the httpserver package too (mockey-based monkey patching and `dynamic,test`
tags):

```bash
go test -tags dynamic,test -gcflags="all=-N -l" -count=1 ./internal/distributed/proxy/httpserver/...
# focused single test:
go test -tags dynamic,test -gcflags="all=-N -l" -count=1 ./internal/distributed/proxy/httpserver/... -run TestSearchV2
```

Notes:

- The repo-wide rule from AGENTS.md: `-tags dynamic,test` and `-gcflags="all=-N -l"` are required or tests fail to
  compile / mockey patching fails.
- Tests build a gin engine, register routes (`NewHandlersV2(...).RegisterRoutesToV2(app)`), and drive it with
  `httptest.NewRecorder`; the proxy is a `mockProxyComponent` that embeds `types.ProxyComponent` and stubs only the
  RPCs exercised (`handler_test.go`). A `proxyComponentWithMetaCache` wrapper provides `GetMetaCache()` where handlers
  need the schema cache.
- See per-file suites: `handler_v2_test.go`, `handler_v1_test.go`, `utils_test.go`, `resource_group_handler_v2_test.go`,
  `file_resource_handler_v2_test.go`, `snapshot_handler_v2_test.go`, `handler_v2_admission_test.go`,
  `traceid_test.go`, `wrapper_test.go`, `timeout_middleware` tests.

## Lint

```bash
# from repo root
golangci-lint run ./internal/distributed/proxy/httpserver/...
```

- Import grouping is enforced by gci: stdlib, third-party, then `github.com/milvus-io/...`.
- Use `mlog` for logging (never `log`/`fmt.Println`/direct zap), with a real `ctx`.
- Use `merr` for errors; wrap with `merr.Wrap/Wrapf`, classify by the blame test.

## E2E

- The RESTful surface is exercised by the repo's e2e suites (search/insert/query against a running Milvus). Do not run
  without a server. Start one with `scripts/start_standalone.sh` or `scripts/standalone_embed.sh` if asked.

## Docs cross-check

- The v2 wire contract is documented in the Milvus REST API reference for the matching line (`3.0`/`master` or `2.6`).
  If a change alters a documented request field, response field, or route, update the server code and flag the doc
  parity. Do not assume a concrete release version.
