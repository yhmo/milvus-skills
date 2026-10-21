# 2.6 branch overlay

The other references describe the `main` baseline. On the `2.6`
maintenance branch, the following differs. Read this overlay in addition to
the baseline references when working on `2.6`.

Confirm the branch first:

```bash
git branch --show-current
```

## Role of each line

- `main` is the 3.0 feature-development line: RLS, snapshot, file-resource,
  and external-collection APIs are implemented here but not yet released.
- `2.6` is the current released line; confirm the latest release with
  `git ls-remote --tags source`.

## Files absent from 2.6

The baseline `source-layout.md` and `technical-details.md` describe
functionality that includes the following; the corresponding files do
**not** exist on 2.6:

### Facade partials

- `MilvusClientV2.Rls.cs`
- `MilvusClientV2.Snapshot.cs`

### `Request/Rls/`

Entire directory (8 files): `CreateRowPolicyReq`, `DeleteRLSPrincipalTagsReq`,
`DropRowPolicyReq`, `GetRLSPrincipalTagsReq`, `ListRLSPrincipalsReq`,
`ListRowPoliciesReq`, `SetRLSPrincipalTagsReq`, `UpdateRowPolicyReq`

### `Request/Snapshot/`

Entire directory (9 files): `CreateSnapshotReq`, `DescribeSnapshotReq`,
`DropSnapshotReq`, `GetRestoreSnapshotStateReq`,
`ListRestoreSnapshotJobsReq`, `ListSnapshotsReq`, `PinSnapshotDataReq`,
`RestoreSnapshotReq`, `UnpinSnapshotDataReq`

### `Request/Utility/`

- `AddFileResourceReq.cs`
- `GetRefreshExternalCollectionProgressReq.cs`
- `ListFileResourcesReq.cs`
- `ListRefreshExternalCollectionJobsReq.cs`
- `RefreshExternalCollectionReq.cs`
- `RemoveFileResourceReq.cs`

### `Response/Rls/`

Entire directory (4 files): `GetRLSPrincipalTagsResp`,
`ListRLSPrincipalsResp`, `ListRowPoliciesResp`, `RowPolicyInfo`

### `Response/Snapshot/`

Entire directory (7 files): `DescribeSnapshotResp`,
`GetRestoreSnapshotStateResp`, `ListRestoreSnapshotJobsResp`,
`ListSnapshotsResp`, `PinSnapshotDataResp`, `RestoreSnapshotJobInfo`,
`RestoreSnapshotResp`

### `Response/Utility/`

- `FileResourceInfo.cs`
- `GetRefreshExternalCollectionProgressResp.cs`
- `ListFileResourcesResp.cs`
- `ListRefreshExternalCollectionJobsResp.cs`
- `RefreshExternalCollectionJobInfo.cs`
- `RefreshExternalCollectionResp.cs`

### `Types/`

- `RefreshExternalCollectionState.cs`
- `RestoreSnapshotState.cs`
- `RowPolicyAction.cs`
- `RowPolicyType.cs`

## `MilvusClientV2` methods absent from 2.6

Void methods:

`AddFileResourceAsync` · `CreateRowPolicyAsync` · `CreateSnapshotAsync` ·
`DeleteRLSPrincipalTagsAsync` · `DropRowPolicyAsync` · `DropSnapshotAsync` ·
`RemoveFileResourceAsync` · `SetRLSPrincipalTagsAsync` ·
`UnpinSnapshotDataAsync` · `UpdateRowPolicyAsync`

Methods returning a response:

`DescribeSnapshotAsync` · `GetRLSPrincipalTagsAsync` ·
`GetRefreshExternalCollectionProgressAsync` · `GetRestoreSnapshotStateAsync` ·
`ListFileResourcesAsync` · `ListRLSPrincipalsAsync` ·
`ListRefreshExternalCollectionJobsAsync` · `ListRestoreSnapshotJobsAsync` ·
`ListRowPoliciesAsync` · `ListSnapshotsAsync` · `PinSnapshotDataAsync` ·
`RefreshExternalCollectionAsync` · `RestoreSnapshotAsync`

## Tests absent from 2.6

Integration: `ExternalCollectionApiTests`, `FileResourceApiTests`,
`RlsApiTests`, `SnapshotApiTests`.

Unit: `ExternalCollectionReqTests`, `RlsReqTests`, `RlsRespTests`.

## Proto submodule

Each branch pins its own `Protos` submodule commit. Confirm the pin with:

```bash
git submodule status
```

Do not manually `cd` into the submodule and check out an arbitrary commit.

## What is the same on 2.6

- Examples are identical
- V1 (`Milvus.Client`) surface is identical
- Build system, multi-targeting, and analyzers are the same

## To quickly check whether a file exists on the current branch

```bash
git ls-tree -r --name-only source/2.6 -- Milvus.Client.V2/ | grep '<FileName>'
```

## Rules when on 2.6

1. Do not reference the files, types, or methods listed above — they do not
   exist on this branch.
2. RLS, snapshot, file-resource, and external-collection APIs are
   baseline-only.
3. If a task references a symbol not found on this branch, check whether it
   belongs to the baseline line and inform the user rather than guessing.
