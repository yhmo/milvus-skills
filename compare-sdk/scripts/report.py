#!/usr/bin/env python3
"""Create, replace, finalize, and validate compare-sdk gap reports."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COMPLETE_MARKER = "<!-- compare-sdk: complete -->"
REQUIRED_SECTIONS = (
    "Source files compared:",
    "Scope:",
    "## Summary",
    "## Main gaps",
    "## Coverage validation",
    "## API Comparison",
    "## Defaults and Coercion Comparison",
    "## Input Validation Comparison",
    "## Wire-expressiveness audit",
    "## Client Telemetry Comparison",
    "## Client Session Comparison",
    "## Internal Mechanisms Comparison",
    "## Reproducibility",
)
COMMIT_PATTERN = re.compile(r"\b[0-9a-f]{40}\b")


def sanitize(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "branch"


def read_content(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise SystemExit(f"error: cannot read {path}: {error}") from error


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            if not content.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def is_inside_git_work_tree(path: Path) -> bool:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"}
    }
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def new_report(output_dir: Path, sdk1: str, sdk2: str, branch: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    if is_inside_git_work_tree(output_dir):
        raise SystemExit(
            "error: refusing to create a repository-local report; "
            "use the temporary run workspace and print it terminal-only"
        )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    stem = f"{sanitize(sdk1.lower())}_{sanitize(sdk2.lower())}_{sanitize(branch)}_gaps_{stamp}"
    path = output_dir / f"{stem}.md"
    suffix = 1
    while path.exists():
        path = output_dir / f"{stem}_{suffix}.md"
        suffix += 1
    title = f"{sdk1.upper()} vs {sdk2.upper()} SDK - {branch} parity gaps"
    while True:
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            path = output_dir / f"{stem}_{suffix}.md"
            suffix += 1
            continue
        wrote = False
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(f"# {title}\n")
                handle.flush()
                os.fsync(handle.fileno())
            wrote = True
            return path.resolve()
        finally:
            if not wrote:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass


def validate_report(report: Path) -> dict[str, Any]:
    if not report.is_file():
        raise SystemExit(f"error: report does not exist: {report}")
    content = report.read_text(encoding="utf-8")
    missing = [section for section in REQUIRED_SECTIONS if section not in content]
    if missing:
        raise SystemExit(f"error: report is missing required sections: {missing}")
    if COMPLETE_MARKER not in content:
        raise SystemExit("error: report is not finalized")
    if re.search(r"\bTODO\b|\bTBD\b", content):
        raise SystemExit("error: report contains TODO/TBD placeholders")
    commits = COMMIT_PATTERN.findall(content)
    if len(set(commits)) < 2:
        raise SystemExit("error: report must record both SDK commit hashes")
    lines = content.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise SystemExit("error: report must start with a Markdown H1 title")
    return {
        "valid": True,
        "report": str(report.resolve()),
        "line_count": len(lines),
        "sdk_commits": sorted(set(commits)),
    }


def finalize_report(report: Path) -> None:
    content = read_content(report)
    if COMPLETE_MARKER not in content:
        write_atomic(report, content.rstrip("\n") + "\n\n" + COMPLETE_MARKER + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new")
    new_parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    new_parser.add_argument("--sdk1", required=True)
    new_parser.add_argument("--sdk2", required=True)
    new_parser.add_argument("--branch", required=True)

    replace_parser = subparsers.add_parser("replace")
    replace_parser.add_argument("--report", type=Path, required=True)
    replace_parser.add_argument("--content-file", type=Path, required=True)

    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--report", type=Path, required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--report", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "new":
        print(new_report(args.output_dir, args.sdk1, args.sdk2, args.branch))
    elif args.command == "replace":
        content = read_content(args.content_file)
        write_atomic(args.report, content)
    elif args.command == "finalize":
        finalize_report(args.report)
    elif args.command == "validate":
        print(json.dumps(validate_report(args.report), sort_keys=True))


if __name__ == "__main__":
    main()
