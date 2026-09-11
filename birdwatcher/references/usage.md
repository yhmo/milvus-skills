# Birdwatcher Usage

How to run birdwatcher, connect it to a Milvus metastore, and drive its commands. Command list is a snapshot; always verify a command's exact name and flags in source (they come from `use:"..."` struct tags and cobra `Use:` fields under `states/`).

## Build and run

```shell
make birdwatcher                # CGO_ENABLED=0 build to bin/birdwatcher
./bin/birdwatcher               # interactive prompt with suggestions + history
```

Startup flags (`cmd/birdwatcher/main.go`):

| Flag | Meaning |
|---|---|
| `-olc "cmd1 ,cmd2"` | One-line-command mode: run a comma-separated script non-interactively. Prefix a command with `#` to mute its stdout. |
| `-simple` | Plain prompt without suggestion/history UI. |
| `-rest -port 8002` | Web server mode: exposes every `show *` command as `GET /<name>?etcd=...&rootPath=...` returning JSON. |
| `-version` | Print the birdwatcher version (see `common/version.go`). |
| `-multiState` | Enable multi-state feature (keep several connected states; `list states`, `disconnect`). |

Local config lives at `.bw_config/birdwatcher.yaml` (created on first run): `WorkspacePath` (default `bw_workspace`, used by backup/restore/workspace commands) and `OutputFormat` (global default output format). `set bw-config --config <source> --key <k> --value <v>` adjusts it at runtime; `open-workspace [name]` changes the workspace.

## Connect

### etcd (default metastore)

```shell
Offline: connect --etcd 127.0.0.1:2379 --rootPath by-dev
# or from env: MILVUS_ETCD_ADDR / MILVUS_ROOT_PATH are picked up for defaults
```

`connect` flags (`states/etcd_connect.go` `ConnectParams`):

- `--etcd` (default `127.0.0.1:2379`), `--rootPath` (default `by-dev`), `--metaPath` (default `meta`).
- `--auto` — auto-detect the rootPath by scanning etcd (skips the reserved `woodpecker` prefix).
- `--force` — connect even if the rootPath does not look like a Milvus instance (ping of `rootPath/meta/session/id` fails).
- `--dry` — connect to the raw metastore without binding an instance (enters `MetaStore(addr)` state; pair with `find-milvus` + `use <instance>`).
- TLS: `--enableTLS --rootCAPem <file> --etcdCert <file> --etcdKey <file> --min_version 1.2`; auth via `--etcdUserName/--etcdPassword`.
- TiKV: `--use_tikv --tikv 127.0.0.1:2389` (+ `--tikv_use_ssl` / cert flags).

In the dry (`MetaStore`) state: `find-milvus` lists candidate root paths; `use <instance-name> [--force]` binds one. `dry-mode` returns from an instance back to the raw metastore state.

### connect oss (object storage)

`connect oss --addr <endpoint> --bucket <bucket> --accessKeyID ... --secretAccessKey ...` (see `states/storage/minio.go`). Once connected, an OSS state provides `ls`, `cd`, `pwd`, `get [path] --target <dir>`. Object-store reads are also resolved automatically for commands that need storage (e.g. `storage-analysis`, `download-segment`, `show manifest`) via config from meta or `--bucket` overrides; ARN/role auth is supported.

### connect milvus (live gRPC / admin)

`connect milvus --address localhost:19530 [--username --password | --api-key] [--db --tls --timeout]` opens a `Milvusctl[...]` state that drives the Milvus SDK directly (useful for run-booking data or running YAML scenarios). See "milvusctl commands" below.

### visit <component> (component gRPC)

In an instance state, `visit datacoord|datanode|indexcoord|querycoord|querynode|rootcoord [{serverId}]` dials the component's gRPC endpoint (auto-selects the primary for coordinators) and enters a `mgrpc` sub-state exposing coordinator/node RPCs such as `compact`, `flush`, `balance-segment`, `checker activate/deactivate/list`, `list-querynodes`, `get-querynode-distribution`, `suspend-node/resume-node`, `suspend-balance/resume-balance`, `check-balance-status`, `transfer-segment`, `transfer-channel`, `pr`. `visit indexnode` is not wired.

## Command catalog

### show — inspect meta (read-only; support `--format json|table|line|plain`)

