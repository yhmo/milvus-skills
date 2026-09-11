# Examples

Use this reference before running or modifying examples.

## Edition layout

- `examples/v1/`: legacy crate-root API examples.
- `examples/v2/`: opt-in `milvus::v2` examples.
- `tutorial/`: standalone Cargo application projects using an exact crates.io SDK version.

Cargo lists explicit example targets in `Cargo.toml`. Verify names with:

```bash
rg -n '^\[\[example\]\]|^name =|^path =' Cargo.toml
find examples -maxdepth 2 -type f -name '*.rs' | sort
```

Example target names are edition-prefixed: `v1_*` for deprecated V1 examples and
`v2_*` for V2 examples. A small V2 starting point is:

```bash
cargo run --example v2_simple
```

Compile without running server mutations:

```bash
cargo check --example v2_simple
cargo build --examples
```

## Prerequisites and safety

Examples generally require Milvus at `http://localhost:19530`. They may create, mutate, or delete collections, databases, indexes, aliases, users, or resource groups.

Ask before running examples unless the user explicitly requested execution and accepted local data changes. Ask separately before starting Docker.

`scripts/run_examples.sh` runs most V2 examples sequentially against an already available Milvus
server. It skips the shared `utils` module plus `cdc` and `optimize`, and it does not start or stop
Milvus. Ask before running it because the examples mutate server state.

## V2 example rules

- Import through `milvus::v2`, not crate-root V1 modules.
- Prefer `use milvus::v2::prelude::*;` so requests, responses, reusable types, errors, client/task, and iterator APIs remain concise.
- Construct requests through validated builders and reusable types through `new()` plus fluent methods. Read responses through their getters while treating public response structs and enums as non-exhaustive.
- Never use generated protobuf types or public protobuf conversion escape hatches.
- Demonstrate both schema-aware column input through `FieldData` and JSON row input through `.row(...)`/`.rows(...)` where relevant.
- Define vector indexes as part of collection creation before loading, unless the example specifically demonstrates separate index management.
- Print query/search results with `ResultRowIter`, `ResultRow`, and `ResultValue`; reserve `get_output_row(s)` for examples that specifically need owned JSON materialization.
- Keep examples small and use random or clearly namespaced resource names.
- Clean up created resources when practical.
- Document special server configuration, authentication, external storage, or CDC prerequisites near the example.

## V1 example rules

Preserve existing V1 imports and behavior unless the task explicitly targets V1. Do not rewrite V1 examples to V2 as incidental cleanup.

## Tutorials

Tutorials are intentionally independent Cargo projects rather than root-crate examples. The
learning path starts with `1_quickstart`, continues through collection/schema/index/DML/DQL topics,
and ends with advanced `7_database` and `8_rbac` administration tutorials.

- Keep each tutorial focused on its named topic; `1_quickstart` remains the shortest complete
  connect/create/insert/load/search application.
- Put a concise explanatory comment immediately before every SDK API call. Explain the operation's
  purpose, effect, and important request parameters. Avoid narrating ordinary Rust syntax or
  reproducing full API Rustdoc.
- Keep each `tutorial/*/Cargo.toml` dependency pinned to the exact released SDK version.
- During ordinary development, `scripts/run_tests.sh` compile-checks tutorials with a temporary
  local Cargo patch; do not add a permanent path dependency.
- Because tutorials are standalone crates rather than root-workspace members, run `cargo fmt
  --manifest-path tutorial/<name>/Cargo.toml` for changed tutorial sources.
- During release preparation, update every tutorial manifest and every tutorial README version
  reference to the target version.
- `scripts/run_tutorials.sh` resolves crates.io, launches standalone Milvus on tutorial-specific
  host ports `29530` and `29091` by default, and runs every tutorial under `tutorial/` dynamically.
  It is Linux-only and accepts port overrides through `MILVUS_GRPC_PORT` and
  `MILVUS_HEALTH_PORT`; it does not patch tutorials to the local SDK or set `MILVUS_IMAGE`.
- The default tutorial container does not enable Milvus authorization. `8_rbac` may run its
  management calls there, but permission-denial behavior is not meaningful; its README explains how
  to test enforcement against a separately configured authorization-enabled server.
- Tutorial lockfiles currently exist locally but are ignored/untracked by repository policy. Do
  not add them unless the maintainer explicitly changes that policy.

## Root README boundary

Keep `README.md` as a concise user entry point aligned with the C++ SDK structure: compatibility,
client choice, Cargo dependencies, one minimal `ClientV2` connection/health program, tutorials,
more examples, troubleshooting, development link, and license. Do not duplicate the complete
create/insert/load/search workflow there; `tutorial/1_quickstart` is the independently buildable
source of truth.

## Debugging

```bash
RUST_BACKTRACE=1 cargo run --example v2_simple
```

Check URI, credentials, server version, and returned `milvus::error::Error` before changing SDK behavior.
