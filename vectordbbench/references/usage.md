# VDBBench usage

VectorDBBench (VDBBench) benchmarks vector databases and cloud services on repeatable
insertion, vector search, filtered search, and full-text search (BM25) workloads. It ships
three entry points plus a batch runner:

| Entry point | Purpose |
|---|---|
| `vectordbbench` | Click CLI: run a single client/command, or a batch via `--config-file` / `BatchCli`. |
| `init_bench` | Streamlit web UI at `vectordb_bench/frontend/vdbbench.py` (run/compare results, custom datasets). |
| `init_bench_rest` | Minimal Flask REST API at `vectordb_bench/restful/app.py`. |

Confirm exact commands, options, and defaults against `vectordbbench --help` and
`vectordbbench <command> --help` for the current checkout, and against
`vectordb_bench/cli/cli.py` and the per-client `cli.py` modules.

## Installation

```bash
python >= 3.11
pip install vectordb-bench                        # pymilvus + zilliz_cloud by default
pip install 'vectordb-bench[pinecone]'            # add an optional client extra
```

Optional client extras live in `pyproject.toml` `[project.optional-dependencies]`
(e.g. `qdrant`, `pinecone`, `weaviate`, `elastic`, `pgvector`, `pgvecto_rs`, `redis`,
`chromadb`, `mongodb`, `tidb`, `cockroachdb`, `clickhouse`, `vespa`, `lancedb`,
`oceanbase`, `doris`, `zvec`, `endee`, `lindorm`, `volc_mysql`, `adbpg`, `restful`).
For development: `pip install -e '.[test]'` then `python -m vectordb_bench`.

## Configuration (.env / config)

Defaults are loaded from `vectordb_bench/__init__.py` `config` via `environs` (`.env` file):

- `LOG_LEVEL`, `LOG_FILE` (default `logs/vectordb_bench.log`)
- `DEFAULT_DATASET_URL` / `DATASET_SOURCE` (`S3` | `AliyunOSS` | `IR_DATASETS`)
- `DATASET_LOCAL_DIR` (default `/tmp/vectordb_bench/dataset`)
- `LOAD_CONCURRENCY` (0 = cpu_count), `USE_SHUFFLED_DATA`, `DROP_OLD`
- `NUM_CONCURRENCY` (comma list of concurrency levels)
- `RESULTS_LOCAL_DIR` (default `vectordb_bench/results`), `CONFIG_LOCAL_DIR`
- `CLOUD_INSERT_READINESS_TIMEOUT`, `CLOUD_INSERT_READINESS_POLL_INTERVAL`

## CLI structure

The `vectordbbench` group registers one command per client index configuration. Command
names are the lowercase function names imported in `vectordb_bench/cli/vectordbbench.py`.
Milvus commands include: `milvusautoindex`, `milvusflat`, `milvushnsw`, `milvushnswpq`,
`milvushnswprq`, `milvushnswsq`, `milvusivfflat`, `milvusivfsq8`, `milvusivfrabiq`,
`milvusdiskann`, `milvusgpuivfflat`, `milvusgpuivfpq`, `milvusgpubruteforce`,
`milvusgpucagra`, `milvussvsvamana`, `milvussvsvamanalvq`, `milvussvsvamanaleanvec`,
`milvusfts`.

### Common options (from `CommonTypedDict` in `vectordb_bench/cli/cli.py`)

- `--config-file PATH` — YAML defaults map per command (see `vectordb_bench/config-files/sample_config.yml`).
- `--case-type` — one of the `CaseType` names (see below).
- `--db-label`, `--task-label`, `--note` / `--note-file` (mutually exclusive run context).
- `--dry-run` — print the assembled task configuration and exit without running.
- Stage toggles: `--drop-old/--skip-drop-old`, `--load/--skip-load`,
  `--search-serial/--skip-search-serial`, `--search-concurrent/--skip-search-concurrent`.
  Dropping old data is required when loading; loading is required when dropping.
