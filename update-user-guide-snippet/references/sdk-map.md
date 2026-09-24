# SDK Map (Feishu user-guide snippets)

Per-SDK details for verifying/updating the user-guide code snippets. Read the
section for the SDK you are working on **before** writing or fixing snippets.

The snippets live in **Feishu documents** (`zilliverse.feishu.cn`); there is no
local markdown to edit and no hardcoded directory — the user supplies the
document/table URL each run. **Step 0** gets the SDK repos as follows: it
**prefers the local checkout** at `$HOME/work/git-go/<repo>` when one exists
(tags are usually already present, so no clone and often no network fetch), and
only falls back to cloning from GitHub into the gitignored
`sdk-tmp/sdks/<repo>/` when no local checkout is available. Ground truth for
"latest API" is the SDK repo's git tags.

> **⚠️ Source of truth is the Feishu documents, NOT web-content.** The
> `web-content/v3.0.x/site/en/userGuide/` markdown files are **downstream
> exports** derived from the Feishu documents — the Feishu docs are the source.
> Never use web-content to judge whether a snippet is current or correct: it
> routinely lags (e.g. it can still import `milvus/client/v2` while the Feishu
> source is already on `client/v3`). When updating Feishu snippets, always write
> against the **latest SDK version** (latest git tag per SDK below), regardless
> of what any web-content export shows.

## pymilvus

- **SDK repo**: `pymilvus` (clone → `sdk-tmp/sdks/pymilvus/`)
- **Snippet language**: `python` (reference baseline — pymilvus is the logic
  reference for every section)
- **Public API surface**: `pymilvus/` package; `MilvusClient` lives in
  `pymilvus/milvus_client/milvus_client.py`
- **Tags**: plain `vX.Y.Z` (ignore `-dev` tags)
- **Verify**: `git -C sdk-tmp/sdks/pymilvus show <tag>:pymilvus/milvus_client/milvus_client.py`

## milvus-sdk-java

- **SDK repo**: `milvus-sdk-java` (clone → `sdk-tmp/sdks/milvus-sdk-java/`)
- **Snippet language**: `java` (uses `MilvusClientV2`)
- **Public API surface**: `sdk-core/src/main/java/io/milvus/v2/`
- **Tags**: plain `vX.Y.Z` (e.g. `v3.0.9`)
- **Verify**: builder methods = `private` fields of `*Req` classes (Lombok
  `@Builder`); e.g. `git -C sdk-tmp/sdks/milvus-sdk-java show <tag>:sdk-core/src/main/java/io/milvus/v2/service/vector/request/SearchReq.java`
- **Beyond MilvusClientV2** (features outside the facade; see the
  `milvus-sdk-java` skill): **client pools**
  (`io.milvus.pool.MilvusClientV2Pool`/`MilvusClientV1Pool`, in `sdk-core`) and
  **BulkWriter / cloud REST import** (separate `milvus-sdk-java-bulkwriter`
  artifact, `io.milvus.bulkwriter.restful.BulkImportUtils` — `bulkImport`,
  `getImportProgress`, `listImportJobs`, `commitImport`, `abortImport`).

## milvus-sdk-node

- **SDK repo**: `milvus-sdk-node` (clone → `sdk-tmp/sdks/milvus-sdk-node/`)
- **Snippet language**: `javascript`
- **Public API surface**: `milvus/` (e.g. `milvus/MilvusClient.ts`,
  `milvus/grpc/*.ts`)
- **Tags**: plain `vX.Y.Z`; `About.md` pins no version (uses `latest`)
- **Verify**: `git -C sdk-tmp/sdks/milvus-sdk-node grep -n "async [a-zA-Z]*(" <tag> -- milvus/MilvusClient.ts milvus/grpc/GrpcClient.ts`

## milvus-sdk-go

- **SDK repo**: NOT standalone — the Go SDK is the `client/` module inside
  `milvus-io/milvus`. Step 0 clones with `prepare_sdk milvus` (→
  `sdk-tmp/sdks/milvus/`).
