# Build and Test

Use this reference before configuring, building, testing, linting, packaging, or investigating CI.

## Requirements and defaults

- C++14 or newer; the default is C++14.
- CMake 3.14+ for supported development workflows.
- Python 3 and Conan 2 for the default dependency path.
- gRPC, protobuf, and abseil versions are declared by `conanfile.py`; check it for the current pins.
- GTest is included only when the Conan `with_tests` option is true.
- Shared/static output follows `BUILD_SHARED_LIBS`; the normal build script defaults it to `ON`.
- Examples default to enabled through `MILVUS_BUILD_EXAMPLES=ON`, independently of tests.

Install development dependencies once from the repository root:

```bash
bash scripts/install_deps.sh
```

## Parallelism and source-mutation caution

Limit all builds to four jobs:

```bash
cmake --build cmake_build -j4
JOBS=4 make test
```

`scripts/build.sh` defaults to running in-place `clang-format` over SDK, test, and example sources before compiling.
When preserving a dirty worktree or performing verification only, use its `-f` flag or build an already configured tree:

```bash
JOBS=4 bash scripts/build.sh -f -u
cmake --build cmake_build -j4 --target testing-ut
```

Do not run broad formatting to hide unrelated changes.

## Normal build entry points

Top-level targets:

```bash
make                       # Debug SDK build
make all-release           # Release SDK build
make test                  # Debug build, unit tests, and mocked tests
make test-release          # Release build, unit tests, and mocked tests
make build-no-conan-debug
make build-no-conan-release
make test-no-conan
```

Useful controls:

```bash
JOBS=4 CPPSTD=17 BUILD_SHARED_LIBS=OFF make test
CMAKE_BUILD_EXAMPLES=OFF JOBS=4 make test
MILVUS_SDK_VERSION=vX.Y.Z JOBS=4 make all-release
```

For an existing configured build tree, prefer direct targets:

```bash
cmake --build cmake_build -j4 --target milvus_sdk
cmake --build cmake_build -j4 --target testing-ut
cmake --build cmake_build -j4 --target testing-it
```

If recursive source globs do not notice a new `.cpp`, rerun configure before building.

## Conan 2 layout

`scripts/build.sh` runs Conan with separate host/build language levels:

- host: `CPPSTD`, default 14, used by the SDK and linked libraries;
- build: C++17, used by tools such as protoc and `grpc_cpp_plugin`.

The generated toolchain is normally:

```text
cmake_build/build/<BuildType>/generators/conan_toolchain.cmake
```

When debugging dependency conflicts, inspect both the package reference and user/channel. Conan treats, for example,
`protobuf/X.Y.Z` and `protobuf/X.Y.Z@milvus/dev` as different requirements even when versions match.

Generate a graph when useful:

```bash
conan graph info . --format=html > graph.html
```

Do not delete the user's Conan cache as a first response. Inspect `conan list`, profiles, lockfiles, and recipe references.

## Test scopes

| Scope | Binary | Server requirement | Purpose |
|---|---|---|---|
| `test/ut` | `cmake_build/test/testing-ut` | None | DTOs, models, conversion helpers, cache primitives |
| `test/it` | `cmake_build/test/testing-it` | In-process mocked gRPC server | RPC conversion, retries, callbacks, cache invalidation |
| `test/st` | `cmake_build/test/testing-st` | Docker-started real Milvus | End-to-end server behavior |

Call `test/it` mocked tests, not unit tests. The system-test binary registers `MilvusContainerEnv`, which invokes
`test/st/milvus_container.py`, starts a Milvus container, sets `MILVUS_HOST`, and stops the container afterward.

Suppress noisy gRPC logs during direct runs:

```bash
GRPC_VERBOSITY=ERROR ./cmake_build/test/testing-ut
GRPC_VERBOSITY=ERROR ./cmake_build/test/testing-it
```

## Focused tests

List names before guessing a filter:

```bash
./cmake_build/test/testing-ut --gtest_list_tests
./cmake_build/test/testing-it --gtest_list_tests
```

Examples:

```bash
./cmake_build/test/testing-ut --gtest_filter='*SchemaCache*:*CollectionTsCache*'
./cmake_build/test/testing-ut --gtest_filter='*Collection*Request*:*Collection*Response*'
./cmake_build/test/testing-it --gtest_filter='MilvusMockedTest.DescribeCollection:MilvusMockedTest.GetPersistentSegmentInfo'
./cmake_build/test/testing-it --gtest_filter='*CacheInvalidation*:*Connection*'
```

Build the test binary first after changing its source:

```bash
cmake --build cmake_build -j4 --target testing-it
```

## System tests

System tests create/drop Milvus resources and start Docker. Obtain explicit user permission before running:

```bash
JOBS=4 make st
```

For a focused case after the binary is built, remember that launching `testing-st` still starts its managed container:

```bash
GRPC_VERBOSITY=ERROR ./cmake_build/test/testing-st --gtest_filter='MilvusServerTestCache.*'
```

Requirements include Docker access and the Python Docker SDK. Do not recreate containers, remove volumes, or install
Docker dependencies without authorization.

## CI behavior

The primary workflow is `.github/workflows/main.yaml`:

- Linux PR jobs run lint, `make test`, and package verification.
- Coverage runs unit, mocked, and system tests with examples disabled.
- macOS runs unit/mocked tests and package verification for core changes.
- Windows builds the shared library and runs `testing-ut`; `testing-it` is intentionally skipped in CI because the
  in-process mocked server is unstable across the Windows EXE/DLL boundary.
- Example-only PR changes skip the heavier coverage/macOS/Windows jobs.

When reproducing CI, match its OS, `BUILD_SHARED_LIBS`, language level, Conan profile, and exact target before changing
production code.

## Lint, coverage, docs, and packages

```bash
JOBS=4 make lint
JOBS=4 CMAKE_BUILD_EXAMPLES=OFF make coverage
make doc
make package
```

- `make lint` runs cpplint, clang-format checks, and clang-tidy.
- `make coverage` starts the real-server system tests; obtain permission first.
- `make package` uses `scripts/build.sh -f -t Release`, then CPack, and writes artifacts under `cmake_build/Pack`.
- Package smoke verification scripts are `scripts/verify_package_linux.sh` and `scripts/verify_package_windows.ps1`.

## Common failures

### New source file is not compiled

The CMake files use recursive globs. Reconfigure, then rebuild with four jobs.

### Protobuf accessor mismatch

Inspect generated headers under `cmake_build/_deps/milvus_proto-build`; proto casing may produce accessors such as
`collectionid()` or `replicaid()`.

### Installed package is not found

The package name and target are:

```cmake
find_package(milvus_sdk CONFIG REQUIRED)
target_link_libraries(app PRIVATE milvus_sdk::milvus_sdk)
```

Provide the installation prefix through `CMAKE_PREFIX_PATH` when necessary. Static non-Conan installs intentionally do
not export a CMake package because their vendored gRPC/protobuf dependencies are not installed for consumers.

### Test output contains verbose gRPC internals

Set `GRPC_VERBOSITY=ERROR`; this affects logging only, not connection behavior.
