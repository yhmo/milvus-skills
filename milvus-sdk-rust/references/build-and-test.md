# Build and Test

Use this reference before building, formatting, testing, or debugging the Milvus Rust SDK.

The root `README.md` is user-facing. Keep local setup and validation details in `DEVELOPMENT.md`
and link to it briefly from the README.

## Contents

- Prerequisites
- First-time setup and builds
- V2 validation order
- V1 compatibility checks
- Formatting and linting
- Milvus/Docker setup
- Test layout
- Common troubleshooting

## Prerequisites

- Rust toolchain with `cargo`.
- Initialized `milvus-proto` submodule.
- Python 3.6 or newer and Docker access on Linux for system/integration tests requiring Milvus.

The build uses `protoc-bin-vendored` when `PROTOC` is unset.

`scripts/install_deps.sh` supports apt, dnf, and yum on Linux and Homebrew on macOS. It installs
Rust, formatting/linting components, and platform build dependencies. Coverage tools are
best-effort and may be omitted with `SKIP_COVERAGE_TOOLS=true`, including Linux `lcov`; macOS CI
uses that opt-out because it runs only the non-server path. Linux setup also installs and verifies
Docker after the Rust toolchain is installed; macOS setup does not require Docker.

## First-time setup and builds

```bash
git submodule update --init --recursive
cargo build
cargo check --all-targets
```

Other useful commands:

```bash
cargo build --release
cargo build --examples
cargo test --no-run
./scripts/gen_doc.sh
```

Generated protobuf bindings appear under Cargo `OUT_DIR`; builds should not modify `src/proto` except when `src/proto/mod.rs` is intentionally edited.

`scripts/gen_doc.sh` generates rustdoc into `doc/`, uses a temporary build directory, and removes
the generated public protobuf documentation subtree before copying the result.

## V2 validation order

Use cheap, targeted checks first:

```bash
cargo test --test v2_ut
cargo test --lib
cargo check --all-targets
```

Current V2 targets:

- Library unit tests: no Milvus server required.
- `v2_ut` at `tests/v2/ut/mod.rs`: mock/local unit integration only, no Milvus server required.
- `v2_st` at `tests/v2/st/mod.rs`: server-backed system tests; the target requires Milvus even when individual cases are not marked ignored.
- `v1_st` at `tests/v1/mod.rs`: server-backed compatibility and integration tests, with some ignored high-load or deployment-specific cases.
- Rust doctests: no Milvus server is started by the doctest command.
- `v2_simple` at `examples/v2/simple.rs`: the smallest general V2 example; compile it without a server or run it explicitly against Milvus.

Run the V2 system target only with a server available:

```bash
cargo test --test v2_st -- --nocapture
```

## V1 compatibility checks

V2 is additive, so V2 changes must keep V1 compiling. Choose checks proportional to the change:

```bash
cargo test --lib
cargo check --all-targets
```

For changes touching shared errors, protobufs, Cargo dependencies, or crate exports, run relevant V1 targets or `cargo test --no-run`. Do not claim V1 compatibility based only on `v2_ut`.

## Formatting and linting

Before handoff, use the repository's canonical formatting check and inspect the diff:

```bash
cargo fmt --all -- --check
git diff --check
```

The standalone tutorial crates are not root-workspace members. When tutorial Rust sources change,
also format/check each manifest explicitly:

```bash
for manifest in tutorial/*/Cargo.toml; do
  cargo fmt --manifest-path "$manifest" -- --check
done
```

Use Clippy when requested or proportionate to the change:

```bash
cargo clippy --all-targets --all-features
```

During V2-only work, inspect the formatting diff before accepting it. Do not retain unrelated rewrites under `src/v1`, `tests/v1`, or `examples/v1` merely because a whole-crate formatter touched them.

## Milvus/Docker setup

Most V1 integration tests and V2 system tests expect Milvus at `http://localhost:19530` unless environment/configuration says otherwise.

Ask before starting or recreating containers. The repository test script manages the Linux
Milvus container through `tests/v2/st/milvus_container.py`:

```bash
./scripts/run_tests.sh
```

For compilation and tests that do not require Milvus, including on GitHub-hosted macOS:

