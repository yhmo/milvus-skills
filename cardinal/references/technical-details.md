# Technical Details

Use this reference for architecture, source placement, and repository-consistent changes on the current active line.

## Contents

- Architecture layers
- Source layout
- Key patterns (Owner/View, Compose, Concepts, DataSet)
- Metrics
- Quantization
- Search and build paths
- Serialization and storage
- The `know/` Knowhere adapter
- Change checklists
- Tracing

## Architecture layers

Cardinal is a three-layer hierarchical design. Lower layers cannot manipulate upper-layer objects:

```text
Algorithm Layer (KMeans, Filter, Operators: bf_core, graph_operator, range_filter, scan_operator)
    ↕
Data Layer (Computer, VecLoader, Dataset, Graph/IVF, Quantization)
    ↕
Storage Layer (Allocator, Storage, IO, Serialization)
```

- **Storage layer** owns bytes: storage format and I/O (fixed/variable length, aligned or not, memory/disk/mmap). It does not interpret data.
- **Data layer** interprets bytes: sparse/dense, fp32/bf16/int8/etc., single/multiple rows; hides storage and gives the algorithm layer a unified interface.
- **Algorithm layer** implements algorithms only; it must not care how data is organized underneath.

See `docs/design.md` for the canonical statement of the layers and the Quick Start walkthrough.

## Source layout

- `include/cardinal/`: public headers installed for downstream; must compile with **C++17** and may only include other `/include` files.
- `cardinal/`: main library source.
  - `compute/`: distance computation and the computer factory.
  - `data/`: `DataSet`, `DataLoader`, `VecLoader`, vector types (dense/sparse, e4m7, uint4/uint20, etc.).
  - `graph/`: graph structures — `MatrixGraph`, `IntCompressedGraph`, `CombinedGraph`, `DynamicGraph`, `EdgeList`, `GraphLocker`.
  - `searcher/`: search implementations — `MemGraphSearcher`, `DiskGraphSearcher`, `IVFSearcher`, `BruteForceSearcher`, `Refiner`, `SearchDispatcher`, context and prefetch optimizer.
  - `transformer/`: data transforms and graph/ivf/mv builders (`graph_builder/`, `ivf_builder/`, `mv_builder/`).
  - `quant/`: quantization — SQ4/SQ8 (`sqn_quant.h`), RBQ (`rbq_*.h` incl. Matroska/split), SAQ (`saq_*.h`), bitwriter, rotations.
  - `operator/`: algorithm operators — `bf_operator`, `graph_operator`, `vector_operator`, `scan_operator`, `search_topk`, `range_filter`.
  - `storage/`: `Storage`, `ChunkedStorage`, `ComposedChunkedStorage`, `MemoryStorage`, `DiskStorage`, pool buffer, translator.
  - `io/`: `aio_pool`, `aio_reader`, `mmap`, `mmap_advice`, file IO.
  - `alloc/`: memory allocators (plain, hugepage, mmap).
  - `algo/`, `kmeansfast/`: KMeans/clustering.
  - Top-level: `metric.h`, `type/`, `common/`, `config.h`, `quantization_config.h`, `*_params.h` (e.g. `rbq_params.h`, `saq_params.h`, `qtip_params.h`), `search_result.h`, `reorder_record.h`, `exception.h`, `macros.h`, `memory.h`, `mmapable_array.h`.
- `know/`: Knowhere integration adapter — `cardinal.cc`, `cardinal_adapter.h`, `cardinal_index_table.cc`, `cardinal_cluster.cc`, config headers.
- `aquila/`: clustering/dedup module (`iforest`, `vector_ops`, `bin_file`, `materialize`) with its own `aquila_test` binary.
- `tests/`: Catch2 unit tests (`test_cardinal`), explicit file list in `tests/CMakeLists.txt`.
- `example/`: runnable snippets matching the `docs/design.md` Quick Start.
- `third_party/`: vendored deps — helpa (SIMD distances), highway, icmprs, kmeans_fast, pipnn, rabitq, smalltopk.
- `docs/design.md`: architecture and conventions.

## Key patterns

- **Owner vs View types**: owner types own resources and are move-only; view types do not own resources and are copyable. Do not store view types as class members; use them transiently.
- **Chained Builder/Searcher via `Compose()`**: builders and searchers compose into multi-stage pipelines. E.g. a Vamana builder is two MRNG builders chained; NSG is NNDescent + MRNG; search pipelines chain a coarse searcher plus one or more `Refiner` stages.
- **Template + Concepts**: heavy use of C++20/23 concepts to constrain template parameters; general types should have a concept constraint.
- **Unified `DataSet` interface**: all vector data (dense, sparse, quantized) lives in `DataSet`. Convert type with `.AsType<>()` and storage with `.ToStorage<>()`; use `.Get(i)` for a row, and change allocator by choosing the storage template parameter (e.g. `FixedLengthMemStorage<alloc::MmapAllocator>`).
- **VecLoader**: wraps a `DataSet` and adds processing (normalization, shuffle, batch read) to decouple data handling from algorithms.
- **MetricTag / compile-time pruning**: metrics are constexpr (`MetricTag<metric>`), and `ENABLE_COMPILE_PRUNE` selects runtime/dynamic metrics vs compile-time unrolled ones. Keep both paths consistent when touching metric-dependent code.
- **RAII** for every resource acquisition; no manual cleanup.

