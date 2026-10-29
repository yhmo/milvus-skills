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
- **Concurrent edits to the same document (multi-channel runs) do not conflict
  at the content level — but mind the revision race.** All writes are
  block-level (`block_replace`/`block_insert_after` targeting a specific
  `<pre>` block-id), so two editors touching different code blocks keep both
  changes. The one real risk is the fetch→write window: if another editor's
  write lands between your `docs +fetch` and your `docs +update`, your write is
  based on a stale revision and Feishu may reject it. Mitigate by (1) re-fetching
  right before each write and reusing only the freshly-read block-ids, and
  (2) treating a rejected write as "re-fetch and retry", never as a silent
  skip. Only two editors editing the *same* block overwrite each other —
  the later write wins. 本 skill 的并发场景：多个文档工程师各自处理不同
  链接组，同一文档通常不会同时被两人编辑；若确实需要多人改同一文档的不同
  代码块，务必各自「写前重新 fetch 最新 revision」，写入被拒即重新 fetch 重试。
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
- **Preserve `<include>` product-branch markup inside code blocks.**
  `<include target="milvus">...</include>` and
  `<include target="zilliz">...</include>` are intentional authoring markup for
  the website generator. They mean the enclosed code is product-specific and
  must remain available for the Milvus / Zilliz Cloud variants. Never delete,
  unwrap, merge, or resolve these branches to make a snippet runnable. For
  local real-run checks, create a temporary harness copy that selects one
  branch (normally `milvus`), and keep the Feishu source unchanged. When
  rewriting the enclosing block, preserve the exact `<include>` tags, their
  targets, and nested code unless the user explicitly asks to change product
  branching.
- **Use document-scope clients.** For each language in a document, create and
  declare the SDK client only in the first code block that uses it; later
  same-language blocks reuse that client and must not re-create it. Hoist later
  language dependency statements (`import`, `use`, `using`, `#include`) into
  that first client-using block. If an operation only switches database, call
  `use_database(...)` instead of creating a new client. A second client is
  allowed only for a different cluster or different credentials, and it must
  use a distinct variable name. Manage client lifetime in the first client
  block (for example Go `defer cli.Close(ctx)`, C# `using`). Do not confuse
  language dependency statements with Feishu product-branch `<include>` markup,
  which remains governed by the rule below.
- **Preserve existing comments inside code blocks.** When editing a snippet,
  keep its inline comments (e.g. `// Send keepalive pings...`,
  `# 1. Set up a Milvus client`) verbatim unless a comment is factually wrong
  or no longer matches the code — in that case correct the comment in place.
  Remove a comment only when it is entirely unrelated to the code (e.g. a
  stray paste). Do NOT drop comments just because the surrounding code is being
  rewritten, and do not treat them as noise to strip.
- **Output comments must be real-run only.** If the pymilvus block carries an
  "Example output" (or similar) comment showing the expected output, the other
  SDK blocks for that section should carry matching output comments **only when
  the code has actually been run against a real Milvus server** (Step 5). Output
  comments must be written from the real run's observed output, never guessed.
  If no real-run happened, do NOT fabricate or copy output comments into the
  other languages — leaving them out is correct in that case.
- Within one section the snippets across SDKs must follow the **same logical
  flow and sub-step numbering** as the pymilvus block.
- Match each document's existing per-SDK style (imports, client initialization,
  variable naming); do not introduce a new style mid-document. With the
  document-scope client rule, later blocks omit repeated client creation and
  reuse the first client variable.
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
     **Pass through the `?table=...&view=...` query parameters.** The wiki URL
     often carries `?table=<tableId>&view=<viewId>` — that table/view is what
     the user is actually looking at in the Feishu UI. Capture both values and
     use them below; never drop them, or the record set/order may not match what
     the user sees.
  2. **Directory table (bitable)** → list its records to find the link column,
     **honoring the URL's table and view** so the record set, filtering, and
     ordering match the user's view:
     `lark-cli base +record-list --base-token <token> --table-id <tableId>
     --view-id <viewId> --limit 200 --as user`. Each record's link field (often
     named `Doc` or similar) is `[Title](wiki-url)`.
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

     > **⚠️ Baseline guard (hard rule — no exceptions).** Before adding ANY
     > block to a section, verify that a `Python`/pymilvus block already
     > exists in that section. If no pymilvus baseline block exists — regardless
     > of whether the user prompt asks to add blocks ("补齐遗漏的 java 代码块",
     > "add missing Java blocks", …) — skip the section and report it as
     > `no pymilvus baseline, cannot add`. The "unless the user explicitly
     > asks" escape of this empty-document rule does NOT override this guard:
     > an imperative prompt is never an acceptable substitute for a missing
     > baseline. Generating code from topic knowledge instead of translating a
     > baseline produces hallucinated snippets that do not match the document
     > and is a violation.
  - "only the collections docs", "just the Search page", etc. narrow the scope
    by title/ID as named by the user. When the user names a page by its position
    in the table they shared ("第 3 个页面" / "the 3rd page"), resolve it from
    the **view-ordered** record list (step 2), not the table's default order —
    the UI and `--view-id` share one ordering, while a bare `record-list`
    without `--view-id` returns a different (creation) order. If in doubt,
    confirm which page the user means by title before editing.
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
  cross-SDK reading order. **After finishing snippet work (syntax, consistency,
  and any real-run), verify the order with
  `scripts/check_block_order.py` on the fetched document and reorder any
  group that deviates** (see Step 4 and Step 6).

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

