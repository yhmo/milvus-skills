# Technical Details

Reference for architecture, source layout, index implementations, and third-party dependencies. Read before explaining or modifying index code.

## Source layout

| Path | Purpose |
|------|---------|
| `include/knowhere/` | Public headers: `index/`, `config.h`, `operands.h`, `dataset.h`, `context.h`, `expected.h`, `utils.h`, `log.h` |
| `src/index/` | Index implementations: `flat/`, `hnsw/`, `ivf/`, `diskann/`, `sparse/`, `minhash/`, `gpu_cuvs/`, `refine/`, `faiss/` |
| `src/common/` | Threading, tracing, metrics utilities |
| `src/cluster/` | Clustering algorithms (KMeans) |
| `src/io/` | I/O layer (disk-backed indexes) |
| `src/simd/` | SIMD distance kernels (AVX2/AVX512/SVE dispatch) |
| `tests/ut/` | Catch2 unit tests (`knowhere_tests` binary) |
| `tests/faiss/`, `tests/python/` | Additional test suites |
| `benchmark/` | HDF5-based benchmarks |
| `python/` | Portable Python wheel packaging |
| `thirdparty/` | Forked third-party libraries |

## Core components

**Index factory** (`src/index/index_factory.cc`, `include/knowhere/index/index_factory.h`)
- Singleton factory that maps index type strings to index nodes.
- New index types register with the `KNOWHERE_SIMPLE_REGISTER_GLOBAL` macro; the registration must stay in sync with the type string and config params.

**Index interface** (`include/knowhere/index/index.h`)
- Template-based `Index<IndexNode>` wrapper over index nodes.
- Core operations: `Build`, `Search`, `RangeSearch`, `GetVectorByIds`, `Size`, `Serialize`/`Deserialize`.

**Configuration** (`include/knowhere/config.h`)
- JSON-based config with compile-time and runtime parameter validation.
- Each index family defines its own config header (e.g. `src/index/hnsw/hnsw_config.h`, `ivf_config.h`, `diskann_config.h`, `sparse_index_config.h`).

**Data types** (`include/knowhere/operands.h`)
- `fp32`, `fp16`, `bf16`, `int8`, `bin1` (binary), `sparse_u32_f32`.
- Conversion and typing live here; do not add ad-hoc casts at call sites.

**Error handling** (`include/knowhere/expected.h`)
- Custom `expected<T>` with a `Status` enum; check `Status::OK` and preserve typed status codes across wrapper boundaries.

**Dataset/context** (`include/knowhere/dataset.h`, `context.h`)
- `DataSet` carries base data, queries, and results; `Context` carries runtime knobs (thread pool, trace context).

## Index implementations

| Family | Path | Notes |
|--------|------|-------|
| Flat | `src/index/flat/flat.cc` | Brute force; fp32/fp16/bf16/int8/binary |
| HNSW | `src/index/hnsw/` | HNSW, HNSW_SQ, HNSW_PQ, HNSW_PRQ; `faiss_hnsw.cc` for the faiss-backed variant |
| IVF | `src/index/ivf/` | IVF_FLAT/SQ/PQ, IVF_RABITQ, BIN_IVF_FLAT, SCANN; `ivf_wrapper.cc`, `ivfrbq_wrapper.cc`, `ivfrbq_fastscan_wrapper.cc` |
| DiskANN | `src/index/diskann/` | DISKANN (`diskann.cc`) and AISAQ (`diskann_aisaq.cc`); requires `with_diskann=True` |
| Sparse | `src/index/sparse/` | SPARSE_INVERTED_INDEX, SPARSE_WAND; inverted-index and SINDI SIMD kernels (`sindi_simd_*.cc`) |
| MinHash | `src/index/minhash/` | MinHash LSH for binary/set data with Jaccard |
| GPU | `src/index/gpu_cuvs/` | cuVS-backed GPU_CAGRA, GPU_BRUTE_FORCE, GPU_IVF_FLAT/PQ; requires `with_cuvs=True` |
| Refine | `src/index/refine/` | Re-ranking wrappers such as DataViewRefiner used by SCANN/IVF_RABITQ |

Key params by family: HNSW uses `M`, `efConstruction`, `ef`; IVF uses `nlist`, `nprobe`; DISKANN/AISAQ uses `R`, `L`, `search_list_size`; Sparse BM25 uses `k1`, `b`, `avgdl`.

## Metrics

L2, IP (inner product), COSINE, Jaccard, Hamming, BM25. Each metric maps to a distance implementation in `src/simd/` or a scorer in the sparse index.

## Third-party dependencies

| Library | Location | Used by |
|---------|----------|---------|
| faiss | `thirdparty/faiss/` | IVF/PQ/flat building blocks, clustering |
| hnswlib | `thirdparty/hnswlib/` | HNSW graph |
| DiskANN | `thirdparty/DiskANN/` | DISKANN, AISAQ |
| Cardinal | `thirdparty/cardinalv1/`, `thirdparty/cardinalv2/` | Enterprise index extensions (optional `with_cardinal=True`) |

Treat `thirdparty/` as vendored upstream: prefer wrappers over forking modifications.
