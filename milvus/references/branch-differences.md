# Branch differences: 2.6 vs 3.0 vs master

The other references describe the `master` baseline (the 3.1 development
line). The `3.0` and `2.6` maintenance branches differ in Go module versions,
package layout, documentation, and Makefile targets. Read this overlay in
addition to the baseline references when working on a maintenance branch.

Confirm the branch first:

```bash
git branch --show-current
```

## Branch roles

| Branch | Role | Released |
| --- | --- | --- |
| `master` | 3.1 feature-development line | not yet |
| `3.0` | current released 3.0 line | yes |
| `2.6` | current released 2.6 line | yes |

## Go module versions (compile-level difference)

| Module | 2.6 | 3.0 | master |
| --- | --- | --- | --- |
| `pkg/` | `github.com/milvus-io/milvus/pkg/v2` | `github.com/milvus-io/milvus/pkg/v3` | `github.com/milvus-io/milvus/pkg/v3` |
| `client/` | `github.com/milvus-io/milvus/client/v2` | `github.com/milvus-io/milvus/client/v3` | `github.com/milvus-io/milvus/client/v3` |
| proto | `github.com/milvus-io/milvus-proto/go-api/v2` | `github.com/milvus-io/milvus-proto/go-api/v3` | `github.com/milvus-io/milvus-proto/go-api/v3` |

On `2.6`, every import referencing `pkg/v3`, `client/v3`, or `go-api/v3`
must be replaced with the `/v2` equivalent — the `/v3` paths do not exist on
that branch and will not compile. Always confirm the current module path
from the nearest `go.mod`.

## Directories absent from maintenance branches

Directories under `internal/` that exist on `master` but not on the
maintenance branches:

| Directory | 2.6 | 3.0 | master |
| --- | --- | --- | --- |
| `internal/agg/` | absent | present | present |
| `internal/snapshotio/` | absent | present | present |
| `internal/dataview/` | absent | absent | present |
| `internal/featureusage/` | absent | absent | present |
| `internal/metacache/` | absent | absent | present |
| `internal/views/` | absent | absent | present |

## Master-only features (3.1 dev)

The following exist only on `master` and are part of the unreleased 3.1
line:

- **Python UDF function chain** (`pyudf`):
  `internal/util/function/pyudf/`, proxy lifecycle integration, and the
  pyudf Makefile targets (`build-pyudf-runtime-wheel`,
  `generate-pyudf-proto`, `generate-pyudf-python-proto`,
  `check-pyudf-proto-product`, `check-pyudf-python`,
  `format-pyudf-python`, `install-pyudf-runtime-wheel`)
- **Segcore code generation**:
  `make generate-segcore-codes` / `make check-segcore-codes-product`
  (generate `segcore_codes_gen.go` from milvus-common's `EasyAssert.h`)
- **Agent guide knowledge bases**: `docs/agent_guides/` with
  `observability/`, `storage/`, and `streaming-system/` subtrees
- `AGENTS.md` / `CLAUDE.md` at the repository root
- `examples/` top-level directory

## Documentation differences

| Path | 2.6 | 3.0 | master |
| --- | --- | --- | --- |
| `docs/dev/error_handling_guide.md` | present | present | present |
| `docs/dev/error_handling_casebook.md` | present | present | present |
| `docs/agent_guides/observability/README.md` | absent | absent | present |

On `2.6` and `3.0`, observability guidance lives in `docs/dev/` — read the
checkout's own docs instead of the master-only `agent_guides` path.

## Makefile targets

All component test targets (`make test-proxy`, `test-querycoord`,
`test-querynode`, `test-datacoord`, `test-datanode`, `test-streaming`,
`test-mixcoord`, `test-pkg`) exist on all three branches. The targets
listed as master-only above (pyudf, segcore-codes) do not exist on
maintenance branches.

## To quickly check whether a path exists on the current branch

```bash
git ls-tree --name-only source/<branch>:internal/<dir>
```

## Rules when on a maintenance branch

1. Replace `/v3` module imports with the branch's `/v2` equivalents (2.6
   only; 3.0 already uses `/v3`).
2. Do not reference the directories, features, or documentation paths
   listed above as master-only — they do not exist on maintenance branches.
3. If a task references a symbol not found on the current branch, check
   whether it belongs to a different line and inform the user rather than
   guessing.
