# Technical Details

Use this reference for architecture, source placement, FFI and binding tracing, format/filesystem behavior, and
repository-consistent changes on the current `main`/active line.

## Contents

- Architecture layers
- Source layout
- FFI boundary and error taxonomy
- Format layer
- Filesystem layer
- Transaction and manifest layer
- Multi-language bindings
- Change checklists
- API tracing

## Architecture layers

```text
Python / Java / Rust / C++ consumers
  -> FFI layer (extern "C", arrow C ABI)          cpp/src/ffi + cpp/include/milvus-storage/ffi_*_c.h
  -> Reader API (RecordBatchReader/ChunkReader)   cpp/src/reader.cpp
  -> Writer API (column group policies)           cpp/src/writer.cpp
  -> Transaction layer (manifest/delta)           cpp/src/transaction/, cpp/src/manifest.cpp
  -> Column Group Reader / Writer / ChunkManager  cpp/src/packed/, cpp/src/format/column_group_*
  -> Format layer (Parquet primary, Vortex, Lance, Iceberg, Paimon)   cpp/src/format/
  -> Filesystem layer (local, S3, GCS, Azure, Aliyun, Tencent, Huawei, Talon)   cpp/src/filesystem/
```

## Source layout

Public C++ headers:

- `cpp/include/milvus-storage/ffi_c.h`: core FFI header; `FFI_EXPORT`, Arrow C data interface include, and the
  `loon_errcode_*` error code exports.
- `cpp/include/milvus-storage/ffi_{exttable,filesystem,filesystem_metrics,fiu}_c.h`: additional FFI surface.
- `cpp/include/milvus-storage/`: C++ public headers by domain (`column_groups.h`, `manifest.h`, `packed/`,
  `properties.h`, `reader.h`, `segment/`, `thread_pool.h`, `transaction/`, `writer.h`, `common/`, `filesystem/`,
  `format/`, `lob_column/`, `arrow/`).
- `cpp/ffi_exports.map` / `cpp/ffi_exports_mac.map`: symbol version scripts used when `WITH_PYTHON_BINDING=ON`; only
  FFI symbols are exported.

C++ implementation (`cpp/src/`):

- `ffi/bridge.cpp` and per-domain `*_c.cpp` (`writer_c.cpp`, `reader_c.cpp`, `manifest_c.cpp`, `properties_c.cpp`,
  `filesystem_c.cpp`, `segment_writer_c.cpp`, `segment_reader_c.cpp`, `result_c.cpp`, `column_groups_c.cpp`,
  `exttable_c.cpp`, `threadpool_c.cpp`, `ffi_fiu_c.cpp`, `filesystem_metrics_c.cpp`, plus v2 entries): the `extern "C"`
  surface consumed by all bindings.
- `common/`: `arrow_util.cpp`, `extend_status.cpp` (Arrow/cloud error -> `loon_errcode_*` mapping), `layout.cpp`,
  `log.cpp`, `metadata.cpp`.
- `filesystem/`: `fs.cpp`, `local_fs_producer.cpp`, and provider subdirectories `azure/`, `gcp/`, `s3/`, `talon/`;
  `util_internal.cpp`.
- `format/`: `format.cpp`, `format_reader.cpp`, `format_reader_cache.cpp`, `column_group_{reader,writer,lazy_reader}.cpp`,
  `async_tasks.cpp`, and format subdirectories `parquet/`, `vortex/`, `lance/`, `iceberg/`, `paimon/`, plus the always-built
  Rust bridge `format/bridge/rust/`.
- `jni/`: JNI glue (`*_jni.cpp`) for the Java/Scala binding.
- `packed/`: `column_group.cpp`, `chunk_manager.cpp`, `reader.cpp`, `writer.cpp`, `splitter/`.
- `segment/`: `segment_reader.cpp`, `segment_writer.cpp`.
- `lob_column/`: `lob_column_manager.cpp`, `lob_column_{reader,writer}.cpp`, `lob_reference.cpp`.
- `transaction/transaction.cpp`, `manifest.cpp`, `properties.cpp`, `reader.cpp`, `writer.cpp`, `thread_pool.cpp`.

Tests and tools:

- `cpp/test/`: gtest sources (top-level `*_test.cpp`, plus `common/`, `filesystem/`, `filter/`, `format/`, `packed/`,
  `segment/`, `lob_column/`) building `milvus_test`; `cpp/test/ffi/` C and C++ FFI tests building `Test_FFI`.
- `cpp/test/include/test_env.h`: test environment helpers; `TEST_ENV_*` variables gate cloud/Talon scenarios.
- `cpp/test/packed/run_cloud_test.sh`: cloud-provider test driver.
- `cpp/tools/loon.cpp` and `cpp/test/tools/loon_test.cpp`: example/tool entry points.
- `cpp/benchmark/`: Google Benchmark micro-benchmarks.

## FFI boundary and error taxonomy

- Bindings marshal Arrow data through the Arrow C data interface (`arrow/c/abi.h`); never pass C++ types across FFI.
- Error codes are exported C constants: `loon_errcode_success`, `loon_errcode_invalid_args`, `loon_errcode_memory`,
  `loon_errcode_arrow`, `loon_errcode_logical`, `loon_errcode_got_exception`, `loon_errcode_unreachable`,
  `loon_errcode_invalid_properties`, `loon_errcode_fault_inject`, `loon_errcode_not_support`,
  `loon_errcode_file_not_found`, `loon_errcode_permission_denied`, AWS-specific (`loon_errcode_aws_*`), and transient
  (`loon_errcode_transient_*`) codes.
