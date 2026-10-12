#!/usr/bin/env python3
"""Normalize blank lines in a user-guide code snippet before writing to Feishu.

The Feishu code blocks are written via `docs +update --content`, which converts
every newline in the payload 1:1 to `<br/>` (an empty line becomes `<br/><br/>`)
with no de-duplication. This helper removes the stray blank lines that commonly
creep into snippets, so the written block is clean and idiomatic. It removes:

  - blank lines between consecutive `import` / `use` / `#include` / `from`
    statements (single blank lines inside a Go `import ( ... )` block are kept —
    that is the stdlib/third-party group separator);
  - blank lines inside data-structure literals (tracked by brace depth with a
    collection-vs-block classifier: `{` after `=`, `:`, `(`, `[`, `,`, an
    identifier, or on a line without a control keyword like `if`/`for`/`func`/
    `main` is a collection opener; `{` on an `if`/`for`/`func`/`main`/... line
    is a statement block whose interior blank lines are preserved);
  - blank lines after a line ending with `,` and right before a closing
    `}` / `]` / `)` of a collection;
  - runs of 2+ consecutive blank lines (collapsed to a single blank line);
  - leading / trailing blank lines.

It also ensures exactly one blank line between the import/include/use region
(consecutive `import` / `use` / `#include` / `from` lines, including a Go
`import ( ... )` block up to its closing `)`) and the following actual code
line — so imports are always visually separated from the code that uses them.

Blank lines that separate logical statements (after client init, between steps,
inside `if` / `func` / `main` bodies) are preserved.

The input is the plain code text (what goes inside `<code>...</code>`, using
real newlines); the output is the normalized text. Run it before composing the
XML `--content` payload for `docs +update`.

Usage:
  python3 normalize_snippet.py < snippet.txt          # normalize from stdin
  python3 normalize_snippet.py --file snippet.txt     # normalize from a file
  python3 normalize_snippet.py --lang java < in.txt   # optional language hint
"""
import argparse
import re
import sys

IMPORT_RE = re.compile(r'^\s*(import |use |#include |from )')
CLOSER_RE = re.compile(r'^[\]\}\)]+(?:\s*(?:,|;))?\s*$')
CONTROL_RE = re.compile(
    r'\b(if|for|while|switch|case|else|do|func|fn|function|match|try|catch|finally|class|struct|impl|main)\b')
# chars that, immediately before a `{`, force it to be a collection opener
# (a function-call argument, slice/map literal, field value, array element…)
COLLECT_BEFORE = '([,:='


def import_like(line, inside_go_import):
    """True if `line` is an import/include/use statement (or a bare entry
    inside a Go `import ( ... )` block)."""
    s = line.strip()
    if not s:
        return False
    if IMPORT_RE.match(s):
        return True
    if inside_go_import and s.startswith('"'):
        return True
    return False


def normalize_go_import_blocks(lines):
    """Rebuild each Go `import ( ... )` block: drop all blank lines inside,
    then re-insert exactly one blank line before the first third-party path
    (first path segment contains a `.`), if a stdlib path precedes it."""
    out = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == 'import (':
            j = i + 1
            while j < len(lines) and lines[j].strip() != ')':
                j += 1
            paths = [l for l in lines[i + 1:j] if l.strip()]
            insert_at = None
            for k, p in enumerate(paths):
                seg = p.strip().strip('"').split('/')[0]
                if '.' in seg and k > 0:
                    insert_at = k
                    break
            out.append(lines[i])
            for k, p in enumerate(paths):
                if insert_at is not None and k == insert_at:
                    out.append('')
                out.append(p)
            if j < len(lines):
                out.append(lines[j])
            i = j + 1
        else:
            out.append(lines[i])
            i += 1
    return out


def collection_depth_per_line(lines):
    """Return a list with, for each line, how many collection braces are open
    at the start of the line. A `{` opens a collection unless it sits on a
    control-flow line (`if`/`for`/`func`/`main`/...) AND is not preceded by a
    collection-forcing character."""
    depths = []
    depth = 0
    for line in lines:
        depths.append(depth)
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '{':
                before = line[i - 1] if i > 0 else ' '
                is_block = bool(CONTROL_RE.search(line)) and before not in COLLECT_BEFORE
                if not is_block:
                    depth += 1
            elif ch == '}':
                if depth > 0:
                    depth -= 1
            i += 1
    return depths


