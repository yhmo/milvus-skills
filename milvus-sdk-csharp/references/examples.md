# Examples

Use this reference before explaining, adding, or running examples in the Milvus C# SDK.

## Layout and role

- `examples/` is a standalone console project (`Milvus.Examples.csproj`) that references the source
  `Milvus.Client.V2` project (`ProjectReference`), so examples build and run directly from the repo
  without any packaging step.
- `examples/Program.cs` is the entry point; it dispatches to an example by name (first CLI argument,
  default `SimpleExample`).
- `examples/ExampleHelpers.cs` builds a `MilvusClientV2` from `MILVUS_URI`/`MILVUS_TOKEN` and resets
  collections so examples are idempotent.
- One `*Example.cs` per feature, each exposing `static Task Run(string uri)`, mirroring the C++ and
  Java SDK examples.

## Running

From the repo root:

```bash
dotnet run --project examples -c Debug                  # default: SimpleExample
dotnet run --project examples -c Debug -- GeneralExample
dotnet run --project examples -c Debug -- JsonFieldExample
```

Connection is controlled by environment variables (both optional):

| Variable     | Default           | Meaning                                   |
|--------------|-------------------|-------------------------------------------|
| `MILVUS_URI` | `localhost:19530` | Milvus `host:port` to connect to          |
| `MILVUS_TOKEN` | *(none)*        | `username:password` or a raw API key      |

```bash
MILVUS_URI=192.168.1.10:19530 MILVUS_TOKEN=root:Milvus \
  dotnet run --project examples -c Debug -- SparseVectorExample
```

## Example index

Examples demonstrate the V2 DTO API in isolation: end-to-end quickstart (`SimpleExample`), broader
lifecycle (`GeneralExample`), schema evolution (`AddFieldExample`), array/JSON/sparse/float16/int8/
binary vectors, upsert, group-by, partition key, dynamic and nullable fields, consistency levels
(including Session), run-analyzer, alias, and RBAC. See `examples/README.md` for the current list.

## Rules

- Ask before running an example that creates, drops, deletes, or mutates Milvus data, and confirm a
  Milvus server is available first.
- Prefer `MilvusClientV2` for new examples unless demonstrating legacy V1 behavior.
- Keep examples concise, idempotent, and self-cleaning (drop collections they create).
- Avoid hard-coded real credentials, cloud endpoints, or user-specific paths; read config from
  environment variables.
- When adding an example, add one `*Example.cs` file, register it in `Program.cs`, and update
  `examples/README.md`.

## Troubleshooting

- `Connection refused` or timeout: Milvus is not running at the URI.
- Auth or permission error: verify `MILVUS_TOKEN`/`MILVUS_URI` and RBAC setup.
- Existing collection conflict: examples are idempotent, but confirm before deleting user data.
- Build failure: examples reference the source project; build errors usually come from `Milvus.Client.V2`.
