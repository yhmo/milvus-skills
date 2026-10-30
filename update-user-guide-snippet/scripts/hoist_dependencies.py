#!/usr/bin/env python3
"""Hoist dependency statements and client declarations to the first client-using block.

Implements the document-scope client and dependency rule from SKILL.md: for each
language in a Feishu user-guide document, ALL `import` / `#include` / `use` /
`using` statements needed anywhere in the document go into exactly ONE block —
the first code block that uses the client for that language (which is NOT
necessarily the document's first code block; data-prep / JSON-sample blocks may
precede it). Later blocks of the same language must contain no dependency
statement and must not re-create the SDK client.

This helper reads a `lark-cli docs +fetch --doc <docx> --detail with-ids --as user`
fetch (XML content or JSON envelope), computes the rewritten `<pre>` blocks, and
writes the `lark-cli docs +update --command block_replace` payloads to a
directory (one file per block, plus a `commands.sh` runner).

Usage:
  lark-cli docs +fetch --doc <docx> --detail with-ids --as user \
    | python3 hoist_dependencies.py --doc "Query" --out sdk-tmp/hoist-query

  python3 hoist_dependencies.py --xml fetch.xml --doc "Query" --out sdk-tmp/hoist-query

The output directory contains, for each language, the reworked payloads:
  <lang>-<n>-<shortid>.txt        one `<pre>` block payload (block_replace content)
  <lang>-<n>-<shortid>.blockid    the target block id
  commands.sh                     ready-to-run `docs +update` lines

Blocks that need no change are not emitted. Print a summary per language:
declared deps, first client-using block, blocks cleaned.
"""
import argparse
import html
import json
import os
import re
import sys

PRE_RE = re.compile(r'<pre\s+id="[^"]*"(?:\s+[^>]*?)lang="([^"]*)"[^>]*>(.*?)</pre>', re.S)
CODE_RE = re.compile(r'^<code>(.*)</code>$', re.S)

# Dependency-line matchers, keyed by the document's `lang` attribute.
DEP_RE = {
    "Python": re.compile(r"^\s*(?:from\s+\S+\s+import\s+\S.*|import\s+\S.*)$"),
    "Java": re.compile(r"^\s*import\s+\S.*;?$"),
    "JavaScript": re.compile(r"^\s*import\s+\S.*;?$"),
    "Go": re.compile(r"^\s*import\s*\(|^\s*\)\s*$|^\s*(?:[A-Za-z_][\w]*\s+)?\"[^\"]*\"\s*$"),
    "Rust": re.compile(r"^\s*use\s+\S.*;?$"),
    "C++": re.compile(r"^\s*#include\s+[<\"]\S+[>\"]$"),
    "C#": re.compile(r"^\s*using\s+(?!var\b|await\b)[\w.]+(?:\s*=\s*.*)?;?$"),
}

# Client-creation / client-use detectors per language.
# has_client returns True for a decoded block that (a) CREATES the client or
# (b) already USES a client variable — either marks it as the first client-using block.
CLIENT_USE = {
    "Python": re.compile(r"\bclient\s*=|client\.\w+\s*\("),
    "Java": re.compile(r"\bclient\s*=|client\.\w+\s*\("),
    "JavaScript": re.compile(r"\bclient\s*=|client\.\w+\s*\("),
    "Go": re.compile(r"\b(?:client|cli)\s*[:=]|\b(?:client|cli)\.\w+\s*\("),
    "Rust": re.compile(r"\bclient\s*=|client\.\w+\s*\("),
    "C++": re.compile(r"\bclient\b"),
    "C#": re.compile(r"\bclient\b"),
}

