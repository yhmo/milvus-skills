# Branch differences: 2.6 vs 3.0 vs main

The other references describe the `main` baseline. The `3.0` and `2.6`
maintenance branches differ significantly in index coverage and sparse-index
implementation. Read this overlay in addition to the baseline references when
working on a maintenance branch.

Confirm the branch first:

```bash
git branch --show-current
```

## Branch roles

| Branch | Role |
| --- | --- |
| `main` | active development line |
| `3.0` | current released 3.0 line |
| `2.6` | current released 2.6 line |

## Feature areas absent from maintenance branches

The following exist on `main` but not on `3.0`/`2.6` (or only partially):

### Present only on main (absent on both 3.0 and 2.6)

- **Sparse inverted-index rewrite**: `src/index/sparse/codec/` (simd
  bitpacking, streamvbyte, maskedvbyte, adaptive), `src/index/sparse/searcher/`
  (block-max WAND/DAAT, TAAT), `src/index/sparse/sindi_*.h` (SINDI variants),
  `aligned_allocator.h`, `block_inverted_index.h`, `flatten/growable
  inverted_index.h`, `parallel_build.h`, `scorer.h`
- **SVS index**: `src/index/svs/` (`svs_flat.cc`, `svs_ivf.cc`,
  `svs_vamana.cc`, `svs_config.h`, `svs_utils.h`)
- **Faiss direct integration**: `src/index/faiss/` (`faiss.cc`,
  `faiss_config.h`, `faiss_dispatch.cc/.h`)
- **Emb-list strategies**: `src/index/emb_list/` (lemur, muvera, token_ann,
  simple_mlp, cblas_decl) and `include/knowhere/index/emb_list_strategy.h`
- **MRL index**: `src/index/mrl_index_node.cc`,
  `include/knowhere/index/mrl_index_node.h`
- **Clustering kmeans**: `src/cluster/kmeans/` (faiss_kmeans.cc,
  kmeans_config.h) and `include/knowhere/cluster/compaction_result.h`
- **Build scheduler and cancellation**: `src/common/build_scheduler.cc`,
  `src/common/cancellation.cc`, `include/knowhere/build_scheduler.h`
- **Misc headers**: `adaptive_store.h`, `array_store.h`, `id_map.h`,
  `mmap.h`, `segcore_error_code.h`, `comp/search_hint.h`,
  `index/clustering_config.h`
- **SIMD LSX/LASX**: `src/simd/distances_lsx.cc/.h`,
  `src/simd/distances_lasx.cc/.h`

### Present on main and 3.0, absent on 2.6

- HNSW RaBitQ wrappers: `IndexHNSWRaBitQWrapper.cc/.h`,
  `RaBitQSearchParameters.h`, `HnswSearchDispatch.h`
- IVF RaBitQ fastscan: `ivfrbq_fastscan_wrapper.cc/.h`

## Rules when on a maintenance branch

1. Do not reference the files or features listed above as present — check
   the branch column first.
2. If a task references a symbol not found on the current branch, check
   whether it belongs to the `main` line and inform the user rather than
   guessing.
3. Verify from source: `git ls-tree -r --name-only source/<branch> -- src/ | grep <name>`.