- **Code blocks that are NOT SDK snippets — skip them.** Do not treat the
  following as SDK code to correct, add languages to, or fill imports for; they
  are excluded from all SDK-related checks and fixes:
  - plain-text / pure-text blocks (marked `text` or containing prose only);
  - bash command lines that are ordinary shell/CLI usage (not a REST curl
    block mirroring `/v2/vectordb/*` — REST curl blocks ARE covered);
  - YAML config blocks;
  - output examples (sample command output / results);
  - JSON blocks that represent pure data (request bodies, responses, examples);
  - Python blocks that only prepare data (e.g. using `numpy` to generate
    vectors/datasets) and are unrelated to the SDK API flow.
  These blocks are read for context (they may define names/values referenced by
  SDK blocks) but are never themselves modified or counted toward the SDK set.

## Workflow

0. **Pre-flight: check Feishu auth.** `lark-cli auth status --json` — user
   identity must be `ready`. If not, stop and ask to run the `lark-shared`
   device-flow login. Also read `references/sdk-map.md`
   for the SDKs you will touch.
0b. **Get the SDK repos you need** (once per run). **Prefer an existing local
   checkout first** (`$HOME/work/git-go/<repo>` when present) — it avoids a
   GitHub clone and, since tags are already there, usually avoids the network
   `fetch` too. Only fall back to cloning into the gitignored
   `sdk-tmp/sdks/` when no local checkout exists. Repo names come from
   `references/sdk-map.md`:

   ```bash
   SDK_URL_BASE=https://github.com/milvus-io
   prepare_sdk() {
     local name="$1" local_dir="$HOME/work/git-go/$1" sdk_dir="sdk-tmp/sdks/$1"
     # 1) prefer the local checkout
     if [ -d "$local_dir/.git" ]; then
       if [ -z "$(git -C "$local_dir" tag)" ]; then
         git -C "$local_dir" fetch --tags --force origin   # only if tags missing
       fi
       echo "using local checkout: $local_dir"
       return
     fi
     # 2) fall back to cloning into the gitignored sdk-tmp
     if [ ! -d "$sdk_dir/.git" ]; then
       git clone --filter=blob:none --no-checkout "$SDK_URL_BASE/$name.git" "$sdk_dir"
     fi
     git -C "$sdk_dir" fetch --tags --force origin
     echo "using cloned repo: $sdk_dir"
   }
   prepare_sdk milvus-sdk-cpp    # repeat per SDK you will touch
   ```

   The Go SDK is an exception: it lives inside `milvus-io/milvus` — use
   `prepare_sdk milvus` and diff under `client/` (per `sdk-map.md`).

   **API index (per-SDK, per-tag; generated once, reused forever).** To avoid
   repeatedly grepping the large SDK repos, generate a flat API index for each
   SDK@tag you will touch (mirrors `sdk-map.md`'s latest tag):
   `scripts/gen_api_index.py` writes a TSV of every public method / builder /
   constructor with its **full parameter list** into
   `sdk-tmp/api-index/<sdk>-<tag>.tsv`:

   ```bash
   # one-time per SDK@tag (uses the local checkout from prepare_sdk above)
   python3 scripts/gen_api_index.py --sdk java --tag v3.0.10 \
     --repo $HOME/work/git-go/milvus-sdk-java --out sdk-tmp/api-index/java-v3.0.10.tsv
   # or generate every SDK at one tag (uses $HOME/work/git-go):
   python3 scripts/gen_api_index.py --all --tag v3.0.10 \
     --repo-root $HOME/work/git-go --out sdk-tmp/api-index
   ```

   A git tag never changes, so a cached index is valid forever. Query it
   directly, or let the tools below consume it:
   `python3 scripts/api_index.py <sdk> <tag> <symbol...>`.
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
   - **Baseline guard (apply before ANY addition).** For every section where
      you intend to add a block, first confirm a `Python`/pymilvus `<pre>`
      block exists in that same section. If it does not, skip the addition and
      report `no pymilvus baseline, cannot add` for that section — no matter
      how the user prompt is phrased (see the Baseline guard in Scope). Only
      after the baseline is verified may you proceed to the Missing SDKs rule
      below.
   - **Feature-scope exception — bulk writer / bulk import (pymilvus & Java
      only).** Bulk-writer/bulk-import features (`RemoteBulkWriter`,
      `LocalBulkWriter`, `BulkWriter`, `bulk_import` / `BulkImport`) are
      implemented ONLY by pymilvus and milvus-sdk-java. In documents whose
      subject is bulk writer / bulk import (e.g. "Data Import Hands-On"
      <https://zilliverse.feishu.cn/wiki/BjHZwBkk0iFScik49QMc1Wwjndb>,
      "Import Data (SDK)", any BulkWriter usage page), write **only `Python`
      and `Java` SDK blocks** — never add Go/Rust/C++/JavaScript blocks to
      such documents, not even the "not supported" empty placeholder blocks
      described below, and never report those languages as missing for them.
      Their absence is intentional feature scope, not an omission.
   - **Feature-scope exception — Expected output sections (Python only).**
      `Expected output` sections exist solely to SHOW the output of the
      preceding runnable example — they are not multi-SDK code groups. Do not
      add other languages to an `Expected output` section, do not treat its
      Python-only block as a missing-SDK gap, and never report it as missing.
   - **Feature-scope exception — install / prerequisite command sections
      (Bash only).** Sections whose content is package installation or
      environment-setup commands (`pip install` / `npm install` / `go get` /
      Maven dependency snippets / `brew` / curl installers, under headings like
      `Install ...` or `Prerequisites`) are shell commands by nature — they are
      not SDK code groups. Keep them Bash-only, never add other languages
      there, and never report them as missing.
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
      pymilvus-mirrored flow. **Keep the block's existing comments**: preserve
      them verbatim while fixing code, correct a comment only if it is wrong or
      outdated, and delete a comment only if it is completely unrelated to the
      code. Never drop comments as a side effect of a rewrite.
3. **Rewrite the code block in Feishu.** Replace a `<pre>` block with
   `lark-cli docs +update`:

   ```bash
   lark-cli docs +update --doc <docx> --command block_replace \
     --block-id <pre-block-id> \
     --content '<pre lang="Python"><code>from pymilvus import MilvusClient
   client = MilvusClient(uri="http://localhost:19530", token="root:Milvus")</code></pre>'
   ```

   **Normalize blank lines before writing (MANDATORY).** Feishu converts each
   newline in the payload 1:1 to `<br/>` (an empty line becomes `<br/><br/>`)
   with no de-duplication — any stray blank line in the payload lands verbatim
   in the document. Before composing `--content`, run the snippet's plain code
   text through the bundled normalizer, which removes blank lines between
   consecutive `import`/`use`/`#include`/`from` statements, blank lines inside
   data-structure literals, blank lines immediately after an opening `{` or
   before a closing `}`/`]`/`)`, runs of 2+ blank lines, and leading/trailing
   blank lines (blank lines that separate logical statements inside `func`/
   `main`/`if` bodies are preserved). **It also ensures exactly one blank line
   between the import/include/use region and the first following code line**
   (imports must always be visually separated from the code that uses them — e.g.
   `import ...` / `use ...` / `#include ...` / `from ...` lines are followed by
   one blank line before the client-init/function code):

   ```bash
   python3 scripts/normalize_snippet.py < snippet.txt > snippet-clean.txt
   # or: python3 scripts/normalize_snippet.py --file snippet.txt
   ```

   Use the cleaned text when building the `--content` payload.

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
    parse check. That directory is per-run scratch — it is removed by Step 8's
    `scripts/cleanup_tmp.py` when the task ends.

    **API-existence cross-check (soft findings) — pass `--api-index` and one
    `--sdk-tag sdk@tag` per SDK present in the document** to have the check
    report SDK calls that are not in the per-tag API index (see Step 0b):

    ```bash
    lark-cli docs +fetch --doc <docx> --scope section \
        --start-block-id <heading-block-id> --detail with-ids --as user \
      | python3 scripts/check_snippets.py --doc "<Doc Title>" \
          --api-index sdk-tmp/api-index \
          --sdk-tag java@v3.0.10 --sdk-tag node@v3.0.5
    ```

    Unknown calls are reported per block as `API?` findings — they are **soft**:
    response-object members, doc-defined constants, and cross-block variables
    legitimately absent from the index (e.g. `resp.getJobId()`) should be
    verified manually, not assumed wrong. `python`/`pymilvus`, and go tags
    `client/vX.Y.Z`, are normalized automatically (`python@v3.0.2` reads the
    `pymilvus-v3.0.2.tsv` index; `go@client/v3.0.0-beta` reads
    `go-v3.0.0-beta.tsv`).
    Manually, the same steps are:
    - Fetch the section again (`docs +fetch --scope section --detail with-ids`),
      pull each edited `<pre>`'s code text, undo the XML escaping, and write it
      to `sdk-tmp/snippet-check/<lang>/<doc>-<n>.<ext>`.
    - Then parse-check per language:
     - `check_snippets.py` first wraps fragment blocks in a throwaway skeleton
       per language (reference lines stay on top, the body goes inside a dummy
       function) before invoking the toolchain; blocks that already contain an
       entry point (`fn main`/`func main`/`int main`/`static ... main`) are
       checked as-is. For `rust` → `rustc --edition 2021 --crate-type lib`:
       errors that only stem from missing SDK crates (unresolved
       import/crate/name codes) count as a soft pass; parse errors fail.
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
   - **Snippet fragment rule (all languages).** A doc block consists of
      reference lines (`import` / `#include` / `use` / `using`) plus the logic
      body — NEVER an entry-point wrapper. Do not write `package main` +
      `func main()` (Go), `#[tokio::main]` + `async fn main()` (Rust),
      `int main()` (C++), or a `main`-bearing class (Java) into any code block.
      "Document-scope runnable" means a tester ASSEMBLES one executable per
      language by concatenating that language's blocks in document order,
      putting reference lines before `main` and all logic bodies inside `main`
      in order — each doc block itself stays a fragment. Keep the SDK client
      and language dependency statements (`import` / `#include` / `use` /
      `using`) in the first client-using block for that language. If a later
      block introduces a new dependency statement, hoist it into that first
      block instead of repeating dependency regions in every block. Do not
      confuse these language dependency statements with Feishu
      `<include target="...">` product-branch markup, which stays in its
      original branch location.
   - **No function wrapper either (all languages).** The fragment rule above is
      not limited to entry points: never wrap the logic body in any named
      function/method either. A block must be reference lines + bare statements
      — not `private static String bulkImport() { ... }` (Java),
      `private static void getImportProgress(String jobId) { ... }` (Java),
      `def bulk_import(): ...` (Python), `func bulkImport() { ... }` (Go), or
      any other function enclosing the body. If the upstream code organizes the
      flow into a helper, inline it into the block: keep the statements (with
      any locals they need hoisted), so a reader pastes executable statements
      rather than a function definition they cannot call.
      **Allowed exception — helper-definition blocks mirroring pymilvus.** A
      block that exists to DEFINE a helper function used immediately below in
      the same block or by later sections (e.g. a `print_search_results`
      formatter defined once per SDK, mirroring the pymilvus block's
      `def print_search_results(...)`) is NOT a violation: write it following
      the pymilvus baseline's structure. The prohibition targets wrapper SHELLS
      that lock the block's whole logic behind a function call, not legitimate
      helper definitions that are part of the flow.
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
     language-idiomatic definition in the first client-using block for that
     language** (or the earliest later block that can host it without breaking
     document order):
     - Java → `String NAME = "value";`
     - Go → `NAME := "value"`
     - JavaScript → `const NAME = "value";`
     - C++ → `const std::string NAME = "value";`

     Place it after the hoisted import/include region and before first use.
     Re-run the check until 0 missing references. The goal is a
     document-scope runnable sequence, not making every later block
     independently self-contained.
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
      - **operational parity** — the set of API calls and their input arguments
        must match the Python baseline **item for item**, including **count** and
        **parameters**. Example: if Python creates 2 indexes (`embedding` +
        `product_name`), every other language must also create those same 2
        indexes with the same field names / metric types — a language that
        creates only 1 index is a divergence to fix. Also compare the argument
        set of each call (field names, metric_type, index_type, limit, etc.)
        against the Python block, not just the call's presence;
      - **missing capability → comment, never omit silently.** If a language's
        SDK does NOT implement a specific call or a specific parameter/option that
        the Python block uses, do NOT silently drop the call or the argument —
        keep the block complete and add a comment in that language's syntax
        (e.g. `// Note: ... not supported in milvus-sdk-java as of vX.Y.Z`)
        stating the SDK has not implemented it. Record it in the report too;
      - **naming** — same collection/database/field names across languages;
      - **output-comment parity (real-run only)** — if the Python baseline has
        an "Example output" / expected-output comment, the other languages should
        mirror it **only when the snippets were actually executed against a real
        Milvus server (Step 5)** and the output was captured. Never write an
        output comment into another language unless it comes from a real run;
        without a real run, leaving the output comment out is the correct
        behavior (do not invent or copy output values).
   - **Block order check — every group must follow the canonical SDK order.**
     For every multi-SDK group (a `<synced-source>` container, or a run of
     sibling `<pre>` blocks in one section), the languages must appear in the
     canonical order `Python → Java → Go → Rust → C++ → JavaScript → Bash`,
     and the group must not silently drop a language the doc's other groups
     have. Standalone single-language blocks (FAQ answers) are exempt. Run the
     bundled `scripts/check_block_order.py` on the fetched document:

     ```bash
     lark-cli docs +fetch --doc <docx> --detail with-ids --as user \
       | python3 scripts/check_block_order.py --doc "<Doc Title>"
     ```

     It prints each group's actual language order and reports OUT OF ORDER /
     missing languages. **Fix order with `docs +update --command block_move_after`
     (move `JavaScript`+`Bash` after `C++`, then `Rust` after `Go`) and re-run
     until 0 failures.** Never leave a group out of canonical order.
  5. **Run the snippets for real (ONLY when the user explicitly asks, e.g. "在
     Milvus server 上真实运行").** This step is NOT part of the default check —
     it runs only when the request explicitly asks to execute against a Milvus
     server (see Usage). It does NOT start a Milvus server itself.
     - **Cloud docs (placeholder endpoints) — substitute localhost, don't touch
       the doc.** If the document's snippets use placeholder/cloud endpoints
       (`https://{cluster-id}.{region}.vectordb.zillizcloud.com:19530`,
       `https://api.cloud.zilliz.com`) or placeholder credentials
       (`YOUR_ZILLIZ_API_KEY`, `inxx-xxxxxxxxxxxxxxxxxxx`,
       `YOUR_STORAGE_ACCESS_KEY`), rewrite those endpoints to
       `http://localhost:19530` (and token to `root:Milvus`) **only in the
       local verification copy** so the snippets actually run against the local
       Milvus — **never change the document's placeholders**. Report this
       substitution in the summary. Never ask the user for real cloud
       credentials.
     - **Consistency/visibility workarounds are harness-only — never touch the
       document for them.** A snippet that inserts rows and later
       searches/queries them can legitimately return no rows in a real run: the
       query uses the default `consistency_level=Bounded`, so freshly inserted
       rows are not yet visible, and the collection may not be loaded. **Never
       "fix" the document for this**: do NOT add a `flush()` call or a
       `load_collection()` call, and do NOT set `consistency_level=Strong` on
       any search/query in a Feishu snippet. Those are run-harness concerns, not
       snippet content — the document keeps its original flow unchanged. Instead
       apply the workaround **only in the local verification copy** (same rule
       as the localhost substitution):
       rewrite each language's search/query block to set
       `consistency_level=Strong` (per-SDK equivalent, e.g. pymilvus
       `consistency_level="Strong"`, java `consistencyLevel(...)`, go
       `WithConsistencyLevel(...)`, node `consistency_level: "Strong"`), adding
       `load_collection()` before the first search/query only when the
       collection must be loaded to be searchable, so the run actually returns
       results. Report these substitutions in the summary. The bundled runners'
       internal seed fixtures may call `flush()`/`load_collection()` to prepare
       shared fixture collections — that is harness plumbing, distinct from
       snippet content; never mirror it into document blocks.
     - **Features that cannot be real-run (skip them, but still verify their
       API statically in Step 4).** These need external resources that cannot be
       simulated locally, so their code blocks are NOT executed; note the skip in
       the report:
       - **Bulk import** (`bulk_import` / `BulkImport` / `createImportJobs` /
         `jobs/import/*`) — needs data files in S3/external storage.
       - **External collections** (`ExternalSource` / `external_source` /
         `CreateExternalCollectionReq` / collection docs referencing
         `s3://` external data paths) — needs the referenced S3/external
         storage; syntax-check only.
       - **CDC / change-data-capture** related APIs.
       - **FileResource** related APIs.
       - **ExternalTable** related APIs.
     - First extract the edited document's code blocks into a local markdown
       file that the bundled runners consume:
     - Fetch the whole document (`docs +fetch --doc <docx> --detail with-ids`),
       extract each `<pre lang="...">` block, undo the XML escaping, and emit a
       temporary page file in the exact shape the runners expect (fenced
       ```lang blocks in document order), e.g.
       `scripts/fetch_to_md.py <docx> --out sdk-tmp/snippet-run/<doc>.md`.
       Apply the localhost substitution and the `consistency_level=Strong`
       workaround (both above) to this extracted copy before running. For
       product-branch `<include target="milvus">` /
       `<include target="zilliz">` markup, keep the Feishu source unchanged and
       unwrap only the selected branch in the temporary copy. The runner must
       assemble same-language blocks in document order into one scope and use
       the single document-scope client created by the first client-using
       block. All of `sdk-tmp/snippet-run/` is per-run scratch, cleaned at
       Step 8.
     - **Probe** whether a Milvus server is reachable first:
       `python3 -c "from pymilvus import connections; connections.connect(host='localhost', port=19530, token='root:Milvus'); connections.disconnect('default')"`
       or probe the REST health endpoint `curl -s http://localhost:9091/healthz`.
     - **No server reachable → start one via the `milvus-server-launch`
       skill** (Docker Compose standalone, variants under
       `milvus-server-launch/{2.6,3.0}`): `cd` into a variant directory and
       `docker compose up -d`, then wait for
       `curl -sf http://localhost:9091/healthz`. Only do this when the live-run
       step was explicitly requested; never start a server for parse-only
       checks. Note that the `2.6` and `3.0` variants share container names
       and ports, so only one can run at a time — but if a `3.0` server is
       already running it is reused even when `2.6` was requested (3.0 is
       backward compatible; see that skill's SKILL.md for the auto-switch
       policy).
     - **Server reachable** → run the edited page's snippets per SDK via the
       bundled runners in `scripts/`:

      ```bash
      # python (pymilvus) — logic baseline
      python3 scripts/run_page.py <extracted.md> [seed.py ...]
      # node
      node scripts/run_page_node.mjs <extracted.md>
      # go (needs client/v2 module; run from sdk-tmp/snippet-run/go)
      python3 scripts/run_page_go.py <extracted.md> [--api-index sdk-tmp/api-index --sdk-tag go@client/v3.0.0-beta]
      # java (needs maven + milvus-sdk-java)
      python3 scripts/run_page_java.py <extracted.md> [--api-index sdk-tmp/api-index --sdk-tag java@v3.0.10]
      # rust (resolves the latest milvus-sdk-rust version from crates.io)
      python3 scripts/run_page_rust.py <extracted.md> [--api-index sdk-tmp/api-index --sdk-tag rust@v3.0.2]
      # cpp (uses a prebuilt milvus-sdk-cpp binary from default-conan-local2,
      #     falling back to the GitHub releases page)
      python3 scripts/run_page_cpp.py <extracted.md> [<version>] [--api-index sdk-tmp/api-index --sdk-tag cpp@v3.0.3]
      ```

      **API-index integration.** Pass `--api-index <dir> --sdk-tag sdk@tag` to a
      runner to (a) pin the SDK dependency version to TAG (java/rust/go/cpp —
      skipping the network registry lookup) and (b) print a soft pre-compile
      report of SDK calls not found in the per-tag index (see Step 0b). The
      compile/run step remains authoritative — unknown-call reports are advisory
      only.

      The cpp runner uses a **prebuilt** milvus-sdk-cpp binary. It first tries
      `milvus-sdk-cpp/<version>@milvus/dev` from the `default-conan-local2` Conan
      repo with `--build=never`; if that yields no binary for the version/system,
      it **falls back to the GitHub releases page**
      (`https://github.com/milvus-io/milvus-sdk-cpp/releases/tag/v<version>`),
      whose **Assets** contain prebuilt binary packages per platform
      (`libmilvus-<ver>-<arch>-<OS>.[deb|rpm|tar.gz]`). The runner selects the
      asset matching the current platform (arch + Linux distro / macOS /
      Windows), downloads it, and extracts `include/` + `lib/` from it. If the
      cpp blocks compile and run against the binary, verification passes; if
      **no usable prebuilt binary is found from either source, cpp verification
      is SKIPPED** (reported as skipped — never a hard failure and never a
      from-source build).
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
    - **Failures are findings**: when a block fails on actual wrong API usage or
      wrong data shape, fix the snippet in the Feishu document (Step 3) and
      re-run so the live run passes — this is the point of the check. A failure
      caused only by consistency/visibility timing (Bounded consistency hiding
      freshly inserted rows, or a collection the page never loads) is NOT a
      snippet bug: leave the document unchanged and make the run pass via the
      `consistency_level=Strong` workaround in the local verification copy (see
      the harness-only rule above).
    - **Output comments are written here and only here.** If the pymilvus block
      shows an "Example output" (or similar) comment and the section's snippets
      actually run against the server, add the matching output comment to the
      other languages **from the observed real-run output** (each language's
      comment syntax, Step 4 consistency rule). Do not copy Python's printed
      shape verbatim if an SDK prints differently — use what that SDK actually
      printed. When a real run did not happen, do not add output comments at all.
 6. **Validate** before reporting done:
   - every section has the full SDK set the document claims (tabs vs blocks
     match);
   - every multi-SDK group is in canonical order — run
     `scripts/check_block_order.py` on the final fetch and confirm 0 failures
     (see Step 4);
   - imports/client init in each snippet are consistent with the latest API;
   - sub-step numbering matches across SDKs in the same section;
   - snippets are syntactically plausible (balanced braces/parens, no stray
     placeholders unless intentional);
   - any original `<include target="milvus">` /
     `<include target="zilliz">` markup inside code blocks is still present
     with the same targets and nested branches;
   - no written block has stray blank lines: no blank lines between imports or
     inside data-structure literals, and no runs of 2+ consecutive blank lines
     (`<br/><br/>` runs in the fetched `<pre>`). Re-run
     `scripts/normalize_snippet.py` on any block that still contains them and
     rewrite it (Step 3);
   - no non-code content was changed.
 7. **Report** a per-document/per-block change list for review, including which
    syntax checks passed/skipped and any unsupported features recorded per SDK.
 8. **Clean up one-off temp artifacts** (end of every run, mandatory):
   `python3 scripts/cleanup_tmp.py` — deletes `sdk-tmp/snippet-check/` and
   `sdk-tmp/snippet-run/` (both are per-run snapshots of the Feishu docs and
   are regenerated next run). The reusable caches `sdk-tmp/api-index/` and
   `sdk-tmp/sdks/` are preserved. Use `--dry-run` first if unsure what would
   be removed; add `--deep` to also sweep ad-hoc scratch files a session
   dropped directly under `sdk-tmp/` (payload XMLs, one-off fix files, ...).
   See "Temporary files & cleanup" below.

## Temporary files & cleanup

The run writes local artifacts under `sdk-tmp/`. They fall into two classes:

- **Reusable caches — kept after the run:**
  - `sdk-tmp/api-index/<sdk>-<tag>.tsv` — API index per SDK@tag; a git tag is
    immutable, so a generated index is valid forever. Regenerating costs a
    full repo scan, so never delete these at end of run.
  - `sdk-tmp/sdks/<repo>` — fallback SDK clones (only used when
    `$HOME/work/git-go/<repo>` is absent); they persist and are refreshed with
    a cheap `git fetch --tags` on the next run.
- **One-off artifacts — deleted at end of run** (Step 8, via
  `scripts/cleanup_tmp.py`):
  - `sdk-tmp/snippet-check/` — extracted snippet files for the parse checks;
    a stale copy of a since-edited Feishu doc is meaningless to the next run.
  - `sdk-tmp/snippet-run/` — extracted markdown pages and the per-language
    runner project dirs (go/java/rust/cpp); regenerated and re-patched
    (localhost substitution, `consistency_level=Strong`) every real run.

`cleanup_tmp.py` only ever deletes directories named `snippet-check` or
`snippet-run` directly inside a `sdk-tmp` dir — anything else under
`sdk-tmp` is untouched in the default mode. With `--deep` it additionally
removes every other entry directly under `sdk-tmp` (ad-hoc scratch such as
`*-payload.xml` or one-off fix files), while `api-index/` and `sdks/` are
always preserved in both modes, and hidden entries (dotfiles) are never
touched. If the skill must abort early (auth failure, missing SDK skills,
user cancel), run the same cleanup before stopping so no stale snapshot is
left behind.

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
- The Feishu documents are the **source of truth**: the web-content userGuide
  pages (see
  `/home/myh/work/git-go/web-content/v3.0.x/site/en/userGuide/`) are generated
  **from** the Feishu docs, so they routinely lag behind them. Do **not** use
  web-content to judge snippet correctness or which SDK version to write
  against — always write against the **latest SDK version** (latest git tag in
  `references/sdk-map.md`), independent of any web-content export.
- Per-SDK client-init and common-operation patterns live in
  `references/snippet-conventions.md`.
