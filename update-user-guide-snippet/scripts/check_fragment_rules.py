#!/usr/bin/env python3
"""Check user-guide code blocks against Rule 6 (fragment, no entry-point /
function wrapper) and Rule 7 (blank-line normalization).

Parses the fetch output of `lark-cli docs +fetch --doc <docx> --detail with-ids
--as user`, extracts every `<pre lang="...">` block, and reports violations:

Rule 6 (Fragment):
  - entry points: `package main` + `func main()`, `int main()`, `fn main()`,
    `#[tokio::main]`, Java `public static void main`, C# `static void Main`;
  - function wrapper shells (Java/Go/Rust/C++/JS/C# method definitions, Python
    `def`), excluding helper-definition blocks that mirror pymilvus (data
    generators like `gen_*`, formatters like `print_search_results`, builders
    like `buildEntity`/`getOutputFields`).

Rule 7 (blank-line normalization, per scripts/normalize_snippet.py):
  - leading/trailing blank lines;
  - 2+ consecutive blank lines;
  - blank lines between consecutive import/use/#include/from statements;
  - blank line right after an opening `{` or right before a closing-only
    `}`/`]`/`)` line;
  - import region → first code line gap not exactly one blank line (handles
    Go `import (...)` groups and Python `from X import (...)` groups).

Non-SDK data/format blocks (JSON, Plain Text, YAML, XML, HTTP, SQL, Shell
output) are excluded from Rule 7; SDK languages plus Bash/Shell are checked.

Usage:
  lark-cli docs +fetch --doc <docx> --detail with-ids --as user \
    | python3 check_fragment_rules.py --doc "<Doc Title>"

  python3 check_fragment_rules.py --xml fetch.xml --doc "<Doc Title>"

Options:
  --doc NAME   human-readable label for the report (default "doc")
  --xml FILE   read fetch output from a file instead of stdin

Exit code is non-zero if any violation is found.
"""
import argparse
import html
import json
import re
import sys

SDK = {"Python", "Java", "JavaScript", "Go", "Rust", "C++", "C#",
       "python", "java", "javascript", "go", "rust", "c++", "c#"}
# code languages for blank-line (rule 7) checks; JSON/Plain Text/YAML/etc are data
CODE_LANGS = SDK | {"Bash", "Shell", "bash", "shell"}

IMPORT_LINE = {
    "Python": re.compile(r"^\s*(?:from\s+\S+\s+import|import\s)"),
    "Java": re.compile(r"^\s*import\s"),
    "JavaScript": re.compile(r"^\s*import\s"),
    "Go": re.compile(r"^\s*import\s"),
    "Rust": re.compile(r"^\s*use\s"),
    "C++": re.compile(r"^\s*#include\s"),
    "C#": re.compile(r"^\s*using\s+(?!var\b|await\b)"),
    "go": re.compile(r"^\s*import\s"),
    "python": re.compile(r"^\s*(?:from\s+\S+\s+import|import\s)"),
}
CLOSE_ONLY = re.compile(r"^\s*[}\])][;,]*\s*$")

