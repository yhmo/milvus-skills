---
name: birdwatcher
description: Use, analyze, and modify the `milvus-io/birdwatcher` repository, a CLI debugging tool for Milvus 2.0+ that connects to the etcd/TiKV metastore and inspects/repairs Milvus meta. Use for interacting with a live Milvus deployment (show collections/segments/indexes/sessions, backup/restore etcd, remove/repair/reset meta, connect oss, visit component gRPC), for Milvus version to birdwatcher compatibility questions, for building/running the tool (prompt, `-olc`, `-rest` web mode), for its command framework and state machine, and for repository-consistent changes or reviews. Do not use for the Milvus server internals, standalone SDKs (PyMilvus, milvus-sdk-*), Knowhere, or milvus-storage itself when a dedicated skill applies.
---

# Birdwatcher (Milvus debug tool)

A debug tool for Milvus 2.0 or later. Birdwatcher connects to the Milvus metastore (etcd, or TiKV) and inspects system meta. The current `master` line targets Milvus 3.0 (it tracks the milvus `master` branch and depends on `milvus-proto/go-api/v3 v3.0.0`, `milvus/pkg/v3 v3.0.0`, and `milvus/client/v3 v3.0.0-beta`).

Work from repository evidence. Treat this skill as a workflow and navigation layer, not as a substitute for the checkout's current `AGENTS.md`, documentation, source, or CI configuration.

## Repository

- This skill is for the `milvus-io/birdwatcher` repository.
- Prefer the local checkout at `$HOME/work/git-go/birdwatcher` when it exists on this machine. If the current working directory is already inside that repository, use its root instead.
- Confirm the checkout with `git rev-parse --show-toplevel` and `git remote -v` before relying on it. Do not assume the preferred path exists or is the correct repository without verification.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.

## Start every task

1. Locate and verify the repository root using the repository guidance above, then keep shell commands rooted there.
2. Read every applicable `AGENTS.md` from the root to the files in scope before explaining or editing code.
3. Inspect `git status --short`; preserve unrelated user changes and generated artifacts.
4. Classify the request as usage guidance, meta inspection, diagnosis, a targeted change, or verification. Do not run destructive commands (`remove`, `repair`, `reset`, `kill`, `force-release`) against a live instance without explicit user confirmation; default these to dry-run (`--run=false`).
5. Read the relevant one-level references:
   - Using the tool, the command catalog, and Milvus version matching: [references/usage.md](references/usage.md)
   - Build, test, and lint commands: [references/build-and-test.md](references/build-and-test.md)
   - The command framework and how to add commands: [references/development.md](references/development.md)

## Usage at a glance

```shell
# build (CGO disabled, no kafka/lance)
make birdwatcher            # outputs bin/birdwatcher

# interactive prompt, connect to etcd then issue commands
./bin/birdwatcher
Offline: connect --etcd 127.0.0.1:2379 --rootPath by-dev
Milvus(by-dev): show collections
Milvus(by-dev): show segment --collection 441440602102625173
Milvus(by-dev): exit
```

- Startup flags: `-version`, `-simple`, `-olc "connect ... ,show collections"`, `-rest -port 8002` (web server exposing `show *` as JSON endpoints), `-multiState`.
- Meta path is `rootPath/meta/` by default; the rootPath is used as the instance name (`by-dev` becomes `Milvus(by-dev)`).
- Read-only `show *` commands accept `--format default|json|table|line|plain`. Many support filtering by `--collection`, `--id`, `--name`, `--state`, etc.

## Investigate before acting

1. Find symbols and files with `grep`/`rg`/`Glob`; do not infer current paths from this skill.
2. Enumerate the actual command surface from source: command "use" strings come from the `use:"..."` struct tags on `framework.ParamBase` / `DataSetParam` / `ExecutionParam` in `states/` and from cobra `Use:` fields.
3. Commands are auto-registered from public methods named `*Command` (`context.Context` + a param struct implementing `framework.CmdParam`). Verify a command exists by grepping its use string rather than assuming.
4. Trace meta reads through `states/etcd/common` helpers (e.g. `ListCollectionsBy`, `ListSegmentsBy`) and the `models/` proto structs; the etcd key layout is generated by `models/model.proto`.
5. Base conclusions on source. Cite concrete paths and distinguish verified behavior from inference.

## Implement changes

- Make the smallest coherent change that preserves the command-framework conventions and established patterns.
- Follow the three param bases: `ParamBase` (plain command), `DataSetParam` (returns a `ResultSet` and gains `--format`), `ExecutionParam` (destructive; gains `--run` dry-run flag). Commands returning data implement `framework.ResultSet` (`PrintAs(Format)`, `Entities()`), optionally `TableResultSet`/`TableTitler`.
- Keep destructive operations (`states/etcd/remove`, `repair`, `reset`) gated behind `ExecutionParam.IsDryRun()`.
- Never hand-edit generated protobuf (`models/model.pb.go`); change `models/model.proto` and regenerate with protoc.
- Preserve compatibility gates: meta-parsing differences across Milvus versions are selected via `etcdversion.SetVersion` (`set current-version`), defaulting to `GTEVersion2_2` in `states/start.go`.
- Do not commit, push, publish, start external services, or run destructive integration workflows unless the user authorizes that action.

## Verify and report

1. Run `gofumpt`/`gci` and golangci-lint via `make lint-fix` / `make static-check` for changed code.
2. Run `go build ./...` and the narrowest relevant `go test` (e.g. `go test ./states/... -run TestCollection`).
3. For CLI-behavior work, trace the command end to end: param parsing (`framework/command.go`), the handler, the `ResultSet`, and the output format path.
4. Report the outcome first, then changed files, verification performed, and any unverified claims or remaining risks.

## Evaluation prompts

Should trigger:

- "Connect birdwatcher to the etcd and list collections/segments/indexes."
- "What Milvus version does the current birdwatcher master support?"
- "Explain what `show segment --collection 123` does and how to filter by state."
- "Add a new `show` command to birdwatcher."
- "Fix the backup/restore flow in birdwatcher."

Should not trigger:

- "Fix a QueryCoord scheduling bug in the Milvus server."
- "Add an API to PyMilvus / milvus-sdk-*."
- "Explain ANN index internals in Knowhere."
