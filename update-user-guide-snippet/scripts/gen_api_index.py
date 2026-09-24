#!/usr/bin/env python3
"""Generate a per-(sdk, tag) API index with FULL parameter lists.

The index is a flat TSV consumed by `api_index.py` (and via it by
`check_snippets.py` / `run_page_*.py`) so API existence checks never need to
grep the large SDK repositories again.

Format (one line per symbol, tab-separated, no header):
  symbol<TAB>lang<TAB>kind<TAB>owner<TAB>params<TAB>return<TAB>file:line

  - symbol: method / builder / field / constructor name
  - lang:   pymilvus | java | node | go | cpp | rust
  - kind:   method | ctor | builder | field | fn (rust pub fn) | async-fn
  - owner:  enclosing class / struct / interface (empty if none)
  - params: full parameter list as "(Type name, Type name, ...)" — the complete
            parameter list; empty "( )" when none
  - return: return type (empty for fields)
  - file:line: repo-relative source location

Usage:
  python3 gen_api_index.py --sdk java --tag v3.0.10 --repo /home/myh/work/git-go/milvus-sdk-java \
      --out sdk-tmp/api-index/java-v3.0.10.tsv
  python3 gen_api_index.py --all --repo-root /home/myh/work/git-go --tag v3.0.10 \
      --out sdk-tmp/api-index

Tags are resolved from the repo via `git show <tag>:<path>` (works on the local
checkout without fetching). One index per (sdk, tag); a tag never changes, so a
cached index is valid forever.
"""
import argparse
import os
import re
import subprocess
import sys

# SDK name -> (lang, default repo name under repo-root, subdirs to scan)
SDKS = {
    "pymilvus": ("pymilvus", "pymilvus", ["pymilvus/milvus_client", "pymilvus/client"]),
    "java": ("java", "milvus-sdk-java", ["sdk-core/src/main/java/io/milvus/v2"]),
    "node": ("node", "milvus-sdk-node", ["milvus/grpc", "milvus/types", "milvus/MilvusClient.ts", "milvus/HttpClient.ts"]),
    "go": ("go", "milvus", ["client/milvusclient", "client/entity", "client/index"]),
    "cpp": ("cpp", "milvus-sdk-cpp", ["src/include/milvus"]),
    "rust": ("rust", "milvus-sdk-rust", ["src/v2"]),
}


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout


def tag_exists(repo, tag):
    return git(repo, "rev-parse", "--verify", "--quiet", tag) is not None


def ls_tree(repo, tag, subdir):
    out = git(repo, "ls-tree", "-r", "--name-only", tag, "--", subdir)
    if not out:
        return []
    return [p for p in out.splitlines() if p]


def show(repo, tag, path):
    return git(repo, "show", f"{tag}:{path}")


def clean_sig(s):
    """Collapse whitespace/newlines inside a signature for a one-line row."""
    return re.sub(r"\s+", " ", s).strip()


def split_params(s):
    """Parse a '(...)' parameter list into (Type name, ...) tokens.

    s is the already-extracted parameter text (may or may not include parens).
    """
    s = s.strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
    s = s.strip()
    if not s:
        return "( )"
    parts = re.split(r",\s*(?![^\[\]<]*[\]>])", s)
    return "(" + ", ".join(p.strip() for p in parts if p.strip()) + ")"


# ---------------------------------------------------------------- extractors

def extract_pymilvus(repo, tag, paths):
    rows = []
    for p in paths:
        files = ls_tree(repo, tag, p)
        for f in files:
            if not f.endswith(".py"):
                continue
            src = show(repo, tag, f)
            if not src:
                continue
            # single-line def: `def name(self, a, b=1):` / `... -> int:`.
            # Keep only the real signature (stop at the first ':' on the def line,
            # allowing an optional `-> ReturnType` before it).
            for m in re.finditer(
                    r"^\s*(?:async\s+)?def\s+([a-zA-Z_][\w]*)\s*\((.*?)\)\s*(?:->\s*[\w\[\]]+)?\s*:",
                    src, re.M | re.S):
                name, params = m.group(1), clean_sig(m.group(2))
                if name.startswith("_") and name != "__init__":
                    continue
                rows.append((name, "pymilvus", "method", "", split_params(params), "", f"{f}:{src.count(chr(10), 0, m.start()) + 1}"))
    return rows


