#!/usr/bin/env python3
"""Run the go snippets of a user-guide page against a live Milvus server.

Extracts every ```go block, hoists the imports, strips per-block client init,
and wraps the block bodies in scoped braces inside main() with a single shared
client. Compiles and runs with `go run`.

Optionally pre-checks API calls against the per-tag SDK index (see
gen_api_index.py / api_index.py): pass --api-index DIR --sdk-tag go@TAG to pin
the client module to TAG and report unknown SDK calls before compiling.

Usage: python3 run_page_go.py <page.md> [--api-index DIR --sdk-tag go@TAG]
"""
import argparse
import os
import shutil
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
PROJ = os.path.join(REPO, "sdk-tmp", "snippet-run", "go")
GO = os.environ.get("GO_BIN", "/usr/local/go/bin/go")

GO_MOD = "module snippet-run\n\ngo 1.24.9\n\n"


def main():
    if not shutil.which(GO) and not os.path.exists(GO):
        print("go: go toolchain missing — SKIPPING go verification")
        sys.exit(0)
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--api-index", default="")
    ap.add_argument("--sdk-tag", default="")
    args, rest = ap.parse_known_args(sys.argv[1:])
    page = rest[0]
    md = open(page).read()
    blocks = re.findall(r"```go\n(.*?)```", md, re.S)

    # API-existence pre-check (soft)
    if args.api_index and args.sdk_tag:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import api_index as ai
        sdk, _, tag = args.sdk_tag.partition("@")
        idx = ai.resolve_index(sdk, tag, args.api_index)
        if idx:
            print(f"go: API index {idx}")
            for i, b in enumerate(blocks):
                unknown = ai.check_code(idx, "go", b, sdk)
                if unknown:
                    print(f"go: block {i}: {len(unknown)} unknown SDK call(s)")
                    for expr, sym in unknown[:10]:
                        print(f"      {sym}  (from {expr!r})")
        else:
            print(f"go: WARN no API index for {sdk}@{tag} — skipping API pre-check")

    imports = []
    import_paths = set()
    bodies = []
    for b in blocks:
        in_import = False
        kept = []
        for line in b.split("\n"):
            s = line.strip()
            if s == "import (":
                in_import = True
                continue
            if in_import:
                if s == ")":
                    in_import = False
                    continue
                if s:
                    # dedupe by import path (ignore alias differences)
                    p = s.split()[-1].strip('"')
                    if p not in import_paths:
                        import_paths.add(p)
                        imports.append(s)
                continue
            if s.startswith("import"):
                # single-line import "path" — store only the quoted path
                p = s.split()[-1].strip('"')
                if p not in import_paths:
                    import_paths.add(p)
                    imports.append(f'"{p}"')
                continue
            kept.append(line)
        bodies.append("\n".join(kept))
    # guide go snippets carry no imports — add the standard ones (by path)
    default_imports = [
        'milvusclient "github.com/milvus-io/milvus/client/v3/milvusclient"',
        '"context"',
        '"log"',
    ]
    for imp in default_imports:
        p = imp.split()[-1].strip('"')
        if p not in import_paths:
            import_paths.add(p)
            imports.append(imp)

    # strip per-block client/addr/ctx init (var name may be `cli` or `client`) so
    # one shared client is created in main(); also drop the now-unused
    # milvusAddr / context.WithCancel / defer lines that accompany it.
    cleaned = []
    for b in bodies:
        b = re.sub(r"\w+,\s*err\s*[:=]=\s*milvusclient\.New\(.*?\)", "", b, flags=re.S)
        b = re.sub(r"\w+Addr\s*[:=]=\s*\"[^\"]*19530[^\"]*\"", "", b)
        b = re.sub(r"^\s*token\s*:?=?\s*\"root:Milvus\"\s*$", "", b, flags=re.M)
        b = re.sub(r"(_,?\s*cancel|ctx,\s*cancel)\s*[:=]=\s*context\.WithCancel\(.*\)", "", b)
        b = re.sub(r"ctx\s*[:=]=\s*context\.Background\(\)", "", b)
        b = re.sub(r"defer\s+cancel\(\)", "", b)
        b = re.sub(r"defer\s+(?:client|cli)\.Close\(ctx\)", "", b)
        cleaned.append(b)

    # Balanced-paren cleanup: the regexes above miss multi-line
    # `cli, err := milvusclient.New(ctx, &milvusclient.ClientConfig{...})`
    # calls (lazy `.*?` stops at the first `)`) and leave stray `)` lines
    # that break compilation. Scan line-by-line with paren depth instead.
    final = []
    i = 0
    while i < len(cleaned):
        ln = cleaned[i]
        m = re.search(r"\w+,\s*err\s*[:=]=\s*milvusclient\.New\(", ln)
        if m:
            start = m.start()
            depth = ln.count("(", start) - ln.count(")", start)
            i += 1
            while i < len(cleaned) and depth > 0:
                depth += cleaned[i].count("(") - cleaned[i].count(")")
                i += 1
            continue
        final.append(ln)
        i += 1
    cleaned = final
    bodies = cleaned

    # detect the client variable name used by the page's blocks (`cli` or `client`)
    var_name = "cli"
    for b in bodies:
        m = re.search(r"\b(client|cli)\s*\.", b)
        if m:
            var_name = m.group(1)
            break

    prog = "package main\n\nimport (\n"
    prog += "\n".join(imports)
    if imports:
        prog += "\n"
    prog += ')\n\nfunc main() {\n'
    prog += '    ctx := context.Background()\n'
    prog += f'    {var_name}, err := milvusclient.New(ctx, &milvusclient.ClientConfig{{\n'
    prog += '        Address:  "localhost:19530",\n'
    prog += '        Username: "root",\n'
    prog += '        Password: "Milvus",\n'
    prog += '    })\n'
    prog += '    if err != nil {\n        log.Fatal(err)\n    }\n'
    prog += f'    defer {var_name}.Close(ctx)\n'
    # Flatten per-block scopes; convert re-declarations of seen names from
    # `name := value` to `name = value` so cross-block references work while
    # re-runs of the same flow don't trip "no new variables".
    seen = set()
    flat = []
    SHORT = re.compile(r"^(\s*)([A-Za-z_][\w$]*(?:\s*,\s*[A-Za-z_][\w$]*)*)\s*:=\s*(.*)$")
    for b in bodies:
        for ln in b.split("\n"):
            m = SHORT.match(ln)
            if m:
                names = [n.strip() for n in m.group(2).split(',')]
                names = [n for n in names if n != "_"]
                if names and all(nm in seen for nm in names):
                    flat.append(f"{m.group(1)}{m.group(2)} = {m.group(3)}")
                    continue
                seen.update(names)
            flat.append(ln)
        flat.append("")
    bodies = [b for b in "\n".join(flat).split("\n// ===") ]  # keep as flat lines list handled below
    # rebuild bodies as a single body list for assembly
    bodies = ["\n".join(flat).rstrip()]

    # Doc fragments may use bare assignments (`name = value`) assuming a prior
    # declaration the page never contains (analyzer docs do this). Convert the
    # FIRST bare assignment of each name into a `:=` declaration; later bare
    # assignments stay plain (Go: assignment to declared var). Harness-only.
    declared = {"err", "ctx", "client", "cli"}
    ASSIGN = re.compile(r"^(\s*)([A-Za-z_][\w$]*)\s*=\s*(?!=)(.*)$")
    SHORTD = re.compile(r"^\s*([A-Za-z_][\w$]*)\s*:=\s*")
    MULTI = re.compile(r"^\s*([A-Za-z_][\w$]*(?:\s*,\s*[A-Za-z_][\w$]*)+)\s*:?=.")
    fixed_lines = []
    src = "\n".join(bodies)
    for ln in src.split("\n"):
        sm = SHORTD.match(ln)
        if sm:
            declared.add(sm.group(1))
            mm = MULTI.match(ln)
            if mm:
                for nm in re.split(r"\s*,\s*", mm.group(1)):
                    declared.add(nm)
            fixed_lines.append(ln)
            continue
        m = ASSIGN.match(ln)
        if m and m.group(2) != "_" and m.group(2) not in declared:
            declared.add(m.group(2))
            fixed_lines.append(f"{m.group(1)}{m.group(2)} := {m.group(3)}")
            continue
        fixed_lines.append(ln)
    body_src = "\n".join(fixed_lines)

    # Harness-only: blank-use for variables the doc declares but never reads
    # (Go rejects unused locals; docs are fragments that may not print).
    lhs_names = set()
    for ln in body_src.split("\n"):
        am = ASSIGN.match(ln)
        if am:
            if am.group(2) != "_":
                lhs_names.add(am.group(2))
        sm = SHORTD.match(ln)
        if sm:
            if sm.group(1) != "_":
                lhs_names.add(sm.group(1))
        mm = MULTI.match(ln)
        if mm:
            for nm in re.split(r"\s*,\s*", mm.group(1)):
                if nm != "_":
                    lhs_names.add(nm)
    body_src = body_src.rstrip()
    for nm in sorted(lhs_names):
        if len(re.findall(rf"(?<![\w.]){re.escape(nm)}\b", body_src)) <= 1:
            body_src += f"\n    _ = {nm}"
    bodies = [body_src]

    for i, b in enumerate(bodies):
        prog += f"    // === block {i} ===\n"
        prog += "\n".join("        " + ln for ln in b.split("\n")) + "\n"
    prog += "}\n"

    os.makedirs(PROJ, exist_ok=True)
    with open(os.path.join(PROJ, "go.mod"), "w") as f:
        f.write(GO_MOD)
    with open(os.path.join(PROJ, "main.go"), "w") as f:
        f.write(prog)

    print(f"go blocks: {len(blocks)}")
    client_mod = f"github.com/milvus-io/milvus/client/v3@{args.sdk_tag.partition('@')[2].removeprefix('client/')}" if args.sdk_tag else "github.com/milvus-io/milvus/client/v3@latest"
    r = subprocess.run(
        [GO, "-C", PROJ, "get", client_mod],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-2000:])
        print("\ngo: dependency fetch failed (network) — snippets NOT executed")
        sys.exit(1)
    # resolve transitive deps and write go.sum
    r = subprocess.run([GO, "-C", PROJ, "mod", "tidy"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-2000:])
        print("\ngo: mod tidy failed (network) — snippets NOT executed")
        sys.exit(1)
    r = subprocess.run([GO, "-C", PROJ, "run", "."], capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr[-3000:] if r.returncode else "")
    print(f"\n=== {page} === go run {'OK' if r.returncode == 0 else 'FAILED'} ({len(blocks)} blocks)")
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
