#!/usr/bin/env python3
"""Seed the isolated collections a page needs so the non-Python SDK runners
(run_page_java/go/rust/cpp/node/csharp) can execute against a live server.

The page md produced by fetch_to_md --isolate already carries page-unique
collection names (e.g. doc_211_my_collection). The non-Python SDK runners do
NOT seed and do NOT re-isolate: they execute the blocks against those exact
names. This helper creates/loads those collections using run_page.py's
data-driven seed engine (matching by stripping the page stem prefix to find the
fixture spec), and optionally keeps them alive.

Usage:
  python3 seed_for_sdks.py <page.md> [--keep]

  --keep   leave the seeded collections alive (default: drop after seeding)

Exit code 0 on success.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_page as rp


def main():
    args = sys.argv[1:]
    keep = "--keep" in args
    args = [a for a in args if a != "--keep"]
    page = args[0]
    md = open(page).read()
    stem = rp._page_stem(page)

    prelude = "from pymilvus import MilvusClient, DataType\n"
    prelude += f'client = MilvusClient(uri="{rp.URI}", token="{rp.TOKEN}")\n'
    env = {"__name__": "__main__"}
    exec(prelude, env)
    client = env["client"]

    # Every fixture-style name the page text touches (already page-unique).
    names = set()
    for m in re.finditer(r"[\"']([a-zA-Z_][a-zA-Z0-9_]*(?:_[a-zA-Z0-9_]+)+)[\"']", md):
        names.add(m.group(1))
    # restrict to names that look like isolated fixture names for this page
    candidates = [n for n in names if n.startswith(stem + "_")]
    # strip the stem to recover the fixture key, then seed matching specs
    seen = set()
    for uniq in sorted(candidates, key=len, reverse=True):
        if uniq in seen:
            continue
        seen.add(uniq)
        orig = uniq[len(stem) + 1:]
        if orig not in rp.SEEDS and orig != "your_collection_name":
            continue
        if orig == "your_collection_name" and rp._seed_for_collection(orig, md) is None:
            continue
        if rp._page_creates(md, uniq):
            continue
        if not client.has_collection(uniq):
            seed = rp._seed_for_collection(orig, md)
            made = seed(client, env["DataType"], uniq, md) or {uniq}
            print(f"seeded {uniq} (from spec {orig})")

    if keep:
        print("kept collections alive (--keep)")
    else:
        # drop every isolated fixture collection created by this seeder
        for uniq in sorted(candidates):
            try:
                if client.has_collection(uniq) and uniq.startswith(stem + "_"):
                    client.drop_collection(uniq)
                    print(f"dropped {uniq}")
            except Exception:
                pass
    sys.exit(0)


if __name__ == "__main__":
    main()
