#!/usr/bin/env python3
"""Run the rust snippets of a user-guide page against a live Milvus server.

Extracts every ```rust block, hoists `use` statements, and wraps the block
bodies inside a main() in a cargo project depending on milvus-sdk-rust.
Compiles and runs with `cargo run`.

Note: the user guide currently has no rust snippets; this runner is prepared
for the future rust SDK coverage.

Optionally pre-checks API calls against the per-tag SDK index (see
gen_api_index.py / api_index.py): pass --api-index DIR --sdk-tag rust@TAG to
pin the crate version to TAG and report unknown SDK calls before compiling.

Usage: python3 run_page_rust.py <page.md> [--api-index DIR --sdk-tag rust@TAG]
"""
import argparse
import json
import os
import shutil
import re
import subprocess
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
PROJ = os.path.join(REPO, "sdk-tmp", "snippet-run", "rust")
SRC = os.path.join(PROJ, "src")


def latest_version():
    """Query crates.io for the latest published milvus-sdk-rust version."""
    req = urllib.request.Request(
        "https://crates.io/api/v1/crates/milvus-sdk-rust",
        headers={"User-Agent": "web-content-snippet-runner/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    return data["crate"]["max_version"]


def cargo_toml(version):
    return f"""[package]
name = "snippet-run"
version = "0.1.0"
edition = "2021"

[dependencies]
milvus-sdk-rust = "{version}"
tokio = {{ version = "1", features = ["macros", "rt-multi-thread"] }}
serde_json = "1"
rand = "0.8"
chrono = "0.4"
"""


def main():
    if not shutil.which("cargo"):
        print("rust: cargo not installed — SKIPPING rust verification")
        sys.exit(0)
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--api-index", default="")
    ap.add_argument("--sdk-tag", default="")
    args, rest = ap.parse_known_args(sys.argv[1:])
    page = rest[0]
    md = open(page).read()
    blocks = re.findall(r"```rust\n(.*?)```", md, re.S)

    # API-existence pre-check (soft)
    if args.api_index and args.sdk_tag:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import api_index as ai
        sdk, _, tag = args.sdk_tag.partition("@")
        idx = ai.resolve_index(sdk, tag, args.api_index)
        if idx:
            print(f"rust: API index {idx}")
            for i, b in enumerate(blocks):
                unknown = ai.check_code(idx, "rust", b, sdk)
                if unknown:
                    print(f"rust: block {i}: {len(unknown)} unknown SDK call(s)")
                    for expr, sym in unknown[:10]:
                        print(f"      {sym}  (from {expr!r})")
        else:
            print(f"rust: WARN no API index for {sdk}@{tag} — skipping API pre-check")

    uses = []
    bodies = []
    for b in blocks:
        kept = []
        for line in b.split("\n"):
            if line.strip().startswith("use "):
                uses.append(line.strip())
                continue
            kept.append(line)
        bodies.append("\n".join(kept))
    uses = list(dict.fromkeys(uses))
    default = "use milvus::v2::prelude::*;"
    if default not in uses:
        uses.insert(0, default)

    prog = "\n".join(uses) + "\n\n#[tokio::main]\nasync fn main() -> Result<()> {\n"
    for i, b in enumerate(bodies):
        prog += f"    // === block {i} ===\n"
        prog += "\n".join("    " + ln for ln in b.split("\n")) + "\n"
    prog += "    Ok(())\n}\n"

    os.makedirs(SRC, exist_ok=True)
    if args.sdk_tag:
        ver = args.sdk_tag.partition("@")[2].lstrip("v")
    else:
        try:
            ver = latest_version()
        except Exception as e:
            print(f"rust: could not resolve latest milvus-sdk-rust from crates.io ({e}) — SKIPPING rust verification")
            sys.exit(0)
    with open(os.path.join(PROJ, "Cargo.toml"), "w") as f:
        f.write(cargo_toml(ver))
    with open(os.path.join(SRC, "main.rs"), "w") as f:
        f.write(prog)

    print(f"rust blocks: {len(blocks)} | verifying milvus-sdk-rust {ver} (crates.io)")
    r = subprocess.run(["cargo", "fetch", "--manifest-path", os.path.join(PROJ, "Cargo.toml")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-2000:])
        print("\nrust: crate fetch failed (network) — snippets NOT executed")
        sys.exit(1)
    r = subprocess.run(["cargo", "run", "--quiet", "--manifest-path", os.path.join(PROJ, "Cargo.toml")],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr[-3000:] if r.returncode else "")
    print(f"\n=== {page} === rust run {'OK' if r.returncode == 0 else 'FAILED'} ({len(blocks)} blocks)")
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
