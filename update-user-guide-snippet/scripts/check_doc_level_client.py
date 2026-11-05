#!/usr/bin/env python3
"""Check user-guide code blocks against Rule 4 (doc-level client) and Rule 5
(dependency hoisting).

Parses the fetch output of `lark-cli docs +fetch --doc <docx> --detail with-ids
--as user`, extracts every `<pre lang="...">` block, and reports, per SDK
language:

Rule 5 (dependency hoisting):
  - `import`/`#include`/`use`/`using` statements must appear in EXACTLY ONE
    block: the first client-using block for that language. Any dependency
    statement in a later block is a violation.
  - When no client-using block is detected (e.g. the doc uses a
    BulkWriter/VolumeManager with a different variable name), dep statements
    scattered across blocks are reported as a SOFT finding needing review.

Rule 4 (doc-level client):
  - the SDK client must be created/declared only in the first client-using
    block; a later block that re-creates the client is a violation.

Scope note: this tool treats the whole fetched document as ONE workflow scope
(consistent with scripts/hoist_dependencies.py). Documents with multiple
independent workflows (each with its own client, e.g. AutoID vs manual-ID
examples) should be checked per workflow — feed the tool a fetch containing
only that workflow's blocks, or review multi-workflow reports manually.

Usage:
  lark-cli docs +fetch --doc <docx> --detail with-ids --as user \
    | python3 check_doc_level_client.py --doc "<Doc Title>"

  python3 check_doc_level_client.py --xml fetch.xml --doc "<Doc Title>"

Options:
  --doc NAME   human-readable label for the report (default "doc")
  --xml FILE   read fetch output from a file instead of stdin

Exit code is non-zero if any hard violation is found (soft findings alone do
not fail).
"""
import argparse
import html
import json
import re
import sys

SDK_LANGS = ["Python", "Java", "JavaScript", "Go", "Rust", "C++", "C#"]

# Dependency-line matchers (mirrors scripts/hoist_dependencies.py).
DEP_RE = {
    "Python": re.compile(r"^\s*(?:from\s+\S+\s+import\s+\S.*|import\s+\S.*)$"),
    "Java": re.compile(r"^\s*import\s+\S.*;?$"),
    "JavaScript": re.compile(r"^\s*import\s+\S.*;?$"),
    "Go": re.compile(r"^\s*import\s*\(|^\s*\)\s*$|^\s*(?:[A-Za-z_][\w]*\s+)?\"[^\"]*\"\s*$|^\s*import\s"),
    "Rust": re.compile(r"^\s*use\s+\S.*;?$"),
    "C++": re.compile(r"^\s*#include\s+[<\"]\S+[>\"]$"),
    "C#": re.compile(r"^\s*using\s+(?!var\b|await\b)[\w.]+(?:\s*=\s*.*)?;?$"),
}

# Client-usage detector: True for a block that creates or uses the client.
CLIENT_USE = {
    "Python": re.compile(r"\bclient\s*=|client\.\w+\s*\("),
    "Java": re.compile(r"\bclient\s*=|client\.\w+\s*\("),
    "JavaScript": re.compile(r"\bclient\s*=|client\.\w+\s*\("),
    "Go": re.compile(r"\b(?:client|cli)(?:,\s*\w+)?\s*[:=]|\b(?:client|cli)\.\w+\s*\("),
    "Rust": re.compile(r"\bclient\s*=|client\.\w+\s*\("),
    "C++": re.compile(r"\bclient\b"),
    "C#": re.compile(r"\bclient\b"),
}

# Client-creation statement detector (for doc-level-client rule 4).
CLIENT_CREATE = {
    "Python": re.compile(r"\bclient\s*=\s*MilvusClient\("),
    "Java": re.compile(r"(?:MilvusClientV2\s+|var\s+)client\s*=\s*new\s+MilvusClientV2\("),
    "JavaScript": re.compile(r"(?:const|let|var)\s+client\s*=\s*new\s+(?:MilvusClient|Client)\("),
    "Go": re.compile(r"(?:client|cli),\s*err\s*[:=]=\s*milvusclient\.New|milvusclient\.New\("),
    "Rust": re.compile(r"let\s+client\s*=\s*ClientV2::new\("),
    "C++": re.compile(r"(?:auto\s+)?client\s*=\s*(?:milvus::)?MilvusClientV2::Create\(\)"),
    "C#": re.compile(r"(?:using\s+)?(?:var\s+|MilvusClientV2\s+)client\s*=\s*new\s+MilvusClientV2\("),
}


def read_content(args):
    content = open(args.xml).read() if args.xml else sys.stdin.read()
    stripped = content.lstrip()
    if stripped.startswith("{") and '"document"' in content[:2000]:
        try:
            return json.loads(stripped)["data"]["document"]["content"]
        except (KeyError, ValueError):
            pass
    return content


def extract_blocks(content):
    out = []
    for m in re.finditer(r'<pre\s+id="([^"]+)"[^>]*lang="([^"]*)"[^>]*>(.*?)</pre>', content, re.S):
        bid, lang, body = m.groups()
        text = re.sub(r"<br\s*/?>", "\n", body)
        text = re.sub(r"<em>(.*?)</em>", r"\1", text)
        text = re.sub(r"<[^>]+>", "", text)
        out.append((bid, lang, html.unescape(text)))
    return out


def _has(pattern, text):
    return any(pattern.match(ln) for ln in text.split("\n"))


def check_doc(content):
    """Return (hard_violations, soft_findings) as lists of (lang, message)."""
    blocks = extract_blocks(content)
    hard, soft = [], []
    for lang in SDK_LANGS:
        items = [(b, t) for b, l, t in blocks if l == lang]
        if not items:
            continue
        # first client-using block
        first = None
        for b, t in items:
            if CLIENT_USE[lang].search(t):
                first = (b, t)
                break
        dep_blocks = [b for b, t in items if _has(DEP_RE[lang], t)]
        create_blocks = [b for b, t in items if CLIENT_CREATE[lang].search(t)]
        if first is None:
            if dep_blocks:
                soft.append((lang, f"no client-using block found; dependency statements in {len(dep_blocks)} block(s) — review (may use BulkWriter/VolumeManager or another variable name)"))
            continue
        first_id = first[0]
        later_deps = [b for b in dep_blocks if b != first_id]
        later_creates = [b for b in create_blocks if b != first_id]
        if later_deps:
            hard.append((lang, f"[dep-hoisting] import/#include/use/using in non-first blocks: {[b[:12] for b in later_deps]}"))
        if later_creates:
            hard.append((lang, f"[doc-level-client] client re-created in blocks: {[b[:12] for b in later_creates]}"))
    return hard, soft


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc", default="doc", help="label for the report")
    ap.add_argument("--xml", help="file containing the fetch output")
    args = ap.parse_args()
    content = read_content(args)
    hard, soft = check_doc(content)
    if not hard and not soft:
        print(f"=== {args.doc}: 0 rule-4/5 findings ===")
        sys.exit(0)
    print(f"=== {args.doc}: {len(hard)} hard violation(s), {len(soft)} soft finding(s) ===")
    for lang, msg in hard:
        print(f"  HARD {lang}: {msg}")
    for lang, msg in soft:
        print(f"  SOFT {lang}: {msg}")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
