#!/usr/bin/env python3
"""Validate a scan-review per-PR completion certificate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_STEPS = {str(i) for i in range(1, 12)}
CHALLENGE_LENSES = {
    "comments_docs",
    "test_coverage",
    "failure_modes",
    "concurrency",
    "performance_maintainability",
    "redundancy",
}
SEVERITIES = {"High", "Medium", "Low"}


def fail(message: str) -> None:
    raise ValueError(message)


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        fail(f"missing file: {path}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")


def validate(args: argparse.Namespace) -> dict[str, Any]:
    certificate = load_json(args.certificate)
    files = load_json(args.files_json)
    if not isinstance(certificate, dict):
        fail("certificate must be a JSON object")
    if not isinstance(files, list):
        fail("files JSON must be the paginated pulls/<number>/files array")

    if certificate.get("version") != 1:
        fail("certificate version must be 1")
    if certificate.get("pr_url") != args.pr_url:
        fail("certificate PR URL does not match")
    if certificate.get("head_sha_start") != args.head_sha:
        fail("review did not start at the current head SHA")
    if certificate.get("head_sha_end") != args.head_sha:
        fail("PR head changed during review or end SHA was not recorded")

    authoritative_paths = {item.get("filename") for item in files}
    if None in authoritative_paths:
        fail("files JSON contains an entry without filename")
    reviewed_paths = certificate.get("reviewed_paths")
    if not isinstance(reviewed_paths, list) or not all(nonempty(path) for path in reviewed_paths):
        fail("reviewed_paths must be a non-empty string list")
    if set(reviewed_paths) != authoritative_paths or len(reviewed_paths) != len(authoritative_paths):
        fail("reviewed path set does not exactly match the current changed-file set")

    additions = sum(int(item.get("additions", 0)) for item in files)
    deletions = sum(int(item.get("deletions", 0)) for item in files)
    if certificate.get("changed_file_count") != len(files):
        fail("changed_file_count does not match GitHub")
    if certificate.get("reviewed_file_count") != len(files):
        fail("reviewed_file_count does not match GitHub")
    if certificate.get("additions") != additions or certificate.get("deletions") != deletions:
        fail("addition/deletion totals do not match GitHub")

    steps = certificate.get("steps")
    if not isinstance(steps, dict) or set(steps) != REQUIRED_STEPS:
        fail("steps must contain exactly keys 1 through 11")
    incomplete = sorted(step for step, status in steps.items() if status != "completed")
    if incomplete:
        fail(f"incomplete review steps: {', '.join(incomplete)}")

    step5 = certificate.get("step5_docs")
    if not isinstance(step5, dict) or not nonempty(step5.get("outcome")):
        fail("step5_docs must record a substantive outcome")
    surfaces = step5.get("surfaces")
    if not (isinstance(surfaces, list) and surfaces and all(nonempty(item) for item in surfaces)):
        if not nonempty(step5.get("not_applicable_reason")):
            fail("Step 5 must list inspected comment/doc surfaces or a reason it is not applicable")

    step7 = certificate.get("step7_tests")
    if not isinstance(step7, dict):
        fail("step7_tests must be an object")
    evidence = step7.get("behavior_evidence")
    if isinstance(evidence, list) and evidence:
        for index, item in enumerate(evidence):
            if not isinstance(item, dict) or not all(
                nonempty(item.get(key)) for key in ("behavior", "evidence", "disposition")
            ):
                fail(f"invalid Step 7 behavior-evidence item at index {index}")
    elif not nonempty(step7.get("not_applicable_reason")):
        fail("Step 7 must map changed behaviors to evidence or explain why it is not applicable")

    surviving = certificate.get("surviving_findings")
    if not isinstance(surviving, int) or surviving < 0:
        fail("surviving_findings must be a non-negative integer")
    severity_counts = certificate.get("posted_severity_counts")
    if not isinstance(severity_counts, dict) or set(severity_counts) != SEVERITIES:
        fail("posted_severity_counts must contain High, Medium, and Low")
    if not all(isinstance(count, int) and count >= 0 for count in severity_counts.values()):
        fail("posted severity counts must be non-negative integers")

    comments = certificate.get("posted_comments")
    if not isinstance(comments, list) or len(comments) != sum(severity_counts.values()):
        fail("posted_comments length does not match posted severity counts")
    for index, comment in enumerate(comments):
        if not isinstance(comment, dict):
            fail(f"posted comment {index} must be an object")
        if comment.get("severity") not in SEVERITIES:
            fail(f"posted comment {index} has invalid severity")
        if comment.get("verified") is not True:
            fail(f"posted comment {index} was not attachment-verified")
        if not all(nonempty(comment.get(key)) for key in ("url", "path")):
            fail(f"posted comment {index} is missing URL or path")
        if not isinstance(comment.get("line"), int) or comment["line"] <= 0:
            fail(f"posted comment {index} has an invalid line")

    if surviving == 0:
        challenge = certificate.get("zero_finding_challenge")
        if not isinstance(challenge, dict) or challenge.get("performed") is not True:
            fail("zero-finding result is missing the required challenge pass")
        lenses = challenge.get("lenses")
        if not isinstance(lenses, list) or not CHALLENGE_LENSES.issubset(set(lenses)):
            fail("zero-finding challenge did not cover every required lens")
        if not nonempty(challenge.get("outcome")):
            fail("zero-finding challenge must record an outcome")

    elapsed = certificate.get("elapsed_seconds")
    if not isinstance(elapsed, int) or elapsed <= 0:
        fail("elapsed_seconds must be a positive integer")
    if not nonempty(certificate.get("result")):
        fail("certificate must contain a table-cell-safe result")

    return {
        "valid": True,
        "pr_url": args.pr_url,
        "head_sha": args.head_sha,
        "changed_files": len(files),
        "changed_lines": additions + deletions,
        "surviving_findings": surviving,
        "posted_comments": len(comments),
        "elapsed_seconds": elapsed,
        "result": certificate["result"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--certificate", type=Path, required=True)
    parser.add_argument("--files-json", type=Path, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--pr-url", required=True)
    args = parser.parse_args()
    try:
        result = validate(args)
    except ValueError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
