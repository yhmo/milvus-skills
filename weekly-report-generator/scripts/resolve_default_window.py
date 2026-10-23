#!/usr/bin/env python3
"""Resolve the weekly-report default time window in local and UTC form."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timedelta, timezone


def parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now().astimezone()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.astimezone()


def default_window(now: datetime) -> tuple[datetime, datetime]:
    monday = now.date() - timedelta(days=now.weekday())
    previous_friday = monday - timedelta(days=3)
    start = datetime.combine(previous_friday, time(10)).astimezone()
    return start, now


def local_iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--now",
        help="override current local time for testing (ISO-8601; naive input is local)",
    )
    args = parser.parse_args()

    now = parse_now(args.now)
    start, end = default_window(now)
    print(
        json.dumps(
            {
                "local_start": local_iso(start),
                "local_end": local_iso(end),
                "utc_start": utc_iso(start),
                "utc_end": utc_iso(end),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
