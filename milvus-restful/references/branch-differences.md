# Branch differences: 2.6 vs 3.0/master

The other references describe the `master` baseline. The `3.0` branch is
nearly identical to `master` (one test file); the `2.6` maintenance branch
differs significantly in handlers, request DTOs, and endpoints. Read this
overlay in addition to the baseline references when working on `2.6`.

Confirm the branch first:

```bash
git branch --show-current
```

## Files absent from 2.6

The following files in `internal/distributed/proxy/httpserver/` exist on
`master`/`3.0` but not on `2.6`:

- `file_resource_handler_v2.go` (+ test) — file-resource REST endpoints
- `snapshot_handler_v2.go` — snapshot REST endpoints
- `metadata_privilege_test.go`, `trace_log_expr_params_test.go`,
  `describe_collection_visibility_test.go`

`2.6` additionally has `handler_v2_hookpath_test.go`, which `master` removed.

## Endpoints absent from 2.6

The following v2 REST routes (backed by gRPC methods) exist on
`master`/`3.0` but not on `2.6`:

- Snapshot management: export snapshot, get export-snapshot state,
  list restore-snapshot jobs, get restore-snapshot state,
  restore external snapshot
- External collections: refresh external collection,
  list refresh jobs, get refresh progress
- Struct fields: `AddCollectionStructField`
- Schema alteration: `AlterCollectionSchema` (master replaces the
  2.6-era `AddCollectionField` endpoint)
- Import: `AbortImport`, `CommitImport` (DataCoord-backed)

`2.6` has `AddCollectionField`, which `master` removed.

## Request DTO differences

`request_v2.go` diverges substantially (master adds snapshot,
file-resource, external-collection, and struct-field request structs and
validation; 2.6 retains the hook-path request and lacks the new DTOs).
`handler_v2.go` diverges even more (1735 diff lines): 2.6 routes through
hook paths that master replaced with dedicated handler files.

## To quickly check whether an endpoint exists on the current branch

```bash
git show source/2.6:internal/distributed/proxy/httpserver/handler_v2.go | grep 'AddCollectionStructField'
```

## Rules when on 2.6

1. Do not reference the files, endpoints, or request structs listed above —
   they do not exist on this branch.
2. Snapshot, file-resource, external-collection, and struct-field REST
   APIs are baseline-only.
3. If a task references a route not found on this branch, check whether it
   belongs to the baseline line and inform the user rather than guessing.