| Command | Notes / key flags |
|---|---|
| `show database` | DBs from RootCoord meta |
| `show collections` | `--id`, `--name`, `--dbid`, `--state`, `--propertyKey` |
| `show collection-loaded` | loaded collections from QueryCoord |
| `show partition` / `show partition-loaded` | partitions / loaded partitions (need `--collection`) |
| `show segment` | `--collection --partition --segment --state --level --sorted --vchannel --storageVersion --detail`. Aliases `segments` |
| `show segment-index` | segment-index info; aliases `segment-indexes,segments-index,...` |
| `show index` | index meta; alias `indexes` |
| `show session` | online component sessions; alias `sessions` |
| `show replica` | QueryCoord replicas; alias `replicas` |
| `show checkpoint` | vchannel checkpoints; requires `--collection`; aliases `checkpoints,cp` |
| `show channel-watch` | DataCoord channel watch states; alias `channel-watched` |
| `show compactions` | `--ignoreDone=false` includes finished tasks |
| `show alias` | alias meta; alias `aliases` |
| `show user` | RootCoord users |
| `show resource-group` | resource groups |
| `show bulkinsert` / `show import-task` | import jobs/tasks; aliases `import,import-job` |
| `show stats-task` | stats tasks |
| `show config-etcd` | etcd-source config items |
| `show snapshot` / `show snapshots` | snapshot metadata from DataCoord |
| `show current-version` / `set current-version <ver>` | current meta-parsing version gate (see version matching below) |
| `show configurations` | iterate online components and dump their config |
| `show json-stats` / `show loaded-json-stats` | JSON key stats / loaded json stats |
| `show etcd-kv-tree` | etcd KV tree with key sizes per prefix |
| `show collection-history`, `show replicate`, `show wal-broadcast`, `show wal-distribution`, `show wal-recovery-storage`, `show vchannel-health` (alias `vch`), `show segment-loaded-grpc`, `show healthz-checks`, `show manifest` | misc diagnostics |
| `healthz-check` | run registered healthz checks (`states/healthz/`): mixed binlogs, loaded-index missing, storage v1 binlog schema mismatch, queryview lag, grant/alias check, issue 43407, dynamic attr mismatch |

### backup / restore — etcd data

| Command | Notes |
|---|---|
| `backup` | dump etcd KV under the instance prefix to `bw_etcd_ALL.<ts>.bak.gz` (see `states/etcd_backup.go`); the same file also receives a final revision snapshot |
| `load-backup [file]` | load a backup file back into the connected etcd (`states/load_backup.go`) |
| `download` / `download global-distribution` | pull global segment distributions |

### remove — delete meta entries (DESTRUCTIVE; `ExecutionParam`, dry-run unless `--run`)

`remove import-job`, `remove import-task`, `remove replicate-pchannel`, `remove session --sessionType <type> --serverID <id>`, `remove segment --collection ... [--partition ... --segment ...]`, `remove compaction --id`, `remove index --indexID ...`, `remove binlog --segment ...`, `remove channel --collection ... --channel ...`, `remove collection-meta-leaked`, `remove collection-drop`, `remove segment-orphan`, `remove dirty-importing-segment`, `remove config-etcd`, `remove stats-task`.

### repair — fix broken meta (DESTRUCTIVE; dry-run unless `--run`)

`repair segment`, `repair segment-storage-layout` (fix storage version and FieldBinlog children), `repair segment-part-dropping`, `repair empty-segment`, `repair manual-compaction`, `repair legacy-collection-remnant`, `repair collection-dbname`, `repair collection-info`, `repair channel`, `repair channel-watch`, `repair checkpoint`, `repair vchannel-registration`, `repair wal-broadcast-task`, `repair wal-recovery-storage`, `repair add_index_params`, `repair mixed-binlogs`.

### reset — offline WAL/MQ reset (DESTRUCTIVE, Milvus MUST be stopped)

- `reset wal` — delete WAL data+meta so the instance restarts onto an empty WAL. Run BEFORE `reset checkpoint`. WAL nodes, etcd and object storage must stay up.
- `reset checkpoint` — reset every persisted MQ position to the target WAL's earliest position (for switching a stopped instance onto a different MQ). Re-run until it succeeds before starting Milvus.

### set — modify meta values

