#!/usr/bin/env python3
"""Create and safely update timestamped react-review Markdown reports."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HEADER = "| PR URL | Author | Total comments | Fixed | Closed comments |\n|---|---|---:|---:|---:|\n"
COMPLETE_MARKER = "<!-- react-review: complete -->"
INCOMPLETE_MARKER = "<!-- react-review: incomplete -->"
REPORT_PATTERN = re.compile(r"^react_\d{8}_\d{6}(?:_\d+)?\.md$")


def escape_cell(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", "<br>")
        .strip()
    )


def unescape_cell(value: str) -> str:
    return value.replace("\\|", "|").replace("\\\\", "\\").replace("<br>", " ")


def validate_input(url: str, author: str) -> None:
    if not url.strip():
        raise SystemExit("error: url must be non-empty")
    if not author.strip():
        raise SystemExit("error: author must be non-empty")


def validate_report_path(report: Path) -> None:
    if not report.is_file():
        raise SystemExit(f"error: report does not exist: {report}")
    if report.is_symlink():
        raise SystemExit(f"error: refusing to modify symlink report: {report}")


def read_report(report: Path) -> list[str]:
    validate_report_path(report)
    lines = report.read_text(encoding="utf-8").splitlines(keepends=True)
    expected_header = HEADER.splitlines(keepends=True)
    if len(lines) < 2 or lines[:2] != expected_header:
        raise SystemExit(f"error: report header is invalid: {report}")
    return lines


def is_complete(lines: list[str]) -> bool:
    return any(line.rstrip("\r\n") == COMPLETE_MARKER for line in lines)


def is_incomplete(lines: list[str]) -> bool:
    return any(line.rstrip("\r\n") == INCOMPLETE_MARKER for line in lines)


def split_data_rows(lines: list[str]) -> list[tuple[list[str], int]]:
    rows: list[tuple[list[str], int]] = []
    for line_number, line in enumerate(lines[2:], start=3):
        stripped = line.rstrip("\r\n")
        if not stripped or stripped in {COMPLETE_MARKER, INCOMPLETE_MARKER}:
            continue
        fields = re.split(r"(?<!\\)\|", stripped)
        if len(fields) != 7 or fields[0] != "" or fields[-1] != "":
            raise SystemExit(f"error: invalid report row at line {line_number}")
        cells = [field.strip() for field in fields[1:6]]
        if any(not cell for cell in cells):
            raise SystemExit(f"error: empty report cell at line {line_number}")
        rows.append((cells, line_number))
    return rows


def row_line(url: str, author: str, total: int, fixed: int, closed: int) -> str:
    return f"| {escape_cell(url)} | {escape_cell(author)} | {total} | {fixed} | {closed} |\n"


def validate_counts(total: int, fixed: int, closed: int) -> None:
    if min(total, fixed, closed) < 0:
        raise SystemExit("error: report counts must be non-negative")
    if closed > total:
        raise SystemExit("error: closed comments cannot exceed total comments")
    if fixed > total:
        raise SystemExit("error: fixed comments cannot exceed total comments")


def write_atomic(report: Path, lines: list[str]) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix=f".{report.name}.", dir=report.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.writelines(lines)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, report)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def append_row(report: Path, url: str, author: str, total: int, fixed: int, closed: int) -> None:
    validate_input(url, author)
    validate_counts(total, fixed, closed)
    lines = read_report(report)
    if is_complete(lines):
        raise SystemExit("error: report is finalized")
    url_cell = escape_cell(url)
    for cells, line_number in split_data_rows(lines):
        if cells[0] == url_cell:
            raise SystemExit(f"error: PR URL already exists at line {line_number}: {url}")
    row = row_line(url, author, total, fixed, closed)
    if lines and lines[-1].rstrip("\r\n") == INCOMPLETE_MARKER:
        lines.insert(-1, row)
        write_atomic(report, lines)
    else:
        with report.open("a", encoding="utf-8") as handle:
            handle.write(row)
            handle.flush()
            os.fsync(handle.fileno())


def replace_row(report: Path, url: str, author: str, total: int, fixed: int, closed: int) -> None:
    validate_input(url, author)
    validate_counts(total, fixed, closed)
    lines = read_report(report)
    if is_complete(lines):
        raise SystemExit("error: report is finalized")
    url_cell = escape_cell(url)
    replacement = row_line(url, author, total, fixed, closed)
    replaced = False
    for index, line in enumerate(lines[2:], start=2):
        stripped = line.rstrip("\r\n")
        if not stripped or stripped in {COMPLETE_MARKER, INCOMPLETE_MARKER}:
            continue
        rows = split_data_rows([HEADER, "", line])
        if rows[0][0][0] == url_cell:
            lines[index] = replacement
            replaced = True
            break
    if not replaced:
        if lines and lines[-1].rstrip("\r\n") == INCOMPLETE_MARKER:
            lines.insert(-1, replacement)
        else:
            lines.append(replacement)
    write_atomic(report, lines)


def remove_row(report: Path, url: str) -> None:
    lines = read_report(report)
    if is_complete(lines):
        raise SystemExit("error: report is finalized")
    url_cell = escape_cell(url)
    kept: list[str] = []
    removed = False
    for index, line in enumerate(lines):
        if index >= 2:
            stripped = line.rstrip("\r\n")
            if stripped and stripped not in {COMPLETE_MARKER, INCOMPLETE_MARKER}:
                rows = split_data_rows([HEADER, "", line])
                if rows[0][0][0] == url_cell:
                    removed = True
                    continue
        kept.append(line)
    if not removed:
        raise SystemExit(f"error: PR URL does not exist: {url}")
    write_atomic(report, kept)


def new_report(output_dir: Path | None = None) -> Path:
    output_dir = output_dir.resolve() if output_dir is not None else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"react_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    path = output_dir / f"{stem}.md"
    suffix = 1
    while path.exists():
        path = output_dir / f"{stem}_{suffix}.md"
        suffix += 1
    path.write_text(HEADER + INCOMPLETE_MARKER + "\n", encoding="utf-8")
    return path.resolve()


def resume_report(output_dir: Path | None = None) -> Path:
    search_dir = output_dir.resolve() if output_dir is not None else Path.cwd()
    candidates = sorted(
        (path for path in search_dir.glob("react_*.md") if REPORT_PATTERN.fullmatch(path.name)),
        key=lambda path: path.name,
        reverse=True,
    )
    for report in candidates:
        try:
            lines = read_report(report)
        except SystemExit:
            continue
        if is_incomplete(lines):
            return report.resolve()
    return new_report(output_dir)


def finalize_report(report: Path) -> None:
    lines = read_report(report)
    if is_complete(lines):
        return
    if is_incomplete(lines):
        lines = [
            COMPLETE_MARKER + "\n" if line.rstrip("\r\n") == INCOMPLETE_MARKER else line
            for line in lines
        ]
    else:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(COMPLETE_MARKER + "\n")
    write_atomic(report, lines)


def list_rows(report: Path, as_json: bool) -> list[dict[str, Any]]:
    lines = read_report(report)
    rows: list[dict[str, Any]] = []
    for cells, line_number in split_data_rows(lines):
        rows.append(
            {
                "url": unescape_cell(cells[0]),
                "author": unescape_cell(cells[1]),
                "total_comments": int(cells[2]),
                "fixed_comments": int(cells[3]),
                "closed_comments": int(cells[4]),
                "line": line_number,
            }
        )
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, sort_keys=True))
    else:
        for row in rows:
            print(
                "\t".join(
                    str(row[key])
                    for key in (
                        "url",
                        "author",
                        "total_comments",
                        "fixed_comments",
                        "closed_comments",
                    )
                )
            )
    return rows


def nonnegative(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("count must be non-negative")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    new_parser = subparsers.add_parser("new")
    new_parser.add_argument("--output-dir", type=Path, default=None)
    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--output-dir", type=Path, default=None)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--report", type=Path, required=True)
    add_parser.add_argument("--url", required=True)
    add_parser.add_argument("--author", required=True)
    add_parser.add_argument("--total-comments", type=nonnegative, required=True)
    add_parser.add_argument("--fixed-comments", type=nonnegative, required=True)
    add_parser.add_argument("--closed-comments", type=nonnegative, required=True)

    replace_parser = subparsers.add_parser("replace")
    replace_parser.add_argument("--report", type=Path, required=True)
    replace_parser.add_argument("--url", required=True)
    replace_parser.add_argument("--author", required=True)
    replace_parser.add_argument("--total-comments", type=nonnegative, required=True)
    replace_parser.add_argument("--fixed-comments", type=nonnegative, required=True)
    replace_parser.add_argument("--closed-comments", type=nonnegative, required=True)

    remove_parser = subparsers.add_parser("remove")
    remove_parser.add_argument("--report", type=Path, required=True)
    remove_parser.add_argument("--url", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--report", type=Path, required=True)
    list_parser.add_argument("--json", action="store_true")

    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--report", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "new":
        print(new_report(args.output_dir))
    elif args.command == "resume":
        print(resume_report(args.output_dir))
    elif args.command == "add":
        append_row(
            args.report,
            args.url,
            args.author,
            args.total_comments,
            args.fixed_comments,
            args.closed_comments,
        )
    elif args.command == "replace":
        replace_row(
            args.report,
            args.url,
            args.author,
            args.total_comments,
            args.fixed_comments,
            args.closed_comments,
        )
    elif args.command == "remove":
        remove_row(args.report, args.url)
    elif args.command == "list":
        list_rows(args.report, args.json)
    elif args.command == "finalize":
        finalize_report(args.report)


if __name__ == "__main__":
    main()
