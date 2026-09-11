# Birdwatcher Build and Test

Build, run, lint, and test the birdwatcher repo.

## Environment

- Go toolchain per `go.mod` (`go 1.26.4`). The default build is CGO-free; only the Kafka (`WKAFKA`) and Lance (`LANCE`) variants need CGO.
- The repo has `replace`/`exclude` directives in `go.mod`, so `go install github.com/milvus-io/birdwatcher` alone may mis-resolve; build from a clone instead (see README).

## Build

```shell
# default binary (no Kafka/Lance), CGO disabled
make birdwatcher                      # -> bin/birdwatcher

# with Kafka support (CGO + librdkafka, build tag WKAFKA)
make birdwatcher_wkafka

# with Lance segment support (CGO; requires milvus-storage installed)
make birdwatcher_lance                # needs MILVUS_STORAGE_PKG_CONFIG_PATH

# plain build / vet without make
CGO_ENABLED=0 go build -o bin/birdwatcher cmd/birdwatcher/main.go
go build ./...
go vet ./...
```

The Dockerfile (`golang:1.24-bookworm`) builds a Kafka-enabled binary and ships it on `debian:bookworm-slim` with `librdkafka1`.

## Run

```shell
./bin/birdwatcher                     # interactive prompt
./bin/birdwatcher -simple             # no suggestion/history UI
./bin/birdwatcher -olc "connect --etcd=127.0.0.1:2379 --rootPath=by-dev,show collections"
./bin/birdwatcher -rest -port 8002    # web server exposing show * endpoints
./bin/birdwatcher -version
```

The interactive mode appends a debug log to `bw_debug.log` and writes an audit log (`audit_<ts>.log`) for every command once connected to an instance. `.bw_config/birdwatcher.yaml` is created on first run.

## Lint and format

Makefile targets install pinned tools into `./bin`:

```shell
make getdeps        # installs golangci-lint v2.11.4 into ./bin
make static-check   # golangci-lint run --timeout=10m --config ./.golangci.yml ./...
make lint-fix       # gofumpt + gci (import grouping: stdlib, default, prefix(github.com/milvus-io)) + golangci-lint --fix
```

CI runs golangci-lint `v2.11.4` on Go 1.25 (`.github/workflows/golangci-lint.yml`). `.golangci.yml` config lives at the repo root.

## Tests

```shell
# unit tests
go test ./...

# focused package
go test ./states/... -run TestCollection
```

`framework/` has unit tests for the command parsing (`framework/command_test.go`); `states/` has tests for etcd connect, extensions, and individual commands; `storage/`, `wal/`, `internal/ops/gen` carry their own tests.

## E2E

`tests/e2e/commands/test_*.sh` exercise the CLI against a connected instance using `-olc` scripts (e.g. `test_show.sh` runs every `show` command with `--format json`; `test_remove.sh`, `test_repair.sh`, `test_reset.sh` cover the destructive groups). They assume a live Milvus/etcd environment — do not run without one unless asked.
