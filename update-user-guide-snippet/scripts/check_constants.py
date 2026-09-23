#!/usr/bin/env python3
"""Check that code blocks do not reference undefined convention constants.

Cross-block analysis on a Feishu document fetch XML: the document's Python and
Bash blocks conventionally define the shared "config constants" (SCREAMING_SNAKE
names such as SERVING_CLUSTER_ENDPOINT, TOKEN, CLUSTER_ENDPOINT). Java / Go /
JavaScript / C++ blocks frequently *reference* these constants without defining
them locally. Static syntax checks (py_compile / node --check / gofmt / g++) do
NOT catch this — it is a runtime NameError in the other languages.

This tool reports every such reference and, with --fix, emits a language-idiomatic
constant definition to insert into the offending block.

Usage:
  lark-cli docs +fetch --doc <docx> --detail with-ids --as user \
    | python3 check_constants.py --doc "Serving Cluster"

  python3 check_constants.py --xml fetch.json --doc "Serving Cluster" --fix \
      > missing_constants.xml.json

Options:
  --doc NAME   human-readable label for the report (default "doc")
  --xml FILE   read fetch XML from a file instead of stdin
  --fix        also emit JSON fixes (block id + insertion anchor + content) to stdout

Exit code is non-zero if any missing-constant reference is found.
"""
import argparse
import html
import json
import re
import sys

PRE_RE = re.compile(r'<pre\s+id="([^"]+)"(?:\s+[^>]*?)lang="([^"]*)"[^>]*>(.*?)</pre>', re.S)
CODE_RE = re.compile(r'^<code>(.*)</code>$', re.S)

# languages that DEFINE the shared config constants (the document's "config" blocks)
DEFINING_LANGS = {"python", "bash"}
# languages that may REFERENCE them without defining (need the definition)
REFERRING_LANGS = {"java", "go", "javascript", "cpp"}

# name patterns that never are user-defined config constants (heuristic exclusions)
NAME_RE = re.compile(r'\b[A-Z][A-Z0-9_]{2,}\b')

# per-language definition detection: (name) -> does this block define it?
DEF_PATTERNS = {
    "python": lambda name: re.compile(rf'\b{name}\s*='),
    "bash": lambda name: re.compile(rf'\b(?:export\s+)?{name}\s*='),
    "java": lambda name: re.compile(rf'\b(?:final\s+)?(?:String|int|long|double|float|boolean|char)\s+{name}\s*='),
    "go": lambda name: re.compile(rf'\b(?:const|var)\s+{name}\b|\b{name}\s*:='),
    "javascript": lambda name: re.compile(rf'\b(?:const|let|var)\s+{name}\b|\b{name}\s*='),
    "cpp": lambda name: re.compile(
        rf'\b(?:const\s+)?(?:std::string|std::wstring|char\s*\*|auto|int|int64_t|float|double|bool|std::int64_t|std::vector<[^>]*>)\s+{name}\s*='),
}

# value extraction from the defining language (Python "NAME = \"value\"" / Bash "export NAME=\"value\"")
VALUE_RE = {
    "python": re.compile(r'\b([A-Z][A-Z0-9_]{2,})\s*=\s*["\']([^"\']*)["\']'),
    "bash": re.compile(r'\b(?:export\s+)?([A-Z][A-Z0-9_]{2,})\s*=\s*["\']([^"\']*)["\']'),
}

# per-language fix: how to write a constant definition, given the name+value
FIX_TEMPLATES = {
    "java": lambda name, value: f'String {name} = "{value}";',
    "go": lambda name, value: f'{name} := "{value}"',
    "javascript": lambda name, value: f'const {name} = "{value}";',
    "cpp": lambda name, value: f'const std::string {name} = "{value}";',
}

# where to insert the definition in each language (after which pattern)
INSERT_AFTER = {
    "java": re.compile(r'^(import .*;\s*)+$', re.M),
    "go": re.compile(r'^\)\s*$'),
    "javascript": re.compile(r'^(import .*;\s*)+$', re.M),
    "cpp": re.compile(r'^(#include .*\s*)+$'),
}

COMMENT_STRIP = re.compile(r'(?m)^\s*(?:#|//|/\*|\*).*$')