- `--k` — top-k neighbors; LAION 100M selects tiered ground truth automatically up to 1,000,000.
- `--num-concurrency` (comma list), `--concurrency-duration`, `--concurrency-timeout`, `--serial-cooldown`.
- `--load-concurrency`, `--insert-batch-size`, `--streaming-insert-rate`.
- `--dataset-with-size-type` — `DatasetWithSizeType` choice (e.g. `"Medium Cohere (768dim, 1M)"`).
- `--dataset-name` — registered `Performance` dataset choice (e.g. `glove-200-cosine`).
- `--payload-profile` — `ids_only` (default) or `vector` for vector performance / cloud payload / FTS cases.
- `--filter-rate` (NewIntFilterPerformanceCase), `--label-percentage` (LabelFilterPerformanceCase).
- `--fts-filter-rate`, `--bm25-k1`, `--bm25-b` (FTSBm25Performance).
- Cloud case options: `--cloud-filter-rate`, `--cloud-label-percentage`, `--cloud-cold-query-count`,
  `--cloud-insert-duration`, `--cloud-insert-readiness-timeout`,
  `--cloud-insert-readiness-poll-interval`, `--tenant-count`, `--tenant-prefix`, `--tenant-id-width`.
- Custom dataset options: `--custom-case-*`, `--custom-dataset-*` (see Custom datasets below).

Client-specific options are defined in each client's `cli.py` TypedDict (e.g. Milvus:
`--uri`, `--user-name`, `--password`, `--num-shards`, `--replica-number`,
`--collection-name`, `--use-partition-key/--no-use-partition-key`; HNSW/SQ/PQ/IVF/GPU/SVS
index parameters such as `--m`, `--ef-construction`, `--ef-search`, `--nlist`, `--nprobe`,
`--sq-type`, `--refine`, `--refine-type`, `--refine-k`, `--nrq`, `--rbq-bits-query`,
`--search-list`, `--cache-dataset-on-device`, `--refine-ratio`, `--metric-type`, `--limit`,
`--svs-graph-max-degree`, `--svs-storage-kind`, etc.).

### Example commands

```bash
# Milvus self-hosted, AUTOINDEX, Cohere medium performance case
vectordbbench milvusautoindex --uri http://localhost:19530 \
  --case-type Performance1536D50K --k 100

# Milvus HNSW with explicit index params
vectordbbench milvushnsw --uri http://localhost:19530 \
  --case-type Performance1536D500K --m 16 --ef-construction 128 --ef-search 128

# LAION 100M large TopK (requires Milvus >= 2.6.14, see version-matching.md)
vectordbbench milvusautoindex --uri http://localhost:19530 \
  --case-type NewIntFilterPerformanceCase \
  --dataset-with-size-type "Large LAION (768dim, 100M)" --filter-rate 0.99 --k 1000000

# Registered Hugging Face / VIBE dataset via the Performance case
vectordbbench milvushnsw --case-type Performance --dataset-name glove-200-cosine --k 100

# Vector payload profile (IDs + result vectors)
vectordbbench milvusautoindex --uri http://localhost:19530 \
  --case-type Performance768D100M --k 1000000 --payload-profile vector

# FTS BM25 on Milvus (MS MARCO small by default)
vectordbbench milvusfts --uri http://localhost:19530
```

## Case types (`CaseType` in `vectordb_bench/models.py`)

- **Capacity**: `CapacityDim128`, `CapacityDim960` — insert until full; reports `max_load_count`.
- **Search Performance**: `Performance768D100M` (LAION 100M), `Performance768D10M`/`Performance768D1M`
  (Cohere), `Performance1536D5M`/`Performance1536D500K`/`Performance1536D50K` (OpenAI),
  plus `...1P`/`...99P` label-filter variants and `PerformanceCustomDataset` / `Performance`
  (registered datasets). Reports QPS, recall, serial p50/p95/p99, concurrent QPS/latency per
  concurrency level, `recall_at` cutoffs, and load duration.
