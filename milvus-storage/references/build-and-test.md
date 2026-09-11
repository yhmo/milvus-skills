# Build and Test

Use this reference before configuring, building, testing, linting, packaging, or investigating CI.

## Requirements and defaults

- C++20 (`CMAKE_CXX_STANDARD 20`), CMake >= 3.20.0, Conan >= 2.0, a C++20 compiler (GCC 10+, Clang 10+, Apple Clang 12+).
- A stable Rust toolchain is required: the Vortex/Lance Rust format bridge at `cpp/src/format/bridge/rust/` is always
  built. Linux also needs `libaio-dev` (folly dependency that Conan CMakeDeps does not propagate).
- Dependencies come from Conan 2. `cpp/conanfile.py` declares options such as `shared`, `fPIC`, `with_asan`,
  `with_ut`, `with_benchmark`, `with_jemalloc`, `with_jni`, `with_python_binding`, `with_fiu`, `with_crt`, `with_talon`.
- Output goes under `cpp/build/<BuildType>/` (default `Release`); the shared library is
  `cpp/build/<BuildType>/lib/libmilvus-storage.so`, tests are `cpp/build/<BuildType>/test/{milvus_test,Test_FFI}`.

One-time setup:

```bash
conan profile detect --force
conan remote add default-conan-local2 https://milvus01.jfrog.io/artifactory/api/conan/default-conan-local2
```

## C++ build entry points (from `cpp/`)

```bash
make build                                  # Release, WITH_UT=True, WITH_FIU=True, benchmarks ON
BUILD_TYPE=Debug make build                 # Debug build
USE_ASAN=True make build                    # address-sanitized build
make build WITH_TALON=True                  # Talon-backed remote filesystem
make package                                # conan export .. --user=milvus --channel=dev
```

Key knobs (override via environment or make variables):

```bash
BUILD_TYPE=Release|Debug
USE_ASAN=True|False
WITH_UT=True|False
WITH_FIU=True|False
WITH_CRT=True|False      # AWS S3 CRT + s3-crt-async bridge feature
WITH_TALON=True|False    # Talon filesystem + talon bridge feature
WITH_BENCHMARK=True|False
USE_JNI=True|False       # builds milvus-storage-jni; requires JAVA_HOME
USE_PYTHON_BINDING=True|False
```

Bindings builds:

```bash
make python-lib   # WITH_PYTHON_BINDING=True; hides symbols, exports only FFI via ffi_exports.map
make java-lib     # WITH_JNI=True; requires JAVA_HOME; copies milvus-storage-jni and deps for java/
```

## Tests

Local gtest and FFI tests:

```bash
make test          # build, then run milvus_test and Test_FFI on the local filesystem
make test-all      # local + MinIO + Azurite runs
make test-cloud-storage            # all providers
make test-cloud-storage aws        # single provider (aws|gcp|azure|aliyun|tencent|huawei)
```

Direct runs need the runtime library path:

```bash
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$(pwd)/build/Release:$(pwd)/build/Release/libs
./build/Release/test/milvus_test
./build/Release/test/Test_FFI
```

Focused gtest filters:

```bash
./build/Release/test/milvus_test --gtest_list_tests
./build/Release/test/milvus_test --gtest_filter='*ColumnGroup*:*ChunkManager*'
./build/Release/test/milvus_test --gtest_filter='TalonIntegrationTest.*'
./build/Release/test/Test_FFI --gtest_filter='*SegmentWriter*'
```

Cloud/Talon scenarios are enabled by environment: `cpp/scripts/setup_minio.sh` + `source cpp/scripts/minio_env.sh`,
`cpp/scripts/setup_azurite.sh` + `source cpp/scripts/azurite_env.sh`, and `TEST_ENV_TALON_ENABLED=true` with
`TEST_ENV_TALON_COORDINATOR` for Talon. Ask before starting Docker/MinIO/Azurite or Talon services.

## Python package tests

Build the FFI library first, then test through the Python package:

```bash
make python-lib                        # from cpp/
cp cpp/build/Release/lib/libmilvus-storage.so python/milvus_storage/lib/
cd python && uv sync --extra dev && uv run pytest tests/ -v --tb=short
```

Lint and format (from `python/`):

```bash
make lint            # format-check + import-check + flake8-check
make format-check
make fix-format
```

## Integration and stress tests (from `tests/`)

Requires a built Python FFI package and `pip install -r tests/requirements.txt`:

```bash
pytest integration/ -v                        # write_read, manifest, transaction, schema_evolution, recovery, external_table
pytest stress/ --stress-scale=0.01 -v         # quick validation; --stress-scale=0.05 moderate
pytest . -v
```

See `docs/integration-test-design.md` for the suite design.

## Lint, coverage, and checks (from `cpp/`)

```bash
make check-format            # clang-format --dry-run --Werror over src/include/test/benchmark
make fix-format
make check-tidy              # python3 ./scripts/run-clang-tidy.py -p build/Release
make fix-tidy
make check-error-ratchet     # enforce scripts/error_handling_baseline.tsv
make update-error-ratchet
BUILD_TYPE=Release ./scripts/coverage-report.sh   # lcov report used by CI (Codecov)
```

## CI behavior

Workflows under `.github/workflows/`:

- `cpp-ci.yml`: Linux build (`make build USE_ASAN=True BUILD_TYPE=Release WITH_TALON=True`), lint job (`make
  check-tidy`), unit tests on local/MinIO/Azurite, coverage upload, and a `talon-integration` job that checks out the
  pinned Talon revision from `cpp/src/format/bridge/rust/Cargo.toml` and runs `TalonIntegrationTest.*`.
- `cpp-mac-ci.yml`: macOS build/tests.
- `clang-format-ci.yml`: formatting gate.
- `python-ci.yml`, `java-ci.yml`: binding builds and tests (`java-ci` runs `sbt test` with
  `LD_LIBRARY_PATH=.../native/linux-x86_64`).
- `error-handling-ratchet.yml`: error-handling baseline gate.
- `nightly-python-e2e.yml`: nightly Python E2E.
- `release.yml`: tag/manual release pipeline (see `references/release.md`).

When reproducing CI, match its OS, build type, ASAN/CRT/TALON flags, Conan profile, and exact target.

## Common failures

- `libaio` missing: `sudo apt-get install -y libaio-dev` (folly requirement; CMakeDeps does not propagate it).
- `JAVA_HOME` not set with `USE_JNI=True`: `make java-lib` fails in CMake with an explicit error.
- `rg`/tooling unavailable in the checkout shell: the skill scripts fall back to repository-verified paths; install
  `ripgrep` or use plain `grep -rn`.
- New `.cpp` not compiled: `cpp/CMakeLists.txt` uses `file(GLOB_RECURSE ...)`; rerun configure before rebuilding.
- Tests fail to find shared libraries: set `LD_LIBRARY_PATH` to `build/<BuildType>` and `build/<BuildType>/libs`.
- A Python binding change does not appear: rebuild with `make python-lib`, copy `libmilvus-storage.so` into
  `python/milvus_storage/lib/`, and reinstall the editable package.
