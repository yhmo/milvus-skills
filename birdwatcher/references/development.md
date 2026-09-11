# Birdwatcher Development

How the command framework and state machine work, and how to add commands consistently.

## Command framework (`framework/`)

Commands are defined as **public methods named `*Command`** on a state struct; they are discovered by reflection (`parseFunctionCommandsFrom` in `framework/command.go`). Requirements:

1. Method name ends with `Command` (case-sensitive).
2. Signature: `func (s *State) FooCommand(ctx context.Context, p *FooParam) (error)` or
   `func (s *State) FooCommand(ctx context.Context, p *FooParam) (SomeResultSet, error)`.
3. The param struct must embed one of the three bases, which carry the command's `use:"..."` tag:

```go
// plain command
type FooParam struct {
    framework.ParamBase `use:"foo" desc:"what it does"`
    Name string `name:"name" default:"" desc:"filter by name"`
    ID   int64  `name:"id" default:"0" desc:"filter by id"`
}
```

```go
// read-only command returning data -> gains a --format flag
type ShowFooParam struct {
    framework.DataSetParam `use:"show foos" desc:"list foos" alias:"foo"`
    CollectionID int64 `name:"collection" default:"0" desc:"collection id to filter"`
}
func (c *ComponentShow) ShowFoosCommand(ctx context.Context, p *ShowFooParam) (*framework.PresetResultSet, error)
```

```go
// destructive command -> dry-run unless --run is given
type RemoveFooParam struct {
    framework.ExecutionParam `use:"remove foo" desc:"remove foo meta"`
}
func (c *ComponentRemove) RemoveFooCommand(ctx context.Context, p *RemoveFooParam) error
```

Supported flag field kinds (`setupFlags`): `string`, `int64`, `bool`, `[]string`, `[]int64`, and anonymous embedded structs (for composition). `values:"..."` adds a flag-value suggestion list; `alias:"a,b"` registers command aliases. Positional args are handled by overriding `ParseArgs(args []string) error`.

### ResultSet

Commands that produce output return a `framework.ResultSet` (`PrintAs(Format) string`, `Entities() any`). Wrap with `framework.NewPresetResultSet(rs, framework.NameFormat(p.Format))`. For `--format table` support, additionally implement `TableResultSet` (`TableHeaders() table.Row`, `TableRows() []table.Row`) and optionally `TableTitler`. JSON output uses `framework.MarshalJSON`. Formats: `default`, `plain`, `json`, `table`, `line`.

## State machine (`states/`)

The app is a set of `framework.State`s switched by `SetNext(tag, state)`/`NextState()`:

- `ApplicationState` (offline `core`) — holds `connect`/`exit`/`debug commands`, `backup`/`load-backup`/`show current-version`/`set current-version`, `healthz`, workspace, and management commands. Started by `states.Start(config, multiStage)`.
- `kvConnectedState` (dry metastore state, label `MetaStore(addr)`) — `find-milvus`, `use`, `connect oss`, `backup`.
- `InstanceState` (label `Milvus(<instanceName>)`) — the main instance-scoped state created by `GetInstanceState`; composes `show.ComponentShow`, `remove.ComponentRemove`, `repair.ComponentRepair`, `reset.ComponentReset`, `set.ComponentSet` via embedding, plus `visit`, `probe`, `web`, `fetch-metrics`, `balance-explain`, garbage-collect/release, `download`. All reads/writes go through `kv.MetaKV` (wrapped by `FileAuditKV` which logs every meta op to the audit file).
- `OSSState` (`connect oss`) — object-storage browser (`ls/cd/pwd/get`).
- `MilvusctlState` (`connect milvus`) — drives the `milvusclient` SDK; commands delegate to the `Op` implementations in `internal/ops/` (also used by the YAML `run scenario` runner in `internal/scenario/`).
- `mgrpc.*` states — reached via `visit <component> [{id}]`; thin wrappers over the component's gRPC client (`datapb`, `querypb`, `rootcoordpb`, `indexpb`).

Command registration for a state happens in `SetupCommands()` via `s.MergeFunctionCommands(cmd, s)` (reflection over its methods) or `s.MergeCobraCommands(cmd, ...)` for pre-built cobra commands (used by `show/remove/repair/reset/set` component constructors like `etcd.ShowCommand(cli, basePath)`).

## Adding a command, end to end

1. Add a param struct with the `use:"..."` tag and a handler method on the right state (read-only: `ComponentShow`; destructive: `ComponentRemove`/`ComponentRepair`/`ComponentReset`/`ComponentSet`; instance-global: `InstanceState`; offline: `ApplicationState`).
2. Return `(*framework.PresetResultSet, error)` for data commands, implementing `PrintAs` (+ optional `TableResultSet`).
3. For an instance command, add it to the `MergeCobraCommands` list in `InstanceState.SetupCommands()` or the matching component's `ComponentXxx` constructor if it must be merged as a cobra command; plain methods registered on the embedded component are picked up automatically by `MergeFunctionCommands`.
4. Add tests alongside (`*_test.go` in the same package) and run `go build ./...` + the package tests.
5. Run `make lint-fix` for gofumpt/gci/golangci-lint.

## Meta model and etcd layout

- etcd keys under `rootPath/meta/...` are (de)serialized by the structs in `models/` (proto-generated: `model.proto` -> `model.pb.go`). Never hand-edit `model.pb.go`.
- `states/etcd/common` contains the read helpers used by `show` commands: `ListCollectionsBy`, `ListSegmentsBy`, `ListSessions`, `ListPartitions`, etc., with selector structs + post filters.
- Key paths are assembled in `states/etcd/common/path.go` / `meta_key.go`; the instance `basePath` is `rootPath/meta`.

## Version gating

`models/version.go` defines `LTEVersion2_1` (`<= 2.1.4`) and `GTEVersion2_2` (`>= 2.2.0`). The active value lives in `states/etcd/version` and is selected at startup (`states/start.go`, default `GTEVersion2_2`) or at runtime via `set current-version`. When meta decoding differs between versions, branch on `etcdversion.GetVersion()`.

## Extensions

Third-party modules can add commands/object-store providers without touching core (`states/extensions.go`): `WithExtensions(exts...)` (via `states.Start` options), `ApplicationFunctionCommandProvider`, `InstanceCobraCommandProvider`, `InstanceFunctionCommandProvider`, `ObjectStoreProviderExtension`.
