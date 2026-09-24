#!/usr/bin/env python3
"""Check that code-block groups in a Feishu user-guide document follow the
canonical SDK order.

The canonical order within one group is:

    Python → Java → Go → Rust → C++ → JavaScript → Bash

A "group" is a `<synced-source>` container holding several `<pre>` blocks, or
a consecutive run of `<pre>` blocks in a section. This tool parses the fetch
XML (from `lark-cli docs +fetch ... --detail with-ids`), extracts every
`<pre lang="...">` in document order, splits them into groups, and reports:

  - the actual order vs. the canonical order;
  - missing languages inside a multi-SDK group (Python/Java/Go/Rust/C++/
    JavaScript/Bash expected);
  - standalone single-language blocks (kept as-is — no order check).

Usage:
  lark-cli docs +fetch --doc <docx> --detail with-ids --as user \
    | python3 check_block_order.py --doc "<Doc Title>"

  python3 check_block_order.py --xml fetch.xml --doc "<Doc Title>"

Options:
  --doc NAME   human-readable label for the report (default "doc")
  --xml FILE   read fetch XML from a file instead of stdin
  --max-depth  if >0, also split at headings (h1-h3) instead of relying only
               on <synced-source> / consecutive-<pre> grouping

Exit code is non-zero if any group is out of order or missing a language.
"""
import argparse
import html
import json
import re
import sys

# canonical order within one multi-SDK group
CANON = ["Python", "Java", "Go", "Rust", "C++", "JavaScript", "Bash"]
NORM = {l.lower(): l for l in CANON}

# Languages that are intentionally ignored: never ordered, never validated,
# never modified. `Shell` (the `zilliz` CLI) is a Zilliz Cloud CLI, not an SDK
# block, so the skill leaves it alone entirely.
IGNORED = {"Shell"}

# A <pre> belongs to a group only if it is directly adjacent to another <pre>
# with only whitespace/comment content between (i.e. inside <synced-source> or
# a run of sibling code blocks). Anything else breaks the run.
# id is optional (test payloads may omit it); lang is required.
PRE_RE = re.compile(
    r'<pre\s+(?:id="([^"]+)"\s+)?(?:\s*[^>]*?)?lang="([^"]*)"[^>]*>(.*?)</pre>', re.S)

# accepted lang attribute values (as written in the document)
LANG_ATTR = {l.lower(): l for l in CANON}


def normalize(lang: str) -> str:
    return LANG_ATTR.get(lang.strip().lower(), lang.strip())


def group_blocks(content: str):
    """Return a list of groups; each group is a list of (block_id, lang).

    Ignored languages (Shell/zilliz CLI) are dropped before grouping so they
    never affect group membership, ordering, or validation.
    """
    # Find <synced-source> containers first. Within each container every <pre>
    # is one group. Blocks outside any container are grouped by consecutive
    # adjacency in the remaining content.
    groups = []
    seen = set()

    container_re = re.compile(
        r'<synced-source(?P<attrs>[^>]*)>(?P<body>.*?)</synced-source>', re.S)
    for m in container_re.finditer(content):
        group = [(pid, normalize(lang))
                 for pid, lang, _ in PRE_RE.findall(m.group("body"))
                 if normalize(lang) not in IGNORED]
        if group:
            groups.append(group)
        seen.update(pid for pid, _ in group)

    # Remaining <pre> blocks outside synced-source containers: group them by
    # adjacency. Two consecutive blocks belong to the same group if nothing
    # visible (text/headings/other block types) lies between them.
    # First remove the containers' bodies entirely (so their <pre>s are gone),
    # but KEEP any <pre> that lives outside a container.
    outside = container_re.sub("", content)
    # Walk the remaining content once, tracking position of each pre and the
    # visible text between consecutive ones.
    cur = []
    prev_end = 0
    for m in PRE_RE.finditer(outside):
        pid, lang = m.group(1), normalize(m.group(2))
        if pid in seen:
            continue
        if lang in IGNORED:
            # Shell/zilliz CLI blocks are ignored entirely: they neither join a
            # group nor break adjacency between the SDK blocks around them.
            prev_end = m.end()
            continue
        gap = outside[prev_end:m.start()]
        # A gap containing any real content (letters/digits/other tags) breaks
        # the adjacency run.
        if re.search(r'[A-Za-z0-9_<]', gap):
            if cur:
                groups.append(cur)
                cur = []
        cur.append((pid, lang))
        prev_end = m.end()
    if cur:
        groups.append(cur)

    return groups


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doc", default="doc", help="label for the report")
    ap.add_argument("--xml", help="file containing the fetch XML content")
    ap.add_argument("--max-depth", type=int, default=0,
                    help=">0: also split groups at headings")
    args = ap.parse_args()

    content = open(args.xml).read() if args.xml else sys.stdin.read()
    stripped = content.lstrip()
    if stripped.startswith("{") and '"document"' in content[:2000]:
        try:
            content = json.loads(stripped)["data"]["document"]["content"]
        except (KeyError, ValueError):
            pass

    groups = group_blocks(content)

    if not groups:
        print(f"=== {args.doc}: no <pre> code blocks found ===")
        return 0

    print(f"=== {args.doc}: {len(groups)} code-block group(s) ===")
    failures = 0
    for gi, group in enumerate(groups):
        langs = [lang for _, lang in group]
        single = len(group) == 1
        if single:
            print(f"  group {gi}: [standalone {langs[0]}] (single-block, order N/A)")
            continue

        exp = CANON
        order_ok = langs == exp
        missing = [l for l in CANON if l not in langs]
        extra = [l for l in langs if l not in CANON]

        status = []
        if not order_ok:
            status.append("OUT OF ORDER")
        if missing:
            status.append(f"missing {missing}")
        if extra:
            status.append(f"unexpected {extra}")
        ok = not status

        if ok:
            print(f"  group {gi}: OK  {langs}")
        else:
            failures += 1
            print(f"  group {gi}: FAIL  actual={langs}")
            print(f"             canonical order is {CANON}")
            print(f"             expected {exp}")
            for s in status:
                print(f"             {s}")

    print(f"=== {args.doc}: {failures} group(s) out of order/missing ===")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
