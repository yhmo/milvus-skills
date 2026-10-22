#!/usr/bin/env python3
"""Fetch a complete GitHub PR snapshot as single-JSON artifact files."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PER_PAGE = 100
MAX_PAGES = 30


class SnapshotError(RuntimeError):
    pass


def canonical_pr_parts(pr_url: str) -> tuple[str, str, int, str]:
    parsed = urlparse(pr_url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise SnapshotError("PR URL must be https://github.com/<owner>/<repo>/pull/<number>")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 4 or parts[2].lower() != "pull":
        raise SnapshotError("PR URL must be https://github.com/<owner>/<repo>/pull/<number>")
    owner, repo, _, number_text = parts
    if not number_text.isdigit():
        raise SnapshotError("PR number must be an integer")
    number = int(number_text)
    if number < 1 or number_text != str(number):
        raise SnapshotError("PR number must be a canonical positive integer")
    canonical = f"https://github.com/{owner}/{repo}/pull/{number}"
    return owner, repo, number, canonical


def gh_api(endpoint: str, label: str) -> Any:
    last_error = ""
    for attempt in range(1, 4):
        result = subprocess.run(
            ["gh", "api", endpoint],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise SnapshotError(f"{label}: GitHub returned invalid JSON: {exc}") from exc
        last_error = result.stderr.strip() or f"exit status {result.returncode}"
        if attempt < 3:
            time.sleep(attempt)
    raise SnapshotError(f"{label}: GitHub API failed after 3 attempts: {last_error}")


def fetch_page(owner: str, repo: str, number: int, kind: str, page: int) -> list[dict[str, Any]]:
    endpoint = f"/repos/{owner}/{repo}/pulls/{number}/{kind}?per_page={PER_PAGE}&page={page}"
    value = gh_api(endpoint, f"fetch {kind} page {page}")
    if not isinstance(value, list):
        raise SnapshotError(f"{kind} page {page} must return a JSON array")
    return value


def fetch_all_pages(owner: str, repo: str, number: int, kind: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch one REST collection with an explicit, non-truncating page loop.

    GitHub page-loop semantics are deterministic for these collection endpoints:
    continue only while a page is exactly ``PER_PAGE`` full, and stop on the
    first short page (including an empty page after an exact final page).  The
    result is appended in page order and later checked against PR metadata.
    """

    values: list[dict[str, Any]] = []
    page = 1
    while True:
        items = fetch_page(owner, repo, number, kind, page)
        if len(items) > PER_PAGE:
            raise SnapshotError(f"{kind} page {page} returned more than per_page={PER_PAGE}")
        values.extend(items)
        if len(items) < PER_PAGE:
            break
        if page > MAX_PAGES:
            raise SnapshotError(
                f"{kind} pagination exceeded the supported limit of {MAX_PAGES} full pages"
            )
        page += 1

    pagination = {
        "strategy": "rest-page-loop-until-short-page",
        "per_page": PER_PAGE,
        "pages": page,
        "stop_reason": "short_page",
        "fetched_items": len(values),
    }
    return values, pagination


def validate_files(files: list[dict[str, Any]]) -> None:
    paths: set[str] = set()
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            raise SnapshotError(f"files entry {index} must be an object")
        filename = item.get("filename")
        if not isinstance(filename, str) or not filename:
            raise SnapshotError(f"files entry {index} has no filename")
        if filename in paths:
            raise SnapshotError(f"files contains duplicate path: {filename}")
        paths.add(filename)
        for field in ("additions", "deletions"):
            value = item.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise SnapshotError(f"files entry {filename} has invalid {field}")


def validate_comments(comments: list[dict[str, Any]]) -> None:
    ids: set[int] = set()
    for index, item in enumerate(comments):
        if not isinstance(item, dict):
            raise SnapshotError(f"review comment {index} must be an object")
        comment_id = item.get("id")
        if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
            raise SnapshotError(f"review comment {index} has invalid id")
        if comment_id in ids:
            raise SnapshotError(f"review comments contain duplicate id {comment_id}")
        ids.add(comment_id)


def metadata_count(metadata: dict[str, Any], field: str) -> int:
    value = metadata.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SnapshotError(f"PR metadata has invalid {field}")
    return value