- **Filtered search**: `NewIntFilterPerformanceCase` (`--filter-rate`), `LabelFilterPerformanceCase`
  (`--label-percentage`).
- **Full-text search**: `FTSBm25Performance` — BM25 retrieval over MS MARCO / HotpotQA; metrics
  recall/MRR/NDCG plus QPS and latency; payload `ids_only` or `text`.
- **Streaming**: `StreamingPerformanceCase` / `StreamingCustomDataset` — sustained insertion
  (`--streaming-insert-rate`) under load.
- **Cloud leaderboard**: `CloudInsertCase`, `CloudPayloadSearchCase`, `CloudColdLatencyCase`,
  `CloudMultiTenantSearchCase` — production-oriented managed-service cases
  (see `docs/release/2026-05-cloud-leaderboard.md`).

## Datasets

- **Vector datasets** (`vectordb_bench/backend/dataset.py`): SIFT, GIST, Cohere (768d,
  100K/1M/10M), LAION (768d, 100M with tiered TopK artifacts), OpenAI (1536d, 50K/500K/5M),
  VIBE HDF5 (24 registered datasets), VDBBench multimodal Parquet (1M/10M/100M).
- **Registered datasets** via `--dataset-name` on the `Performance` case; catalog in
  `REGISTERED_DATASETS` (`vectordb_bench/backend/cli/cli.py`) and
  `docs/release/2026-09-hugging-face-datasets.md`.
- **FTS datasets** (`FtsDatasetWithSizeType`): MS MARCO and HotpotQA in small/medium/large.
- **Custom datasets** (`/custom` page or CLI): folder of Parquet files — `train.parquet`
  (id + emb float32) and optional split files `train-[i]-of-[n].parquet`, `test.parquet`
  (queries), `neighbors.parquet` (ground truth). Shuffled data uses `shuffle_train*.parquet`.

## Batch runs

`vectordbbench batchcli --batch-config-file <yaml>` runs multiple sub-commands from a YAML
file whose top-level keys are sub-command names and values are lists of per-run option maps
(see `vectordb_bench/config-files/batch_sample_config.yml`). Per-command YAML defaults are
read with `--config-file` (see `sample_config.yml`).

## Web UI (init_bench)

Streamlit app at `vectordb_bench/frontend/vdbbench.py`; pages live under
`vectordb_bench/frontend/pages/`. The result page compares runs by `task_label`; the run-test
page selects databases, case types, and parameters; the custom page registers local datasets.
Only one task runs at a time (`benchmark_runner` in `vectordb_bench/interface.py`).

## REST API (init_bench_rest)

Flask app in `vectordb_bench/restful/app.py`:

- `GET /get_res?task_label=<label>` — formatted results for a label.
- `GET /get_status` — running state, task count, current task index.
- `GET /stop` — stop the running benchmark.
- `POST /run` — submit a benchmark task (JSON body of `TaskConfig`-style fields).

## Results

Runs are written under `RESULTS_LOCAL_DIR` (default `vectordb_bench/results/`) as result JSON
(one `TestResult` per run, `CaseResult` per case, metrics from `vectordb_bench/metric.py`).
`dbPrices.json`, `leaderboard*.json`, and per-vendor directories hold the published standard
results. Key metrics: `qps`, `recall`, `recall_at`, `ndcg`, `mrr`, `serial_latency_p*`,
`conc_*_list`, `load_duration`, `insert_duration`, `optimize_duration`, `max_load_count`,
`payload_profile`.

## Timeouts

Defined in `vectordb_bench/__init__.py` `config` and enforced by the runners. Capacity cases
get an overall loading timeout (24h); other cases get a data-loading timeout and an
optimization-preparation timeout, scaled by dataset size (see README "Timeout" table).
