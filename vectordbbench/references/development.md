# Development: code structure, tests, and verification

Confirm commands against the current `Makefile`, `pyproject.toml`, and `tests/` before running
them. This is a Python 3.11+ project; code is formatted by black (line-length 120) and linted
by ruff.

## Code structure

```
vectordb_bench/
├── __init__.py            # env-based `config` (datasets, timeouts, concurrency defaults)
├── interface.py           # BenchMarkRunner: submits/runs tasks, collects results
├── models.py              # TaskConfig, CaseConfig, CaseType, TaskStage, results models
├── metric.py              # Metric dataclass + recall/NDCG/MRR computations
├── backend/
│   ├── clients/           # one package per database: <name>.py, config.py, optional cli.py
│   │   ├── __init__.py    # DB enum + db2client resolution (init_cls/config_cls/case_config_cls)
│   │   ├── api.py         # VectorDB abstract class, DBConfig/DBCaseConfig, MetricType, IndexType
│   │   ├── milvus/        # Milvus wrapper + configs + CLI commands (17 commands)
│   │   ├── zilliz_cloud/
│   │   └── ...
│   ├── cases.py           # case type → case class mapping (type2case)
│   ├── assembler.py       # TaskConfig → per-case CaseRunners (Assembler)
│   ├── task_runner.py     # CaseRunner: drop/load/optimize/search stages; large-topk property
│   ├── dataset.py         # datasets (SIFT/GIST/Cohere/LAION/OpenAI/VIBE-HDF5/FTS) + size types
│   ├── data_source.py     # S3 / AliyunOSS / IR_DATASETS / Hugging Face readers
│   ├── payload.py         # PayloadProfile (ids_only | vector | text)
│   ├── filter.py          # Filter/FilterOp
│   └── result_collector.py
├── cli/
│   ├── cli.py             # click group `cli`, CommonTypedDict, run(), HNSW/IVF TypedDicts
│   ├── vectordbbench.py   # imports every client CLI module (registers commands)
│   └── batch_cli.py       # BatchCli + YAML batch runner
├── restful/app.py         # Flask REST API (init_bench_rest)
├── frontend/              # Streamlit UI (init_bench); pages/, components/, config/
├── results/               # published + local results JSON, leaderboard data
└── config-files/          # sample_config.yml, batch_sample_config.yml
```

## Adding a new client

Follow README "Adding New Clients" exactly:

1. `vectordb_bench/backend/clients/<name>/<name>.py` — subclass `VectorDB` (from `..api`) and
   implement the abstract methods (insert/search per case, load, filters, payloads as needed).
2. `vectordb_bench/backend/clients/<name>/config.py` — `DBConfig` (connection; use
   `pydantic.SecretStr` for secrets) and optional `DBCaseConfig` per index type.
3. Register in `vectordb_bench/backend/clients/__init__.py`: add to the `DB` enum and wire
   `init_cls` / `config_cls` / `case_config_cls`.
4. Optional `cli.py` — `TypedDict` with `click.option`-annotated fields, one `@cli.command()`
   function per index config, built with `click_parameter_decorators_from_typed_dict` and the
   `run()` helper from `vectordb_bench/cli/cli.py`; import the module in
   `vectordb_bench/cli/vectordbbench.py`.
5. Add a pydantic optional-dependency extra in `pyproject.toml` when the driver is not bundled.
6. Cover config validation, CLI wiring, and case behavior in `tests/test_<name>*.py`.

## Tests

pytest suite in `tests/` (`tests/pytest.ini`; markers: `integration` for external services).
Run focused tests from the repository root:

```bash
PYTHONPATH=. python3 -m pytest tests/test_milvus.py -q
PYTHONPATH=. python3 -m pytest tests/test_large_topk_cli.py tests/test_milvus_zilliz_cli.py -q
PYTHONPATH=. python3 -m pytest tests/test_bench_runner.py -k 'reuse' -q
```

Useful suites by area: `test_dataset.py`, `test_vibe.py`, `test_huggingface_parquet.py`
(datasets); `test_fts_*.py`, `test_fts_cases.py` (FTS); `test_large_topk_*.py` (TopK gating);
`test_cloud_*.py` (cloud cases); `test_insert_control_*.py`, `test_rate_runner*.py`
(load/concurrency runners); `test_<client>*.py` per database.

## Lint and format

```bash
make lint      # black --check + ruff check on vectordb_bench
make format    # black + ruff --fix
```

`pyproject.toml` selects a broad ruff rule set (E/F/C90/I/N/B/C/G/A/ANN/S/T/W/ARG/...) with
several ignores (e.g. `PLC0415` for client modules that import drivers lazily). Keep changed
lines within 120 columns and follow the existing per-client import style (lazy driver imports).

## Verification for common changes

| Change | Minimum evidence |
|---|---|
| Usage / parameter wiring | `vectordbbench <command> --dry-run ...` plus the client CLI test. |
| Config model change | The client's `tests/test_<client>_config.py` or `test_models.py`; pydantic validation. |
| New/updated backend client | Unit test for config + CLI, plus a mocked or integration run if available. |
| Case/metric change | `tests/test_fts_metrics.py`, `test_bench_runner.py`, or the matching case test. |
| Version/feature gate (e.g. TopK) | `tests/test_large_topk_*.py`, `tests/test_milvus_zilliz_cli.py`. |
| Dataset registration | `tests/test_dataset.py`, `tests/test_vibe.py`, `tests/test_huggingface_parquet.py`. |

Only run real loads (which download datasets and mutate the target database) when the user
authorizes them; prefer `--dry-run` and unit tests during iteration.
