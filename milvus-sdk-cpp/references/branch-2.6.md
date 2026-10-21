# 2.6 branch overlay

The other references describe the `master` baseline. On the `2.6`
maintenance branch, the following differs. Read this overlay in addition to
the baseline references when working on `2.6`.

Confirm the branch first:

```bash
git branch --show-current
```

## Layout: what 2.6 lacks compared to the baseline

The top-level structure (`CMakeLists.txt`, `conanfile.py`, `src/`, `test/`,
`examples/`, `tutorial/`, `doc/`, `scripts/`) is the same as the baseline.
The following paths that the baseline references describe do **not** exist
on 2.6:

- `AGENTS.md`
- `Doxyfile`
- `test/e2e/`

## Headers absent from 2.6

The baseline `technical-details.md` describes headers that include the
following; none of them exist on 2.6 (master adds 71 new headers total):

### Infrastructure

- `ClientRequestContext.h`
- `ClientTelemetry.h`
- `MilvusClientV2Session.h`

### Request types

- `request/collection/`: `AddCollectionStructFieldRequest`,
  `AddFunctionFieldRequest`, `DropCollectionFieldRequest`,
  `DropFunctionFieldRequest`
- `request/import/`: entire directory (10 files including
  `CloudImportRequest`, `MilvusImportRequest`, `VolumeImportRequest`,
  `CloudDescribeImportRequest`, `CloudListImportJobsRequest`, etc.)
- `request/rbac/PrivilegeRequest.h`
- `request/rls/`: entire directory (7 files including `RowPolicyRequest`,
  `SetRLSPrincipalTagsRequest`, `ListRowPoliciesRequest`, etc.)
- `request/snapshot/`: entire directory (10 files including
  `CreateSnapshotRequest`, `ListSnapshotsRequest`, `RestoreSnapshotRequest`,
  etc.)
- `request/utility/`: `FileResourceRequest`,
  `GetRefreshExternalCollectionProgressRequest`,
  `ListCompactionTasksRequest`, `ListRefreshExternalCollectionJobsRequest`,
  `RefreshExternalCollectionRequest`

### Response types

- `response/import/BulkImportResponse.h`
- `response/rls/`: entire directory (3 files)
- `response/snapshot/`: entire directory (6 files)
- `response/utility/`: `GetRefreshExternalCollectionProgressResponse.h`,
  `ListFileResourcesResponse.h`,
  `ListRefreshExternalCollectionJobsResponse.h`,
  `RefreshExternalCollectionResponse.h`

### Types

- `types/AggregationBucket.h`
- `types/BloomFilter.h`
- `types/BulkImportConfig.h`
- `types/FileResourceInfo.h`
- `types/FunctionChain.h`
- `types/IndexParam.h`
- `types/OrderByField.h`
- `types/RefreshExternalCollectionJobInfo.h`
- `types/RefreshExternalCollectionState.h`
- `types/RestoreSnapshotJobInfo.h`
- `types/RestoreSnapshotState.h`
- `types/RoaringBitmap.h`
- `types/RowPolicy.h`
- `types/RowPolicyAction.h`
- `types/RowPolicyType.h`
- `types/SearchAggregation.h`
- `types/TelemetryConfig.h`

### Implementation files

- `ClientRequestContext.cpp`
- `ClientTelemetry.cpp`
- `MilvusClientV2SessionImpl.cpp` / `MilvusClientV2SessionImpl.h`
- Corresponding `request/` and `response/` implementation files for all of
  the above

## What is the same on 2.6

- `BulkImport.cpp` / `BulkImport.h` exist on both branches (master refactors
  the request types but the class itself is present on 2.6).
- C++ standard is 14 on both branches.
- `MilvusClient.h` (V1), `MilvusClientV2.h`, caches, iterators, and
  connection/retry behavior are structurally the same.

## Examples absent from 2.6

Examples live in `examples/src/v2/` on both branches. The following exist on
master but not on 2.6:

`alias.cpp` · `external_table.cpp` · `function_chain.cpp` · `index.cpp` ·
`minhash_function.cpp` · `order_by.cpp` · `partition.cpp` · `rls.cpp` ·
`search_aggregation.cpp` · `snapshot.cpp` · `text_field.cpp`

Verify a target example exists on the current branch before running or
referencing it.

## To quickly check whether a header exists on the current branch

```bash
git ls-tree -r --name-only source/2.6 -- src/include/milvus/ | grep '<HeaderName>'
```

## Rules when on 2.6

1. Do not reference the headers, directories, types, or examples listed
   above — they do not exist on this branch.
2. `MilvusClientV2Session`, telemetry, snapshot, RLS/row-policy,
   file-resource, external-collection, and aggregation APIs are baseline-only.
3. If a task references a symbol not found on this branch, check whether it
   belongs to the baseline line and inform the user rather than guessing.
