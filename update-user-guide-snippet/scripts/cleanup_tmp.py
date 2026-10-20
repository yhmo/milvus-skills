#!/usr/bin/env python3
"""Remove one-off intermediate artifacts produced by this skill's run.

Reusable caches are preserved:

- ``sdk-tmp/api-index/`` -- per-SDK@tag API index TSVs, valid forever (git tags
  are immutable); regenerating them costs a full repo scan, so keep them.
- ``sdk-tmp/sdks/`` -- fallback SDK clones; they persist across runs and only
  receive a cheap ``git fetch --tags`` refresh.

One-off artifacts removed by this script (they are snapshots of the Feishu
documents / harness scaffolding for the current run only, and are regenerated
on every run):

- ``sdk-tmp/snippet-check/`` -- extracted snippet files for parse checks.
- ``sdk-tmp/snippet-run/``   -- extracted markdown pages and per-language
  runner project dirs (go/java/rust/cpp).

With ``--deep``, every other entry directly under ``sdk-tmp`` is also removed
(ad-hoc scratch files past runs dropped there: ``*-payload.xml``, one-off fix
XMLs, stray extraction files, ...). ``api-index/`` and ``sdks/`` are ALWAYS
preserved, in both modes, and hidden entries (dotfiles) are never touched.

Only paths named ``snippet-check`` or ``snippet-run`` directly inside a
``sdk-tmp`` directory are deleted in the default mode; ``--deep`` still never
leaves the bounds of a ``sdk-tmp`` directory.

Usage::

    python3 scripts/cleanup_tmp.py [--tmp-dir sdk-tmp] [--deep] [--dry-run] [--quiet]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# The only directory entries this script is allowed to delete.
CLEANABLE = ("snippet-check", "snippet-run")
# Never removed, even with --deep.
PROTECTED = ("api-index", "sdks")


def skill_root() -> Path:
    """Directory containing this skill (parent of the scripts/ dir)."""
    return Path(__file__).resolve().parent.parent


def candidate_tmp_dirs(explicit: str | None) -> list[Path]:
    """Return the sdk-tmp dirs to clean, most specific first, deduplicated.

    Default: the skill-root ``sdk-tmp`` (used by the bundled runners) plus a
    cwd-relative ``sdk-tmp`` when it exists (manual invocations of
    ``check_snippets.py`` / ``fetch_to_md.py`` default to writing there).
    """
    dirs: list[Path] = []
    if explicit:
        dirs.append(Path(explicit).expanduser().resolve())
    else:
        dirs.append(skill_root() / "sdk-tmp")
        cwd_tmp = Path.cwd() / "sdk-tmp"
        if cwd_tmp.resolve() not in {d.resolve() for d in dirs} and cwd_tmp.is_dir():
            dirs.append(cwd_tmp.resolve())
    return dirs


def remove_path(target: Path) -> None:
    """Delete a directory tree, file, or symlink; ignore absence."""
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target, ignore_errors=True)
    else:
        try:
            target.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--tmp-dir", help="Clean only this sdk-tmp directory instead of the defaults."
    )
    ap.add_argument(
        "--deep",
        action="store_true",
        help="Also remove other ad-hoc scratch entries directly under sdk-tmp "
        f"(everything except {', '.join(PROTECTED)}).",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="List what would be deleted without deleting."
    )
    ap.add_argument(
        "--quiet", action="store_true", help="Suppress per-path output; print only the summary."
    )
    args = ap.parse_args()

    removed, missing = [], []
    for tmp_dir in candidate_tmp_dirs(args.tmp_dir):
        names = list(CLEANABLE)
        if args.deep and tmp_dir.is_dir():
            for entry in sorted(tmp_dir.iterdir()):
                if entry.name.startswith("."):
                    continue
                if entry.name not in names and entry.name not in PROTECTED:
                    names.append(entry.name)
        for name in names:
            target = tmp_dir / name
            # Safety: never delete unless it sits directly inside a dir literally
            # named sdk-tmp, and its name is a known scratch dir (default mode)
            # or not a protected cache (--deep mode).
            if target.parent.name != "sdk-tmp":
                continue
            if target.name not in CLEANABLE and (not args.deep or target.name in PROTECTED):
                continue
            if not target.exists():
                missing.append(target)
                continue
            if args.dry_run:
                if not args.quiet:
                    print(f"[dry-run] would remove: {target}")
                removed.append(target)
                continue
            if not args.quiet:
                print(f"removing: {target}")
            remove_path(target)
            removed.append(target)

    if not args.quiet:
        for target in missing:
            print(f"not present (skipped): {target}")
    kept = ["api-index", "sdks"]
    print(f"cleanup done: {len(removed)} dir(s) removed; kept caches: {', '.join(kept)}")
    if args.dry_run:
        print("(dry-run: nothing was actually deleted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