def normalize_lang(lang: str) -> str:
    return {
        "Python": "python", "Java": "java", "JavaScript": "javascript",
        "Go": "go", "Bash": "bash", "C++": "cpp",
    }.get(lang, lang.lower())


def decode_block(raw: str) -> str:
    m = CODE_RE.match(raw.strip())
    if m:
        raw = m.group(1)
    text = re.sub(r"<br\s*/?>", "\n", raw)
    text = re.sub(r"<em>(.*?)</em>", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def collect_defined_constants(blocks):
    """Return {name: value} from the defining languages (Python/Bash)."""
    constants = {}
    for pid, lang_raw, body in blocks:
        lang = normalize_lang(lang_raw)
        if lang not in DEFINING_LANGS:
            continue
        code = decode_block(body)
        code = COMMENT_STRIP.sub("", code)
        vre = VALUE_RE.get(lang)
        if not vre:
            continue
        for m in vre.finditer(code):
            name, value = m.group(1), m.group(2)
            if name not in constants:
                constants[name] = value
    return constants


def strip_comments(code: str) -> str:
    lines = []
    in_block = False
    for line in code.split("\n"):
        s = line.strip()
        if not in_block and s.startswith("#") or s.startswith("//"):
            continue
        lines.append(line)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doc", default="doc", help="label for the report")
    ap.add_argument("--xml", help="file containing the fetch XML content")
    ap.add_argument("--fix", action="store_true", help="emit JSON fixes to stdout")
    args = ap.parse_args()

    content = open(args.xml).read() if args.xml else sys.stdin.read()
    stripped = content.lstrip()
    if stripped.startswith("{") and '"document"' in content[:2000]:
        try:
            content = json.loads(stripped)["data"]["document"]["content"]
        except (KeyError, ValueError):
            pass

    blocks = PRE_RE.findall(content)
    if not blocks:
        print(f"=== {args.doc}: no <pre> code blocks found")
        return 0

    constants = collect_defined_constants(blocks)

    findings = []      # per-reference: (pid, lang_raw, name, value)
    by_block = {}      # (pid, lang_raw) -> dict(constants, code)
    for pid, lang_raw, body in blocks:
        lang = normalize_lang(lang_raw)
        if lang not in REFERRING_LANGS:
            continue
        code = decode_block(body)
        def_re = DEF_PATTERNS[lang]
        code_nocomment = strip_comments(code)
        seen = set()
        missing = []
        for m in NAME_RE.finditer(code_nocomment):
            name = m.group(0)
            if name in seen:
                continue
            seen.add(name)
            if name not in constants:
                continue  # not a document-level config constant
            if def_re(name).search(code_nocomment):
                continue  # defined locally
            value = constants[name]
            findings.append((pid, lang_raw, name, value))
            missing.append((name, value))
        if missing:
            by_block[(pid, lang_raw)] = {"constants": missing, "code": code}

    fixes = []
    for (pid, lang_raw), info in by_block.items():
        lang = normalize_lang(lang_raw)
        template = FIX_TEMPLATES[lang]
        def_lines = [template(name, value) for name, value in info["constants"]]
        after = INSERT_AFTER[lang]
        lines = info["code"].split("\n")
        best = -1
        for i, ln in enumerate(lines):
            if after.match(ln):
                best = i
        insert_at = best + 1 if best >= 0 else 0
        new_code = lines[:insert_at] + def_lines + [""] + lines[insert_at:]
        fixes.append({"block_id": pid, "lang": lang_raw,
                      "constants": [n for n, _ in info["constants"]],
                      "insert_after_line": insert_at,
                      "new_block": "\n".join(new_code)})

    print(f"=== {args.doc}: {len(constants)} config constants defined "
          f"({sorted(constants)}); {len(findings)} missing-constant references ===",
          file=sys.stderr)
    by_lang = {}
    for pid, lang, name, value in findings:
        by_lang.setdefault(lang, []).append(name)
        print(f"  [{lang}] block {pid}: references '{name}' "
              f"(defined in Python/Bash as \"{value}\") but does not define it",
              file=sys.stderr)
    for lang, names in by_lang.items():
        print(f"  -> {lang}: fix by adding: {', '.join(names)}", file=sys.stderr)

    if args.fix:
        sys.stdout.write(json.dumps({"fixes": fixes}, indent=2) + "\n")

    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
