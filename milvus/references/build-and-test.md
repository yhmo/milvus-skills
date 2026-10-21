# Build, test, lint, and generation

Confirm commands against the current `Makefile`, scripts, module files, and applicable `AGENTS.md` before running them.

## Go tests

Milvus server Go tests require both build tags and disabled optimization/inlining for mockey-based patching:

```bash
go test -tags dynamic,test -gcflags="all=-N -l" -count=1 ./internal/proxy/... -run TestName
go test -tags dynamic,test -gcflags="all=-N -l" -count=1 ./internal/querycoordv2/...
```

Run focused packages/tests first. Then use component shortcuts when appropriate:

```bash
make test-proxy
make test-querycoord
make test-querynode
make test-datacoord
make test-datanode
make test-streaming
make test-mixcoord
make test-pkg
```

`make test-go` builds the C++ unittest prerequisites and runs the broad Go suite; it is materially more expensive than a focused package test.

For the separate modules:

```bash
cd pkg && go test -tags dynamic,test -gcflags="all=-N -l" -count=1 ./path/to/package/...
cd client && go test -count=1 ./path/to/package/...
```

The monorepo carries more than the root module. Besides `pkg/` and `client/` (module major version is branch-dependent — `client/v3` on master/3.0, `client/v2` on 2.6; confirm from `go.mod`), there are standalone modules at `tests/go_client/` (client-facing e2e, run from `tests/go_client` with `go test ./testcases/...` against a running Milvus) and `examples/telemetry_demo/`, `examples/telemetry_e2e_test/`. Confirm module ownership from the nearest `go.mod` and run tests from that directory; do not apply root-module package patterns while standing in another module.

## Formatting and static checks

```bash
make fmt
make static-check
make verifiers
```

Use the smallest relevant formatter/linter during iteration. `make verifiers` includes native and Rust checks plus formatting/static analysis and can require a built native tree.

## C++ and Rust

```bash
make build-cpp
make test-cpp
make run-test-cpp filter='SuiteOrTestPattern'
make rustfmt
make rustcheck
```

For a targeted native change, inspect `internal/core/CMakeLists.txt`, the nearest subdirectory CMake file, and existing test targets before selecting a command. Preserve cgo runtime library paths established by `scripts/setenv.sh` or the Make targets.

## Integration and local services

```bash
make integration-test
scripts/start_standalone.sh
scripts/start_cluster.sh
scripts/standalone_embed.sh
scripts/stop_graceful.sh
```

Integration tests and local deployments can start containers, consume significant resources, or mutate local data. Run them only when authorized and relevant. Prefer bounded, targeted suites or fault injection for behavioral verification.

## Generated artifacts

```bash
make generated-proto-without-cpp
make generate-mockery-proxy
make generate-mockery-querycoord
make generate-mockery-querynode
make generate-mockery-datacoord
make generate-mockery-datanode
make generate-mockery-pkg
```

Select the exact target from the current `Makefile`. Review generator diffs for unrelated churn and never repair generated output manually.

## Verification selection

| Change | Minimum evidence |
|---|---|
| Pure explanation | Source/doc trace; no test required unless validating ambiguity. |
| Local Go logic | Focused test with required tags/gcflags; relevant formatter. |
| Component contract | Focused tests on producer and consumer; component shortcut or broader suite. |
| Error/wire mapping | Focused tests, merr guard/projection tests, whole-repo origin audit; full `make test-go` when required by checkout guidance. |
| Streaming ordering/recovery | Relevant streaming docs and packages, failure/replay trace, focused streaming tests, then `make test-streaming`. |
| C++/cgo behavior | Native unit test plus Go boundary test; audit all native construction/rewrite sites. |
| Generated contract | Regenerate, test all consuming modules, and run repository guards. |
| Cross-component design | All subsystem docs, producer/consumer tests, failure-mode verification, and the broadest practical verifier suite. |
