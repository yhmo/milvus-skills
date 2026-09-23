---
name: update-user-guide-snippet
description: Create, update, and fix the code snippets in the Milvus user guide documents hosted on Feishu, using the pymilvus snippet as the reference baseline and each SDK's latest stable git tag as ground truth. Touches ONLY code blocks — never surrounding prose or headings. The user must provide a Feishu document or directory table URL; the skill follows the wiki links inside it and updates the documents they point to. Use when the user asks to update/refresh/fix/check the code snippets (脚本片段) in the Feishu user guide documents, mentions "user guide" / userGuide / Milvus Docs wiki/Base, or asks to correct/complete the SDK snippets in the Feishu docs.
---

# Update User Guide Snippets (Feishu)

Keep the multi-SDK code blocks in the Feishu user-guide documents correct and
complete.

- resolve the user-guide documents from the Feishu document or directory table
  URL the user provides (follow the wiki links it contains);
- for each document, read the sections and their code blocks;
- detect each SDK's latest API state (from the SDK repo git tags);
- check the snippets against it;
- **fix snippets that are syntactically wrong or use outdated/incorrect APIs**;
- **add missing SDK code blocks** where a section lacks a language the SDK
  supports;
- the **pymilvus snippet is the reference baseline** — every other SDK mirrors
  its flow;
- **never edit prose, headings, callouts, or any non-code content** — only code
  blocks are changed.

## Usage

No slash command — describe the task in natural language, and **always provide a
Feishu document or directory table URL** to point at the target docs. State the
scope if you don't want the default (all documents linked from that URL that
already have content), and be explicit if you want only fixes vs. also adding
missing SDK blocks.

**"Check for errors" (查错/检查错漏) always covers ALL languages** — syntax
check + consistency check (mirroring the pymilvus flow, sub-step numbering,
config-constant definitions). Real-run verification against a Milvus server is
**NOT part of the default check**: it runs only when the user explicitly asks
("在 Milvus server 上真实运行"/"run the snippets on a real Milvus server",
"用 server 验证"/"verify against the server").

| Intent | Prompt example |
|---|---|
| Basic update (default scope) | "更新飞书里 user guide 文档的代码片段：<Feishu URL>" / "Update the Feishu user guide code snippets: <Feishu URL>" |
| Fix errors/usage only | "修正飞书 user guide 文档里过时的代码用法：<Feishu URL>" / "fix outdated code usage: <Feishu URL>" |
| Add missing SDK blocks | "给飞书 user guide 文档补全缺失的 SDK 代码块：<Feishu URL>" / "add missing SDK blocks: <Feishu URL>" |
| Pin a subset of docs | "只处理 collections 目录下的文档" / "only process the collections documents" |
| Single doc | "修正 Create Collection 页面里的代码：<doc URL>" / "fix the code in the Create Collection page: <doc URL>" |
| Real-run verification | "在 Milvus server 上真实运行这些片段" / "run the snippets on a real Milvus server" (adds Step 5) |

## Ground rules

> **⚠️ 重要警告 / IMPORTANT — 只改代码块,绝不改文字**
>
> This skill ONLY modifies **code blocks** (`<pre>` / fenced code). It MUST NEVER
> alter any non-code content: prose, headings, callouts, tables, lists, images,
> citations, links, or any other text in the document. All changes are applied
> exclusively via `docs +update --command block_replace` / `block_insert_after`
> targeting `<pre>` blocks. Touching any text is a violation. 本 skill 只会修改
> 代码片段,绝不改动文档中的任何文字内容。

- **Feishu documents are the only working surface.** There is no local
  markdown to edit and no git push/PR step — changes are written directly to the
  Feishu document via `lark-cli docs +update`. See "Pushing / PR" below for the
  implications.
- **Do not stop to ask for scope confirmation before a large backfill.** Once
  the page coverage is determined (default: all documents that already contain
  code blocks), proceed automatically without prompting — fixing snippets across
  many documents is the expected, routine behavior. Only ask the user when the
  request itself is genuinely ambiguous.
- **pymilvus is the logic reference.** When writing or fixing a snippet, first
  read the `Python` block for the section, then translate that exact operation
  flow to each SDK using that SDK's conventions.