## Metrics

Supported: `L2`, `IP`, `Cosine`, `Hamming`, `Jaccard` (plus `Dynamic` and `None`), defined in `cardinal/metric.h`. Distance computation is dispatched through `compute/`; `MakeSymComputer`/`MakeAsymComputer` create symmetric/asymmetric computers from a `VecLoader`.

## Quantization

- SQ4/SQ8 (Scalar Quantization): `sqn_quant.h`.
- RBQ (Residual-Based Quantization): `rbq_quant.h` with Matroska extensions (`rbq_matroska_*.h`) and split variants (`rbq_split_*.h`); params in `rbq_params.h`.
- SAQ (Scalar Anisotropic Quantization): `saq_quant.h`, impl in `saq_impl*.h`.
- Rotation transforms (PCA) in `rotations*.h`; `bitwriter` for packed output.
- Quantized data is stored in `DataSet`; `Encode(dataset)` returns the encoded dataset usable directly by computers/builders/searchers.

## Search and build paths

- Build: `transformer/graph_builder/`, `ivf_builder/`, `mv_builder/`; graphs are `MatrixGraph<>` (memory) and can be compressed (`AsCompressed()` to `IntCompressedGraph`).
- Search: `MemGraphSearcher`, `DiskGraphSearcher`, `IVFSearcher`, `BruteForceSearcher` implement `search::Searcher` interfaces in `searcher/`; `Dispatcher`/`SearchDispatcher` select implementations; `Refiner` re-ranks candidates against higher-precision or disk data.
- `Searcher.Preheat(dataset, sample_query, config)` optimizes before search. Search results are `SearchResult` rows with `GetId()`.

## Serialization and storage

- Serialization is performed at the data layer in a **unified format**; graph for disk and memory search is serialized identically and deserialized into different layouts. See `serialization/`.
- Storage backends: memory (`MemoryStorage`/`FixedLengthMemStorage`), disk (`DiskStorage` with libaio path), mmap (`MmapAllocator`, `mmapable_array.h`), plus `ChunkedStorage`/`ComposedChunkedStorage` and a `pool_buffer`.
- The `build/` tree and `CMakeLists.txt` define the Conan `cmake_layout`; shared library target is `cardinal_shared` (linked by tests) and installed component `Cardinal::cardinal`.

## The `know/` Knowhere adapter

- `cardinal.cc`, `cardinal_adapter.h`: expose Cardinal builders/searchers through Knowhere's index interface.
- `cardinal_index_table.cc`: index table / configuration mapping.
- `cardinal_cluster.cc`: cluster-level (multi-node) integration.
- `local_mem_output_stream.h`: adapts Cardinal serialization output to Knowhere's stream model.
- Keep adapter behavior aligned with Knowhere's contracts (e.g. explicit emb-list counts, dataset metadata access).

## Change checklists

For a new algorithm path (build or search):

1. Public header in `include/cardinal/` (C++17-safe) and implementation in `cardinal/`.
2. Data representation through `DataSet`/`VecLoader`; add concepts for new template parameters.
3. Operator or computer wiring in `cardinal/operator/` or `cardinal/compute/`.
4. Searcher/builder chaining via `Compose()` where pipelines are expected.
5. Config through the appropriate `*_params.h`/`quantization_config.h` and `config.cpp`.
6. Unit test in `tests/` and entry in `tests/CMakeLists.txt`; add examples only for user-visible workflows.

For serialization/compatibility changes:

1. Identify the index version gate (e.g. nullable id-map v10/v11) and all readers/writers.
2. Keep both synchronous and asynchronous build paths consistent.
3. Preserve back-compat for older on-disk formats; add compatibility tests (`test_compatibility.cpp`).
4. Verify round-trip and cross-version reads.

## Tracing

Prefer:

```bash
rg -n "MemGraphSearcher|DiskGraphSearcher|IVFSearcher" cardinal/searcher know tests
rg -n "SQ4Quant|RBQQuant|SAQQuant|Encode\(|AsCompressed" cardinal tests
rg -n "DataSet|MakeVecLoader|MakeSymComputer" cardinal example tests
rg -n "MetricTag|ENABLE_COMPILE_PRUNE" cardinal/metric.h cardinal/compute
rg -n "CardinalIndex|cardinal_adapter" know
```

Use `$SKILL_DIR/scripts/repo-context.sh` (this skill's `scripts/` directory) for a current-checkout snapshot.
