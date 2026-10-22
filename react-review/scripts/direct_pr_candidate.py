#!/usr/bin/env python3
"""Resolve one react-review PR URL into a safe candidate TSV."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path


SUPPORTED_ORGS = ("milvus-io", "zilliztech")
EXCLUDED_REPOS = {
    "milvus-io/milvus-storage",
    "zilliztech/GPTCache",
    "zilliztech/claude-context",
}
KNOWN_AUTOMATION_AUTHORS = {"pymilvus-bot"}
URL_PATTERN = re.compile(
    r"^https://github\.com/(?P<owner>milvus-io|zilliztech)/"
    r"(?P<repo>[A-Za-z0-9_.-]+)/pull/(?P<number>[1-9][0-9]*)/?$"
)
HEADER = "pr_url\tauthor\tcreated_at\trepo\tnumber\tstate\ttitle\tinternal\n"


def run_gh(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", "api", *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def membership_is_definitive(result: subprocess.CompletedProcess[str]) -> bool | None:
    status_line = result.stdout.splitlines()[0] if result.stdout else ""
    match = re.match(r"^HTTP/[0-9.]+\s+(\d{3})\b", status_line)
    if not match:
        return None
    status = int(match.group(1))
    if result.returncode == 0 and 200 <= status < 300:
        return True
    if status == 404:
        return False
    return None


def is_internal(author: str, author_association: str) -> bool:
    if author_association in {"OWNER", "MEMBER"}:
        return True
    if not author:
        raise SystemExit("error: PR author login is empty")

    for org in SUPPORTED_ORGS:
        endpoint = f"/orgs/{org}/members/{author}"
        last_error = ""
        for attempt in range(1, 4):
            result = run_gh("--include", endpoint, check=False)
            answer = membership_is_definitive(result)
            if answer is True:
                return True
            if answer is False:
                break
            last_error = result.stderr.strip() or "missing or malformed HTTP status"
            if attempt < 3:
                time.sleep(attempt)
        if last_error:
            raise SystemExit(
                f"error: membership check for {author} in {org} was indeterminate: {last_error}"
            )
    return False


def clean_tsv(value: str) -> str:
    return value.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    match = URL_PATTERN.fullmatch(args.url.strip())
    if not match:
        raise SystemExit("error: expected a canonical open PR URL under milvus-io or zilliztech")

    owner = match.group("owner")
    repo_name = match.group("repo")
    number = match.group("number")
    repo = f"{owner}/{repo_name}"
    if repo in EXCLUDED_REPOS:
        raise SystemExit(f"error: repository is excluded from react-review: {repo}")

    try:
        response = run_gh(f"repos/{repo}/pulls/{number}")
        pr = json.loads(response.stdout)
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() or "GitHub API request failed"
        raise SystemExit(f"error: cannot resolve PR: {message}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"error: GitHub returned invalid PR JSON: {error}") from error
    if not isinstance(pr, dict):
        raise SystemExit("error: GitHub PR response must be a JSON object")

    canonical_url = pr.get("html_url") or ""
    normalized_input = args.url.strip().rstrip("/")
    if canonical_url != normalized_input:
        raise SystemExit(f"error: canonical PR URL is {canonical_url or 'unavailable'}")
    if (pr.get("state") or "").lower() != "open":
        raise SystemExit(f"error: PR is not open: {canonical_url}")

    user = pr.get("user") or {}
    author = user.get("login") or ""
    author_type = user.get("type") or ""
    normalized_author = author.lower()
    if (
        not author
        or author_type == "Bot"
        or normalized_author.endswith("[bot]")
        or normalized_author in KNOWN_AUTOMATION_AUTHORS
    ):
        raise SystemExit(f"error: PR author is a bot or automation account: {author}")

    association = pr.get("author_association") or ""
    internal = "1" if is_internal(author, association) else "0"
    values = [
        canonical_url,
        author,
        pr.get("created_at") or "",
        ((pr.get("base") or {}).get("repo") or {}).get("full_name") or repo,
        str(pr.get("number") or number),
        pr.get("state") or "",
        clean_tsv(pr.get("title") or ""),
        internal,
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(HEADER + "\t".join(values) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "author": author,
                "author_association": association,
                "internal": internal,
                "number": int(number),
                "pr_url": canonical_url,
                "repo": repo,
                "state": pr.get("state") or "",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