# Client-creation statements to REMOVE from later blocks (and from the first
# block only its own declaration is kept). These patterns are the duplicated
# `client = ...` / `ConnectConfig` / connection-setup lines that later blocks
# must not repeat.
CLIENT_CREATE = {
    "Python": re.compile(
        r"(?:from\s+pymilvus\s+import\s+MilvusClient\s*\n\s*)?"
        r"client\s*=\s*MilvusClient\s*\(.*?\)\s*\n?", re.S),
    "Java": re.compile(
        r"MilvusClientV2\s+client\s*=\s*new\s+MilvusClientV2\(.*?\)\s*;\n?", re.S),
    "JavaScript": re.compile(
        r"const\s+client\s*=\s*new\s+MilvusClient\([\s\S]*?\)\s*;\s*\n?"
        r"|\b(?:const|let|var)\s+(?:address|token)\s*=\s*[\"'][^\"']*[\"']\s*;\s*\n?"),
    "Go": re.compile(
        r"(?:ctx,\s*cancel\s*:?=?\s*context\.WithCancel\(.*?\)\s*\n?\s*defer\s+cancel\(\)\s*\n?)?"
        r"(?:\w+Addr\s*[:=]=\s*\"[^\"]*\"\s*\n?)?"
        r"(?:\w+,\s*err\s*[:=]=\s*milvusclient\.New\(.*?\)\s*\n?)?"
        r"(?:\w+\s*:?=?\s*\"root:Milvus\"\s*\n?)?"
        r"(?:defer\s+(?:client|cli)\.Close\(ctx\)\s*\n?)?", re.S),
    "Rust": re.compile(
        r"let\s+client\s*=\s*ClientV2::new\([\s\S]*?\.await\?;\s*\n?", re.S),
    "C++": re.compile(
        r"(?:#include\s+[<\"]\S+[>\"]\s*\n+)?"
        r"auto\s+client\s*=\s*(?:milvus::)?MilvusClientV2::Create\(\)\s*;\s*\n?"
        r"(?:milvus::ConnectParam\s+\w+\s*\{[^}]*\}\s*;\s*\n?)?"
        r"(?:auto\s+)?status\s*=\s*client->Connect\([^;]*\)\s*;\s*\n?"
        r"if\s*\(!status\.IsOk\(\)\)\s*\{[^}]*\}\s*\n?", re.S),
    "C#": re.compile(
        r"using\s+(?!var\b|await\b)[\w.]+;\s*\n*"  # namespace usings (handled via DEP removal)
        r"|\bvar\s+config\s*=\s*new\s+ConnectConfig\s*\{[\s\S]*?\}\s*;\s*\n?"
        r"|(?:var\s+|MilvusClientV2\s+)client\s*=\s*new\s+MilvusClientV2\([\s\S]*?\)\s*;\s*\n?"
        r"|await\s+client\.ConnectAsync\(\)\s*;\s*\n?"),
}

# Languages whose dependency region is a multi-line `import ( ... )` block.
GO_IMPORT_BLOCK = "Go"


def normalize_lang(lang: str) -> str:
    return {"JavaScript": "JavaScript", "C++": "C++", "C#": "C#", "Python": "Python",
            "Java": "Java", "Go": "Go", "Rust": "Rust"}.get(lang, lang)


