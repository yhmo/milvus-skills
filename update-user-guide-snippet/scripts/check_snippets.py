#!/usr/bin/env python3
"""Extract <pre> code blocks from a Feishu document fetch and syntax-check them.

Reads the XML `content` produced by `lark-cli docs +fetch ... --detail with-ids`
(either from stdin or a file), extracts every <pre lang="..."> code block,
undoes the XML escaping the document uses (&lt;, &gt;, &amp;, <br/>, <em>), and
runs a parse-only syntax check per language with the local toolchain.

Optionally cross-checks API calls against the per-tag SDK API index
(see `gen_api_index.py` / `api_index.py`): pass --api-index (index dir) and
--sdk-tag sdk@tag (repeatable). Unknown SDK calls are reported per block
(soft findings, not hard failures).

Usage:
  lark-cli docs +fetch --doc <docx> --scope section \
      --start-block-id <heading> --detail with-ids --as user | \
    python3 check_snippets.py --doc "Create Collection" [--sdk-tmp sdk-tmp] \
      [--api-index sdk-tmp/api-index --sdk-tag java@v3.0.10 --sdk-tag node@v3.0.5]

  python3 check_snippets.py --xml section.xml --doc "Create Collection"

Options:
  --doc NAME       human-readable label for the report (default "doc")
  --out-dir DIR    where extracted snippet files are written (default: sdk-tmp/snippet-check)
  --cpp-includes   colon-separated include dirs for the cpp check (default: none)
  --api-index DIR  directory holding per-(sdk, tag) API index .tsv files
  --sdk-tag SDK@TAG  enable API-existence check for this SDK@tag (repeatable)

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


# Languages intentionally not checked: `Shell` (the `zilliz` CLI) is a Zilliz
# Cloud CLI, not an SDK block, and the skill leaves it alone entirely.
IGNORED = {"shell"}

# Languages whose doc blocks are snippet fragments (reference lines + body) and
# need a throwaway skeleton assembled before a toolchain can parse them.
FRAGMENT_LANGS = {"go", "java", "cpp", "rust"}

ENTRY_POINT_RE = {
    # A block that already carries an entry point is legacy/self-contained —
    # check it as-is instead of double-wrapping.
    "go": re.compile(r"^\s*(package\s+\w+|func\s+main\s*\()", re.M),
    "java": re.compile(r"\bmain\s*\("),
    "cpp": re.compile(r"\bint\s+main\s*\("),
    "rust": re.compile(r"fn\s+main\s*\("),
}

# rustc error codes that only stem from the SDK crates not being vendored in
# the check environment — resolution-only, treated as a soft pass.
RUST_SOFT_CODES = {
    "E0412", "E0422", "E0425", "E0432", "E0433", "E0434", "E0437",
    "E0405", "E0463", "E0599", "E0560", "E0603", "E0658",
    # `Result<()>`-style aliases resolve only with the SDK crate present.
    "E0107",
}


def wrap_fragment(lang: str, code: str) -> str:
    """Assemble a parseable file: reference lines on top, body in a dummy fn."""
    if lang not in ENTRY_POINT_RE or ENTRY_POINT_RE[lang].search(code):
        return code
    lines = code.split("\n")
    if lang == "go":
        refs, body, i = [], [], 0
        while i < len(lines):
            ln = lines[i].rstrip()
            if ln.startswith("import ("):
                j = i
                while j < len(lines) and lines[j].strip() != ")":
                    j += 1
                refs.extend(lines[i : j + 1])
                i = j + 1
                continue
            if ln.startswith("import "):
                refs.append(ln)
            else:
                body.append(ln)
            i += 1
        return (
            "package snippet_check\n\n"
            + "\n".join(refs)
            + "\n\nfunc snippetRun() {\n"
            + "\n".join(body)
            + "\n}\n"
        )
    if lang == "java":
        refs = [l for l in lines if l.strip().startswith("import ")]
        body = [l for l in lines if not l.strip().startswith("import ")]
        return (
            "\n".join(refs)
            + "\n\nclass SnippetCheck { static void snippetRun() throws Exception {\n"
            + "\n".join(body)
            + "\n} }\n"
        )
    if lang == "cpp":
        ref_re = re.compile(r"\s*(#(include|define)|using\s)")
        refs = [l for l in lines if ref_re.match(l)]
        body = [l for l in lines if not ref_re.match(l)]
        return (
            "\n".join(refs)
            + "\n\nint snippetRun() {\n"
            + "\n".join(body)
            + "\nreturn 0;\n}\n"
        )
    if lang == "rust":
        refs = [
            l for l in lines
            if l.strip().startswith(("use ", "extern crate"))
        ]
        body = [
            l for l in lines
            if not l.strip().startswith(("use ", "extern crate"))
        ]
        return (
            "\n".join(refs)
            + "\n\nasync fn snippet_run() -> Result<(), Box<dyn std::error::Error>> {\n"
            + "\n".join(body)
            + "\nOk(())\n}\n"
        )
    return code


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
    ap.add_argument("--api-index", default="", help="dir holding per-(sdk,tag) API index .tsv")
    ap.add_argument("--sdk-tag", action="append", default=[], metavar="SDK@TAG")
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

    # Build per-lang ApiIndex from --sdk-tag entries.
    idx_by_lang = {}
    if args.api_index:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import api_index as ai
        for sdk_tag in args.sdk_tag:
            sdk, _, tag = sdk_tag.partition("@")
            idx = ai.resolve_index(sdk, tag, args.api_index)
            if idx:
                idx_by_lang[idx.lang] = idx
            else:
                print(f"  WARN: no API index for {sdk}@{tag} in {args.api_index}")

    blocks = PRE_RE.findall(content)
    if not blocks:
        print(f"=== {args.doc}: no <pre> code blocks found (raw length {len(content)})")
        return 0

    results = []
    api_findings = 0
    for i, (lang_raw, body) in enumerate(blocks):
        lang = normalize_lang(lang_raw)
        if lang in IGNORED:
            results.append((i, lang_raw, "skipped (ignored lang)", True))
            continue
        if lang not in LANGS:
            results.append((i, lang_raw, "skipped (unknown lang)", True))
            continue
        code = decode_block(body)
        if not code.strip():
            results.append((i, lang_raw, "skipped (empty block)", True))
            continue
        ext, cmd = LANGS[lang]
        path = os.path.join(args.out_dir, f"{lang}-{i:02d}{ext}")
        wrapped = wrap_fragment(lang, code) if lang in FRAGMENT_LANGS else code
        with open(path, "w") as f:
            f.write(wrapped)
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
            elif lang == "rust":
                output = (r.stderr or r.stdout)
                codes = set(re.findall(r"error\[E(\d+)\]", output))
                if codes and codes <= {c[1:] for c in RUST_SOFT_CODES}:
                    results.append(
                        (i, lang_raw, "OK (soft: unresolved SDK crates only)", True)
                    )
                else:
                    err = output.strip().splitlines()
                    results.append((i, lang_raw, "FAIL", False, err[-3:]))
            else:
                err = (r.stderr or r.stdout).strip().splitlines()
                results.append((i, lang_raw, "FAIL", False, err[-3:]))
        except FileNotFoundError:
            results.append((i, lang_raw, "skipped (toolchain missing)", True))
        except subprocess.TimeoutExpired:
            results.append((i, lang_raw, "skipped (timeout)", True))

        # API-existence cross-check (soft findings)
        if lang in idx_by_lang:
            idx = idx_by_lang[lang]
            unknown = ai.check_code(idx, lang, code, idx.sdk)
            if unknown:
                api_findings += len(unknown)
                print(f"  API? [{lang}] block {i}: {len(unknown)} unknown SDK call(s)")
                for expr, sym in unknown[:10]:
                    print(f"      {sym}  (from {expr!r})")

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

    if api_findings:
        print(f"=== {args.doc}: {api_findings} API calls not found in SDK index "
              f"(soft findings — verify manually if they are response-object "
              f"members or doc-defined constants) ===")

    return 0 if all(r[3] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
