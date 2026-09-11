# Go SDK Build and Test

Build, test, lint, and CI for the Go SDK module (`client/` inside the milvus repo).

## Environment

- Go 1.24.x per `client/go.mod` (repo CI uses newer toolchains; `client/.golangci.yml` declares `go: "1.25"` for lint).
- The SDK is a self-contained module: it must compile without the server C++ core (`milvus` core is not built for SDK-only work)
  and must not import server `milvus/pkg` or `internal/` packages.

## Build

```bash
cd client
go build ./...
go vet ./...
```

Build is plain `go build`; no CGO/core dependency. `go mod tidy` is safe inside `client/`.

## Unit tests

```bash
cd client
go test -tags dynamic,test -gcflags="all=-N -l" -count=1 ./...
# focused:
go test -tags dynamic,test -gcflags="all=-N -l" -count=1 ./milvusclient/... -run TestSearch
```

Notes:

- The `dynamic,test` build tags and `-gcflags="all=-N -l"` are required so mockey-based monkey patching works and the mock
  server (`mock_milvus_server_test.go`) compiles. Follow the repo-wide rule from AGENTS.md.
- Many tests use `mock_milvus_server_test.go` (a mockery-generated `milvuspb.MilvusServiceServer`) plus `github.com/bytedance/mockey`.
- `client/Makefile` `unittest`/`lint` targets are stubs; use the `go test`/golangci-lint commands directly.

## Lint

```bash
# from client/
golangci-lint run --config .golangci.yml ./...
```

- Config: `client/.golangci.yml` (golangci-lint v2). Enabled linters include `gocritic`, `gosec`, `govet`, `staticcheck`,
  `revive`, `ineffassign`, `misspell`, `whitespace`, `decorder`, `depguard`, `forbidigo`, `durationcheck`, `unconvert`.
- `depguard` forbids stdlib `errors` and `github.com/pkg/errors` (use `github.com/cockroachdb/errors`), `io/ioutil`, tikv rawkv, etc.
- `forbidigo` forbids `time.Tick`, `os.Open`/`os.ReadFile`/`os.WriteFile`, `runtime.NumCPU`/`GOMAXPROCS`, and direct
  `merr.Err*` returns / `.ErrorCode =` assignments (use `merr.Error(status)`).
- gocritic runs `ruleguard` rules from `client/ruleguard/`.
- Formatting: `gofumpt` + `gci` (import grouping: stdlib, third-party, `github.com/milvus-io/...`). Run `gofmt`/`gofumpt -l -w .`
  and `gci write` before submitting.

## Regenerating mocks

The mock file `client/milvusclient/mock_milvus_server_test.go` is generated:

```bash
# from repo root
make generate-mockery-client
# equivalent: cd client && ../bin/mockery --srcpkg=github.com/milvus-io/milvus-proto/go-api/v3/milvuspb --name=MilvusServiceServer --filename=mock_milvus_server_test.go --output=milvusclient --outpkg=milvusclient --with-expecter
```

Never hand-edit this file.

## Proto version bump

The SDK depends on `github.com/milvus-io/milvus-proto/go-api/v3`. To bump it across all modules (main, `client`, `pkg`,
`tests/go_client`) run from the repo root:

```bash
make update-milvus-api PROTO_API_VERSION=v2.3.0-dev.1   # or a commit ID
# backed by scripts/update-api-version.sh
```

This runs `go get -u github.com/milvus-io/milvus-proto/go-api/v3@<ver>` + `go mod tidy` in each module (including `client/`).
After bumping protos, recompile and re-run the SDK tests; new/changed RPCs or schema fields may need option/column updates.

## CI

- `.github/workflows/main.yaml` paths include `client/**`; Go coverage runs `client` via `scripts/run_go_codecov.sh`
  (`for d in cmd/tools internal pkg client`), which runs `go test` with `-tags dynamic,test -gcflags=all=-N -l -race` and
  `-coverpkg=./...`.
- SDK changes are also exercised by the repo's general Go CI (main.yaml) and by e2e in `tests/go_client` (see examples.md).

## E2E (tests/go_client)

The e2e module `tests/go_client` uses a `replace github.com/milvus-io/milvus/client/v3 => ../../client` directive, so a local
SDK change is picked up without publishing. It runs against a running Milvus server (L0/L1/L2 tagged test cases). Do not run
these without a server unless asked.
