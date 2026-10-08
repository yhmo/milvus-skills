# Snippet Conventions

Per-SDK conventions for writing user-guide code snippets. Read the relevant
sections before drafting or fixing a snippet. The pymilvus block is always the
logic reference — translate its operation flow, keep the sub-step numbering.

> **⚠️ Feishu is the source; web-content is a downstream export.** The
> `web-content/v3.0.x/site/en/userGuide/` markdown files are generated from the
> Feishu documents, not the other way around. Never let web-content dictate an
> SDK version or API choice — it lags the Feishu source. Write every snippet
> against the **latest SDK version** (latest git tag per SDK in `sdk-map.md`).


## Writing into Feishu documents (code-block XML)

Snippets are stored as `<pre lang="..."><code>...</code></pre>` blocks inside
`<synced-source>` containers in Feishu documents. When writing a block via
`lark-cli docs +update --command block_replace`:

- Keep the block's `lang` (and original `caption`) exactly as fetched.
- Inside `<code>`, escape XML: `<` → `&lt;`, `>` → `&gt;`, `&` → `&amp;`.
- Newlines: use real newlines in the `--content` payload (the CLI converts
  them) or `<br/>` when inlining. **There is no blank-line de-duplication** —
  an empty line in the payload becomes `<br/><br/>` in the stored block.
  **MANDATORY: run `scripts/normalize_snippet.py` on the plain code text
  before composing the payload** — it removes blank lines between
  `import`/`use`/`#include` statements and inside data-structure literals,
  collapses runs of 2+ blank lines, and trims leading/trailing blank lines
  (blank lines that separate logical statements inside `func`/`main`/`if`
  bodies are preserved). Draft freely; the normalizer cleans the result.
- **Strip `<em>…</em>` emphasis markers** the Feishu renderer wraps around
  identifiers (e.g. `ConnectConfig.<em>builder</em>()`, `[]<em>string</em>`).
  Write plain code text.
- When checking out fetched code for local syntax checks, undo the escaping
  (`&lt;`→`<`, `&gt;`→`>`, `&amp;`→`&`, `<br/>`→newline) and drop `<em>`.
- Never wrap a replaced block in `<synced-source>` — the container already
  exists.

## pymilvus — `python` (reference baseline)

- Client init:

  ```python
  from pymilvus import MilvusClient, DataType
  client = MilvusClient(uri="http://localhost:19530", token="root:Milvus")
  ```

- Operations are plain `client.<method>(...)` calls; schema built with
  `MilvusClient.create_schema()` + `schema.add_field(...)`.
- When a section adds cpp/java/... from this baseline, mirror the exact steps and
  numbered comments.

## milvus-sdk-java — `java`

- Standard imports and init:

  ```java
  import io.milvus.v2.client.ConnectConfig;
  import io.milvus.v2.client.MilvusClientV2;

  ConnectConfig connectConfig = ConnectConfig.builder()
          .uri("http://localhost:19530")
          .token("root:Milvus")
          .build();
  MilvusClientV2 client = new MilvusClientV2(connectConfig);
  ```

- Requests are Lombok builders: `XxxReq.builder().field(...).build()`, passed to
  `client.method(req)`. Enums live in `io.milvus.v2.common.*` (e.g.
  `DataType.Int64`, `IndexParam.IndexType`).
- **Never use `DataType.String`** — it is a legacy/internal enum value. Use
  `DataType.VarChar` for string fields in java snippets.
- Verify class/package names against the latest `milvus-sdk-java` tag
  (`sdk-core/src/main/java/io/milvus/v2/`).

## milvus-sdk-node — `javascript`

- Init:

  ```javascript
  import { MilvusClient, DataType } from "@zilliz/milvus2-sdk-node";
  const client = new MilvusClient({ address: "http://localhost:19530", token: "root:Milvus" });
  ```

- Methods are async (`await client.createDatabase({...})`). Options are plain
  objects; types in `@zilliz/milvus2-sdk-node`.

## milvus-sdk-go — `go`

- Init:

```go
import "github.com/milvus-io/milvus/client/v3/milvusclient"
cli, err := milvusclient.New(ctx, &milvusclient.ClientConfig{
    Address: "http://localhost:19530",
    APIKey:  "root:Milvus",
})
```

  Note: the constructor takes `*ClientConfig`, not a plain `Config` struct —
  match the real type.

