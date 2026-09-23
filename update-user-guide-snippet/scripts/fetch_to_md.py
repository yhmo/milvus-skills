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
    "Shell": "bash", "XML": "xml",
}


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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doc", default="doc", help="label for the report")
    ap.add_argument("--xml", help="file containing the fetch XML content")
    ap.add_argument("--out", required=True, help="output markdown path")
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

    with open(args.out, "w") as f:
        for i, (lang_raw, body) in enumerate(blocks):
            lang = normalize_lang(lang_raw)
            code = decode_block(body)
            f.write(f"```{lang}\n{code}\n```\n\n")

    print(f"=== {args.doc}: wrote {len(blocks)} code blocks to {args.out} ===")
    for i, (lang_raw, _) in enumerate(blocks):
        print(f"  [{normalize_lang(lang_raw)}] block {i}")


if __name__ == "__main__":
    main()
