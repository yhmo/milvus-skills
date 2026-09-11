#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


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


def is_internal(author: str) -> bool:
    for org in SUPPORTED_ORGS:
        result = run_gh("--silent", f"/orgs/{org}/members/{author}", check=False)
        if result.returncode == 0:
            return True
    return False


def clean_tsv(value: str) -> str:
    return value.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve one react-review PR URL into a candidate TSV"
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    match = URL_PATTERN.fullmatch(args.url.strip())
    if not match:
        raise SystemExit(
            "error: expected a canonical open PR URL under milvus-io or zilliztech"
        )

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

    canonical_url = pr.get("html_url") or ""
    normalized_input = args.url.rstrip("/")
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
    internal = "1" if is_internal(author) else "0"

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
