#!/usr/bin/env python3
"""Validate that every open in-scope thread has a durable disposition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STATUSES = {"processed", "failed", "skipped_unchanged", "remained_open"}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"error: cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"error: {path} must contain a JSON object")
    return value


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate(
    snapshot: dict[str, Any],
    ledger: dict[str, Any],
    decision_dir: Path,
    result_dir: Path,
) -> dict[str, int]:
    if snapshot.get("version") != 3:
        raise SystemExit("error: snapshot must use version 3")
    if ledger.get("version") != 1 or not isinstance(ledger.get("threads"), dict):
        raise SystemExit("error: ledger must use version 1 with a threads object")
    if ledger.get("head_sha") != snapshot.get("head_sha"):
        raise SystemExit("error: ledger head does not match snapshot")

    open_threads = {
        thread["id"]: thread
        for thread in snapshot.get("threads", [])
        if thread.get("isResolved") is not True
    }
    entries = ledger["threads"]
    if set(entries) != set(open_threads):
        missing = sorted(set(open_threads) - set(entries))
        unknown = sorted(set(entries) - set(open_threads))
        raise SystemExit(
            f"error: ledger thread set mismatch; missing={missing}, unknown={unknown}"
        )

    counts = {status: 0 for status in sorted(STATUSES)}
    for thread_id, thread in open_threads.items():
        entry = entries[thread_id]
        if not isinstance(entry, dict) or set(entry) != {"status", "note"}:
            raise SystemExit(f"error: ledger entry {thread_id} must contain status and note")
        status = entry.get("status")
        note = entry.get("note")
        if status not in STATUSES or not nonempty(note):
            raise SystemExit(f"error: invalid ledger entry for {thread_id}")
        counts[status] += 1

        if status == "processed":
            decision_path = decision_dir / f"{thread_id}.json"
            result_path = result_dir / f"{thread_id}.json"
            decision = load_json(decision_path)
            result = load_json(result_path)
            if decision.get("thread_id") != thread_id or result.get("thread_id") != thread_id:
                raise SystemExit(f"error: artifact thread ID mismatch for {thread_id}")
            if result.get("accepted") is not True:
                raise SystemExit(f"error: processed thread {thread_id} has no accepted result")
        elif status == "skipped_unchanged":
            if thread.get("author_replies") or snapshot.get("unified_replies"):
                raise SystemExit(
                    f"error: thread {thread_id} has possible author context and cannot be skipped as unchanged"
                )
            original_sha = thread.get("root_original_commit_sha") or ""
            if not original_sha or original_sha != snapshot.get("head_sha"):
                raise SystemExit(
                    f"error: thread {thread_id} cannot be skipped unchanged without an identical head"
                )
        elif status == "remained_open" and len(str(note).strip()) < 20:
            raise SystemExit(
                f"error: remained_open thread {thread_id} requires substantive evidence"
            )

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--decision-dir", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args()
    counts = validate(
        load_json(args.snapshot),
        load_json(args.ledger),
        args.decision_dir,
        args.result_dir,
    )
    print(json.dumps({"valid": True, **counts}, sort_keys=True))


if __name__ == "__main__":
    main()
