# 2.6 branch overlay

The other references describe the `master`/`3.0` baseline. On the `2.6`
maintenance branch, the following differs. Read this overlay in addition to
the baseline references when working on `2.6`.

Confirm the branch first:

```bash
git branch --show-current
```

## Layout: what 2.6 lacks compared to the baseline

The top-level structure (`pom.xml`, `sdk-core/`, `sdk-bulkwriter/`,
`examples/`, `benchmark/`, `tests/`, `doc/`) is the same as the baseline. The
following paths that the baseline references describe do **not** exist on 2.6:

- `tutorial/`
- `scripts/` (`extract_changelog.sh`, `run_examples.sh`)
- `AGENTS.md`
- `sdk-core/src/main/java/io/milvus/telemetry/`
- `sdk-core/src/main/java/io/milvus/v2/client/MilvusClientV2Session.java`
- `sdk-core/src/main/java/io/milvus/v2/service/snapshot/` (entire package)
- `sdk-core/src/main/java/io/milvus/v2/service/vector/request/FunctionChain*.java`
- `sdk-core/src/main/java/io/milvus/v2/service/vector/request/aggregation/`

`docker-compose.yml` exists at the repository root on 2.6; on the baseline it
has moved to `sdk-core/src/test/resources/docker/`.

Examples live in `examples/` on both branches; file sets differ. Verify a
target example exists on the current branch before running or referencing it.

## `MilvusClientV2` methods absent from 2.6

The baseline `technical-details.md` describes methods that include the
following; none of them exist on 2.6:

- Snapshot management: `createSnapshot`, `listSnapshots`, `restoreSnapshot`,
  `dropSnapshot`, `describeSnapshot`, `pinSnapshotData`,
  `unpinSnapshotData`, `listRestoreSnapshotJobs`,
  `getRestoreSnapshotState`
- Row-level security / row policies: `setRLSPrincipalTags`,
  `getRLSPrincipalTags`, `listRLSPrincipals`, `deleteRLSPrincipalTags`,
  `createRowPolicy`, `listRowPolicies`, `dropRowPolicy`, `updateRowPolicy`
- File resources: `addFileResource`, `listFileResources`,
  `removeFileResource`
- External collection refresh: `refreshExternalCollection`,
  `listRefreshExternalCollectionJobs`,
  `getRefreshExternalCollectionProgress`
- Sessions and telemetry: `session`, `startTelemetry`, `getTelemetry`
- Compaction and schema: `listCompactionTasks`,
  `addCollectionStructField`, `addFunctionField`, `dropFunctionField`,
  `dropCollectionField`

To quickly check whether a method exists on the current branch:

```bash
git show source/2.6:sdk-core/src/main/java/io/milvus/v2/client/MilvusClientV2.java | grep '<MethodName>'
```

## V2 types absent from 2.6

- `MilvusClientV2Session`
- `SnapshotService` and all snapshot request/response models
- `FunctionChain`, `FunctionChainArg`, `FunctionChainExpr`,
  `FunctionChainOp`, `FunctionChainStage`, `FunctionParamValue`
- Aggregation models (`SearchAggregation`, `AggregationBucket`,
  `AggregationHit`, `TopHitsSpec`, `OrderSpec`, `SortSpec`, etc.)
- `CompactionTaskState`, `CompactionType`
- `io.milvus.telemetry` package
- `orm/iterator/QueryIteratorCursor`

## Test layout: 2.6 uses the pre-v3.0.9 flat structure

The baseline `source-layout.md` describes the v3.0.9+ grouped layout
(`unit/`, `integration/`, `system/`). On 2.6, tests mirror the production
packages instead:

```text
sdk-core/src/test/java/io/milvus/
├── TestUtils.java
├── client/
├── common/
├── orm/
├── param/
├── server/
└── v2/
```

`DockerTest` classes on 2.6 launch a Milvus container via
`org.testcontainers.milvus.MilvusContainer` with a pinned image (not
`TestUtils.startMilvusStandalone` with docker compose). There are no
`@Tag`-based test groups or `-Pintegration` / `-Psystem` profiles.

## Proto submodule

Each branch pins its own `milvus-proto` commit. Sync it after checking out
the target branch:

```bash
git submodule update --init sdk-core/src/main/milvus-proto
```

Do not manually `cd` into the submodule and check out an arbitrary commit.

## Rules when on 2.6

1. Do not reference the directories, classes, methods, or test layout from
   the baseline that are listed above as absent — they do not exist on this
   branch.
2. Use the pre-v3.0.9 flat test layout and Testcontainers-based `DockerTest`.
3. If a task references a symbol not found on this branch, check whether it
   belongs to the baseline line and inform the user rather than guessing.