MAIN_PAT = [
    re.compile(r"^\s*package\s+main\s*$", re.M),
    re.compile(r"func\s+main\s*\("),
    re.compile(r"\bint\s+main\s*\("),
    re.compile(r"fn\s+main\s*\("),
    re.compile(r"#\[tokio::main\]"),
    re.compile(r"public\s+static\s+void\s+main\s*\("),
    re.compile(r"static\s+void\s+Main\s*\("),
]
FUNC_DEF = {
    "Python": re.compile(r"^def\s+(\w+)\s*\(", re.M),
    "Java": re.compile(r"^\s*(?:(?:public|private|protected)\s+)?(?:static\s+)?(?:final\s+)?(?!new\b)(?:[A-Za-z_][\w.<>\[\],\s]*?)\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*(?:throws\s+[^{;]*?)?\{", re.M),
    "Go": re.compile(r"^func\s+(\w+)\s*\(", re.M),
    "Rust": re.compile(r"^fn\s+(\w+)\s*\(", re.M),
    "C++": re.compile(r"^\s*(?!new\b)(?:[A-Za-z_][\w:<>\[\],\s*&]+?)\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*\{", re.M),
    "JavaScript": re.compile(r"^\s*(?:async\s+)?function\s+(\w+)\s*\(", re.M),
    "C#": re.compile(r"^\s*(?:(?:public|private|protected|internal)\s+)?(?:static\s+)?(?!new\b)(?:[A-Za-z_][\w.<>\[\],?\s]*?)\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*(?:async\s*)?\{", re.M),
}
ALLOWED_HELPERS = {
    'print_search_results', 'print_results', 'print_json', 'printSearchResults', 'PrintSearchResults',
    'generate_random_str', 'generate_random_string', 'generate_random_vectors', 'generateString',
    'gen_binary_vector', 'gen_float_vector', 'gen_fp16_vector', 'gen_sparse_vector',
    'gen_string_array', 'gen_int_array', 'gen_dense_vector', 'gen_dense_vectors',
    'gen_binary_vectors', 'gen_float_vectors', 'gen_float16_vector', 'gen_sparse_vectors',
    'gen_float_vector_list', 'gen_string_array', 'gen_int_array', 'gen_sparse_vector_data',
    'gen_binary_vectors_as_str', 'gen_fp16_vector', 'gen_float16_vectors',
    'genBinaryVector', 'genFloatVector', 'genFloat16Vector', 'genSparseVector', 'generateFloatVectors',
    'genStringArray', 'genIntArray', 'genFp16Vector', 'genSparseVectors', 'GenerateFloatVector',
    'get_random_vector', 'get_random_string', 'get_random_boolean',
    'build_entity', 'buildEntity', 'build_sparse_vector', 'build_collection',
    'get_output_fields', 'getOutputFields', 'createSchema',
    'get_embedding', 'generate_minhash_signature', 'extract_token_set',
    'generate_dense_vector', 'convert_bool_list_to_bytes', 'make_row', 'product',
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


def rule6(lang, text):
    problems = []
    for pat in MAIN_PAT:
        if pat.search(text):
            problems.append("main-entry")
            break
    fd = FUNC_DEF.get(lang)
    if fd:
        for m in fd.finditer(text):
            name = m.group(1)
            if name in {"if", "for", "while", "switch", "catch", "do", "return", "foreach"}:
                continue
            if name in ALLOWED_HELPERS:
                continue
            problems.append(f"function-wrapper:{name}")
    return problems


def import_matcher(lang):
    return IMPORT_LINE.get(lang)


def rule7(lang, text):
    problems = []
    lines = text.split("\n")
    if text.startswith("\n"):
        problems.append("leading-blank")
    if re.search(r"\n[ \t]*\n[ \t]*$", text):
        problems.append("trailing-blank")
    if re.search(r"\n[ \t]*\n[ \t]*\n", text):
        problems.append("double-blank")
    imp = import_matcher(lang)
    if imp:
        seen, pending = False, False
        for ln in lines:
            if imp.match(ln):
                if pending and seen:
                    problems.append("blank-between-imports")
                pending, seen = False, True
            elif ln.strip() == "":
                pending = True
            else:
                seen, pending = False, False
    for i, ln in enumerate(lines):
        s = ln.rstrip()
        if s.endswith("{"):
            if i + 1 < len(lines) and lines[i + 1].strip() == "":
                problems.append("blank-after-brace")
        if CLOSE_ONLY.match(s):
            if i > 0 and lines[i - 1].strip() == "":
                problems.append("blank-before-close")
    if imp and imp.search(text):
        end = import_region_end(lines, lang)
        if end is not None and end + 1 < len(lines):
            nxt = end + 1
            blanks = 0
            while nxt < len(lines) and lines[nxt].strip() == "":
                blanks += 1
                nxt += 1
            if nxt < len(lines) and blanks != 1:
                problems.append(f"import-code-gap={blanks}")
    return problems


def import_region_end(lines, lang):
    pat = IMPORT_LINE.get(lang)
    if not pat:
        return None
    end = None
    i, n = 0, len(lines)
    while i < n:
        if pat.match(lines[i]):
            s = lines[i].rstrip()
            if s.endswith("("):
                depth = s.count("(") - s.count(")")
                j = i + 1
                while j < n and depth > 0:
                    depth += lines[j].count("(") - lines[j].count(")")
                    j += 1
                end = j - 1
                i = j
            else:
                end = i
                i += 1
        else:
            i += 1
    return end


COMMENT_PREFIX = re.compile(r"^\s*(?://|#|/\*|//!)")
LEAD_SPACES = re.compile(r"^[ \t]*")


def over_indent(text):
    """Return N (>=2) if the fragment's top-level statements are uniformly
    shifted right by N spaces; None otherwise."""
    indents = []
    for ln in text.split("\n"):
        s = ln.rstrip()
        if not s.strip():
            continue
        if COMMENT_PREFIX.match(s):
            continue
        indents.append(len(LEAD_SPACES.match(s).group(0)))
    if not indents:
        return None
    m = min(indents)
    return m if m >= 2 else None


def dedent(text, n):
    return "\n".join((l[n:] if len(l) - len(l.lstrip()) >= n else l) for l in text.split("\n"))


def check_doc(content):
    viol = []
    for bid, lang, text in extract_blocks(content):
        probs = []
        if lang in SDK:
            probs += rule6(lang, text)
        if lang in CODE_LANGS:
            probs += rule7(lang, text)
            n = over_indent(text)
            if n is not None:
                probs.append(f"indent-over={n}")
        if probs:
            viol.append((bid, lang, probs))
    return viol


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc", default="doc", help="label for the report")
    ap.add_argument("--xml", help="file containing the fetch output")
    ap.add_argument("--fix", metavar="OUTDIR",
                    help="write block_replace payloads fixing indent-over to OUTDIR (plus commands.sh)")
    args = ap.parse_args()
    content = read_content(args)
    viol = check_doc(content)
    if args.fix:
        import os
        os.makedirs(args.fix, exist_ok=True)
        cmds = ["#!/usr/bin/env bash"]
        fixed = 0
        for bid, lang, probs in viol:
            n = next((int(p.split("=")[1]) for p in probs if p.startswith("indent-over=")), None)
            if n is None:
                continue
            text = next(t for b, l, t in extract_blocks(content) if b == bid)
            new = dedent(text, n).strip("\n") + "\n"
            fn = f"{args.fix}/{bid[:12]}.txt"
            open(fn, "w").write(f'<pre lang="{lang}" caption="&#xA;" wrap="false"><code>{html.escape(new, quote=True)}</code></pre>')
            open(fn + ".bid", "w").write(bid)
            cmds.append(f'lark-cli docs +update --doc "$DOC" --command block_replace --block-id {bid} --content "$(cat {fn})" --as user')
            fixed += 1
        open(f"{args.fix}/commands.sh", "w").write("\n".join(cmds) + "\n")
        print(f"=== {args.doc}: {fixed} indent-fix payload(s) written to {args.fix} ===")
        sys.exit(0)
    if not viol:
        print(f"=== {args.doc}: 0 rule-6/7 violations ===")
        sys.exit(0)
    print(f"=== {args.doc}: {len(viol)} rule-6/7 violation(s) ===")
    for bid, lang, probs in viol:
        print(f"  {bid} [{lang}] {probs}")
    sys.exit(1)


if __name__ == "__main__":
    main()