- `cpp/src/common/extend_status.cpp` is the mapping hub: preserve the existing code when adding a new failure path.
- `scripts/error_handling_ratchet.sh` compares against `scripts/error_handling_baseline.tsv`; new error sites must
  update the baseline deliberately (`make update-error-ratchet`).

## Format layer

- Parquet is the primary write format (`cpp/src/format/parquet/`); Vortex and Lance go through the Rust bridge
  (`cpp/src/format/bridge/rust/`, `prsbridge` target) with `VortexReader`/`LanceReader` C++ wrappers in
  `cpp/src/format/`.
- `WITH_CRT` enables the `s3-crt-async` bridge feature; `WITH_TALON` enables `talon`; keep feature propagation from
  `cpp/CMakeLists.txt` into the bridge consistent.
- `format_reader_cache.cpp` and Lance dataset reuse across fragments/snapshot versions are recent behavioral areas;
  verify cache keying (endpoint + path + snapshot version) before touching.
- Never hand-edit generated bridge headers or Cargo.lock; change the Rust crate and re-run the build.

## Filesystem layer

- `filesystem/fs.cpp` dispatches by URI scheme. Providers: local, AWS S3 (incl. MinIO/R2), GCS, Azure, Aliyun, Tencent,
  Huawei, and the optional Talon remote cache (`filesystem/talon/`).
- Cloud tests are environment-driven: `cpp/scripts/setup_minio.sh` + `cpp/scripts/minio_env.sh`,
  `cpp/scripts/setup_azurite.sh` + `cpp/scripts/azurite_env.sh`, and `cpp/test/packed/run_cloud_test.sh` for all
  providers.
- Talon integration tests are gated by `TEST_ENV_TALON_ENABLED` and run as `--gtest_filter='TalonIntegrationTest.*'`
  against a coordinator + worker + MinIO.

## Transaction and manifest layer

- ACID-like semantics via manifest versioning, delta logs, and conflict resolution in `cpp/src/transaction/` and
  `cpp/src/manifest.cpp`; properties handling in `cpp/src/properties.cpp`.
- Reader paths (`cpp/src/reader.cpp`) expose `RecordBatchReader`-style scans, `ChunkReader` random access, and `Take`
  row-index reads through `cpp/src/packed/` and `segment/`.
- Writer paths (`cpp/src/writer.cpp`) support column-group policies (single/schema/size based) with row-group sizing,
  file rolling, and buffering.

## Multi-language bindings

- Python (`python/milvus_storage/`): `_ffi.py` (ctypes) plus `writer.py`, `reader.py`, `manifest.py`, `properties.py`,
  `transaction.py`, `filesystem.py`, `exttable.py`, `fiu.py`, `common.py`, `exceptions.py`; package metadata in
  `python/pyproject.toml`; tests in `python/tests/`.
- Java/Scala (`java/`): sbt project (Scala 2.13), package `io.milvus`, JNI via `cpp/src/jni/`; native staging under
  `java/native/linux-x86_64` with `java/patch_native_runpath.sh` and `java/verify_native_dependencies.sh`.
- Rust (`rust/`): DataFusion integration (`table_provider.rs`, `execution_plan.rs`, `ffi.rs`, `error.rs`); built with
  `build.rs` against `wrapper.h`. This is separate from the in-engine Rust format bridge.
- When a C++ behavior changes, trace its projection into each binding and its tests; do not change only one language.

## Change checklists

For a new or changed FFI entry point:

1. Declare it in the matching `cpp/include/milvus-storage/ffi_*_c.h` (or domain header) with `FFI_EXPORT` and C types.
2. Implement it in `cpp/src/ffi/` (bridge.cpp or a domain `*_c.cpp`); map failures through `extend_status.cpp`.
3. Add the symbol to `cpp/ffi_exports.map` (and `ffi_exports_mac.map`) when Python packaging must export it.
4. Add a C test under `cpp/test/ffi/` (covered by `Test_FFI`) and a gtest under `cpp/test/` where behavior warrants it.
5. Project into the bindings that need it: `python/milvus_storage/_ffi.py` + module, `cpp/src/jni/*_jni.cpp` + `java/`,
   or `rust/src/ffi.rs`.
6. Cover cross-language round trips with `tests/integration/` when the change is user-visible.

For a format or filesystem change:

1. Trace the call path through `cpp/src/format/` or `cpp/src/filesystem/` to its FFI projection.
2. Respect bridge feature gating and `CONAN`/CMake option wiring (`WITH_CRT`, `WITH_TALON`, `WITH_ASAN`, ...).
3. Verify cache keys and lazy-reader semantics where readers are reused across fragments/versions.
4. Run the narrowest gtest filter first, then provider-specific cloud tests if affected.

## API tracing

Prefer:

```bash
rg -n "Symbol" cpp/include cpp/src cpp/test
rg -n "Symbol" python/milvus_storage java/src rust/src
rg -n "Symbol" tests/integration tests/stress
```

Or run:

```bash
"$SKILL_DIR/scripts/api-trace.sh" Symbol
```