- Ground truth for "latest API" is the SDK repository's git tags — clone into
  the gitignored `sdk-tmp/sdks/` (see Step 0 below) and verify method
  names/signatures against the tag's public API. Per-SDK repo names, clone paths,
  public API surfaces, tag formats, and verify commands live in
  `references/sdk-map.md` — read it before
  working on an SDK. Do not guess.
  > Path note: the `references/` / `scripts/` paths below are relative to the
  > skill directory (which is symlinked into the agent's skills dir).
- **Only touch code blocks.** Never rewrite surrounding prose, headings,
  callouts, tables, images, or citations.
- Within one section the snippets across SDKs must follow the **same logical
  flow and sub-step numbering** as the pymilvus block.
- Match each document's existing per-SDK style (imports, client initialization,
  variable naming); do not introduce a new style mid-document.
- **Ignore `DataType.String`**: when an SDK's `DataType` enum contains a `String`
  value (e.g. java `io.milvus.v2.common.DataType.String`), never write it into a
  snippet — use `DataType.VarChar` instead. It is a legacy/internal value.

## Prerequisites — Feishu access

- Requires a valid **user identity** (`lark-cli auth status`; user identity is
  the default for document operations and can see these documents). If user
  identity is missing/expired, run `lark-cli auth login --domain docs` (see the
  `lark-shared` skill for the device-flow instructions) before doing anything.
- There is **no hardcoded table**: the user must supply a Feishu document or
  directory table URL each run. The skill follows the wiki links inside that
  document/table and updates the documents they point to.
- Load the `lark-doc` skill (`lark-cli skills read lark-doc`) and read its
  `references/lark-doc-fetch.md`, `references/lark-doc-update.md`, and
  `references/lark-doc-xml.md` before reading or editing any document.

## Prerequisites — load the SDK skills you will touch

**Before writing or checking any snippet for a language, load that SDK's skill**
so the session has its API-tracing knowledge and conventions loaded. Load every
SDK whose code blocks appear in the documents you are processing:

| Snippet lang | Skill to load |
|---|---|
| `python` | `pymilvus` |
| `java` | `milvus-sdk-java` |
| `javascript` | `milvus-sdk-node` |
| `go` | `milvus-sdk-go` |
| `cpp` | `milvus-sdk-cpp` |
| `rust` | `milvus-sdk-rust` |
| `csharp` | `milvus-sdk-csharp` |
| `bash` | `milvus-restful` (RESTful API — not an SDK, but the curl blocks
  mirror the `/v2/vectordb/*` endpoints it documents) |

- Load via the agent's skill mechanism (e.g. `skill` tool / `lark-cli skills
  read` equivalent). Do this **before** Step 0b's SDK-repo cloning and before
  drafting any snippet — the skill provides the API surface, conventions, and
  common pitfalls that complement the git-tag ground truth in `sdk-map.md`.
- `sdk-map.md` and `snippet-conventions.md` remain the authoritative ground
  truth for tag-based API verification; the SDK skills add context (tracing,
  idioms, edge cases) — cross-check both.

### If an SDK skill is missing from the environment

Updating a document WITHOUT the corresponding SDK skill risks API deviations
(wrong method names, wrong idioms, missing features). When a required skill is
**not available in the environment**:

1. **STOP and tell the user** which skills are missing (e.g. "milvus-sdk-cpp is
   not installed in this environment").
2. **Ask the user whether to continue anyway.** Present the choice explicitly —
   do not silently proceed:
   - continue without the skill (accepting the deviation risk), and the report
     must state which skills were missing; or
   - abort / retry in an environment that has the skills installed.
3. Only after the user confirms continuing may you proceed, and even then:
   - rely **heavily** on `sdk-map.md` git-tag verification and the SDK repo's
     official examples instead of the missing skill;
   - flag in the final report every language whose skill was unavailable, so the
     user knows those snippets are higher-risk.

## Scope

- **Documents to process come from the URL the user provides.** Resolve them
  like this:
  1. Inspect the URL to learn its type and token:
     `lark-cli drive +inspect --url <url> --as user`. A `wiki/` URL unwraps to
     either a `docx` (a document) or a `bitable` (a directory table).
  2. **Directory table (bitable)** → list its records to find the link column:
     `lark-cli base +record-list --base-token <token> --table-id <tbl...>
     --limit 200 --as user`. Each record's link field (often named `Doc` or
     similar) is `[Title](wiki-url)`.
  3. **Document (docx)** → fetch its content and collect the wiki links in its
     body: `lark-cli docs +fetch --doc <docx> --as user`, then scan for
     `https://.../wiki/...` links.
  4. A link value containing `wiki/` is a real document to process. Values like
     `http://<Title>` are **placeholders** for documents not yet created —
     skip them.
  5. By default process only documents that **already contain code blocks**
     (probe with `docs +fetch --scope outline`; empty outlines or
     outline-less documents with no `<pre>` are skipped and reported). Do NOT
     create code in empty documents unless the user explicitly asks.
  - "only the collections docs", "just the Search page", etc. narrow the scope
    by title/ID as named by the user.