- **Snippet language**: `go`
- **Public API surface**: `client/` (module
  `github.com/milvus-io/milvus/client/v3` for the 3.0 line; the guide snippets
  import `milvusclient "github.com/milvus-io/milvus/client/v3/milvusclient"`).
  The `client/v2` module path is the 2.6 line only — do not use it in 3.0
  guide snippets.
- **Tags**: `client/vX.Y.Z` (e.g. `client/v3.0.0`; the 2.6 line is
  `client/v2.6.5`); pre-releases carry a suffix (`client/v3.0.0-beta`).
  Constructor takes `*ClientConfig`.
- **Verify**: `git -C sdk-tmp/sdks/milvus show <tag>:client/milvusclient/collection.go`

## milvus-sdk-cpp

- **SDK repo**: `milvus-sdk-cpp` (clone → `sdk-tmp/sdks/milvus-sdk-cpp/`)
- **Snippet language**: `cpp` (usually missing from user guide — the typical gap)
- **Public API surface**: `src/include/milvus/` (request builders `WithXxx`,
  `MilvusClientV2.h`)
- **Tags**: plain `vX.Y.Z` (e.g. `v3.0.2`)
- **Verify**: `git -C sdk-tmp/sdks/milvus-sdk-cpp show <tag>:src/include/milvus/MilvusClientV2.h`
- **Beyond MilvusClientV2**: **`milvus::BulkImport`** (standalone static
  cloud-REST import — `CreateImportJobs`, `ListImportJobs`,
  `GetImportJobProgress`, `CommitImport`, `AbortImport`; counterparts of
  pymilvus `bulk_import` / `get_import_progress`). No client pool.
- **Live-run**: use a **prebuilt binary** from the `default-conan-local2` Conan
  repo (`https://milvus01.jfrog.io/artifactory/api/conan/default-conan-local2`):
  `conan install --requires="milvus-sdk-cpp/<ver>@milvus/dev" --build=never
  -s compiler.cppstd=14`. The published binaries are built with **cppstd=14** —
  match that setting (and compile the snippet with `-std=c++14`). If no prebuilt
  binary matches the version/system, **skip cpp verification** (report it; never
  build from source).

## milvus-sdk-csharp

- **SDK repo**: `milvus-sdk-csharp` (clone → `sdk-tmp/sdks/milvus-sdk-csharp/`)
- **Snippet language**: `csharp`
- **Public API surface**: `Milvus.Client/` (namespace `Milvus.Client`)
- **Tags**: `v2.2.x`, `v2.3.0-preview.1`, etc. (many pre-release suffixes)
- **Verify**: `git -C sdk-tmp/sdks/milvus-sdk-csharp grep -n "public .*Task<" <tag> -- Milvus.Client/`

## milvus-sdk-rust

- **SDK repo**: `milvus-sdk-rust` (clone → `sdk-tmp/sdks/milvus-sdk-rust/`)
- **Snippet language**: `rust`
- **Public API surface**: `src/v2/` (crate `milvus-sdk-rust`; `ClientV2` at
  `src/v2/client.rs`; types/requests under `src/v2/`)
- **Tags**: plain `vX.Y.Z` (e.g. `v3.0.1`, `v2.6.1`)
- **Verify**: `git -C sdk-tmp/sdks/milvus-sdk-rust show <tag>:src/v2/client.rs`;
  examples under `examples/v2/` show the client API
- **Conventions**: import via `use milvus::v2::prelude::*;`; connect with
  `ClientV2::new(&ConnectConfig::new().uri(uri).token("root:Milvus")).await?`;
  requests use `XxxRequest::builder()....build()?`
- **Beyond ClientV2**: **`milvus::v2::bulk_import::BulkImport`** (standalone
  cloud-REST import — `bulk_import`, `list_import_jobs`, `get_import_progress`;
  counterparts of pymilvus `bulk_import` / `get_import_progress`). No client
  pool.
