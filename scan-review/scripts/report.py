#!/usr/bin/env python3
"""Create and safely update timestamped scan-review Markdown reports."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HEADER = "| PR URL | Author | Review results | Time cost |\n|---|---|---|---|\n"
COMPLETE_MARKER = "<!-- scan-review: complete -->"
INCOMPLETE_MARKER = "<!-- scan-review: incomplete -->"
REPORT_PATTERN = re.compile(r"^scan_\d{8}_\d{6}(?:_\d+)?\.md$")


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


def validate_input(url: str, author: str, result: str, time_cost: str) -> None:
    values = {"url": url, "author": author, "result": result, "time_cost": time_cost}
    for name, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise SystemExit(f"error: {name} must be non-empty")


def validate_report_path(report: Path) -> None:
    if not report.is_file():
        raise SystemExit(f"error: report does not exist: {report}")
    if report.is_symlink():
        raise SystemExit(f"error: refusing to modify symlink report: {report}")


def read_report(report: Path) -> list[str]:
    validate_report_path(report)
    lines = report.read_text(encoding="utf-8").splitlines(keepends=True)
    if len(lines) < 2 or lines[0] != HEADER.splitlines(keepends=True)[0] or lines[1] != HEADER.splitlines(keepends=True)[1]:
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
        if len(fields) != 6 or fields[0] != "" or fields[-1] != "":
            raise SystemExit(f"error: invalid report row at line {line_number}")
        cells = [field.strip() for field in fields[1:5]]
        if any(not cell for cell in cells):
            raise SystemExit(f"error: empty report cell at line {line_number}")
        rows.append((cells, line_number))
    return rows


def row_line(url: str, author: str, result: str, time_cost: str) -> str:
    cells = [
        escape_cell(url),
        escape_cell(author),
        escape_cell(result),
        escape_cell(time_cost),
    ]
    return "| " + " | ".join(cells) + " |\n"


def append_row(report: Path, url: str, author: str, result: str, time_cost: str) -> None:
    validate_input(url, author, result, time_cost)
    lines = read_report(report)
    if is_complete(lines):
        raise SystemExit("error: report is finalized")
    url_cell = escape_cell(url)
    for cells, line_number in split_data_rows(lines):
        if cells[0] == url_cell:
            raise SystemExit(f"error: PR URL already exists at line {line_number}: {url}")
    row = row_line(url, author, result, time_cost)
    if lines and lines[-1].rstrip("\r\n") == INCOMPLETE_MARKER:
        lines.insert(-1, row)
        write_atomic(report, lines)
    else:
        with report.open("a", encoding="utf-8") as handle:
            handle.write(row)
            handle.flush()
            os.fsync(handle.fileno())


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


def replace_row(report: Path, url: str, author: str, result: str, time_cost: str) -> None:
    validate_input(url, author, result, time_cost)
    lines = read_report(report)
    if is_complete(lines):
        raise SystemExit("error: report is finalized")
    url_cell = escape_cell(url)
    replacement = row_line(url, author, result, time_cost)
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


def new_report(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"scan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    path = output_dir / f"{stem}.md"
    suffix = 1
    while path.exists():
        path = output_dir / f"{stem}_{suffix}.md"
        suffix += 1
    path.write_text(HEADER + INCOMPLETE_MARKER + "\n", encoding="utf-8")
    return path.resolve()


def resume_report(output_dir: Path) -> Path:
    candidates = sorted(
        (path for path in output_dir.glob("scan_*.md") if REPORT_PATTERN.fullmatch(path.name)),
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
        lines = [COMPLETE_MARKER + "\n" if line.rstrip("\r\n") == INCOMPLETE_MARKER else line for line in lines]
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
                "result": unescape_cell(cells[2]),
                "time_cost": unescape_cell(cells[3]),
                "line": line_number,
            }
        )
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, sort_keys=True))
    else:
        for row in rows:
            print("\t".join(str(row[key]) for key in ("url", "author", "result", "time_cost")))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new")
    new_parser.add_argument("--output-dir", type=Path, default=Path.cwd())

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--output-dir", type=Path, default=Path.cwd())

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--report", type=Path, required=True)
    add_parser.add_argument("--url", required=True)
    add_parser.add_argument("--author", required=True)
    add_parser.add_argument("--result", required=True)
    add_parser.add_argument("--time-cost", required=True)

    replace_parser = subparsers.add_parser("replace")
    replace_parser.add_argument("--report", type=Path, required=True)
    replace_parser.add_argument("--url", required=True)
    replace_parser.add_argument("--author", required=True)
    replace_parser.add_argument("--result", required=True)
    replace_parser.add_argument("--time-cost", required=True)

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
        append_row(args.report, args.url, args.author, args.result, args.time_cost)
    elif args.command == "replace":
        replace_row(args.report, args.url, args.author, args.result, args.time_cost)
    elif args.command == "remove":
        remove_row(args.report, args.url)
    elif args.command == "list":
        list_rows(args.report, args.json)
    elif args.command == "finalize":
        finalize_report(args.report)


if __name__ == "__main__":
    main()
