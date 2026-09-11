#!/usr/bin/env python3
import argparse
from datetime import datetime
from pathlib import Path


HEADER = "| PR URL | Author | Review results | Time cost |\n|---|---|---|---|\n"


def escape_cell(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", "<br>")
        .strip()
    )


def new_report(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    path = output_dir / f"{stem}.md"
    suffix = 1
    while path.exists():
        path = output_dir / f"{stem}_{suffix}.md"
        suffix += 1
    path.write_text(HEADER, encoding="utf-8")
    return path.resolve()


def append_row(report: Path, url: str, author: str, result: str, time_cost: str) -> None:
    if not report.is_file():
        raise SystemExit(f"error: report does not exist: {report}")
    with report.open("a", encoding="utf-8") as handle:
        cells = [
            escape_cell(url),
            escape_cell(author),
            escape_cell(result),
            escape_cell(time_cost),
        ]
        handle.write("| " + " | ".join(cells) + " |\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and append scan-review Markdown reports")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new")
    new_parser.add_argument("--output-dir", type=Path, default=Path.cwd())

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--report", type=Path, required=True)
    add_parser.add_argument("--url", required=True)
    add_parser.add_argument("--author", required=True)
    add_parser.add_argument("--result", required=True)
    add_parser.add_argument("--time-cost", required=True)

    args = parser.parse_args()
    if args.command == "new":
        print(new_report(args.output_dir))
    else:
        append_row(args.report, args.url, args.author, args.result, args.time_cost)


if __name__ == "__main__":
    main()
