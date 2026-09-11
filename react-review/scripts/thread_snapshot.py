#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


THREAD_QUERY = r"""
query($owner:String!,$repo:String!,$number:Int!,$after:String){
  repository(owner:$owner,name:$repo){
    pullRequest(number:$number){
      url state headRefOid author{login}
      reviewThreads(first:100,after:$after){
        pageInfo{hasNextPage endCursor}
        nodes{
          id isResolved isOutdated viewerCanReply viewerCanResolve path line originalLine
          comments(first:100){
            pageInfo{hasNextPage endCursor}
            nodes{
              databaseId author{login} body createdAt url
              commit{oid}
              originalCommit{oid}
            }
          }
        }
      }
    }
  }
}
"""

COMMENTS_QUERY = r"""
query($id:ID!,$after:String){
  node(id:$id){
    ... on PullRequestReviewThread{
      comments(first:100,after:$after){
        pageInfo{hasNextPage endCursor}
        nodes{
          databaseId author{login} body createdAt url
          commit{oid}
          originalCommit{oid}
        }
      }
    }
  }
}
"""

ISSUE_COMMENTS_QUERY = r"""
query($owner:String!,$repo:String!,$number:Int!,$after:String){
  repository(owner:$owner,name:$repo){
    pullRequest(number:$number){
      comments(first:100,after:$after){
        pageInfo{hasNextPage endCursor}
        nodes{databaseId author{login} body url createdAt}
      }
    }
  }
}
"""


def gh_graphql(query: str, fields: dict[str, Any]) -> dict[str, Any]:
    command = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in fields.items():
        if value is None:
            continue
        flag = "-F" if isinstance(value, int) else "-f"
        command.extend([flag, f"{key}={value}"])
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    payload = json.loads(completed.stdout)
    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]


def authenticated_login() -> str:
    completed = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"],
        check=True,
        text=True,
        capture_output=True,
    )
    login = completed.stdout.strip()
    if not login:
        raise SystemExit("error: gh api user returned an empty login")
    return login


def fetch_extra_comments(thread_id: str, after: str | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    cursor = after
    while cursor:
        data = gh_graphql(COMMENTS_QUERY, {"id": thread_id, "after": cursor})
        connection = data["node"]["comments"]
        result.extend(connection["nodes"])
        cursor = connection["pageInfo"]["endCursor"] if connection["pageInfo"]["hasNextPage"] else None
    return result


def mentions_login(body: str, login: str) -> bool:
    """True when body @-mentions login or links to github.com/login."""
    if not body or not login:
        return False
    literal = re.escape(login)
    if re.search(rf"(?<![@\w-])@{literal}(?![\w-])", body, re.IGNORECASE):
        return True
    return re.search(rf"https?://github\.com/{literal}(?![\w-])", body, re.IGNORECASE) is not None


def fetch_unified_replies(
    owner: str,
    repo: str,
    number: int,
    pr_author: str,
    mentioned_logins: list[str],
) -> list[dict[str, Any]]:
    """Top-level issue comments posted by the PR author that mention the reviewer or an automated review bot."""
    unified: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        fields: dict[str, Any] = {"owner": owner, "repo": repo, "number": number}
        if cursor:
            fields["after"] = cursor
        data = gh_graphql(ISSUE_COMMENTS_QUERY, fields)
        pull = data["repository"]["pullRequest"]
        if pull is None:
            raise SystemExit(f"error: PR not found: {owner}/{repo}#{number}")
        connection = pull["comments"]
        for node in connection["nodes"]:
            author = ((node.get("author") or {}).get("login") or "").lower()
            body = node.get("body") or ""
            if author != pr_author.lower():
                continue
            if not any(mentions_login(body, login) for login in mentioned_logins):
                continue
            unified.append(
                {
                    "databaseId": node.get("databaseId"),
                    "author": node.get("author"),
                    "body": body,
                    "url": node.get("url"),
                    "createdAt": node.get("createdAt"),
                }
            )
        if not connection["pageInfo"]["hasNextPage"]:
            break
        cursor = connection["pageInfo"]["endCursor"]
    return unified


def snapshot(repo_full_name: str, number: int, reviewer: str) -> dict[str, Any]:
    owner, repo = repo_full_name.split("/", 1)
    reviewer_lower = reviewer.lower()
    automated_review_logins = {
        "copilot",
        "copilot-pull-request-reviewer",
        "chatgpt-codex-connector",
    }
    cursor = None
    pr_info = None
    all_threads: list[dict[str, Any]] = []
    while True:
        data = gh_graphql(
            THREAD_QUERY,
            {"owner": owner, "repo": repo, "number": number, "after": cursor},
        )
        pull = data["repository"]["pullRequest"]
        if pull is None:
            raise SystemExit(f"error: PR not found: {repo_full_name}#{number}")
        if pr_info is None:
            pr_info = pull
        connection = pull["reviewThreads"]
        for thread in connection["nodes"]:
            comments = thread["comments"]
            nodes = comments["nodes"]
            if comments["pageInfo"]["hasNextPage"]:
                nodes.extend(fetch_extra_comments(thread["id"], comments["pageInfo"]["endCursor"]))
            thread["comments"] = nodes
            all_threads.append(thread)
        if not connection["pageInfo"]["hasNextPage"]:
            break
        cursor = connection["pageInfo"]["endCursor"]

    pr_author = ((pr_info or {}).get("author") or {}).get("login") or ""
    mentioned_logins = [reviewer] + list(automated_review_logins)
    unified_replies = fetch_unified_replies(owner, repo, number, pr_author, mentioned_logins)
    selected = []
    for thread in all_threads:
        comments = thread["comments"]
        if not comments:
            continue
        root_author = (comments[0].get("author") or {}).get("login") or ""
        root_author_lower = root_author.lower()
        if root_author_lower != reviewer_lower and root_author_lower not in automated_review_logins:
            continue
        author_replies = [
            comment["url"]
            for comment in comments[1:]
            if ((comment.get("author") or {}).get("login") or "").lower() == pr_author.lower()
        ]
        root = comments[0]
        root_commit_sha = ((root.get("commit") or {}).get("oid") or "")
        root_original_commit_sha = ((root.get("originalCommit") or {}).get("oid") or "")
        selected.append(
            {
                **thread,
                "root_author": root_author,
                "root_author_is_reviewer": root_author_lower == reviewer_lower,
                "root_author_is_automated": root_author_lower in automated_review_logins,
                "author_reply_urls": author_replies,
                "root_comment_commit_sha": root_commit_sha,
                "root_original_commit_sha": root_original_commit_sha,
                "head_changed_since_comment": bool(
                    root_original_commit_sha
                    and root_original_commit_sha != pr_info["headRefOid"]
                ),
            }
        )

    return {
        "version": 2,
        "repo": repo_full_name,
        "number": number,
        "pr_url": pr_info["url"],
        "state": pr_info["state"],
        "head_sha": pr_info["headRefOid"],
        "pr_author": pr_author,
        "reviewer": reviewer,
        "threads": selected,
        "unified_replies": unified_replies,
        "total_comments": len(selected),
        "closed_comments": sum(1 for thread in selected if thread["isResolved"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot reviewer- or automated-bot-owned PR review threads")
    parser.add_argument("--repo", required=True, help="OWNER/REPO")
    parser.add_argument("--number", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = snapshot(args.repo, args.number, authenticated_login())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("pr_url", "head_sha", "total_comments", "closed_comments")}, sort_keys=True))


if __name__ == "__main__":
    main()
