# Build, test, lint, and CI

Confirm commands against the current `Makefile`, `conanfile.py`, `CMakeLists.txt`, and workflows before running them.

## Prerequisites

- Conan 2.x (README pins `conan==2.25.1`), CMake 3.18+, a C++20 compiler, and the custom remote:

```bash
pip install conan==2.25.1
conan profile detect
conan remote add default-conan-local2 https://milvus01.jfrog.io/artifactory/api/conan/default-conan-local2
```

- Many dependencies are pinned in `conanfile.py` from the `@milvus/dev` channel (`opentelemetry-cpp/1.23.0@milvus/dev`, `grpc/1.67.1@milvus/dev`, `folly/2026.04.20.00@milvus/dev`) with force-overrides for `protobuf/5.27.0@milvus/dev`, `lz4`, `openssl/3.3.2`, `libcurl`, `fmt/11.2.0`, and `nlohmann_json`. Linux additionally pulls `libunwind` and `openblas`; the build is conditionally compiled with `libaio` when present.
- On macOS, install Homebrew `libomp` (`make deps` does this) so OpenMP and OpenMPI-style flags resolve.

## Build

```bash
make            # Release build via Conan + CMake into build/
make test       # -o &:with_ut=True, -DWITH_COMMON_UT=ON, then ctest --output-on-failure
make clean      # rm -rf build
make install    # cmake --install build
```

Useful variables (see Makefile):

- `BUILD_TYPE`: Conan/CMake build type, default `Release`.
- `CONAN_CPPSTD`: C++ standard passed to Conan, default `20`.
- `CONAN_EXTRA`: extra `conan install` args, e.g. `'-o \&:with_asan=True'`.
- `CMAKE_EXTRA`: extra `cmake -S . -B build` args.
- `NPROC`: parallel jobs for Conan dependency builds and CMake builds.

Conan writes its toolchain to `build/conan_toolchain.cmake`; `cmake -S . -B build` picks it up through the Makefile. If you reconfigure manually, pass `-DCMAKE_TOOLCHAIN_FILE=build/conan_toolchain.cmake`. After a source glob change (new `.cpp`), reconfigure before building.

## Tests

`make test` builds the `milvus-common` shared library with unit-test helpers (`WITH_COMMON_UT=ON`, which defines `MCL_ENABLE_TEST_CGROUP_OVERRIDE`) and registers two GTest executables via `ctest --test-dir build`:

| Binary | Source | Covers |
|---|---|---|
| `build/cachinglayer_test` | `test/test_cachinglayer/*.cpp` | DList, CacheSlot, TieredStorageConfig, loading-overhead policy/group, utils |
| `build/all_tests` | `test/init_gtest.cpp`, `TracerTest.cpp`, `StreamTest.cpp`, `PtrHashTest.cpp` | Tracer, file streams, ptrhash |

Run focused cases:

```bash
./build/cachinglayer_test --gtest_list_tests
./build/cachinglayer_test --gtest_filter='*LoadingOverheadGroup*:*DListTest*'
./build/all_tests --gtest_filter='*Tracer*'
ctest --test-dir build --output-on-failure
```

After editing a test source, rebuild the library and binary before rerunning:

```bash
cmake --build build -j"$(nproc)"
```

Note that GTest links `gtest/gmock` only when the `with_ut` option is on; the default `make` build does not produce test binaries.

## Lint and format

Pre-commit (`clang-format` v18.1.8 plus basic hooks) is the project's lint gate:

```bash
pre-commit run --all-files
```

Keep formatting scoped to files you touch. There is no separate `make lint` target in this repository.

## ASan and sanitizer runs

CI runs the Linux unit tests with AddressSanitizer:

```bash
make test BUILD_TYPE=Release CONAN_EXTRA='-o \&:with_asan=True -s compiler.version=12'
```

Use ASan builds when touching concurrency, waiting-queue, or loading-overhead accounting code.

## CI behavior

- `.github/workflows/ut.yaml`: triggers on pushes/PRs touching `include/**`, `src/**`, `test/**`, `conanfile.py`, `Makefile`, `CMakeLists.txt`, or the workflow itself.
  - `ut-linux`: ubuntu-22.04, gcc-12, 180-minute timeout (cold Conan caches rebuild grpc/folly/OpenTelemetry/OpenBLAS), Conan cache keyed on `conanfile.py`, ASan enabled.
  - `ut-macos`: macos-15, 60-minute timeout, Conan in a venv, and `-Wl,-headerpad_max_install_names` link flags for OpenSSL source builds.
- `.github/workflows/pre-commit.yaml`: runs the pre-commit suite on PRs and pushes to master.
- The `notify-conanfiles.yaml` workflow notifies the conanfiles CI that this repository's pinned dependencies changed.

## Common failures

### Conan package conflicts

Dependency conflicts between `opentelemetry-cpp` and `grpc` are resolved by the `force=True` overrides in `conanfile.py`. Do not remove an override to satisfy a resolver; instead align the pinned revision with the intended dependency graph. Inspect with `conan list`, profiles, and lockfiles before deleting the local Conan cache.

### aio_context_pool.cc is not compiled

The file is excluded when `find_library(aio)` fails (no `libaio` installed). On Linux CI `libaio-dev` is installed. If the symbol is missing, install `libaio-dev` and reconfigure rather than force-including the file.

### Test helpers missing (MCL_ENABLE_TEST_CGROUP_OVERRIDE)

The macro is defined only when `WITH_COMMON_UT=ON`; build via `make test` or pass `-DWITH_COMMON_UT=ON` manually.

### macOS OpenMP failures

Install Homebrew `libomp` (`make deps`), and use `make` so `SDKROOT` and the SDK-sysroot stripping logic in `CMakeLists.txt` are applied. For OpenSSL source builds, pass the `headerpad_max_install_names` link flags exactly as in `ut-macos`.