def decode_block(raw: str) -> str:
    m = CODE_RE.match(raw.strip())
    if m:
        raw = m.group(1)
    text = re.sub(r"<br\s*/?>", "\n", raw)
    text = re.sub(r"<em>(.*?)</em>", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def extract_deps(lang: str, code: str):
    """Return (list_of_dep_lines, code_without_deps)."""
    pat = DEP_RE[lang]
    if lang == GO_IMPORT_BLOCK:
        # collect the whole `import ( ... )` region as a single dep group
        m = re.search(r"^\s*import\s*\(.*?\)", code, re.M | re.S)
        if m:
            region = m.group(0)
            # normalize inner quotes / whitespace
            inner = region.strip()
            return [inner], code.replace(region, "", 1)
        return [], code
    kept, deps = [], []
    for ln in code.split("\n"):
        if pat.match(ln):
            deps.append(ln.rstrip())
        else:
            kept.append(ln)
    return deps, "\n".join(kept)


def canonical_deps(lang: str, deps):
    """Merge per-block dependency lines into one deduplicated region."""
    if lang == GO_IMPORT_BLOCK:
        paths = []
        for dep in deps:
            inner = dep.strip()[len("import ("):-1].strip()
            for ln in inner.split("\n"):
                p = ln.strip()
                if p:
                    paths.append(p)
        seen = []
        for p in paths:
            if p not in seen:
                seen.append(p)
        return ["import (\n" + "\n".join("    " + p for p in seen) + "\n)"]
    # named imports / usings / includes: dedupe by line
    seen = []
    for d in deps:
        d = d.rstrip()
        if d not in seen:
            seen.append(d)
    return seen


def strip_client_creation(lang: str, code: str) -> str:
    if lang not in CLIENT_CREATE:
        return code
    pat = CLIENT_CREATE[lang]
    out = code
    # repeatedly strip (patterns may span newlines)
    for _ in range(4):
        out2 = pat.sub("", out)
        if out2 == out:
            break
        out = out2
    # clean up blank-line runs left by removals
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip("\n") + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doc", default="doc", help="label for the report")
    ap.add_argument("--xml", help="file containing the fetch XML content")
    ap.add_argument("--out", required=True, help="output directory for payloads")
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
        sys.exit(1)

    os.makedirs(args.out, exist_ok=True)

    # Parse once, capturing block id + lang + raw body.
    lang_blocks = {}  # lang -> list of (block_id, decoded_code)
    blocks2 = re.finditer(r'<pre\s+id="([^"]+)"[^>]*lang="([^"]*)"[^>]*>(.*?)</pre>', content, re.S)
    for m in blocks2:
        bid, lang_raw, body = m.group(1), m.group(2), m.group(3)
        lang = normalize_lang(lang_raw)
        if lang not in DEP_RE:
            continue
        lang_blocks.setdefault(lang, []).append((bid, decode_block(body)))

    commands = []
    for lang, items in lang_blocks.items():
        # 1) find first client-using block
        first_ci = None
        for bid, code in items:
            if CLIENT_USE[lang].search(code):
                first_ci = (bid, code)
                break
        if first_ci is None:
            print(f"  [{lang}] no client-using block found; leaving unchanged")
            continue
        first_id, first_code = first_ci
        # 2) collect all dependency lines across the whole document for this lang
        all_deps = []
        for bid, code in items:
            deps, _ = extract_deps(lang, code)
            all_deps.extend(deps)
        canon = canonical_deps(lang, all_deps)
        # 3) rewrite first block: canon deps + body without deps + client creation kept
        _, first_body = extract_deps(lang, first_code)
        # first block: canon deps + body (client creation preserved in body;
        # for C# the `using var client = ...` lifetime line is not a namespace
        # using, so it stays in first_body untouched)
        first_rewritten = "\n".join(canon) + "\n" + first_body
        first_rewritten = first_rewritten.strip("\n") + "\n"
        # normalize via snippet normalizer if available
        try:
            import subprocess
            p = subprocess.run(
                [sys.executable, os.path.join(os.path.dirname(__file__), "normalize_snippet.py"),
                 "--file", "/dev/stdin"],
                input=first_rewritten, capture_output=True, text=True)
            if p.returncode == 0 and p.stdout.strip():
                first_rewritten = p.stdout.rstrip("\n") + "\n"
        except Exception:
            pass

        # 4) rewrite later blocks: remove deps + remove client creation
        changed = []
        for bid, code in items:
            if bid == first_id:
                continue
            _, body_no = extract_deps(lang, code)
            cleaned = strip_client_creation(lang, body_no)
            cleaned = cleaned.strip("\n")
            if cleaned == code.strip("\n"):
                continue  # nothing to change
            changed.append((bid, cleaned))
        # 5) decide if first block changed
        first_changed = first_rewritten.strip("\n") != first_code.strip("\n")

        print(f"  [{lang}] first client-using block: {first_id[:16]}")
        print(f"      deps hoisted: {len(canon)} | blocks cleaned: {len(changed)} | first changed: {first_changed}")
        if first_changed:
            emit(args.out, lang, "first", first_id, first_rewritten, commands)
        for k, (bid, cleaned) in enumerate(changed):
            emit(args.out, lang, f"later-{k}", bid, cleaned, commands)

    # write commands.sh
    with open(os.path.join(args.out, "commands.sh"), "w") as f:
        f.write("#!/usr/bin/env bash\n")
        f.write("# Run these with: DOC=<docx-token> bash commands.sh\n")
        for c in commands:
            f.write(c + "\n")
    os.chmod(os.path.join(args.out, "commands.sh"), 0o755)
    print(f"=== {args.doc}: payloads written to {args.out}; run 'bash {os.path.join(args.out, 'commands.sh')}' ===")


def emit(out_dir, lang, tag, bid, code, commands):
    import xml.sax.saxutils as sx
    short = bid[:12]
    code = code.rstrip("\n")
    escaped = sx.escape(code, {'"': '&quot;'})
    payload = f'<pre lang="{lang}" caption="&#xA;"><code>{escaped}</code></pre>'
    fname = f"{lang}-{tag}-{short}"
    with open(os.path.join(out_dir, fname + ".txt"), "w") as f:
        f.write(payload)
    with open(os.path.join(out_dir, fname + ".blockid"), "w") as f:
        f.write(bid)
    commands.append(f'lark-cli docs +update --doc "$DOC" --command block_replace --block-id {bid} --content "$(cat {os.path.join(out_dir, fname + ".txt")})" --as user')


if __name__ == "__main__":
    main()
