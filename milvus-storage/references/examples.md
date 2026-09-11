# Examples and Benchmarks

Use this reference before changing, building, or running benchmarks or example entry points.

## Benchmarks

Google Benchmark micro-benchmarks live in `cpp/benchmark/` (`benchmark_wr.cpp`, `benchmark_format_read.cpp`,
`benchmark_format_write.cpp`, `benchmark_predicate.cpp`, `benchmark_storage_layer.cpp`, `benchmark_footer_size.cpp`,
`benchmark_compression_levels.cpp`, `benchmark_data_loader.cpp`, `benchmark_crt_reader.cpp`,
`benchmark_talon_reader.cpp`, `benchmark_v2_v3.cpp`).

Build and run when `WITH_BENCHMARK=True` (default):

```bash
cd cpp && make build
./build/Release/benchmark/benchmark --benchmark_filter="Typical/"
./build/Release/benchmark/benchmark --benchmark_list_tests
```

Design documents: `cpp/benchmark/benchmark.md`, `docs/multi-format-benchmark-design.md`, and
`docs/predicate-pushdown-benchmark.md`. Do not invent benchmark infrastructure; use the existing Google Benchmark
layout. Running full benchmarks is expensive; ask before broad runs.

## Tools

- `cpp/tools/loon.cpp`: example/tool binary built with the testing tree; `cpp/test/tools/loon_test.cpp` covers it.
- Format/tools CMake is in `cpp/tools/CMakeLists.txt` and `cpp/test/tools/`.

## Python usage examples

`python/tests/` are the canonical usage examples:

- `python/tests/test_write_read.py`: write + scan round trip.
- `python/tests/test_transaction.py`: transaction semantics.
- `python/tests/test_properties.py`: dataset properties.

Run them after `make python-lib` and copying the shared library into `python/milvus_storage/lib/` (see
`references/build-and-test.md`).

## Integration tests as examples

`tests/integration/` doubles as executable usage documentation, organized by area:

- `write_read/`, `manifest/`, `transaction/`, `schema_evolution/`, `recovery/`, `external_table/`.

`tests/stress/` covers high-concurrency, large-scale, and long-running scenarios and is scaled by `--stress-scale`.

## Conventions

- Keep examples in sync with the C++ FFI surface; do not show bindings calling non-exported symbols.
- Cloud-backed examples require credentials/environment and must not run without explicit user authorization.
