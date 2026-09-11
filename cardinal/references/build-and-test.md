# Build and Test

Use this reference before configuring, building, testing, linting, or investigating CI for Cardinal.

## Requirements and defaults

- Linux (macOS unsupported; Cardinal uses Linux-only APIs such as `libaio` and `MADV_HUGEPAGE`).
- CMake >= 3.22, GCC >= 12 (Clang 18+ recommended for performance), Python >= 3.8, Conan 2.25.1.
- C++20/23 codebase; `/include` files compile with C++17 for downstream compatibility.
- The conanfile force-pins C++20 (`compiler.cppstd=20`) and `compiler.libcxx` (libstdc++11 on Linux, libc++ on macOS).

Install development dependencies once from the repository root:

```bash
bash scripts/install_deps.sh
```

This installs the toolchain and system packages and configures the private Milvus Conan remote.

## Build entry points

The Makefile is the preferred entry point; it delegates to `scripts/build.sh`:

```bash
make                              # Release + UT + compile-time pruning (CI analyzer config)
make WITH_ASAN=True               # CI ut config: Release + UT + compile_prune + AddressSanitizer
make BUILD_TYPE=Debug             # Debug + UT + compile_prune
make WITH_UT= WITH_COMPILE_PRUNE= # Release, library only
make CONAN_PROFILE=gcc12          # custom Conan profile
make JOBS=6                       # cap compile parallelism
make UPDATE=True                  # pass --update to 'conan install' (refresh recipes)
make help                         # show all targets and flags
```

Important: `scripts/build.sh` defaults `WITH_UT` and `WITH_COMPILE_PRUNE` to True on *unset* only. Passing them as empty strings (e.g. `make WITH_UT=`) disables them. Direct Conan invocation:

```bash
conan install . --build=missing \
    -o '&:with_ut=True' -o '&:with_compile_prune=True' \
    -s:a compiler.libcxx=libstdc++11 -s:a compiler.cppstd=20 -s:a build_type=Release
conan build . \
    -o '&:with_ut=True' -o '&:with_compile_prune=True' \
    -s:a compiler.libcxx=libstdc++11 -s:a compiler.cppstd=20 -s:a build_type=Release
```

Settings/options must be passed to **both** `conan install` and `conan build`; Conan 2's `conan build` re-evaluates the conanfile and won't inherit the `install` invocation's flags.

## Test data

Some unit tests require downloaded datasets:

```bash
bash scripts/sifttest.sh
```

CI runs this before tests. Re-run it when a test fails because data files (`index_siftsmall.car`, `ivf.data.bin`, `vamana.data.bin`) are missing.

## Running tests

Test binaries are built under `build/<BuildType>/`:

```bash
# All unit tests (Catch2) plus aquila tests
make test

# Cardinal Catch2 test binary directly (with Conan runtime libs)
. build/Release/generators/conanrun.sh && ./build/Release/tests/test_cardinal

# Specific test by name or Catch2 tag
. build/Release/generators/conanrun.sh && ./build/Release/tests/test_cardinal "[tag]"
. build/Release/generators/conanrun.sh && ./build/Release/tests/test_cardinal "test name"
```

- `build/Release/tests/test_cardinal` is the main Catch2 unit test binary (see `tests/CMakeLists.txt` for the exact source set; `Catch2::Catch2WithMain` provides the runner).
- `build/Release/aquila/aquila_test` covers the `aquila/` clustering/dedup module and is also run by `make test`.
- Tests use Catch2. List tests with `--list-tests`; filter with tags like `[sq4]`, `[graph]` or by name.
- Add new test files to the glob list in `tests/CMakeLists.txt` (it uses explicit file lists, not broad recursion).

Common failing area: storage tests that touch the disk aio path need `libaio` on the link line; `tests/CMakeLists.txt` already adds `find_library(LIBAIO_LIBRARY ...)`.

## Lint and formatting

- Pre-commit hooks: `pre-commit` (check-added-large-files, check-merge-conflict, end-of-file-fixer, trailing-whitespace, clang-format v18.1.8). Run `pre-commit install --hook-type pre-push` once; run `pre-commit run` before committing.
- `.clang-format` (v18) and `.clang-tidy` / `.clang-tidy-ignore` configure formatting and static analysis; CI runs the analyzer workflow with clang-tidy-20.

## CI behavior

- `ut.yaml`: unit tests on the `cardinal-amd` self-hosted runner; runs `scripts/install_deps.sh`, `scripts/sifttest.sh`, then the UT target.
- `analyzer.yaml`: static analysis (clang-tidy-20) on PRs/pushes to `master` and `2.6`.
- `knowhere-ut.yaml`: Cardinal-as-Knowhere-index integration UT; `pre-commit.yml`: style checks.
- CCache and Conan caches persist on the self-hosted runner; keep cache keys in workflow files consistent with dependency and recipe inputs.

## Common failures

- **Test binary missing**: build with `WITH_UT=True` first (the default); `make WITH_UT=` produces a library-only build with no `test_cardinal`.
- **Missing data files**: run `bash scripts/sifttest.sh` to download the SIFT small dataset used by tests.
- **Conan cache staleness**: recipes are pinned by revision in `conanfile.py`; a rotated remote recipe needs `make UPDATE=True` locally to refresh, while CI keeps `--update` off for reproducibility.
- **New source file not compiled**: Cardinal CMake uses explicit file lists in several places (e.g. `tests/CMakeLists.txt`); add the new file there rather than relying on globbing.
