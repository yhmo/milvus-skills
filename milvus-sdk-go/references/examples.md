# Go SDK Examples

Example programs for the Go SDK and where to find them.

## In-repo example tests

Go examples are written as `Example` functions in `*_example_test.go` files inside the package under test. They appear on
`pkg.go.dev` and are validated by `go test`. They connect to a live Milvus at `127.0.0.1:19530` by default.

Example files in `client/milvusclient/`:

- `collection_example_test.go` — create/list/describe/drop collection, load/release
- `write_example_test.go` — insert / upsert / delete with column and row inputs
- `read_example_test.go` — search, hybrid search, query, get, iterator usage
- `index_example_test.go` — create index with `index` package builders
- `maintenance_example_test.go` — flush, compact, load tasks
- `partition_example_test.go` — partition create/drop/list
- `alias_example_test.go` — alias create/alter/drop
- `database_example_test.go` — database use/list/create/drop
- `rbac_example_test.go` — users/roles/privileges
- `resource_group_example_test.go` — resource group operations
- `replicate_example_test.go` — replication

Example tests live in package `milvusclient_test` (external test package), use the public API only, and are marked `// nolint`.

## Running examples

```bash
cd client
# compile-check only (no server needed)
go test -tags dynamic,test -gcflags="all=-N -l" -count=1 -run '^$' ./milvusclient/... -list Example 2>/dev/null
# run a specific example (requires a Milvus server at 127.0.0.1:19530)
go test -tags dynamic,test -gcflags="all=-N -l" -count=1 ./milvusclient/ -run ExampleClient_Search_basic
```

Because examples connect to a real server, do not run them as part of routine verification unless a server is available or the
user explicitly asks.

## API documentation examples

`client/entity/schema_example_test.go` shows schema construction, and `client/index/auto_example_test.go` shows index builder
usage. Public API docs live at https://milvus.io/api-reference/go/v3.0.x/About.md.

## E2E usage (`tests/go_client`)

Real end-to-end coverage lives in `tests/go_client` (module `github.com/milvus-io/milvus/tests/go_client`), which `replace`s
the SDK back to `../../client`. It has L0/L1/L2 tagged test cases run against a Milvus server. Use it to validate a behavioral
change end-to-end; it requires a running server.