def validate_snapshot_counts(
    metadata: dict[str, Any],
    files: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> None:
    expected_files = metadata_count(metadata, "changed_files")
    expected_additions = metadata_count(metadata, "additions")
    expected_deletions = metadata_count(metadata, "deletions")
    expected_review_comments = metadata_count(metadata, "review_comments")

    actual_additions = sum(item.get("additions", 0) for item in files)
    actual_deletions = sum(item.get("deletions", 0) for item in files)
    if len(files) != expected_files:
        raise SnapshotError(
            f"files pagination merged {len(files)} entries; PR metadata reports {expected_files}"
        )
    if actual_additions != expected_additions or actual_deletions != expected_deletions:
        raise SnapshotError(
            "files pagination totals do not match PR metadata: "
            f"additions {actual_additions}/{expected_additions}, "
            f"deletions {actual_deletions}/{expected_deletions}"
        )
    if len(comments) != expected_review_comments:
        raise SnapshotError(
            f"review-comments pagination merged {len(comments)} entries; "
            f"PR metadata reports {expected_review_comments}"
        )


def metadata_is_consistent(before: dict[str, Any], after: dict[str, Any]) -> None:
    head_before = before.get("head", {}).get("sha") if isinstance(before.get("head"), dict) else None
    head_after = after.get("head", {}).get("sha") if isinstance(after.get("head"), dict) else None
    fields = ("state", "merged_at", "changed_files", "additions", "deletions", "review_comments")
    for field in fields:
        if before.get(field) != after.get(field):
            raise SnapshotError(
                f"PR metadata changed while pages were fetched: {field} "
                f"{before.get(field)!r} -> {after.get(field)!r}"
            )
    if head_before != head_after:
        raise SnapshotError(
            f"PR head changed while pages were fetched: {head_before!r} -> {head_after!r}"
        )


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def snapshot_pr(pr_url: str, output_dir: Path, overwrite: bool) -> dict[str, Any]:
    owner, repo, number, canonical_url = canonical_pr_parts(pr_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        output_dir / name
        for name in ("metadata.json", "files.json", "review_comments.json", "snapshot.json")
    ]
    if not overwrite and any(path.exists() for path in outputs):
        raise SnapshotError(f"output directory already contains a snapshot: {output_dir}")

    initial_metadata = gh_api(f"/repos/{owner}/{repo}/pulls/{number}", "fetch initial PR metadata")
    if not isinstance(initial_metadata, dict):
        raise SnapshotError("PR metadata must be a JSON object")
    if initial_metadata.get("html_url") != canonical_url:
        raise SnapshotError("GitHub metadata HTML URL does not match the canonical PR URL")
    head_object = initial_metadata.get("head")
    head_sha = head_object.get("sha") if isinstance(head_object, dict) else None
    if not isinstance(head_sha, str) or not head_sha:
        raise SnapshotError("PR metadata has no head SHA")

    files, files_pagination = fetch_all_pages(owner, repo, number, "files")
    comments, comments_pagination = fetch_all_pages(owner, repo, number, "comments")
    metadata = gh_api(f"/repos/{owner}/{repo}/pulls/{number}", "fetch final PR metadata")
    if not isinstance(metadata, dict):
        raise SnapshotError("final PR metadata must be a JSON object")
    metadata_is_consistent(initial_metadata, metadata)

    validate_files(files)
    validate_comments(comments)
    validate_snapshot_counts(metadata, files, comments)
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    manifest = {
        "version": 1,
        "pr_url": canonical_url,
        "owner": owner,
        "repo": repo,
        "number": number,
        "fetched_at": fetched_at,
        "state": metadata.get("state"),
        "merged_at": metadata.get("merged_at"),
        "head_sha": head_sha,
        "files_count": len(files),
        "review_comments_count": len(comments),
        "pagination": {
            "files": files_pagination,
            "review_comments": comments_pagination,
        },
        "artifacts": {
            "metadata": "metadata.json",
            "files": "files.json",
            "review_comments": "review_comments.json",
        },
    }

    write_json_atomic(output_dir / "metadata.json", metadata)
    write_json_atomic(output_dir / "files.json", files)
    write_json_atomic(output_dir / "review_comments.json", comments)
    write_json_atomic(output_dir / "snapshot.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-url", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        manifest = snapshot_pr(args.pr_url, args.output_dir, args.overwrite)
    except (SnapshotError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
