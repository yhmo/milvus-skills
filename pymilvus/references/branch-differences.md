# Branch differences: 2.6 vs 3.0

Use this when working on a specific PyMilvus release branch. The unified
descriptions in other references target the `master`/`3.0` line; the `2.6`
maintenance branch differs in project layout, public API, and Python version.
Always check the current branch before applying branch-sensitive knowledge.

Verify the branch first:

```bash
git branch --show-current
git fetch source   # or the remote pointing to milvus-io/pymilvus
```

## Project layout: similarities and differences

Both branches share the same top-level structure (`pymilvus/`, `tests/`,
`examples/`, `Makefile`, `pyproject.toml`) and the same subdirectory layout
under `pymilvus/` (`milvus_client/`, `client/`, `orm/`, `grpc_gen/`,
`bulk_writer/`, `model/`). The differences are:

| Path | 2.6 | 3.0 / master |
| --- | --- | --- |
| `pymilvus/function_chain/` | absent | present |
| `pymilvus/client/bloom_filter.py` | absent | present |
| `pymilvus/client/roaring_filter.py` | absent | present |
| `pymilvus/client/search_aggregation.py` | absent | present |
| `pymilvus/client/iterator/` | absent (flat files) | present (subdirectory) |
| `.github/workflows/auto-cherrypick.yml` | absent | present |
| `.github/workflows/update-milvus-pymilvus-dev.yml` | absent | present |

Examples live in `examples/` on both branches. File sets differ between
branches; always verify a target example exists on the current branch before
running or referencing it.

## Public API export differences (`pymilvus/__init__.py` `__all__`)

3.0/master exports the following names that do not exist in 2.6:

- `FunctionChain`, `FunctionChainStage`
- `BloomFilterBuilder`, `build_bloom_filter`
- `RoaringBitmapBuilder`, `build_roaring_bitmap`
- `SearchAggregation`, `AggregationBucket`, `AggregationHit`, `TopHits`
- `CompactionTaskState`, `CompactionType`, `SegmentState`

If a task on the 2.6 branch references any of these names, the symbol does not
exist there. Do not try to "find" it — confirm the branch first.

## `MilvusClient` / `AsyncMilvusClient` method differences

3.0/master adds approximately 30 public methods that are absent in 2.6,
including:

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

The same gaps apply to `AsyncMilvusClient` on 2.6.

## Python version requirements

### 2.6 branch

- `pyproject.toml` `requires-python = '>=3.8'`
- CI tests Python 3.8 and 3.14 (Ubuntu and Windows)
- Makefile `CODEGEN_PYTHON = >=3.8,<3.14`
- Do not introduce Python 3.9+ syntax (match statements, `X | Y` type unions
  in annotations without `from __future__ import annotations`, built-in
  generic subscripts in annotations, etc.)

### 3.0 / master branch

- `pyproject.toml` `requires-python = '>=3.9'`
- CI tests Python 3.9 and 3.14 (Ubuntu and Windows)
- Makefile `CODEGEN_PYTHON = >=3.9,<3.14`

## Syncing the milvus-proto submodule

Each branch pins its own `milvus-proto` submodule commit. After checking out
the target branch, sync the submodule to the branch-specified commit:

```bash
git submodule update --init pymilvus/grpc_gen/milvus-proto
```

Or, if the submodule is already initialized but out of date:

```bash
git submodule update pymilvus/grpc_gen/milvus-proto
```

Do not manually `cd` into the submodule and check out an arbitrary commit —
always let `git submodule update` resolve the pin from the current branch's
tree. After syncing, regenerate proto output only if the branch's proto source
changed.

## Rules for branch-sensitive work

1. Read `git branch --show-current` before applying any architecture, API, or
   dependency knowledge from other references.
2. If on `2.6`, follow the 2.6 Python version constraints above.
3. If on `2.6`, do not reference `function_chain`, `bloom_filter`,
   `roaring_filter`, `search_aggregation`, or the snapshot/segment/file-resource
   client methods — they do not exist.
4. If proto output seems inconsistent, sync the submodule first (see above)
   before diagnosing.
5. If a task references a symbol not found on the current branch, check whether
   it belongs to the other line and inform the user rather than guessing.
