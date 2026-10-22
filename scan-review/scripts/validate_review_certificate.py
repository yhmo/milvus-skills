#!/usr/bin/env python3
"""Validate a scan-review per-PR completion certificate against artifacts and GitHub."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_STEPS = {str(number) for number in range(1, 12)}
CHALLENGE_LENSES = {
    "comments_docs",
    "test_coverage",
    "failure_modes",
    "concurrency",
    "performance_maintainability",
    "redundancy",
}
SEVERITIES = {"High", "Medium", "Low"}
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
PR_URL_PATTERN = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/pull/[1-9][0-9]*$")


def fail(message: str) -> None:
    raise ValueError(message)


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def substantive(value: Any, minimum_length: int = 12) -> bool:
    return nonempty(value) and len(value.strip()) >= minimum_length


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fail(f"missing file: {path}")
    except (OSError, json.JSONDecodeError) as exc:
        return fail(f"cannot read JSON from {path}: {exc}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_utc_timestamp(value: Any, field: str) -> datetime:
    if not nonempty(value):
        fail(f"{field} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        fail(f"{field} must be an ISO-8601 UTC timestamp: {exc}")
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        fail(f"{field} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def validate_files(files: list[Any]) -> tuple[set[str], int, int]:
    paths: set[str] = set()
    additions = 0
    deletions = 0
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            fail(f"files entry {index} must be an object")
        path = item.get("filename")
        if not nonempty(path):
            fail(f"files entry {index} has no filename")
        if path in paths:
            fail(f"files contains duplicate path: {path}")
        paths.add(path)
        for field in ("additions", "deletions"):
            value = item.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                fail(f"files entry {path} has invalid {field}")
            if field == "additions":
                additions += value
            else:
                deletions += value
    return paths, additions, deletions


def validate_step5(step5: Any) -> None:
    if not isinstance(step5, dict) or not substantive(step5.get("outcome")):
        fail("step5_docs must record a substantive outcome")
    surfaces = step5.get("surfaces")
    valid_surfaces = (
        isinstance(surfaces, list)
        and bool(surfaces)
        and all(
            isinstance(item, dict)
            and substantive(item.get("surface"))
            and substantive(item.get("evidence"))
            for item in surfaces
        )
    )
    if not valid_surfaces and not substantive(step5.get("not_applicable_reason")):
        fail("Step 5 must map inspected comment/doc surfaces to evidence or explain why not applicable")


def validate_step7(step7: Any, changed_paths: set[str]) -> None:
    if not isinstance(step7, dict):
        fail("step7_tests must be an object")
    evidence = step7.get("behavior_evidence")
    valid_evidence = (
        isinstance(evidence, list)
        and bool(evidence)
        and all(
            isinstance(item, dict)
            and substantive(item.get("behavior"))
            and nonempty(item.get("path"))
            and item["path"] in changed_paths
            and substantive(item.get("evidence"))
            and substantive(item.get("disposition"))
            for item in evidence
        )
    )
    if not valid_evidence and not substantive(step7.get("not_applicable_reason")):
        fail("Step 7 must map changed behaviors and paths to evidence or explain why not applicable")


def validate_artifact_digests(certificate: dict[str, Any], ledger_path: Path, notes_path: Path) -> None:
    digests = certificate.get("artifact_sha256")
    if not isinstance(digests, dict) or set(digests) != {"ledger", "notes"}:
        fail("artifact_sha256 must contain exactly ledger and notes")
    expected = {"ledger": ledger_path, "notes": notes_path}
    for name, path in expected.items():
        claimed = digests.get(name)
        if not isinstance(claimed, str) or not HEX_SHA256.fullmatch(claimed):
            fail(f"artifact_sha256.{name} must be a lowercase SHA-256 hex digest")
        if not path.is_file():
            fail(f"{name} artifact does not exist: {path}")
        if sha256_file(path) != claimed:
            fail(f"{name} artifact SHA-256 does not match certificate")


def load_online_comments(path: Path) -> dict[int, dict[str, Any]]:
    comments = load_json(path)
    if not isinstance(comments, list):
        fail("comments JSON must be a paginated pulls comments array")
    by_id: dict[int, dict[str, Any]] = {}
    for index, comment in enumerate(comments):
        if not isinstance(comment, dict):
            fail(f"online comment {index} must be an object")
        comment_id = comment.get("id")
        if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
            fail(f"online comment {index} has invalid id")
        if comment_id in by_id:
            fail(f"online comments contain duplicate id {comment_id}")
        by_id[comment_id] = comment
    return by_id


def validate_comment_online(
    comment: dict[str, Any],
    index: int,
    online_by_id: dict[int, dict[str, Any]],
    changed_paths: set[str],
    expected_pr_url: str,
    head_sha: str,
    reviewer_login: str,
    started_at: datetime,
    ended_at: datetime,
) -> None:
    comment_id = comment.get("id")
    if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
        fail(f"posted comment {index} has an invalid id")
    online = online_by_id.get(comment_id)
    if not isinstance(online, dict):
        fail(f"posted comment {comment_id} was not found in current GitHub review-comment data")
    author_object = online.get("user")
    author = author_object.get("login") if isinstance(author_object, dict) else None
    if not isinstance(author, str) or author.lower() != reviewer_login.lower():
        fail(f"posted comment {comment_id} was not authored by reviewer {reviewer_login}")
    online_pr = online.get("pull_request_url")
    if not isinstance(online_pr, str):
        fail(f"posted comment {comment_id} has no pull_request_url")
    html_pr = online_pr.replace(
        "https://api.github.com/repos/", "https://github.com/"
    ).replace("/pulls/", "/pull/")
    if html_pr != expected_pr_url:
        fail(f"posted comment {comment_id} belongs to a different pull request")
    for field, online_value in (
        ("url", online.get("html_url")),
        ("path", online.get("path")),
        ("side", online.get("side")),
    ):
        if comment.get(field) != online_value:
            fail(f"posted comment {comment_id} {field} does not match GitHub")
    if not isinstance(comment.get("line"), int) or comment["line"] != online.get("line"):
        fail(f"posted comment {comment_id} line does not match GitHub")
    if online.get("commit_id") != head_sha or online.get("original_commit_id") != head_sha:
        fail(f"posted comment {comment_id} is not anchored to the reviewed head SHA")
    if comment["path"] not in changed_paths:
        fail(f"posted comment {comment_id} path is not in the changed-file set")
    body_digest = hashlib.sha256(str(online.get("body", "")).encode("utf-8")).hexdigest()
    if comment.get("body_sha256") != body_digest:
        fail(f"posted comment {comment_id} body digest does not match GitHub")
    created_at = parse_utc_timestamp(online.get("created_at"), f"comment {comment_id} created_at")
    if created_at < started_at or created_at > ended_at:
        fail(f"posted comment {comment_id} was not created inside the certified review interval")


def validate_zero_finding_challenge(challenge: Any) -> None:
    if not isinstance(challenge, dict) or challenge.get("performed") is not True:
        fail("zero-finding result is missing the required challenge pass")
    lenses = challenge.get("lenses")
    valid_lenses = isinstance(lenses, list) and all(
        isinstance(item, dict)
        and item.get("lens") in CHALLENGE_LENSES
        and substantive(item.get("outcome"))
        and substantive(item.get("evidence"))
        for item in lenses
    )
    if not valid_lenses or not isinstance(lenses, list):
        fail("zero-finding challenge lenses are invalid")
    lens_names = {item.get("lens") for item in lenses}
    if lens_names != CHALLENGE_LENSES or len(lenses) != len(CHALLENGE_LENSES):
        fail("zero-finding challenge did not cover every required lens exactly once")
    if not substantive(challenge.get("outcome")):
        fail("zero-finding challenge must record an outcome")


def validate(args: argparse.Namespace) -> dict[str, Any]:
    certificate = load_json(args.certificate)
    files = load_json(args.files_json)
    if not isinstance(certificate, dict):
        fail("certificate must be a JSON object")
    if not isinstance(files, list):
        fail("files JSON must be the paginated pulls/<number>/files array")
    if not isinstance(args.pr_url, str) or not PR_URL_PATTERN.fullmatch(args.pr_url):
        fail("PR URL is not canonical")
    if not nonempty(args.reviewer_login):
        fail("reviewer login must be non-empty")

    if certificate.get("version") != 2:
        fail("certificate version must be 2")
    if certificate.get("pr_url") != args.pr_url:
        fail("certificate PR URL does not match")
    certificate_reviewer = certificate.get("reviewer_login")
    if (
        not isinstance(certificate_reviewer, str)
        or certificate_reviewer.lower() != args.reviewer_login.lower()
    ):
        fail("certificate reviewer login does not match")
    head_sha_start = certificate.get("head_sha_start")
    if not nonempty(head_sha_start) or head_sha_start != args.initial_head_sha:
        fail("review start SHA does not match the pre-review snapshot")
    if certificate.get("head_sha_end") != args.head_sha:
        fail("PR head changed during review or end SHA was not recorded")
    if args.initial_head_sha != args.head_sha:
        fail("PR head changed between pre-review and post-review snapshots")
    started_at = parse_utc_timestamp(certificate.get("started_at"), "started_at")
    ended_at = parse_utc_timestamp(certificate.get("ended_at"), "ended_at")
    if ended_at <= started_at:
        fail("certificate ended_at must be after started_at")

    authoritative_paths, additions, deletions = validate_files(files)
    reviewed_paths = certificate.get("reviewed_paths")
    if (
        not isinstance(reviewed_paths, list)
        or not reviewed_paths
        or not all(nonempty(path) for path in reviewed_paths)
    ):
        fail("reviewed_paths must be a non-empty string list")
    if set(reviewed_paths) != authoritative_paths or len(reviewed_paths) != len(authoritative_paths):
        fail("reviewed path set does not exactly match the current changed-file set")
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

    validate_step5(certificate.get("step5_docs"))
    validate_step7(certificate.get("step7_tests"), authoritative_paths)
    validate_artifact_digests(certificate, args.ledger_path, args.notes_path)

    surviving = certificate.get("surviving_findings")
    if not isinstance(surviving, int) or isinstance(surviving, bool) or surviving < 0:
        fail("surviving_findings must be a non-negative integer")
    suppressed = certificate.get("suppressed_existing_findings", 0)
    if not isinstance(suppressed, int) or isinstance(suppressed, bool) or suppressed < 0:
        fail("suppressed_existing_findings must be a non-negative integer")
    severity_counts = certificate.get("posted_severity_counts")
    if not isinstance(severity_counts, dict) or set(severity_counts) != SEVERITIES:
        fail("posted_severity_counts must contain High, Medium, and Low")
    if not all(
        isinstance(count, int) and not isinstance(count, bool) and count >= 0
        for count in severity_counts.values()
    ):
        fail("posted severity counts must be non-negative integers")

    comments = certificate.get("posted_comments")
    if not isinstance(comments, list):
        fail("posted_comments must be a list")
    actual_severity_counts = {severity: 0 for severity in SEVERITIES}
    comment_ids: set[int] = set()
    for index, comment in enumerate(comments):
        if not isinstance(comment, dict):
            fail(f"posted comment {index} must be an object")
        severity = comment.get("severity")
        if severity not in SEVERITIES:
            fail(f"posted comment {index} has invalid severity")
        actual_severity_counts[severity] += 1
        if not all(nonempty(comment.get(key)) for key in ("url", "path", "body_sha256")):
            fail(f"posted comment {index} is missing URL, path, or body digest")
        if not HEX_SHA256.fullmatch(comment.get("body_sha256", "")):
            fail(f"posted comment {index} has an invalid body SHA-256")
        if not isinstance(comment.get("line"), int) or comment["line"] <= 0:
            fail(f"posted comment {index} has an invalid line")
        if comment.get("side") != "RIGHT":
            fail(f"posted comment {index} must be anchored to RIGHT")
        comment_id = comment.get("id")
        if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
            fail(f"posted comment {index} has an invalid id")
        if comment_id in comment_ids:
            fail(f"posted comment {comment_id} is listed more than once")
        comment_ids.add(comment_id)
    if severity_counts != actual_severity_counts:
        fail("posted severity counts do not match posted comment severities")
    if len(comments) != sum(actual_severity_counts.values()):
        fail("posted comment count does not match severity totals")
    if surviving != len(comments) + suppressed:
        fail("surviving findings must equal posted comments plus suppressed existing findings")
    if surviving > 0 and not comments and suppressed == 0:
        fail("surviving findings cannot disappear without posting or existing-thread suppression")

    online_by_id = load_online_comments(args.comments_json)
    online_reviewer_interval_ids: set[int] = set()
    for online in online_by_id.values():
        author_object = online.get("user")
        author = author_object.get("login") if isinstance(author_object, dict) else None
        if not isinstance(author, str) or author.lower() != args.reviewer_login.lower():
            continue
        created_at = parse_utc_timestamp(online.get("created_at"), "online comment created_at")
        if started_at <= created_at <= ended_at:
            online_reviewer_interval_ids.add(online["id"])
    if online_reviewer_interval_ids != comment_ids:
        missing = sorted(online_reviewer_interval_ids - comment_ids)
        extra = sorted(comment_ids - online_by_id.keys())
        fail(
            "posted comment IDs do not exactly match reviewer comments in the certified interval; "
            f"unreported={missing}, unavailable={extra}"
        )

    for index, comment in enumerate(comments):
        validate_comment_online(
            comment,
            index,
            online_by_id,
            authoritative_paths,
            args.pr_url,
            args.head_sha,
            args.reviewer_login,
            started_at,
            ended_at,
        )
    if not comments:
        for online in online_by_id.values():
            author_object = online.get("user")
            author = author_object.get("login") if isinstance(author_object, dict) else None
            if not isinstance(author, str) or author.lower() != args.reviewer_login.lower():
                continue
            created_at = parse_utc_timestamp(online.get("created_at"), "online comment created_at")
            if started_at <= created_at <= ended_at:
                fail("certificate claims no comments but GitHub has a reviewer comment in the interval")

    if surviving == 0:
        validate_zero_finding_challenge(certificate.get("zero_finding_challenge"))

    elapsed = certificate.get("elapsed_seconds")
    if not isinstance(elapsed, int) or isinstance(elapsed, bool) or elapsed <= 0:
        fail("elapsed_seconds must be a positive integer")
    calculated_elapsed = (ended_at - started_at).total_seconds()
    if abs(elapsed - calculated_elapsed) > 2:
        fail("elapsed_seconds does not match started_at/ended_at")
    result = certificate.get("result")
    if not nonempty(result) or any(character in result for character in "\r\n|"):
        fail("certificate must contain a table-cell-safe result")

    return {
        "valid": True,
        "pr_url": args.pr_url,
        "head_sha": args.head_sha,
        "changed_files": len(files),
        "changed_lines": additions + deletions,
        "surviving_findings": surviving,
        "suppressed_existing_findings": suppressed,
        "posted_comments": len(comments),
        "elapsed_seconds": elapsed,
        "result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--certificate", type=Path, required=True)
    parser.add_argument("--files-json", type=Path, required=True)
    parser.add_argument("--comments-json", type=Path, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--initial-head-sha", required=True)
    parser.add_argument("--pr-url", required=True)
    parser.add_argument("--reviewer-login", required=True)
    parser.add_argument("--ledger-path", type=Path, required=True)
    parser.add_argument("--notes-path", type=Path, required=True)
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