```bash
./scripts/run_tests.sh --no-server
```

`run_tests.sh --no-server` runs `cargo check --all-targets`, compile-checks all standalone
tutorial crates against the current checkout with a Cargo patch, then runs library tests, `v2_ut`,
and doctests. `CODE_COV=true` is intentionally rejected with `--no-server`.

The full Linux path starts one standalone Milvus container (the default image is selected by the launcher) after non-server checks, runs `v1_st` and `v2_st`, and removes the container. Override the image with
`MILVUS_IMAGE`; `SYSTEM_TEST_THREADS` defaults to 2.
When coverage is enabled, the script requires `cargo-llvm-cov` and `genhtml`, performs an
instrumented rebuild, and writes `code_coverage/lcov.info` plus HTML output.

The Python launcher supports Python 3.6 through current Python 3 releases. It labels containers by
host-port pair, removes only non-running leftovers, and refuses to kill a matching running
container because another test run may own it.

Typical exposed services:

- Milvus gRPC: `19530`
- health/metrics: `9091`

For a bounded custom server-backed command, `run_tests.sh` starts Milvus first and then executes the
supplied command. Do not use that mode for arbitrary commands that do not need Milvus.

## Tutorial validation

The standalone tutorial crates are pinned to an exact published SDK version.

- `scripts/run_tests.sh` compile-checks all tutorials against the current checkout by passing a
  temporary `patch.crates-io.milvus-sdk-rust.path` Cargo configuration. This validates source
  compatibility before publication.
- `scripts/run_tutorials.sh` always resolves the pinned SDK from crates.io, starts one standalone
  Milvus container on host ports `29530` and `29091` by default, exports the corresponding
  `MILVUS_URI`, and executes every tutorial. Override the host ports with `MILVUS_GRPC_PORT` and
  `MILVUS_HEALTH_PORT` when necessary. It intentionally does not set or forward `MILVUS_IMAGE`;
  the launcher default selects the image.

Running `scripts/run_tutorials.sh` starts Docker and mutates temporary Milvus resources, so ask
before running it unless the user explicitly requested tutorial execution or release validation.

The eight-crate path is:

1. `1_quickstart`: connect, create, insert, load, search, and clean up.
2. `2_collection`: collection lifecycle and properties.
3. `3_schema`: supported scalar, container, vector, and struct schemas.
4. `4_index`: vector and scalar index administration.
5. `5_dml`: row/column insert, full/partial upsert, and delete.
6. `6_dql`: query, search, hybrid search, and iterators.
7. `7_database`: advanced database administration.
8. `8_rbac`: advanced users, roles, privilege groups, and grants.

Tutorial source keeps short explanatory comments immediately before SDK calls. Each comment should
state what the API does and explain the important request parameters without duplicating full
Rustdoc.

## Test layout

- `tests/v1/`: legacy integration, concurrency, and explicit Cargo test targets.
- `tests/v2/ut/`: V2 domain, request composition, validation, and compatibility tests.
- `tests/v2/st/`: Docker/server-backed V2 tests.
- Unit tests inside `src/v2`: internal schema validation and global timestamp behavior.

Call a test an integration/system test when it connects to Milvus; do not label it a unit test.

## Common troubleshooting

### Connection refused

Milvus is not running, unhealthy, or configured at another URI. Check the test environment before changing SDK code.

### Rate limiting

Confirm the test is using the intended Milvus instance and configuration. Add SDK retry logic only when it is part of the requested behavior.

### Generated binding investigation

Locate generated files with:

```bash
find target/debug/build/milvus-sdk-rust-*/out -name 'milvus.proto.*.rs'
```

Never patch them. Change proto/codegen inputs and rebuild.

### System tests require Milvus

Do not infer that the whole `v2_st` target is safe because some cases may be ignored. Run it only when the user authorized server-backed testing; add `--ignored` only when intentionally selecting ignored cases.

### Port already allocated

The test launcher reports a live matching labeled container rather than removing it. Another
`run_tests.sh` invocation may still be active. Containers not owned by the launcher can also occupy
the fixed ports; inspect the host before changing cleanup behavior.
