#!/usr/bin/env python3
"""Convert a Feishu document fetch (XML content) into a temporary markdown page.

The bundled run_page_* runners consume fenced code blocks in document order
(e.g. ```python ... ```), which is exactly what these Feishu user-guide docs
contain as <pre lang="..."> blocks. This helper extracts every <pre> from the
fetch XML, undoes the escaping, and writes a .md with the blocks in order so the
runners can execute them against a live Milvus server.

Usage:
  lark-cli docs +fetch --doc <docx> --detail with-ids --as user \
    | python3 fetch_to_md.py --doc "Create Collection" --out sdk-tmp/snippet-run/create-collection.md

  python3 fetch_to_md.py --xml fetch.xml --doc "Create Collection" --out out.md

Options:
  --doc NAME    label used only for the report (default: doc)
  --xml FILE    read fetch XML from a file instead of stdin
  --out PATH    output markdown path (required)
  --isolate     rewrite every collection the page references to a page-unique
                name (derived from --out basename), so ALL SDK runners hit the
                same isolated collection per document (see the per-document
                isolated-collection rule in SKILL.md Step 5). Implies the run
                harness never shares fixtures across pages.
"""
import argparse
import html
import re
import sys

PRE_RE = re.compile(r'<pre\s+id="[^"]*"(?:\s+[^>]*?)lang="([^"]*)"[^>]*>(.*?)</pre>', re.S)
CODE_RE = re.compile(r'^<code>(.*)</code>$', re.S)

LANG_TAG = {
    "Python": "python", "Java": "java", "JavaScript": "javascript",
    "Go": "go", "Bash": "bash", "C++": "cpp", "Rust": "rust",
    "XML": "xml",
}

# `Shell` (the `zilliz` CLI) is a Zilliz Cloud CLI, not an SDK block: the skill
# leaves it alone entirely, so it is dropped from the extracted page (never run).
IGNORED = {"Shell"}


def normalize_lang(lang: str) -> str:
    return LANG_TAG.get(lang, lang.lower())


def decode_block(raw: str) -> str:
    m = CODE_RE.match(raw.strip())
    if m:
        raw = m.group(1)
    text = re.sub(r"<br\s*/?>", "\n", raw)
    text = re.sub(r"<em>(.*?)</em>", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


# Collection names the harness knows as fixtures. Combined with collection names
# the page itself creates (or placeholders it defines), these are rewritten to
# page-unique names under --isolate so every SDK runner hits the same isolated
# collection per document.
KNOWN_COLLECTIONS = {
    "quick_setup", "my_collection", "product_catalog", "iterator_collection",
    "customer_profiles", "my_collection_1", "my_collection_2",
}


def _referenced_collections(*texts):
    names = set()
    for text in texts:
        for m in re.finditer(r"[\"']([A-Za-z0-9_]{1,64})[\"']", text):
            cand = m.group(1)
            if cand in KNOWN_COLLECTIONS:
                names.add(cand)
        for m in re.finditer(
                r"(?:collection_name|collectionName|collection)\s*[:=]\s*"
                r"[\"']([^\"']+)[\"']", text):
            names.add(m.group(1))
    return names


def _page_stem(out_path):
    base = out_path.rsplit("/", 1)[-1]
    stem = re.sub(r"\.md$", "", base)
    return re.sub(r"[^A-Za-z0-9_]", "_", stem)


def _rewrite_collections(text, mapping):
    for orig, repl in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(rf"\b{re.escape(orig)}\b", repl, text)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doc", default="doc", help="label for the report")
    ap.add_argument("--xml", help="file containing the fetch XML content")
    ap.add_argument("--out", required=True, help="output markdown path")
    ap.add_argument("--isolate", action="store_true",
                    help="rewrite collection names to page-unique isolated names")
    args = ap.parse_args()

    content = open(args.xml).read() if args.xml else sys.stdin.read()

    # Accept either the raw XML content or the CLI's JSON envelope
    # ({data: {document: {content: ...}}}), auto-detected by the first char.
    stripped = content.lstrip()
    if stripped.startswith("{") and '"document"' in content[:2000]:
        try:
            import json
            content = json.loads(stripped)["data"]["document"]["content"]
        except (KeyError, ValueError):
            pass  # not the expected envelope; fall through to raw content

    blocks = PRE_RE.findall(content)
    if not blocks:
        print(f"=== {args.doc}: no <pre> code blocks found (raw length {len(content)})")
        sys.exit(1)

    # --isolate: map every collection the page touches to a page-unique name so
    # all SDK runners hit the same isolated collection (never shared fixtures).
    mapping = {}
    decoded = [(lang_raw, normalize_lang(lang_raw), decode_block(body))
               for lang_raw, body in blocks if lang_raw not in IGNORED]
    if args.isolate:
        refs = _referenced_collections(*(d for _, _, d in decoded))
        stem = _page_stem(args.out)
        mapping = {n: f"{stem}_{n}" for n in sorted(refs)}

    with open(args.out, "w") as f:
        for lang_raw, lang, code in decoded:
            if args.isolate:
                code = _rewrite_collections(code, mapping)
            f.write(f"```{lang}\n{code}\n```\n\n")

    written = [b for b in blocks if b[0] not in IGNORED]
    iso_note = f" | isolated names: {sorted(mapping.values())}" if mapping else ""
    print(f"=== {args.doc}: wrote {len(written)} code blocks to {args.out} "
          f"(ignored {len(blocks) - len(written)} Shell/zilliz CLI blocks){iso_note} ===")
    for i, (lang_raw, _) in enumerate(blocks):
        if lang_raw in IGNORED:
            print(f"  [{lang_raw}] block {i}: ignored (zilliz CLI)")
        else:
            print(f"  [{normalize_lang(lang_raw)}] block {i}")


if __name__ == "__main__":
    main()
