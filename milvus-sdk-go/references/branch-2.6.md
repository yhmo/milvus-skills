# 2.6 branch overlay

The other references describe the `master` baseline (Go module
`github.com/milvus-io/milvus/client/v3`). On the `2.6` maintenance branch,
the Go SDK module path, proto module, and API surface differ. Read this
overlay in addition to the baseline references when working on `2.6`.

Confirm the branch first:

```bash
git branch --show-current
```

## Module path: the most critical difference

On `2.6`, the Go module and proto module use `/v2` import paths — **every**
import that the baseline references describe with `/v3` must be replaced:

| | 2.6 | master (baseline) |
| --- | --- | --- |
| SDK module | `github.com/milvus-io/milvus/client/v2` | `github.com/milvus-io/milvus/client/v3` |
| Proto module | `github.com/milvus-io/milvus-proto/go-api/v2` | `github.com/milvus-io/milvus-proto/go-api/v3` |
| SDK version constant | `2.6.5` | `3.0.0` |

For example:

```go
// 2.6 branch — correct
import "github.com/milvus-io/milvus/client/v2/milvusclient"

// master — wrong on 2.6 (will not compile)
import "github.com/milvus-io/milvus/client/v3/milvusclient"
```

This applies to every subpackage: `entity`, `column`, `index`, `row`,
`common`, `bulkwriter`, and `milvusclient`.

## Directories absent from 2.6

The following directories under `client/` that the baseline references
describe do **not** exist on 2.6:

- `client/internal/` (conc, crypto, merr, retry, rowutil, typeutil)
- `client/membership/`

## `milvusclient/` files absent from 2.6

The baseline `technical-details.md` describes functionality that includes
the following; none of it exists on 2.6:

- Snapshot: `snapshot.go`, `snapshot_options.go`
- File resources: `file_resource.go`, `file_resource_options.go`
- External tables: `external_table.go`, `external_table_options.go`
- Search aggregation: `search_aggregation.go`, `search_aggregation_result.go`
- Bloom filter: `bloom_filter.go`
- Roaring filter: `roaring_filter.go`
- Telemetry: `telemetry.go`
- Client errors: `errors.go`

Corresponding `*_test.go` files are also absent.

## `entity/` files absent from 2.6

- `external_table.go`
- `file_resource.go`

## `Client` methods absent from 2.6

- `getCurrentDB()`
- `GetTelemetry()` (returns `*ClientTelemetryManager`)
- `recordOperation()`

## Dependencies absent from 2.6 (direct)

These are direct dependencies on master but absent (or indirect only) on 2.6:

- `github.com/RoaringBitmap/roaring/v2`
- `github.com/cespare/xxhash/v2`
- `github.com/google/uuid`
- `github.com/x448/float16`

## What is the same on 2.6

- `bulkwriter/` is identical on both branches.
- `column/`, `common/`, `row/`, `ruleguard/` are structurally the same.
- `service.go` public methods are the same.
- Option-pattern API shape (`NewXxxOption` → `XxxOption` → typed result)
  is the same.

## To quickly check whether a file exists on the current branch

```bash
git ls-tree --name-only source/2.6:client/milvusclient/ | grep '<FileName>'
```

## Rules when on 2.6

1. Replace every `client/v3` import with `client/v2` and every
   `go-api/v3` import with `go-api/v2`.
2. Do not reference the directories, files, methods, or dependencies listed
   above — they do not exist on this branch.
3. If a task references a symbol not found on this branch, check whether it
   belongs to the baseline line and inform the user rather than guessing.
