# 2.6 branch overlay

The other references describe the `main` baseline. On the `2.6`
maintenance branch, the following differs. Read this overlay in addition to
the baseline references when working on `2.6`.

Confirm the branch first:

```bash
git branch --show-current
```

## Crate version and dependencies

| | 2.6 | main (baseline) |
| --- | --- | --- |
| Crate version | `2.6.1` | `3.0.2` |

main adds the following direct dependencies that 2.6 does not have:
`hostname`, `sha2`, `uuid`, `xxhash-rust`, `hex`, `rustls`, `webpki-roots`,
`tokio-util`, and a `yoke-derive` pin.

## Files absent from 2.6

The baseline `technical-details.md` describes functionality that includes
the following; the corresponding files do **not** exist on 2.6:

### `src/v2/` root

- `bloom_filter.rs`
- `roaring_bitmap.rs`

### `src/v2/client/`

- `global_cluster.rs`
- `rls.rs`
- `session.rs`
- `snapshot.rs`
- `telemetry.rs`

### `src/v2/request/`

- `rls.rs`
- `snapshot.rs`

### `src/v2/response/`

- `rls.rs`
- `snapshot.rs`

### `src/v2/types/`

- `aggregation.rs`
- `function_chain.rs`
- `global_cluster.rs`
- `rls.rs`
- `snapshot.rs`

## `ClientV2` methods absent from 2.6

- `telemetry()` — returns `ClientTelemetry`
- `session()` — returns `MilvusClientV2Session`

## `prelude` names absent from 2.6

The baseline prelude exports these names; they are not available through
`milvus::v2::prelude::*` on 2.6:

- `rls::*`, `snapshot::*`
- `bloom_filter::*`, `roaring_bitmap::*`
- `ClientTelemetry`, `MilvusClientV2Session`
- `new_client_request_id`, `with_client_request_id`

## Other files absent from 2.6

- `AGENTS.md`
- `doc/guide/v2/concepts.md`
- `doc/guide/v2/quick-start.md`
- Examples: `v2/external_table.rs`, `v2/function_chain.rs`, `v2/rls.rs`,
  `v2/snapshot.rs`, `v2/text_field.rs`

## Proto submodule

Each branch pins its own `milvus-proto` commit. Confirm the pin with:

```bash
git submodule status
```

Do not manually `cd` into the submodule and check out an arbitrary commit.

## What is the same on 2.6

- MSRV: Rust 1.86, edition 2021
- tonic 0.13.1, prost >=0.13,<0.14
- `test/` directory
- V1 compatibility surface
- `bulk_import` module

## To quickly check whether a file exists on the current branch

```bash
git ls-tree -r --name-only source/2.6 -- src/v2/ | grep '<FileName>'
```

## Rules when on 2.6

1. Do not reference the files, types, methods, or prelude names listed
   above — they do not exist on this branch.
2. Snapshot, RLS, session, telemetry, global cluster, aggregation,
   bloom-filter, and roaring-bitmap APIs are baseline-only.
3. If a task references a symbol not found on this branch, check whether it
   belongs to the baseline line and inform the user rather than guessing.
