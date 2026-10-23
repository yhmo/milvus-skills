#!/usr/bin/env python3
"""Remove a completed compare-sdk temporary workspace safely."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path


EXPECTED_PREFIX = "compare-sdk."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    args = parser.parse_args()

    target = Path(args.path)
    temp_root = Path(tempfile.gettempdir()).resolve()
    if not target.is_absolute():
        raise SystemExit("error: workspace path must be absolute")
    if target.is_symlink():
        raise SystemExit("error: refusing to remove a symlink workspace")
    try:
        resolved = target.resolve(strict=True)
    except FileNotFoundError:
        return
    if not resolved.is_dir():
        raise SystemExit("error: workspace path is not a directory")
    if resolved.parent != temp_root:
        raise SystemExit(f"error: workspace must be a direct child of {temp_root}")
    if not resolved.name.startswith(EXPECTED_PREFIX) or len(resolved.name) <= len(EXPECTED_PREFIX):
        raise SystemExit(f"error: workspace name must start with {EXPECTED_PREFIX}")
    shutil.rmtree(resolved)


if __name__ == "__main__":
    main()
