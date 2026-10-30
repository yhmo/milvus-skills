# Snippet Conventions

Per-SDK conventions for writing user-guide code snippets. Read the relevant
sections before drafting or fixing a snippet. The pymilvus block is always the
logic reference — translate its operation flow, keep the sub-step numbering.

> **⚠️ Feishu is the source; web-content is a downstream export.** The
> `web-content/v3.0.x/site/en/userGuide/` markdown files are generated from the
> Feishu documents, not the other way around. Never let web-content dictate an
> SDK version or API choice — it lags the Feishu source. Write every snippet
> against the **latest SDK version** (latest git tag per SDK in `sdk-map.md`).

## Product-branch includes inside code blocks

`<include target="milvus">...</include>` and
`<include target="zilliz">...</include>` may occur inside Feishu `<pre>` blocks.
They are authoring directives consumed by the website generator, not invalid
code. Do not remove, unwrap, merge, or choose one branch when editing the
Feishu source. Preserve both targets and their nested content exactly. A local
runner may create a temporary copy that unwraps the `milvus` branch for
execution.


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

## Fragment rule (every language)

A doc code block is a **snippet fragment**: reference lines (`import` /
`#include` / `use` / `using`) plus the logic body. NEVER write an entry-point
wrapper into a doc block in ANY language — no `package main` + `func main()`
(Go), no `#[tokio::main]` + `async fn main()` (Rust), no `int main()` (C++),
no `main`-bearing class (Java).

"Runnable" is verified by ASSEMBLING a document-scope executable for each
language: concatenate that language's blocks in document order, keep one shared
client/connection, hoist later dependency statements into the first
client-using block, place reference lines before `main`, and place all logic
bodies inside `main` in order. The assembly is the test harness's job — the doc
blocks themselves remain fragments, but they are designed to compose at
document scope rather than to be copied as fully isolated snippets.

The rule covers every function wrapper, not only entry points: a block must
never be the body of a named function/method either — no
`private static String bulkImport() { ... }` (Java), no
`private static void getImportProgress(String jobId) { ... }` (Java), no
`def bulk_import(): ...` (Python), no `func bulkImport() { ... }` (Go), or any
other function enclosing the body. Reference lines + bare statements only. If
the upstream code organizes the flow into a helper, inline its statements into
the block (hoisting any locals the statements need) instead of keeping the
function shell.

Allowed exception: a block that DEFINES a helper used immediately below in the
same block or by later sections (mirroring the pymilvus baseline's structure,
e.g. a `print_search_results(results, title)` formatter) is legitimate — write
the equivalent helper in each SDK following pymilvus. The prohibition targets
wrapper shells hiding the whole logic behind a call, not helper definitions
that are part of the flow.

`Expected output` sections are a second exception: they exist only to SHOW the
output of the preceding runnable example. Keep them Python-only — never add
other SDK blocks there and never report them as missing.

Install / prerequisite sections are a third: package-install and
environment-setup commands (pip / npm / go get / Maven deps / brew, under
headings like `Install ...` or `Prerequisites`) stay Bash-only — they are
shell commands by nature, not SDK code groups, so never add other languages
there and never report them as missing.

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

## Document-scope client and dependency rule

For each language within one document, create and declare the SDK client only
in the **first code block that uses it**. Later blocks of the same language
reuse that same client variable and must not re-create it.

- **All dependency statements live in exactly one block per language.** The
  `import` / `use` / `using` / `#include` statements needed anywhere in the
  document are hoisted into the first code block that uses the client for that
  language, and **no later block of that language may contain any such
  statement** — later blocks are pure logic that reuse the hoisted
  declarations. This is about language dependency statements, not Feishu
  `<include target="...">` product-branch markup.
- **"First client-using block" is not necessarily the document's first code
  block.** A document may open with prose-only, data-prep, or non-client
  blocks (JSON samples, a pymilvus snippet that only prepares data), and only
  introduce the SDK client in a later (2nd/3rd) code block. The dependency
  statements live in whichever block first uses the client for that language.
  Hoist even types/names used only later (Java `QueryIterator`, Rust
  `std::collections::HashMap`, Go `entity`/`column`) into that block, so later
  blocks stay free of declarations.
- If an operation only changes the target database, call `use_database(...)`
  (or the language-equivalent API) on the existing client instead of creating a
  new client.
- A second client is allowed only when the document explicitly connects to a
  different cluster or uses different credentials; give it a distinct variable
  name.
- Put client lifetime management in the first client block: Python may keep the
  client for the document scope, Go should `defer cli.Close(ctx)`, C# should
  use `using`/`using var`, Rust/C++ keep the owned client alive for the
  assembled scope.
- For real-run verification, concatenate same-language blocks in document order
  into one scope. For product-branch `<include target="milvus">` /
  `<include target="zilliz">`, preserve the source and unwrap only the selected
  branch in a temporary harness copy.

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
- **Feature scope — bulk writer / bulk import is pymilvus & Java only.**
  `RemoteBulkWriter` / `LocalBulkWriter` / `BulkWriter` / bulk-import APIs
  exist only in pymilvus and milvus-sdk-java. Documents whose subject is bulk
  writer or bulk import (e.g. "Data Import Hands-On", "Import Data (SDK)",
  any BulkWriter usage page) carry only `Python` and `Java` blocks — never
  add other SDK blocks to them, not even the "not supported" placeholder
  comment blocks above, and never report the other languages as missing for
  these documents. Their absence is intentional feature scope.
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

- Init (fragment — the test harness supplies `#[tokio::main] async fn main()`;
  never write the wrapper into the doc block):

  ```rust
  use milvus::v2::prelude::*;

  let config = ConnectConfig::new().uri("http://localhost:19530").token("root:Milvus");
  let client = ClientV2::new(&config).await?;
  ```

- `.await` and `?` are legal inside a doc block even though a standalone file
  would not compile: the harness embeds the body in an async fn returning
  `Result`, which is what makes the fragment testable.
- Operations are async: `client.create_database(CreateDatabaseRequest::builder()...build()?).await?;`.
  Verify method/type names against `milvus-sdk-rust` v3.0.x (`src/v2/`, see
  `sdk-map.md`).