def extract_java(repo, tag, paths):
    rows = []
    for p in paths:
        files = ls_tree(repo, tag, p)
        for f in files:
            if not f.endswith(".java"):
                continue
            src = show(repo, tag, f)
            if not src:
                continue
            # class / interface owner (take last declaration)
            owner = ""
            om = re.search(r"(?:public\s+)?(?:class|interface|enum)\s+(\w+)", src)
            if om:
                owner = om.group(1)
            # public methods (incl. Lombok builder methods). Signature may span
            # lines; params end at the last ')' before an optional { / ; / throws.
            for m in re.finditer(
                    r"public\s+(?:final\s+|static\s+|synchronized\s+)*"
                    r"([\w.<>\[\],\s]+?)\s+([a-zA-Z_]\w*)\s*\("
                    r"([^()]*?(?:\([^()]*\)[^()]*?)*)\)"
                    r"\s*(?:throws\s+[\w\s,.]+)?\s*[\{;]",
                    src, re.M | re.S):
                ret, name, params = clean_sig(m.group(1)), m.group(2), clean_sig(m.group(3))
                if name.startswith("get") and len(name) > 3 and params in ("", "( )"):
                    continue  # no-arg getters are noise
                if name.startswith("set") and len(name) > 3:
                    kind = "builder" if "Builder" in owner else "method"
                elif "Builder" in owner:
                    kind = "builder"
                else:
                    kind = "method"
                rows.append((name, "java", kind, owner, split_params(params), ret, f"{f}:{src.count(chr(10), 0, m.start()) + 1}"))
            # constructors
            for m in re.finditer(
                    r"public\s+(\w+)\s*\("
                    r"([^()]*?(?:\([^()]*\)[^()]*?)*)\)\s*[\{;]", src, re.M | re.S):
                if m.group(1) == owner:
                    rows.append((owner, "java", "ctor", owner, split_params(clean_sig(m.group(2))), "", f"{f}:{src.count(chr(10), 0, m.start()) + 1}"))
    return rows


def extract_node(repo, tag, paths):
    rows = []
    for p in paths:
        files = ls_tree(repo, tag, p)
        for f in files:
            if not f.endswith(".ts"):
                continue
            src = show(repo, tag, f)
            if not src:
                continue
            # async methods: `async foo(params): ...`
            for m in re.finditer(r"async\s+([a-zA-Z_]\w*)\s*\(\s*([^()]*?(?:\([^()]*\)[^()]*?)*)\)\s*[:{]",
                                 src, re.M | re.S):
                name, params = m.group(1), clean_sig(m.group(2))
                rows.append((name, "node", "method", "", split_params(params), "", f"{f}:{src.count(chr(10), 0, m.start()) + 1}"))
            # synchronous methods: `foo(params): Type {`
            for m in re.finditer(r"([a-zA-Z_]\w*)\s*\(\s*([^()]*?(?:\([^()]*\)[^()]*?)*)\)\s*:\s*[\w<>\[\]]+\s*\{",
                                 src, re.M | re.S):
                name, params = m.group(1), clean_sig(m.group(2))
                if name in ("if", "for", "while", "switch", "function", "return", "typeof"):
                    continue
                rows.append((name, "node", "method", "", split_params(params), "", f"{f}:{src.count(chr(10), 0, m.start()) + 1}"))
    return rows


def extract_go(repo, tag, paths):
    rows = []
    for p in paths:
        files = ls_tree(repo, tag, p)
        for f in files:
            if not f.endswith(".go") or f.endswith("_test.go"):
                continue
            src = show(repo, tag, f)
            if not src:
                continue
            # methods: func (c *Client) Name(...) / func (f *Field) WithXxx(...)
            for m in re.finditer(r"func\s+\(\w+\s+\*(\w+)\)\s+([a-zA-Z_]\w*)\s*\((.*?)\)\s*([\w.*\[\]]+)?\s*\{?", src, re.M | re.S):
                owner, name, params, ret = m.group(1), m.group(2), clean_sig(m.group(3)), clean_sig(m.group(4) or "")
                rows.append((name, "go", "method", owner, split_params(params), ret, f"{f}:{src.count(chr(10), 0, m.start()) + 1}"))
            # package-level option constructors: func New*Option(...)
            for m in re.finditer(r"^func\s+(New[\w]+)\s*\((.*?)\)\s*([\w.*\[\]]+)?\s*\{?", src, re.M | re.S):
                name, params, ret = m.group(1), clean_sig(m.group(2)), clean_sig(m.group(3) or "")
                rows.append((name, "go", "ctor", "", split_params(params), ret, f"{f}:{src.count(chr(10), 0, m.start()) + 1}"))
    return rows


