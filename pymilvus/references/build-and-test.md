# Build and test

Use this before installing dependencies, formatting, linting, or running tests in the PyMilvus repo.

## Prerequisites

- Python 3.9+ for normal package usage.
- CI currently tests Python 3.9 and 3.14 on Ubuntu (`ubuntu-22.04`) and Windows.
- Protobuf codegen and `make gen_proto` run under a constrained Python version range because the `codegen` dependency group pins a specific `grpcio-tools` version. Check `pyproject.toml` for the current pins.
- A Milvus server is not required for the mock-based unit tests, the `tests/benchmark` suite, or the `tests/integration/lite` suite, but many `examples/` scripts require a server at `localhost:19530` or external services.

## First-time setup

The repo uses `uv` for dependency management and locking (`uv.lock`). From the repository root:

```bash
uv sync --group dev
```

`uv sync` installs the project and locked dependencies; `--group dev` adds the dev dependency group (pytest, coverage, black, ruff, codegen, benchmark/profiling, bulk-writer development dependencies, and `xxhash` so the accelerated bloom-filter path runs in CI, not just the pure-Python fallback). Equivalent convenience targets: `make install` (bare `uv sync`) and `make sync` (`uv sync --group dev`).

Optional pre-commit setup:

```bash
uv run pre-commit install
```

The pre-commit config (`.pre-commit-config.yaml`) runs `make format` and `make lint` before commits.

## Makefile commands

Root `Makefile` commands (all run through `uv`):

```bash
make sync       # uv sync --group dev
make install    # uv sync
make unittest   # pytest tests/unit --cov=pymilvus -v
make coverage   # pytest tests/unit --cov=pymilvus --cov-report=xml -v
make lint       # black --check --diff and ruff check on pymilvus/ and tests/
make format     # run black, then ruff check --fix on pymilvus/ and tests/
make benchmark  # pytest tests/benchmark --benchmark-only
make integration-lite  # pytest tests/integration/lite -v (Milvus Lite extra)
make example / make example_index   # run examples/example.py or examples/example_index.py
make package    # uv build --sdist --wheel --out-dir dist/ .
make get_proto  # git submodule update --init
make gen_proto  # run grpc_gen/python_gen.sh with the codegen group (Python >=3.9,<3.14)
make check_proto_product   # gen_proto then compare generated output to submodule
make version    # uv run hatchling version (read-only dynamic version)
```

Prefer targeted commands during development, then broader validation before finalizing.

## Targeted tests

Unit tests live under `tests/unit/`. Run a specific test file:

```bash
uv run --group dev pytest tests/unit/grpc_handler/test_file.py -v
```

Run a specific test:

```bash
uv run --group dev pytest tests/unit/grpc_handler/test_file.py::TestClass::test_name -v
```

Run async tests with pytest normally; async tests should use `@pytest.mark.asyncio`, not manual event-loop wrappers.

## Full local validation

Unit tests excluding benchmarks (matches `make unittest`):

```bash
uv run --group dev pytest tests/unit --cov=pymilvus -v
```

Coverage XML, matching CI:

```bash
make coverage
```

Lint check:

```bash
make lint
```

Format/fix:

```bash
make format
```

Milvus Lite integration tests:

```bash
make integration-lite
```

Build package artifacts:

```bash
make package
```

## Unit test authoring rules

Read `tests/README.md` and `tests/unit/README.md` before writing or refactoring tests.

Important rules:

- Check `tests/unit/conftest.py` before writing setup code.
- Prefer existing fixtures such as `mock_grpc_handler`, `mock_async_grpc_handler`, `mock_milvus_client`, `mock_milvus_client_handler`, `mock_grpc_stub`, `mock_async_stub`, `mock_grpc_channel`, `mock_async_channel`, and proto fixture helpers like `mock_field_data_int64`, `mock_field_data_array`, `mock_field_data_float_vector`, `mock_collection_schema`.
- Prefer helper builders such as `make_status`, `make_response`, `make_collection_schema_response`, `make_mutation_response`, `make_search_response`, and `make_query_response`.
- Use parametrization instead of copy-paste tests.
- For simple client-method delegation tests, add rows to an existing delegation table instead of adding one method per test.
- Use `@pytest.mark.asyncio` for async tests.
- Extract repeated helper classes/functions to module level.
- Avoid test classes with only one or two trivial tests.
- Avoid duplicating coverage already provided by parametrized tables.

## Test layout

Main test directories:

- `tests/unit/` — deterministic unit tests (the default `make unittest`/`make coverage` scope):
  - `tests/unit/grpc_handler/` — sync gRPC handler behavior.
  - `tests/unit/async_grpc_handler/` — async handler behavior.
  - `tests/unit/orm/` — legacy ORM behavior.
  - `tests/unit/prepare/` — request preparation helpers.
  - `tests/unit/entity_helper/` — entity/helper conversions.
  - plus top-level test files such as `test_milvus_client.py`, `test_async_milvus_client.py`, `test_connection_manager.py`, `test_bulk_writer_*.py`, `test_bloom_filter.py`, `test_roaring_filter.py`, `test_search_iterator.py`, and more.
- `tests/integration/lite/` — embedded Milvus Lite integration tests (`make integration-lite`).
- `tests/benchmark/` — pytest-benchmark suite (`make benchmark`), excluded from unit test targets.

## CI workflows to mirror

- `.github/workflows/pull_request.yml` runs `uv sync --group dev`, then `make coverage` and `make integration-lite` on Python 3.9 and 3.14 across Ubuntu and Windows, uploading coverage to Codecov.
- `.github/workflows/code_checker.yml` runs `uv sync --group dev` and `make lint` on Python 3.9 and 3.14.
- `.github/workflows/check_milvus_proto.yml` runs `git submodule update --init`, `make gen_proto`, and `make check_proto_product` on Python 3.9 and 3.13.

When reproducing CI locally, start with the smallest relevant command, then run the matching CI command.

## Design documents

`docs/plans/` holds design documents such as the global client, connection manager, and function-chain API designs. It is not a Sphinx documentation build.

## Common cautions

- Do not call integration-style examples unit tests.
- Do not assume a local Milvus server is running.
- Do not run examples, benchmarks, or package publishing commands that modify external state without user confirmation.
- Do not bypass pre-commit hooks or CI checks with `--no-verify` unless the user explicitly instructs it.
- If proto output changed unexpectedly, inspect the toolchain version and submodule state before editing generated files.
