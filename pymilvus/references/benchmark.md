# Benchmarks

Use this before running or modifying benchmark tooling.

## Benchmark locations

Primary benchmark suite:

- `tests/benchmark/README.md` — full guide.
- `tests/benchmark/conftest.py` — mock gRPC fixtures.
- `tests/benchmark/mock_responses.py` — fake protobuf responses.
- `tests/benchmark/test_search_bench.py` — search/query/hybrid benchmark cases.
- `tests/benchmark/test_perf_improvements.py` — additional performance-focused cases.
- `tests/benchmark/scripts/profile_cpu.sh` — CPU profiling wrapper.
- `tests/benchmark/scripts/profile_memory.sh` — memory profiling wrapper.

General examples may also contain performance scripts, but `tests/benchmark/` is the maintained benchmark suite.

## What the benchmark suite measures

The `tests/benchmark` suite measures client-side PyMilvus overhead without requiring a running Milvus server:

- Request preparation: validation, serialization, and parameter handling.
- Response parsing: deserialization, field conversion, vector conversion, result construction.
- It deliberately excludes network I/O and server-side Milvus processing by mocking gRPC calls.

Do not use these benchmarks to claim end-to-end Milvus server performance.

## Install benchmark dependencies

From repo root:

```bash
uv sync --group dev
```

The dev group includes `pytest-benchmark[histogram]`, `py-spy`, `memray` on non-Windows, and related benchmark dependencies.

## Timing benchmarks

Run all benchmark cases:

```bash
make benchmark
# or
uv run --group dev pytest tests/benchmark --benchmark-only
```

Run a specific benchmark:

```bash
uv run --group dev pytest tests/benchmark/test_search_bench.py::TestSearchBench::test_search_float32_varying_output_fields --benchmark-only
```

Save a baseline:

```bash
uv run --group dev pytest tests/benchmark/ --benchmark-only --benchmark-save=baseline
```

Compare against a saved baseline:

```bash
uv run --group dev pytest tests/benchmark/ --benchmark-only --benchmark-compare=baseline
```

Generate histograms:

```bash
uv run --group dev pytest tests/benchmark/ --benchmark-only --benchmark-histogram
```

## CPU profiling

Generate a flamegraph:

```bash
uv run --group dev py-spy record -o cpu_profile.svg --native -- pytest tests/benchmark/test_search_bench.py::TestSearchBench::test_search_float32 -v
```

Generate speedscope output:

```bash
uv run --group dev py-spy record -o cpu_profile.speedscope.json -f speedscope -- pytest tests/benchmark/test_search_bench.py::TestSearchBench::test_search_float32 -v
```

Use helper script:

```bash
./tests/benchmark/scripts/profile_cpu.sh test_search_bench.py::test_search_float32
```

## Memory profiling

Run with memray:

```bash
uv run --group dev memray run -o search_bench.bin pytest tests/benchmark/test_search_bench.py::test_search_float32 -v
uv run --group dev memray flamegraph search_bench.bin
uv run --group dev memray table search_bench.bin
uv run --group dev memray tree search_bench.bin
uv run --group dev memray summary search_bench.bin
```

Live monitoring:

```bash
uv run --group dev memray run --live pytest tests/benchmark/test_search_bench.py::test_search_float32 -v
```

Use helper script:

```bash
./tests/benchmark/scripts/profile_memory.sh test_search_bench.py::test_search_float32
```

## Expected bottleneck areas

When investigating performance, inspect:

- Protobuf deserialization for large responses.
- Vector data conversion, especially bytes to numpy arrays.
- Protobuf-to-Python type conversions.
- Iteration over many output fields.
- Unnecessary memory copies or result object construction overhead.

## Rules for benchmark work

- Ask before running long or resource-intensive benchmarks.
- State clearly whether a benchmark is client-side mocked or end-to-end server-backed.
- Save a baseline before optimization if comparing performance.
- Keep benchmark inputs representative and documented.
- Do not mix benchmark results from different Python versions, dependency versions, or machine types without calling that out.
- If modifying performance-sensitive parsing/conversion code, run targeted benchmark cases plus relevant unit tests.
