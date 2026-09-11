#!/usr/bin/env python3
import argparse
from datetime import datetime
from pathlib import Path


HEADER = "| PR URL | Author | Total comments | Fixed | Closed comments |\n|---|---|---:|---:|---:|\n"


def escape_cell(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", "<br>")
        .strip()
    )


def new_report() -> Path:
    output_dir = Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"react_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    path = output_dir / f"{stem}.md"
    suffix = 1
    while path.exists():
        path = output_dir / f"{stem}_{suffix}.md"
        suffix += 1
    path.write_text(HEADER, encoding="utf-8")
    return path.resolve()


def nonnegative(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("count must be non-negative")
    return parsed


def append_row(report: Path, url: str, author: str, total: int, fixed: int, closed: int) -> None:
    if not report.is_file():
        raise SystemExit(f"error: report does not exist: {report}")
    if closed > total:
        raise SystemExit("error: closed comments cannot exceed total comments")
    if fixed > total:
        raise SystemExit("error: fixed comments cannot exceed total comments")
    if total == 0:
        return
    with report.open("a", encoding="utf-8") as handle:
        handle.write(
            f"| {escape_cell(url)} | {escape_cell(author)} | {total} | {fixed} | {closed} |\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and append react-review reports")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("new")

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--report", type=Path, required=True)
    add_parser.add_argument("--url", required=True)
    add_parser.add_argument("--author", required=True)
    add_parser.add_argument("--total-comments", type=nonnegative, required=True)
    add_parser.add_argument("--fixed-comments", type=nonnegative, required=True)
    add_parser.add_argument("--closed-comments", type=nonnegative, required=True)

    args = parser.parse_args()
    if args.command == "new":
        print(new_report())
    else:
        append_row(
            args.report,
            args.url,
            args.author,
            args.total_comments,
            args.fixed_comments,
            args.closed_comments,
        )


if __name__ == "__main__":
    main()
