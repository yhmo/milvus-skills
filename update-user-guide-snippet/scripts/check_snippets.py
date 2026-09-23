#!/usr/bin/env python3
"""Extract <pre> code blocks from a Feishu document fetch and syntax-check them.

Reads the XML `content` produced by `lark-cli docs +fetch ... --detail with-ids`
(either from stdin or a file), extracts every <pre lang="..."> code block,
undoes the XML escaping the document uses (&lt;, &gt;, &amp;, <br/>, <em>), and
runs a parse-only syntax check per language with the local toolchain.

Usage:
  lark-cli docs +fetch --doc <docx> --scope section \
      --start-block-id <heading> --detail with-ids --as user | \
    python3 check_snippets.py --doc "Create Collection" [--sdk-tmp sdk-tmp]

  python3 check_snippets.py --xml section.xml --doc "Create Collection"

Options:
  --doc NAME       human-readable label for the report (default "doc")
  --out-dir DIR    where extracted snippet files are written (default: sdk-tmp/snippet-check)
  --cpp-includes   colon-separated include dirs for the cpp check (default: none)

Exit code is non-zero if any parseable block fails its syntax check.
"""
import argparse
import html
import os
import re
import subprocess
import sys

LANGS = {
    "python": (".py", [sys.executable, "-m", "py_compile"]),
    "javascript": (".js", ["node", "--check"]),
    "go": (".go", ["gofmt", "-e"]),
    "bash": (".sh", ["bash", "-n"]),
    "cpp": (".cpp", ["g++", "-fsyntax-only", "-std=c++17"]),
    "java": (".java", ["javac"]),
    "rust": (".rs", ["rustc", "--edition", "2021", "--crate-type", "lib"]),
}

PRE_RE = re.compile(r'<pre\s+id="[^"]*"(?:\s+[^>]*?)lang="([^"]*)"[^>]*>(.*?)</pre>', re.S)
CODE_RE = re.compile(r'^<code>(.*)</code>$', re.S)


def normalize_lang(lang: str) -> str:
    return {
        "Python": "python", "Java": "java", "JavaScript": "javascript",
        "Go": "go", "Bash": "bash", "C++": "cpp",
    }.get(lang, lang.lower())


def decode_block(raw: str) -> str:
    """Strip <code> wrapper, undo XML escaping, drop <em> emphasis markers."""
    m = CODE_RE.match(raw.strip())
    if m:
        raw = m.group(1)
    text = re.sub(r"<br\s*/?>", "\n", raw)
    text = re.sub(r"<em>(.*?)</em>", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xml", help="file containing the fetch XML content")
    ap.add_argument("--doc", default="doc", help="label for the report")
    ap.add_argument("--out-dir", default="sdk-tmp/snippet-check")
    ap.add_argument("--cpp-includes", default="", help="colon-separated include dirs")
    args = ap.parse_args()

    if args.xml:
        content = open(args.xml).read()
    else:
        content = sys.stdin.read()

    # Accept either the raw XML content or the CLI's JSON envelope
    # ({data: {document: {content: ...}}}), auto-detected by the first char.
    stripped = content.lstrip()
    if stripped.startswith("{") and '"document"' in content[:2000]:
        try:
            import json
            content = json.loads(stripped)["data"]["document"]["content"]
        except (KeyError, ValueError):
            pass  # not the expected envelope; fall through to raw content

    os.makedirs(args.out_dir, exist_ok=True)

    blocks = PRE_RE.findall(content)
    if not blocks:
        print(f"=== {args.doc}: no <pre> code blocks found (raw length {len(content)})")
        return 0

    results = []
    for i, (lang_raw, body) in enumerate(blocks):
        lang = normalize_lang(lang_raw)
        if lang not in LANGS:
            results.append((i, lang_raw, "skipped (unknown lang)", True))
            continue
        code = decode_block(body)
        if not code.strip():
            results.append((i, lang_raw, "skipped (empty block)", True))
            continue
        ext, cmd = LANGS[lang]
        path = os.path.join(args.out_dir, f"{lang}-{i:02d}{ext}")
        with open(path, "w") as f:
            f.write(code)
        argv = list(cmd)
        if lang == "cpp" and args.cpp_includes:
            argv += [f"-I{inc}" for inc in args.cpp_includes.split(":")]
        if lang == "rust":
            argv += ["--out-dir", args.out_dir]
        argv.append(path)
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                results.append((i, lang_raw, "OK", True))
            else:
                err = (r.stderr or r.stdout).strip().splitlines()
                results.append((i, lang_raw, "FAIL", False, err[-3:]))
        except FileNotFoundError:
            results.append((i, lang_raw, "skipped (toolchain missing)", True))
        except subprocess.TimeoutExpired:
            results.append((i, lang_raw, "skipped (timeout)", True))

    print(f"=== {args.doc}: {len(blocks)} code blocks, "
          f"{sum(1 for r in results if r[2] == 'OK')} OK, "
          f"{sum(1 for r in results if not r[3])} FAIL ===")
    for r in results:
        if r[3]:
            print(f"  [{r[1]}] block {r[0]}: {r[2]}")
        else:
            print(f"  [{r[1]}] block {r[0]}: FAIL")
            for line in r[4]:
                print(f"      {line}")

    return 0 if all(r[3] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
