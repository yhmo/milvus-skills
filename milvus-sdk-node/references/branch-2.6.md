# 2.6 branch overlay

The other references describe the `main` baseline. On the `2.6`
maintenance branch, the following differs. Read this overlay in addition to
the baseline references when working on `2.6`.

Confirm the branch first:

```bash
git branch --show-current
```

## Package version and dependencies

The package `version` and target server line (`milvusVersion`) differ between
branches. Read the current values from `package.json` rather than assuming:

```bash
grep -E '"version"|"milvusVersion"' package.json
```

## Directories absent from 2.6

- `milvus/telemetry/` — the entire client-telemetry module
  (`ClientTelemetry.ts`, `index.ts`)

## Files absent from 2.6

### Top-level

- `3.0_change.md`
- `codecov.yml`

### `milvus/types/`

- `SearchAggregation.ts`
- `Volume.ts`

### `milvus/utils/`

- `BloomFilter.ts`
- `RoaringFilter.ts`
- `SearchAggregation.ts`

## API differences

### `MilvusClient` methods absent from 2.6

- `session(clusterId: string): MilvusClientSession` — the lightweight DQL
  session bound to a target cluster id

The `MilvusClientSession` class itself does not exist on 2.6.

### `milvus/index.ts` exports absent from 2.6

- `export * from './telemetry'` — the telemetry re-export line is
  main-only; `MilvusClientTelemetry` and related types are not importable
  from the package entry on 2.6.

## Examples absent from 2.6

- `milvus/EntityTTL.ts`
- `nextjs/eslint.config.mjs`
- `nextjs/proxy.ts`

## Test files absent from 2.6

The following `test/grpc/` spec files exist on main but not on 2.6:
`Snapshot.spec.ts`, `SearchAggregation.spec.ts`, `FileResource.spec.ts`,
`ExternalCollection.spec.ts`, `ElementLevel.spec.ts`,
`NullableVector.spec.ts`, `StructArrayAdvanced.spec.ts`, `Text.spec.ts`,
`FunctionFieldBackfill.e2e.spec.ts`, `UpsertArrayPartialOp.spec.ts`.

2.6 has `UpsertFieldOps.spec.ts`, which main has replaced with
`UpsertArrayPartialOp.spec.ts`.

## Proto submodule

Each branch pins its own `milvus-proto` commit:

```bash
git submodule status
```

The proto submodule tracks branch `3.0` of `milvus-io/milvus-proto` on main;
on 2.6 it tracks the appropriate 2.6-line commit. Do not manually `cd` into
the submodule and check out an arbitrary commit.

## What is the same on 2.6

- `milvus/grpc/` domain class files are identical
- `milvus/http/` mixin factories are identical
- `milvus/const/` and `milvus/bulkwriter/` are identical
- Build system (Jest, prettier, lint) is the same

## To quickly check whether a file exists on the current branch

```bash
git ls-tree -r --name-only source/2.6 -- milvus/ | grep '<FileName>'
```

## Rules when on 2.6

1. Do not reference the directories, files, methods, or exports listed
   above — they do not exist on this branch.
2. Client telemetry, session, search aggregation, bloom-filter, and
   roaring-filter APIs are baseline-only.
3. If a task references a symbol not found on this branch, check whether it
   belongs to the baseline line and inform the user rather than guessing.