`set field-attr --collection ... --fieldName ...`, `set collection consistency-level --collection ... --level ...`, `set bw-config`.

### binlog / storage inspection

`scan-binlog` (read binlog files), `scan-deltalog`, `inspect-parquet`, `inspect-vector-index` (validity bitmaps, indexed vs null rows), `scan-v3-index`/`scan-scalar-index-v3` (scalar index V3 diagnostic), `download-segment --segment <id>`, `download-pk --collection --segment`, `verify-segment`, `storage-analysis`, `probe pk`, `check-partiton-key`, `show manifest`. These need object-storage access (resolved automatically or via `connect oss` / `--bucket`).

### management / misc

`kill` (remove a component session from etcd), `compact-batch`, `flush` (manual flush; supports legacy and streaming 2.6+ mode), `force-release`, `list metrics-port`, `fetch-metrics`, `pprof`, `jemalloc-stats`, `update-log-level --level <name> --component <type> --serverID <id>`, `show-log-level`, `listen-events`, `consume` / `consumev2` / `cmp_pchannels` (consume topics from MQ), `pulsarctl` / `list topic` / `list subscription`, `parse-ts`, `parse-wal-message-id`, `parse-indexparam [file]`, `validate-indexfiles [dir]`, `assemble-indexfiles [dir]`, `test-minio-cfg`, `debug commands`, `list states`, `disconnect`, `exit`.

### milvusctl commands (after `connect milvus`)

`list collections` (`--format json`), `describe collection --name`, `create collection`, `drop collection`, `has collection`, `create index`, `create partition`, `add collection field`, `load collection`, `release collection`, `flush collection`, `insert`/`upsert` (with `--gen specs`), `delete`, `search`, `query`, `export pk`, `create snapshot` / `list snapshots` / `describe snapshot` / `drop snapshot`, `gc pause` / `gc resume`, `use database`, `run scenario <file.yaml>` (YAML driving the ops registered in `internal/ops/`: `create_collection`, `insert`, `query`, `search`, `hybrid_search`, `export_pk`, `gc_pause`, ...).

## Output formats

`show *` (DataSetParam) and any command returning a `framework.ResultSet` accept `--format`:

- `default`/`plain` — verbose human-readable dump.
- `json` — machine-readable (used by the web server and e2e tests).
- `table` — go-pretty table (needs the command to implement `TableResultSet`).
- `line` — compact one-entry-per-line.

The global default is taken from `.bw_config/birdwatcher.yaml` `OutputFormat`; `--format` overrides it.

## Milvus version matching

Birdwatcher reads the etcd meta written by a running Milvus. Meta layout, storage formats, and RPCs change across Milvus releases, so version matters:

- **Current `master` = Milvus 3.0 (server `master`).** `go.mod` pins `milvus-proto/go-api/v3 v3.0.0`, `milvus/pkg/v3 v3.0.0`, `milvus/client/v3 v3.0.0-beta`. Newer features (WAL/streaming, external collections, ARN object-store auth, Lance-backed segments, nullable vectors, snapshot metadata) assume a 3.0 server.
- **Meta-parsing version gate.** `show current-version` / `set current-version` choose between:
  - `GTEVersion2_2` (`>= 2.2.0`) — the default, set in `states/start.go`. Covers Milvus 2.2 up through 3.0.
  - `LTEVersion2_1` (`<= 2.1.4`) — for very old (pre-2.2) instances whose meta layout differs.
- **2.6 / 3.0 streaming (WAL) support.** Commands like `flush` (streaming mode), `reset wal`, `reset checkpoint`, `show wal-*`, `show vchannel-health`, `consumev2` only apply to Milvus with the WAL/streaming architecture (2.6+/3.0). Do not run `reset *` against a running instance.
- **Segment storage version.** Segments carry a `StorageVersion` (v1 legacy vs v2). `show segment --storageVersion <n>` filters; `repair segment-storage-layout` migrates meta; `storage/binlog/v1` vs `storage/binlog/v2` readers back this.
- **Compatibility rule of thumb:** keep birdwatcher `master` paired with a Milvus `master`/3.0 build; for a specific released Milvus line, use the matching tagged birdwatcher release (`v1.x.y`, e.g. a 2.5-era instance works with the 2.5-era birdwatcher tag). Confirm against `go.mod` dependencies and the current source rather than this snapshot.