- **Document ↔ wiki link mapping**: every directory entry points to a Feishu
  wiki node. `lark-cli drive +inspect --url <wiki_url> --as user` unwraps it to
  the underlying `docx` token; use that token for all `docs +fetch` / `docs
  +update` calls. Prefer passing the wiki URL directly to `docs +fetch` where
  supported.
- **SDK ↔ code-block language** mapping (the Feishu docs use these `lang`
  values on `<pre>`):

  | `lang` | SDK |
  |---|---|
  | `Python` | pymilvus (reference baseline) |
  | `Java` | milvus-sdk-java (`MilvusClientV2`) |
  | `JavaScript` | milvus-sdk-node |
  | `Go` | milvus-sdk-go (`client/` module) |
  | `C++` | milvus-sdk-cpp |
  | `Rust` | milvus-sdk-rust (`src/v2/`, `ClientV2`) — used when a section has a
    Rust block, or to add one |
  | `Bash` | RESTful API (not an SDK — never a logic baseline; **add it the same
    way as SDK blocks, but ONLY when the feature has a REST endpoint** under
    `/v2/vectordb/*` — verify via the `milvus-restful` skill / the curl
    patterns on other pages; skip if the operation is SDK-only) |

- **Canonical code-block order within a group.** Within one section (one
  `<synced-source>` container, or one FAQ-style group), place the code blocks
  in this fixed order:

  ```
  Python → Java → Go → Rust → C++ → JavaScript → Bash
  ```

  When writing a new group, add blocks in this order. When a language's block
  already exists, keep it in its canonical slot (reorder existing blocks if
  needed, using `block_move_after`). This gives readers a consistent
  cross-SDK reading order.

  A **`<synced-source>` container** (or a section with multiple standalone SDK
  blocks) signals the author intends a multi-SDK section — so a missing
  language's block (e.g. `Rust`, `C++`, or a `Bash`/REST block when the feature
  exposes a `/v2/vectordb/*` endpoint) is added **whenever the section is a
  multi-SDK section**, even if it currently holds only one or two languages
  (e.g. only a Python block). If a language's SDK does not actually implement
  the feature, still add an **empty block with a comment** stating the feature
  is unsupported (see "SDK does not implement the feature" in the Workflow).

