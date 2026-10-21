# 2.6 branch overlay

The other references describe the `master`/`3.0` baseline. On the `2.6`
maintenance branch, the following differs. Read this overlay in addition to
the baseline references when working on `2.6`.

Confirm the branch first:

```bash
git branch --show-current
```

## Layout: what 2.6 lacks compared to the baseline

The top-level structure (`pymilvus/`, `tests/`, `examples/`, `Makefile`,
`pyproject.toml`) and the core subdirectories (`milvus_client/`, `client/`,
`orm/`, `grpc_gen/`, `bulk_writer/`, `model/`) are the same as the baseline.
The following paths that the baseline references describe do **not** exist on
2.6:

- `pymilvus/function_chain/`
- `pymilvus/client/bloom_filter.py`
- `pymilvus/client/roaring_filter.py`
- `pymilvus/client/search_aggregation.py`
- `pymilvus/client/iterator/` (2.6 uses flat files instead of this subdirectory)
- `.github/workflows/auto-cherrypick.yml`
- `.github/workflows/update-milvus-pymilvus-dev.yml`

Examples live in `examples/` on both branches; file sets differ. Verify a
target example exists on the current branch before running or referencing it.

## Public API: names absent from 2.6 `__all__`

The baseline `technical-details.md` lists public exports that include the
following; none of them exist on 2.6:

- `FunctionChain`, `FunctionChainStage`
- `BloomFilterBuilder`, `build_bloom_filter`
- `RoaringBitmapBuilder`, `build_roaring_bitmap`
- `SearchAggregation`, `AggregationBucket`, `AggregationHit`, `TopHits`
- `CompactionTaskState`, `CompactionType`, `SegmentState`

## Client methods absent from 2.6

The baseline describes `MilvusClient` and `AsyncMilvusClient` methods that
include the following; none of them exist on 2.6:

- Snapshot management: `create_snapshot`, `list_snapshots`,
  `restore_snapshot`, `drop_snapshot`, `describe_snapshot`,
  `pin_snapshot_data`, `unpin_snapshot_data`,
  `list_restore_snapshot_jobs`, `get_restore_snapshot_state`
- Session: `session`
- Segments and compaction: `list_segments`, `list_compaction_tasks`
- Struct/function fields: `add_collection_struct_field`,
  `add_function_field`, `drop_function_field`, `drop_collection_field`
- File resources: `add_file_resource`, `list_file_resources`,
  `remove_file_resource`
- External collection refresh: `refresh_external_collection`,
  `list_refresh_external_collection_jobs`,
  `get_refresh_external_collection_progress`
- Schema alteration: `_alter_collection_schema`

To quickly check whether a symbol exists on the current branch:

```bash
git show source/2.6:pymilvus/milvus_client/milvus_client.py | grep 'def <method_name>'
```

## Python version: 2.6 constraints

The baseline states `requires-python >=3.9`; on 2.6 it is `>=3.8`:

- CI tests Python 3.8 and 3.14 (not 3.9)
- Makefile `CODEGEN_PYTHON = >=3.8,<3.14`
- Do not introduce Python 3.9+ syntax (match statements, `X | Y` type unions
  in annotations without `from __future__ import annotations`, built-in
  generic subscripts in annotations, etc.)

## Proto submodule

Each branch pins its own `milvus-proto` commit. Sync it after checking out
the target branch:

```bash
git submodule update --init pymilvus/grpc_gen/milvus-proto
```

Do not manually `cd` into the submodule and check out an arbitrary commit.

## Rules when on 2.6

1. Do not reference the directories, exports, or methods listed above — they
   do not exist on this branch.
2. Write Python 3.8-compatible code only.
3. If a task references a symbol not found on this branch, check whether it
   belongs to the baseline line and inform the user rather than guessing.