def normalize(text):
    lines = text.split('\n')
    lines = normalize_go_import_blocks(lines)

    # Go `import ( ... )` region tracking
    go_inside = []
    depth = False
    for line in lines:
        s = line.strip()
        if s == 'import (':
            depth = True
        elif depth and s == ')':
            depth = False
        go_inside.append(depth)

    # collection brace depth at the start of each line
    coll_at = collection_depth_per_line(lines)

    # trim leading / trailing blank lines
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    lines = lines[start:end]
    go_inside = go_inside[start:end]
    coll_at = coll_at[start:end]

    out = []
    prev_nb_idx = None  # index (into `lines`) of the previous non-blank line
    for i, line in enumerate(lines):
        if not line.strip():
            # find the next non-blank line
            next_nb = None
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    next_nb = j
                    break
            prev = lines[prev_nb_idx] if prev_nb_idx is not None else None
            nxt = lines[next_nb] if next_nb is not None else None

            # inside a collection literal -> no blank lines
            if coll_at[i] > 0:
                continue
            # blank between imports (single blanks inside Go import blocks are
            # the reconstructed group separator — keep those)
            if prev is not None and nxt is not None:
                prev_imp = import_like(prev, go_inside[prev_nb_idx])
                next_imp = import_like(nxt, go_inside[next_nb])
                in_go_block = go_inside[prev_nb_idx] and go_inside[next_nb]
                if prev_imp and next_imp and not in_go_block:
                    continue
            # blank after a data-structure entry (previous line ends with `,`)
            if prev is not None and prev.rstrip().endswith(','):
                continue
            # blank immediately after an opening brace (block or collection) —
            # never idiomatic
            if prev is not None and prev.rstrip().endswith('{'):
                continue
            # blank immediately before a closing `}` / `]` / `)` — never
            # idiomatic
            if nxt is not None and CLOSER_RE.match(nxt):
                continue
            # collapse runs of 2+ blank lines
            if out and not out[-1].strip():
                continue
            out.append('')
            continue
        out.append(line)
        prev_nb_idx = i
    out = ensure_blank_after_imports(out)
    return '\n'.join(out)


def ensure_blank_after_imports(lines):
    """Ensure exactly one blank line between the import/include/use region and
    the first following code line.

    The import region is a maximal run of consecutive import-like lines
    (`import` / `use` / `#include` / `from`, plus the interior of a Go
    `import ( ... )` block, treated as one region through its closing `)`). If
    a non-import code line directly follows the region without a blank line,
    one is inserted; if there are multiple blank lines, they collapse to one.
    Blank lines *between* consecutive import lines were already removed above.
    """
    out = []
    go_depth = False
    prev_was_import = False
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            # collapse runs of blank lines (keep a single blank)
            if out and not out[-1].strip():
                i += 1
                continue
            out.append(line)
            i += 1
            continue
        if s == 'import (':
            go_depth = True
        closing_go_import = go_depth and s == ')'
        cur_import = import_like(s, go_depth) or closing_go_import
        if go_depth and s == ')':
            go_depth = False
        if cur_import:
            prev_was_import = True
            out.append(line)
        else:
            if prev_was_import:
                # ensure one blank line between import region and this code line
                if out and out[-1].strip():
                    out.append('')
            prev_was_import = False
            out.append(line)
        i += 1
    # trim trailing blank lines
    while out and not out[-1].strip():
        out.pop()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--file', help='read code text from a file instead of stdin')
    ap.add_argument('--lang', help='language hint (informational only)')
    args = ap.parse_args()

    if args.file:
        text = open(args.file, encoding='utf-8').read()
    else:
        text = sys.stdin.read()
    sys.stdout.write(normalize(text))


if __name__ == '__main__':
    main()