- **Standalone (non-`<synced-source>`) code blocks are single-language answers,
  NOT multi-SDK sections.** FAQ-type documents (e.g. the FAQs wiki page) hold
  `<pre>` blocks scattered directly under a question paragraph, not inside a
  `<synced-source>` container. Each such block answers one SDK-specific
  question (e.g. "What can I do if I cannot connect to Zilliz Cloud with the
  Node.js SDK?" → a lone `JavaScript` block). Treat these as complete: fix the
  block's own errors, but do NOT add other languages to it. Detect this by the
  absence of a `<synced-source>` wrapper around the `<pre>` — do not infer a
  missing-SDK gap just because other languages are absent.

## Workflow

0. **Pre-flight: check Feishu auth.** `lark-cli auth status --json` — user
   identity must be `ready`. If not, stop and ask to run the `lark-shared`
   device-flow login. Also read `references/sdk-map.md`
   for the SDKs you will touch.
0b. **Clone the SDK repos you need** (once per run) into the gitignored
   `sdk-tmp/sdks/`, using the repo names in
   `references/sdk-map.md`:

   ```bash
   SDK_URL_BASE=https://github.com/milvus-io
   prepare_sdk() {
     local dir="sdk-tmp/sdks/$1"
     if [ ! -d "$dir/.git" ]; then
       git clone --filter=blob:none --no-checkout "$SDK_URL_BASE/$1.git" "$dir"
     fi
     git -C "$dir" fetch --tags --force origin   # always refresh tags
   }
   prepare_sdk milvus-sdk-cpp    # repeat per SDK you will touch
   ```

   The Go SDK is an exception: it lives inside `milvus-io/milvus` — use
   `prepare_sdk milvus` and diff under `client/` (per `sdk-map.md`).
1. **Enumerate the documents.** Resolve the user-provided URL per the Scope
   rules (directory table records or document links → wiki links) and build the
   list of documents to process. For each document, record its title and docx
   token.
2. **For each document:**
   - Read the outline: `lark-cli docs +fetch --doc <docx> --scope outline
     --max-depth 3 --as user` to enumerate sections. Skip if there are no code
     blocks (verify by fetching).
   - For each section, `lark-cli docs +fetch --doc <docx> --scope section
     --start-block-id <heading-block-id> --detail with-ids --as user` to read
     the section including its `<pre>` code blocks and block ids.
   - Record, per section, which languages already have a `<pre>` block.
   - **Standalone `<pre>` blocks** (not wrapped in `<synced-source>`, as in
     FAQ pages) are single-language answers — fix their errors only, do NOT add
     other languages (see Scope).
   - **Missing SDKs** → for a `<synced-source>` section, add the missing
      language's block using the pymilvus block as the logic baseline,
      translated per the conventions in
      `references/snippet-conventions.md`. This applies even when the section
      currently holds only a Python block (the container signals multi-SDK
      intent).
   - **Missing Bash (REST) block** → treat like a missing SDK block. If the
      feature exposes a REST endpoint under `/v2/vectordb/*`, write the curl
      block (verify with the `milvus-restful` skill or the curl patterns on
      other pages). If the operation is SDK-only (no REST endpoint), still add
      an **empty Bash block with a comment** stating REST does not expose this
      operation (per the "SDK does not implement the feature" rule). Bash is
      never the logic baseline.
   - **SDK does not implement the feature**: if a section's feature is not (yet)
      supported by a given SDK (verified against that SDK's latest tag — the
      methods/options simply do not exist), still **add an empty code block for
      that language** in its canonical position, containing only a comment that
      states the feature is not supported, e.g.:

      ```cpp
      // Note: Not yet supported in milvus-sdk-cpp as of v3.0.2.
      ```

      Use the SDK's comment syntax (`#` for python/bash, `//` for
      cpp/java/go/javascript/rust). This keeps the per-group language set
      complete and the ordering consistent, while making it explicit the SDK
      intentionally lacks the feature. Record it in the report too (e.g. "C++:
      <feature> not supported as of vX.Y.Z"). Never write code for APIs that do
      not exist — only the comment.
   - **Existing snippets** → check against the SDK's latest tag: deprecated or
     renamed methods, changed builder signatures, wrong imports, missing steps,
     XML-escaping mistakes that break the code. Fix in place, keeping the
     pymilvus-mirrored flow.
3. **Rewrite the code block in Feishu.** Replace a `<pre>` block with
   `lark-cli docs +update`:

   ```bash
   lark-cli docs +update --doc <docx> --command block_replace \
     --block-id <pre-block-id> \
     --content '<pre lang="Python"><code>from pymilvus import MilvusClient
   client = MilvusClient(uri="http://localhost:19530", token="root:Milvus")</code></pre>'
   ```

   Rules for the `--content` payload (see `lark-doc-xml.md` for the full spec):
   - A code block is `<pre lang="<lang>" [caption="..."]><code>…</code></pre>`.
     Keep the block's original `lang` (and `caption`, if the original had one).
   - Inside `<code>`, escape XML: `<` → `&lt;`, `>` → `&gt;`, `&` → `&amp;`;
     newlines must be actual newlines in the payload (the CLI converts them), or
     `<br/>` when inlining on one line.
   - Remove the `<em>…</em>` emphasis markers the Feishu renderer adds around
     identifiers (e.g. `ConnectConfig.<em>builder</em>()`); write plain code.
   - Never wrap a code block in `<synced-source>` — the container already exists
     and must be preserved; you are replacing only the inner `<pre>`.
   - Use `--dry-run` once before the first real write of a run to sanity-check
     the request, then drop it.
   - A `block_replace` invalidates the replaced block's id; re-fetch if you need
     to touch it again.
 4. **Syntax-check and consistency-check every written or edited snippet
    (mandatory — covers ALL languages; no execution).** Each modified snippet
    must pass a parse-only syntax check with the SDK's toolchain (no live
    Milvus server or runtime execution needed). This is what "查错" / "检查错漏"
    means by default — it never requires a server and always covers every
    language present. The blocks live in Feishu, so first extract the final
    code text to a local temp file.
    The bundled helper `scripts/check_snippets.py` does the extraction +
    per-language parse check in one step:

    ```bash
    lark-cli docs +fetch --doc <docx> --scope section \
        --start-block-id <heading-block-id> --detail with-ids --as user \
      | python3 scripts/check_snippets.py --doc "<Doc Title>"
    ```

    It reads the fetch XML, extracts every `<pre lang="...">` block, undoes the
    XML escaping (`&lt;`→`<`, `&gt;`→`>`, `&amp;`→`&`, `<br/>`→newline, drops
    `<em>`), writes each to `sdk-tmp/snippet-check/`, and runs the per-language
    parse check. Manually, the same steps are:
    - Fetch the section again (`docs +fetch --scope section --detail with-ids`),
      pull each edited `<pre>`'s code text, undo the XML escaping, and write it
      to `sdk-tmp/snippet-check/<lang>/<doc>-<n>.<ext>`.
    - Then parse-check per language:
     - `python` → `python -m py_compile <file>` (or `ast.parse`).
     - `javascript` → `node --check <file>`.
     - `cpp` → `g++ -fsyntax-only -std=c++17 <file>` with the SDK's include paths
       (mirror the `sdk-tmp/sdks/milvus-sdk-cpp/src/include` include dir).
     - `go` → `gofmt -e <file>` (parses the file and reports syntax errors; works
       outside a module and does not require the SDK's `go.mod` version). Do NOT
       rely on `go vet` — snippets are fragments, not a buildable package.
     - `java` → `javac` with the SDK jars on the classpath (if the toolchain is
       available); otherwise report that javac was skipped.
     - `bash` → `bash -n <file>`.
   - Fix any reported syntax error in the Feishu block (Step 3) and re-run until
     clean. If a toolchain is missing, say so explicitly in the report rather
     than silently skipping.
   - Code blocks that are **fragments by design** (a mid-file data array, a
     continuation block referencing earlier blocks) may fail a standalone parse;
     judge by intent — concatenate continuation blocks in the same section for
     the check when that reflects how they run, and note it in the report.
   - **Cross-block: undefined config-constant references.** Static syntax checks
     do NOT catch blocks that reference document-level config constants
     (SCREAMING_SNAKE names like `SERVING_CLUSTER_ENDPOINT`, `TOKEN`,
     `CLUSTER_ENDPOINT`) without defining them — that is a runtime error in
     Java/Go/JavaScript/C++, invisible to `py_compile`/`node --check`/`gofmt`/
     `g++ -fsyntax-only`. Run the bundled `scripts/check_constants.py` on the
     fetched document:

     ```bash
     lark-cli docs +fetch --doc <docx> --detail with-ids --as user \
       | python3 scripts/check_constants.py --doc "<Doc Title>"
     ```

     It collects the constants defined in the document's **Python/Bash** blocks
     (the config baseline), then reports every Java/Go/JavaScript/C++ block that
     *references* such a constant without defining it. **Fix by adding the
     language-idiomatic definition to the block** (this makes each block
     self-contained and independently runnable):
     - Java → `String NAME = "value";`
     - Go → `NAME := "value"`
     - JavaScript → `const NAME = "value";`
     - C++ → `const std::string NAME = "value";`

     Insert the definition after the block's import/include region. Re-run the
     check until 0 missing references.
   - **Consistency check — all languages mirror the pymilvus flow.** For every
     multi-SDK section, manually compare each language block against the Python
     baseline and report (and fix) any divergence:
     - **sub-step ordering** — same numbered steps / calls in the same order
       (e.g. if Python does `use_database()` before `create_collection()`, every
       other language should too — Java `databaseName(...)` and C++
       `WithDatabaseName(...)` shortcuts that skip the explicit "use database"
       step are a divergence to flag);
     - **equivalent API choice** — same logical operation mapped to each SDK's
       idiom, not a different operation (e.g. switching database vs. passing the
       db name inline);
     - **naming** — same collection/database/field names across languages.
 5. **Run the snippets for real (ONLY when the user explicitly asks, e.g. "在
    Milvus server 上真实运行").** This step is NOT part of the default check —
    it runs only when the request explicitly asks to execute against a Milvus
    server (see Usage). It does NOT start a Milvus server itself. First extract
    the edited document's code blocks into a local markdown file that the
    bundled runners consume:
    - Fetch the whole document (`docs +fetch --doc <docx> --detail with-ids`),
      extract each `<pre lang="...">` block, undo the XML escaping, and emit a
      temporary page file in the exact shape the runners expect (fenced
      ```lang blocks in document order), e.g.
      `scripts/fetch_to_md.py <docx> --out sdk-tmp/snippet-run/<doc>.md`.
    - **Probe** whether a Milvus server is reachable first:
      `python3 -c "from pymilvus import connections; connections.connect(host='localhost', port=19530, token='root:Milvus'); connections.disconnect('default')"`
      or probe the REST health endpoint `curl -s http://localhost:9091/healthz`.
    - **Server reachable** → run the edited page's snippets per SDK via the
      bundled runners in `scripts/`:

      ```bash
      # python (pymilvus) — logic baseline
      python3 scripts/run_page.py <extracted.md> [seed.py ...]
      # node
      node scripts/run_page_node.mjs <extracted.md>
      # go (needs client/v2 module; run from sdk-tmp/snippet-run/go)
      python3 scripts/run_page_go.py <extracted.md>
      # java (needs maven + milvus-sdk-java)
      python3 scripts/run_page_java.py <extracted.md>
      # rust (resolves the latest milvus-sdk-rust version from crates.io)
      python3 scripts/run_page_rust.py <extracted.md>
      # cpp (uses a prebuilt milvus-sdk-cpp binary from default-conan-local2)
      python3 scripts/run_page_cpp.py <extracted.md> [<version>]
      ```

      The cpp runner installs a **prebuilt** `milvus-sdk-cpp/<version>@milvus/dev`
      binary from the `default-conan-local2` Conan repo with `--build=never`. If
      a binary matching the version/system exists, the cpp blocks are compiled
      and run against it; if **no usable prebuilt binary is found, cpp
      verification is SKIPPED** (reported as skipped — never a hard failure and
      never a from-source build).
    - **Go env**: the go runner needs a toolchain satisfying the client module's
      `go.mod` requirement and a reachable module proxy. On this machine use
      `GOTOOLCHAIN=go1.25.8 GOPROXY=https://goproxy.cn,direct` (both cached/
      reachable); set them in the environment before running `run_page_go.py`.
    - **Per-SDK readiness**: each SDK runner needs its dependency environment
      (npm pkg / go module / maven jar / cargo crate) and toolchain. If the SDK's
      dependency fetch fails (e.g. no network to the registry) or the toolchain is
      missing, **explicitly report** that SDK's snippets were NOT executed and why
      — never silently skip.
    - **Server NOT reachable** → do NOT run the snippets, but **explicitly tell
      the user** in the report: "No Milvus server detected at
      localhost:19530/9091 — snippets were NOT executed. Start a Milvus
      instance (e.g. docker standalone) to enable this check." Never silently
      skip it.
    - **Failures are findings**: when a block fails (wrong API usage, wrong data
      shape), fix the snippet in the Feishu document (Step 3) and re-run so the
      live run passes — this is the point of the check.
 6. **Validate** before reporting done:
   - every section has the full SDK set the document claims (tabs vs blocks
     match);
   - imports/client init in each snippet are consistent with the latest API;
   - sub-step numbering matches across SDKs in the same section;
   - snippets are syntactically plausible (balanced braces/parens, no stray
     placeholders unless intentional);
   - no non-code content was changed.
 7. **Report** a per-document/per-block change list for review, including which
    syntax checks passed/skipped and any unsupported features recorded per SDK.

## Pushing / PR

There is **no git push or PR** for this skill — the Feishu documents are edited
in place, and `docs +update` is immediately visible to everyone with access to
the wiki space. Implications:

- A `docs +update` write **is** the deliverable; there is no local "edits-only"
  stage. Use `--dry-run` to preview a write before committing to it, and report
  every written block in the summary so the user can review what changed.
- Prefer small, reviewable batches per document/section rather than rewriting a
  whole document in one shot.

## Known context

- There is no hardcoded directory table — the user supplies the document/table
  URL each run (see Scope). The typical directory lists ~196 documents; ~190
  have real wiki links, ~6 are placeholders (rbac, concepts, scaling, tools,
  about, storage_optimization) not yet created in Feishu.
- Documents use `<synced-source>` containers with up to six `<pre>` blocks
  (`Python`, `Java`, `JavaScript`, `Go`, `Bash`, `C++`). The block ids and
  `lang` values come from `docs +fetch --detail with-ids`.
- The Feishu docs correspond to the web-content userGuide pages (see
  `/home/myh/work/git-go/web-content/v3.0.x/site/en/userGuide/`), which can be
  cross-referenced when a section's intent is unclear, but the Feishu
  documents are the source of truth for what is actually published.
- Per-SDK client-init and common-operation patterns live in
  `references/snippet-conventions.md`.