def extract_cpp(repo, tag, paths):
    rows = []
    for p in paths:
        files = ls_tree(repo, tag, p)
        for f in files:
            if not f.endswith(".h"):
                continue
            src = show(repo, tag, f)
            if not src:
                continue
            owner = ""
            om = re.search(r"(?:class|struct)\s+(\w+)", src)
            if om:
                owner = om.group(1)
            # virtual methods (MilvusClientV2 facade): virtual Status Foo(...) = 0;
            for m in re.finditer(
                    r"virtual\s+[\w:]*\s*([A-Za-z_]\w*)\s*\("
                    r"([^()]*?(?:\([^()]*\)[^()]*?)*)\)\s*=\s*0", src, re.M | re.S):
                name, params = m.group(1), clean_sig(m.group(2))
                rows.append((name, "cpp", "method", owner, split_params(params), "Status", f"{f}:{src.count(chr(10), 0, m.start()) + 1}"))
            # fluent request builders: `WithXxx(Type name);` declarations (return
            # type is on its own line or omitted), plus inline `... WithXxx(...)`.
            for m in re.finditer(
                    r"With([A-Za-z_]\w*)\s*\("
                    r"([^()]*?(?:\([^()]*\)[^()]*?)*)\)\s*(?:const\s*)?\;",
                    src, re.M | re.S):
                name, params = "With" + m.group(1), clean_sig(m.group(2))
                rows.append((name, "cpp", "builder", owner, split_params(params), "", f"{f}:{src.count(chr(10), 0, m.start()) + 1}"))
    return rows


def extract_rust(repo, tag, paths):
    rows = []
    for p in paths:
        files = ls_tree(repo, tag, p)
        for f in files:
            if not f.endswith(".rs"):
                continue
            src = show(repo, tag, f)
            if not src:
                continue
            owner = ""
            om = re.search(r"pub\s+(?:async\s+)?(?:struct|impl)\s+(\w+)", src)
            for m in re.finditer(r"pub\s+(?:async\s+)?fn\s+([a-zA-Z_]\w*)\s*\((.*?)\)\s*(?:->\s*([\w:<>\[\]]+))?\s*\{?", src, re.M | re.S):
                name, params, ret = m.group(1), clean_sig(m.group(2)), clean_sig(m.group(3) or "")
                kind = "async-fn" if "async" in src[max(0, m.start() - 40):m.start()] else "fn"
                rows.append((name, "rust", kind, owner, split_params(params), ret, f"{f}:{src.count(chr(10), 0, m.start()) + 1}"))
    return rows


EXTRACTORS = {
    "pymilvus": extract_pymilvus,
    "java": extract_java,
    "node": extract_node,
    "go": extract_go,
    "cpp": extract_cpp,
    "rust": extract_rust,
}


def gen(sdk, tag, repo, out):
    lang, repo_name, subdirs = SDKS[sdk]
    if not tag_exists(repo, tag):
        print(f"gen_api_index: tag {tag!r} not found in {repo}")
        return False
    rows = EXTRACTORS[sdk](repo, tag, subdirs)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    seen = set()
    with open(out, "w") as f:
        for name, lang_, kind, owner, params, ret, loc in rows:
            key = (name, lang_, owner, params)
            if key in seen:
                continue
            seen.add(key)
            f.write(f"{name}\t{lang_}\t{kind}\t{owner}\t{params}\t{ret}\t{loc}\n")
    print(f"gen_api_index: {sdk}@{tag} -> {out} ({len(seen)} symbols)")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sdk", choices=sorted(SDKS))
    ap.add_argument("--tag", required=True)
    ap.add_argument("--repo", help="repo path (overrides repo-root/<name>)")
    ap.add_argument("--repo-root", default=os.path.expanduser("~/work/git-go"))
    ap.add_argument("--out", required=True, help="output .tsv path, or a dir with --all")
    ap.add_argument("--all", action="store_true", help="generate for every SDK at --tag")
    args = ap.parse_args()

    if args.all:
        ok = True
        for sdk in SDKS:
            repo = os.path.join(args.repo_root, SDKS[sdk][1])
            out = os.path.join(args.out, f"{sdk}-{args.tag}.tsv")
            ok &= gen(sdk, args.tag, repo, out)
        return 0 if ok else 1
    if not args.sdk:
        ap.error("--sdk is required unless --all")
    repo = args.repo or os.path.join(args.repo_root, SDKS[args.sdk][1])
    return 0 if gen(args.sdk, args.tag, repo, args.out) else 1


if __name__ == "__main__":
    sys.exit(main())
