# Build and Test

Use this reference before configuring, building, testing, linting, packaging, or investigating CI.

## Prerequisites

Install development dependencies once:

```bash
bash scripts/install_deps.sh
pip3 install pre-commit
pre-commit install --hook-type pre-commit --hook-type pre-push
```

See [references/technical-details.md](technical-details.md) for dependency roles (OpenBLAS always; libaio for DiskANN; CUDA for cuVS).

## Build commands

Build output lands under `$(BUILD_DIR)/$(BUILD_TYPE)/` (default `build/Release/`). The test binary is
`build/Release/tests/ut/knowhere_tests`.

| Build Type | Command |
|------------|---------|
| CPU Release | `make` |
| CPU Debug | `make WITH_DEBUG=True` |
| CPU + UT | `make WITH_UT=True` |
| CPU + UT + ASAN | `make WITH_UT=True WITH_ASAN=True` |
| GPU (cuVS) | `make WITH_GPU=True` |
| GPU + UT | `make WITH_GPU=True WITH_UT=True` |
| Cardinal | `make WITH_CARDINAL=True` |
| Custom build dir | `make BUILD_DIR=$(pwd)/build_asan WITH_ASAN=True` |

## Build flags

| Flag | Description |
|------|-------------|
| `WITH_GPU=True` | Enable GPU (cuVS) build |
| `WITH_UT=True` | Enable unit tests |
| `WITH_BENCHMARK=True` | Enable benchmarks build |
| `WITH_ASAN=True` | Enable AddressSanitizer |
| `WITH_SVS=True` | Enable SVS (Intel Scalable Vector Search, x86 only) |
| `WITH_CARDINAL=True` | Enable Cardinal build |
| `CARDINAL_VERSION_FORCE_CHECKOUT=True` | Force Cardinal checkout to the configured version |
| `WITH_DEBUG=True` | Debug build (default: Release) |
| `CONAN_PROFILE=<p>` | Use one custom Conan profile for host and build |
| `LIBCXX=<lib>` | Override `compiler.libcxx` (auto-detected from OS; macOS defaults to `libc++`) |
| `BUILD_DIR=<dir>` | Override the build output directory |

The Makefile builds with Conan settings `compiler.cppstd=20` and, on Linux, `with_diskann=True`.

## Tests

Build first with `WITH_UT=True`, then run:

```bash
make test                                  # run the full suite
./build/Release/tests/ut/knowhere_tests    # same binary directly
./build/Release/tests/ut/knowhere_tests "[float metrics]"   # by tag
./build/Release/tests/ut/knowhere_tests "Test Mem Index*"   # by name pattern
./build/Release/tests/ut/knowhere_tests --list-tests        # list test names
./build/Release/tests/ut/knowhere_tests --list-tags         # list tags
```

Useful Catch2 flags: `-s` shows successful output, `-d yes` shows durations.

Key test files in `tests/ut/`:

| File | Covers |
|------|--------|
| `test_index.cc` | Index build/search operations |
| `test_float_metrics.cc` | Float vector metrics (L2, IP, COSINE) |
| `test_binary_metrics.cc` | Binary vector metrics (Hamming, Jaccard) |
| `test_sparse.cc` | Sparse vector index |
| `test_diskann.cc` | DISKANN indexes |
| `test_minhash_index.cc` | MinHash index |
| `test_simd.cc` | SIMD distance kernels |

## Lint and pre-commit

```bash
make lint          # clang-tidy over src/ (requires a prior build)
make format        # clang-format via pre-commit on all files
pre-commit run --files <changed-files>   # format + lint only changed files
make pre-commit    # run all pre-commit hooks
```

Code style: Google C++ style, 120-char line limit, 4-space indent, config in `.clang-format`.

## Python wheel and coverage

```bash
make wheel         # portable Python wheel (requires a prior build)
make codecov       # coverage report (requires a coverage build)
```

## Common issues

- **libstdc++ errors**: override with `make LIBCXX=libstdc++11`.
- **macOS**: `libc++` is auto-detected; OpenMP uses Homebrew's `libomp`.
- **CMake 4.x**: export `CMAKE_POLICY_VERSION_MINIMUM=3.5` for old dependency recipes (already the Makefile default).
- **ASAN failures**: check for leaks, use-after-free, and buffer overflows; pass `BUILD_DIR` to separate the ASAN build.
- **Build flags leaking into dependencies**: the Makefile deliberately `unexport`s `WITH_*`; do not bypass this when invoking Conan directly.
- **New source file not compiled**: CMake uses recursive globs; reconfigure before rebuilding.
