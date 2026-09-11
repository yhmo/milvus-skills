# Build and Test

Use this reference before building, testing, linting, or debugging the Milvus C# SDK.

## Prerequisites

- .NET SDK 8.0 or newer (see `global.json` for the pinned SDK and `rollForward` policy).
- Initialized `Protos/` submodule (proto sources).
- Python 3 and Docker on Linux for the V2 system tests (the `milvus_container.py` harness) and for the
  V1 Testcontainers-based tests.
- A Milvus server is not required for unit tests or the V2 in-process mock integration tests.

## First-time setup

```bash
git submodule update --init --recursive
dotnet restore
dotnet build
```

`Milvus.Client.V2` multi-targets `net8.0;netstandard2.0;net462`. Set `DeveloperBuild=True` to build
only `net8.0` locally (the default test target), matching the repository's developer workflow:

```bash
dotnet build -p:DeveloperBuild=True
```

## Build commands

```bash
dotnet build                              # debug
dotnet build -c Release                   # release
dotnet build -p:DeveloperBuild=True       # net8.0-only fast build
```

## Test layout

`dotnet test` runs all projects in the solution. Filter to a project with `--project`, and to a
test layer with xunit filters on the fully qualified name:

- V1 (`Milvus.Client.Tests`): per-feature classes using the Testcontainers.Milvus `MilvusFixture`
  assembly fixture (requires Docker).
- V2 unit tests (`Milvus.Client.V2.Tests.Unit`): DTO→proto conversion, validation, timestamp/FP16
  utilities; no server.
- V2 mock integration tests (`Milvus.Client.V2.Tests.Integration`): in-process `MockMilvusServer`
  (ASP.NET TestHost); no server.
- V2 system tests (`Milvus.Client.V2.Tests.System`): real Milvus container via
  `MilvusTestContainer`/`milvus_container.py` (requires Docker and Python 3).

Run layers separately:

```bash
dotnet test --project Milvus.Client.V2.Tests --filter "FullyQualifiedName~Unit"
dotnet test --project Milvus.Client.V2.Tests --filter "FullyQualifiedName~Integration"
dotnet test --project Milvus.Client.V2.Tests --filter "FullyQualifiedName~System"
```

Run one test class or method:

```bash
dotnet test --project Milvus.Client.V2.Tests --filter "FullyQualifiedName~DqlTests"
dotnet test --project Milvus.Client.V2.Tests --filter "FullyQualifiedName~CreateCollectionReqTests"
```

## Server-backed tests

- V1 tests start their Milvus container through `Testcontainers.Milvus`
  (`MilvusFixture.cs`); override the image with `MILVUS_IMAGE`.
- V2 system tests invoke `milvus_container.py start|stop` (ports `MILVUS_GRPC_PORT` 29630,
  `MILVUS_HEALTH_PORT` 19191, `MILVUS_MINIO_PORT` 19100) and honor `MILVUS_IMAGE` plus
  `MILVUS_CONTAINER_SCRIPT`. It starts Milvus (embedded etcd) plus a MinIO sidecar using remote/object
  storage, because the current server images cannot load segments under local storage.
- CI (`.github/workflows/Build.yml`) runs `dotnet test` on a matrix of Milvus versions, setting
  `MILVUS_IMAGE` per job.

Ask before starting Docker containers or running server-backed tests unless the user explicitly
requested them.

## Coverage

Coverage uses the `coverlet.collector` package; produce a report with:

```bash
dotnet test --project Milvus.Client.V2.Tests --collect "XPlat Code Coverage"
```

Convert the Cobertura output to HTML with `reportgenerator` if a readable report is needed. Coverage
should reflect SDK source, not test plumbing; exclude generated proto code and the test projects.

## Common troubleshooting

### Proto-generated classes are missing

Confirm the `Protos/` submodule is initialized and restored; generated output lives under each
project's `obj/` tree. Change proto sources or `*.csproj` `<Protobuf>` items, not generated files.

### System tests fail to connect

Confirm Docker is running, the ports are free, and the Milvus image is pullable. Check
`milvus_container.py` logs for the started container.

### Warnings-as-errors

`TreatWarningsAsErrors` and `AnalysisLevel=latest` are enabled. Fix analyzer warnings in changed
code rather than suppressing them, and follow the existing style.

### Restore failures

`Directory.Packages.props` centralizes versions; `nuget.config` points at nuget.org with source
mapping. Check both when a restore fails unexpectedly.
