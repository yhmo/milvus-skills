#!/usr/bin/env python3
"""Compare a generated report with a Feishu page by its Time window."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ISO_DATETIME = re.compile(
    r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\s+"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::\d{2})?"
)
CN_DATETIME = re.compile(
    r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日\s*"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::\d{2})?"
)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise SystemExit(f"error: cannot read {path}: {error}") from error


def document_content(value: str) -> str:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return value
    if not isinstance(parsed, dict):
        return value
    document = parsed.get("data", {}).get("document", {})
    content = document.get("content") if isinstance(document, dict) else None
    return content if isinstance(content, str) else value


def time_section(content: str) -> str:
    lines: list[str] = []
    active = False
    for line in content.splitlines():
        if re.fullmatch(r"\s*#{2,6}\s*Time\s*", line, re.IGNORECASE):
            active = True
            continue
        if active and line.lstrip().startswith("#"):
            break
        if active:
            lines.append(line.strip())
    return "\n".join(lines).strip()


def parse_window(section: str) -> list[dict[str, int]] | None:
    matches: list[re.Match[str]] = []
    matches.extend(ISO_DATETIME.finditer(section))
    matches.extend(CN_DATETIME.finditer(section))
    matches.sort(key=lambda match: match.start())
    if len(matches) < 2:
        return None
    return [
        {
            "year": int(match.group("year")),
            "month": int(match.group("month")),
            "day": int(match.group("day")),
            "hour": int(match.group("hour")),
            "minute": int(match.group("minute")),
        }
        for match in matches[:2]
    ]


def compare(new_report: str, existing_document: str) -> dict[str, Any]:
    new_section = time_section(new_report)
    existing_section = time_section(existing_document)
    new_window = parse_window(new_section)
    existing_window = parse_window(existing_section)
    if new_window is None:
        raise SystemExit("error: generated report has no parseable ## Time window")
    if existing_window is None:
        return {
            "decision": "overwrite",
            "same_window": False,
            "reason": "existing page has no parseable Time window",
            "new_time_window": new_window,
            "existing_time_window": None,
        }
    same = new_window == existing_window
    return {
        "decision": "skip" if same else "overwrite",
        "same_window": same,
        "reason": "same Time window" if same else "different Time window",
        "new_time_window": new_window,
        "existing_time_window": existing_window,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new", type=Path, required=True, help="generated Markdown report")
    parser.add_argument(
        "--existing",
        type=Path,
        required=True,
        help="existing page Markdown or docs +fetch JSON output",
    )
    args = parser.parse_args()
    result = compare(
        read_text(args.new),
        document_content(read_text(args.existing)),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
