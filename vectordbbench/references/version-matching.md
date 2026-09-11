# Milvus / Zilliz version matching

This file documents how VDBBench pins and gates against Milvus and Zilliz Cloud versions so
that AI agents pick compatible targets, avoid unsupported parameters, and explain failures
accurately. Always verify against the current `pyproject.toml` pins, the Milvus client wrapper
(`vectordb_bench/backend/clients/milvus/*`), and the current Milvus/Zilliz release notes before
recommending a server or feature.

## Pinned client (pymilvus)

`pyproject.toml` pins the driver that all Milvus and Zilliz Cloud benchmarks run through:

```toml
"pymilvus>=2.6.15,<3.0.0",   # with pandas, numpy
```

- VDBBench talks to Milvus through `pymilvus.MilvusClient` over gRPC/HTTP using a `uri`
  (`http://host:port`), optional `user`/`password`/`token` (`MilvusConfig` in
  `backend/clients/milvus/config.py`).
- `pymilvus` is a hard dependency (bundled with the base install); all other databases are
  optional extras. Raising the pinned `pymilvus` floor may be needed to pick up a Milvus
  server feature, but stay below the `<3.0.0` ceiling until VDBBench is validated against it.
- Milvus Lite (embedded) works when the `uri` points at a local Milvus Lite file/instance, but
  the large-TopK and GPU features below require a real server.

## Milvus server / Zilliz Cloud compatibility

- Self-hosted Milvus 2.x is benchmarked via its gRPC URI. The same `Milvus` wrapper backs
  Zilliz Cloud through `backend/clients/zilliz_cloud/` (Serverless/Standard via a cloud
  `uri`/`token`).
- The wrapper creates one collection per run (`--collection-name`, default `VDBBench`), uses
  `drop_old` to drop it, and issues `query_mode=large_topk` collection properties when needed
  (see below). Reused collections are validated and rejected when their property is
  incompatible.
- Metrics sent to Milvus use the configured `MetricType` (`L2`, `COSINE`, `IP`, `DP`). GPU
  brute-force/IVF indexes map COSINE to L2 in `MilvusIndexConfig.parse_metric()` because those
  GPU indexes only support IP/L2; the dataset is normalized for COSINE in that case.

## Feature gates to match against server version

### Large TopK (`query_mode=large_topk`)

Gated in `vectordb_bench/backend/task_runner.py`:

```python
MILVUS_DEFAULT_TOPK_LIMIT = 16_384
LARGE_TOPK_QUERY_MODE_DBS = frozenset({DB.Milvus, DB.ZillizCloud})
```

- When `k > 16_384` on a `Performance`-label case for Milvus or Zilliz Cloud, VDBBench sets the
  `query_mode=large_topk` collection property at collection creation, before the vector index
  is built.
- **Self-hosted Milvus must be 2.6.14 or later** — the release that introduced the property.
  Earlier servers accept the property without honoring it (wrong/limited TopK behavior), so
  prefer 2.6.14+ for any run with `--k > 16384`. Zilliz Cloud supports it on the corresponding
  tiers.
- Other backends forward `k` unchanged; VDBBench does not alter their collection properties.
- LAION-100M itself caps `k` at 1,000,000 and restricts integer-filter rates by published
  ground-truth width (see README and `backend/dataset.py`).

### Full-text search (BM25)

`MilvusFTS` (CLI command `milvusfts`, case `FTSBm25Performance`) uses Milvus full-text search:
the schema adds an analyzer-enabled VARCHAR `text` field plus a sparse vector index
(`enable_analyzer=True`, default analyzer `english`) and builds BM25-style retrieval
(`backend/clients/milvus/milvus.py`, `config.py` `MilvusFtsConfig`). FTS on Milvus requires a
server with full-text search support (Milvus 2.5+; Zilliz Cloud full-text search tier). Verify
the exact server floor against current Milvus release notes before recommending.

### GPU indexes

Milvus GPU commands (`milvusgpuivfflat`, `milvusgpuivfpq`, `milvusgpubruteforce`,
`milvusgpucagra`) require a Milvus server deployed with GPU nodes (cuVS-backed indexes
`IndexType.GPU_*`). They only support IP/L2 metrics and take GPU-specific parameters
(`--cache-dataset-on-device`, `--refine-ratio`, CAGRA graph/search params).

### Quantized / refined indexes

Milvus index configs in `backend/clients/milvus/config.py` map 1:1 to server index types;
each requires server support matching its release:

- `HNSW_SQ` (`--sq-type` SQ4U/SQ6/SQ8, `--refine`, `--refine-type` SQ6/SQ8/BF16/FP16/FP32,
  `--refine-k`), `HNSW_PQ` (`--nbits`), `HNSW_PRQ` (`--nrq`).
- `IVF_RABITQ` (`--rbq-bits-query` SQ1..SQ8/0, refine options).
- `DISKANN` (`--search-list`), `SVS` Vamana (`svs_*` params) and LeanVec/LVQ storage kinds.
- `AUTOINDEX`, `FLAT`, `IVF_FLAT`, `IVF_SQ8` map to the always-available Milvus index types.

If a server rejects an index/param, first confirm the server version supports that index and
parameter spelling before changing the client.

### Partition key / multitenancy

`use_partition_key` is enabled by default for `CloudMultiTenantSearchCase` and toggleable with
`--use-partition-key/--no-use-partition-key`; it relies on Milvus partition-key support on the
`label` field (Zilliz Cloud Serverless/Standard and Milvus >= 2.4 line). Filter cases use
int-range (`id >= n`) and label-equality (`label == 'x'`) expressions gated by
`supported_filter_types` on the client.

## Choosing a target version

1. Default to the latest self-hosted Milvus 2.x that satisfies the feature floor for the case
   (`2.6.14+` for large TopK, FTS-capable 2.5+ for `milvusfts`, GPU build for GPU indexes).
2. Keep `pymilvus` at `>=2.6.15,<3.0.0`; do not recommend a `3.x` driver for VDBBench.
3. For Zilliz Cloud, prefer Serverless for small/medium cases and Standard for large/GPU cases;
   confirm the tier supports the requested index and TopK.
4. Document the chosen server + driver versions in `--note` / `--note-file` so results stay
   reproducible (never put credentials in notes).