- Operations use option builders: `cli.CreateCollection(ctx,
  milvusclient.NewCreateCollectionOption("name", schema))`. The module lives in
  `client/` inside `milvus-io/milvus`; verify against the latest `client/v3.x`
  tag (see `.skills/update-user-guide-snippet/references/sdk-map.md` for the Go
  specifics). Use the `client/v3` module path for 3.0 guide snippets — the
  `client/v2` path is the 2.6 line.

## milvus-sdk-cpp — `cpp` (usually the missing SDK to add)

- Init and error handling (use the public `Status::IsOk()` / `Status::Message()`
  API — `util::CheckStatus` is an example-utility helper, NOT part of the SDK):

  ```cpp
  #include "milvus/MilvusClientV2.h"
  auto client = milvus::MilvusClientV2::Create();
  auto status = client->Connect(milvus::ConnectParam("http://localhost:19530").WithToken("root:Milvus"));
  if (!status.IsOk()) {
      std::cout << status.Message() << std::endl;
  }
  ```

- Requests are fluent builders with `WithXxx(...)`, wrapped in
  `client->Operation(...)`. Verify method names against
  `src/include/milvus/` in the latest `milvus-sdk-cpp` tag.
- **Reuse the `status` variable across sequential API calls in the same block** —
  declare `auto status = ...` once, then assign `status = ...` for each next call;
  do not introduce `status2` / `status3`:
  ```cpp
  auto status = client->UseDatabase("my_database");
  if (!status.IsOk()) { std::cout << status.Message() << std::endl; }

  status = client->CreateCollection(milvus::CreateCollectionRequest()...);
  if (!status.IsOk()) { std::cout << status.Message() << std::endl; }
  ```
- When adding cpp to a section that currently lacks it, translate the pymilvus
  flow step for step and keep the same numbered comments.

## RESTful — `bash`

- `curl` calls to `/v2/vectordb/...` with `"Authorization": "Bearer $TOKEN"` and a
  JSON body. Not an SDK — keep it but do not treat it as a baseline for logic.

## General

- **Canonical code-block order within a group** — place the language blocks of
  each section (a `<synced-source>` container, or one FAQ-style group) in this
  fixed order:
  ```
  Python → Java → Go → Rust → C++ → JavaScript → Bash
  ```
  Keep every group complete and in this order. Reorder existing blocks with
  `block_move_after` when needed.
- **SDK (or REST) does not implement the feature** → still add an **empty code
  block** for that language in its canonical position, containing only a
  comment stating the feature is unsupported, e.g.:
  ```cpp
  // Note: Not yet supported in milvus-sdk-cpp as of v3.0.2.
  ```
  Use the language's comment syntax (`#` for python/bash, `//` for
  cpp/java/go/javascript/rust). Never invent API code — only the comment.
- Numbered comments must stay in sync across all SDKs in a section (the pymilvus
  block defines the numbering).
- Prefer the same endpoint/collection/db names across SDKs so readers can compare
  (e.g. `my_collection`, `my_database_1`).
- Never invent APIs: confirm each method/option exists at the SDK's latest tag.
- **Ellipsis for truncated vectors must be written in each language's legal
  form** — a raw `...` is only valid in Python (Ellipsis) and Java (varargs).
  When a long vector (e.g. dim 768) is shown with only a few values, mark the
  truncation per language so the snippet still parses:
  - Python → `[v1, v2, ..., vN, ...]` (Ellipsis literal, legal)
  - Java → `Arrays.asList(v1, ..., vN, ...)` (varargs `...`, legal)
  - JavaScript → `[v1, ..., vN /* ...remaining dims */]` (row comment or
    trailing `/* ... */` comment; a bare trailing `...` is a SyntaxError)
  - Go / C++ / Rust → `{v1, ..., vN /* ...remaining dims */}` (comment)
  - Bash → `...` after the listed values in the JSON array (accepted as a
    documentation ellipsis even though strict JSON would reject it)
  Always run the syntax check after writing an ellipsis to confirm the chosen
  form parses.

## milvus-sdk-rust — `rust`

- Init (async, needs `#[tokio::main]`):

  ```rust
  use milvus::v2::prelude::*;

  #[tokio::main]
  async fn main() -> Result<()> {
      let config = ConnectConfig::new().uri("http://localhost:19530").token("root:Milvus");
      let client = ClientV2::new(&config).await?;
      // ...
      Ok(())
  }
  ```

- Operations are async: `client.create_database(CreateDatabaseRequest::builder()...build()?).await?;`.
  Verify method/type names against `milvus-sdk-rust` v3.0.x (`src/v2/`, see
  `sdk-map.md`).
