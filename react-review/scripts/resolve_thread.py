#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


LIVE_QUERY = r"""
query($owner:String!,$repo:String!,$number:Int!,$id:ID!){
  viewer{login}
  repository(owner:$owner,name:$repo){
    pullRequest(number:$number){
      url state headRefOid author{login}
      comments(first:100){
        pageInfo{hasNextPage endCursor}
        nodes{databaseId author{login} body url createdAt}
      }
    }
  }
  node(id:$id){
    ... on PullRequestReviewThread{
      id isResolved viewerCanReply viewerCanResolve
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

RESOLVE_MUTATION = r"""
mutation($id:ID!){
  resolveReviewThread(input:{threadId:$id}){
    thread{id isResolved}
  }
}
"""

FIXED_ACKNOWLEDGEMENT = "The issue is confirmed fixed."
RESOLVING_ACKNOWLEDGEMENT = "The issue is confirmed fixed. Resolving this conversation."
AGREEMENT_ACKNOWLEDGEMENT = "Thanks for the clarification. I agree that no change is needed here."
RESOLVING_AGREEMENT_ACKNOWLEDGEMENT = (
    "Thanks for the clarification. I agree that no change is needed here. "
    "Resolving this conversation."
)


def is_fixed_acknowledgement(body: Any) -> bool:
    if not isinstance(body, str):
        return False
    normalized = " ".join(body.casefold().split())
    return re.fullmatch(
        r"(?:the|this) issue is confirmed fixed[.!]?(?: resolving this conversation[.!]?)?",
        normalized,
    ) is not None


def normalize_body(body: Any) -> str:
    if not isinstance(body, str):
        return ""
    return " ".join(body.casefold().split())


def is_agreement_acknowledgement(body: Any) -> bool:
    normalized = normalize_body(body)
    return normalized in {
        normalize_body(AGREEMENT_ACKNOWLEDGEMENT),
        normalize_body(RESOLVING_AGREEMENT_ACKNOWLEDGEMENT),
    }


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"error: {path} must contain a JSON object")
    return value


def graphql(query: str, fields: dict[str, Any]) -> dict[str, Any]:
    command = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in fields.items():
        flag = "-F" if isinstance(value, int) else "-f"
        command.extend([flag, f"{key}={value}"])
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    payload = json.loads(completed.stdout)
    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def mentions_login(body: str, login: str) -> bool:
    """True when body @-mentions login or links to github.com/login."""
    if not body or not login:
        return False
    literal = re.escape(login)
    if re.search(rf"(?<![@\w-])@{literal}(?![\w-])", body, re.IGNORECASE):
        return True
    return re.search(rf"https?://github\.com/{literal}(?![\w-])", body, re.IGNORECASE) is not None


AUTOMATED_REVIEW_LOGINS = {
    "copilot",
    "copilot-pull-request-reviewer",
    "chatgpt-codex-connector",
}


def complete_comments(thread_id: str, connection: dict[str, Any]) -> list[dict[str, Any]]:
    comments = list(connection["nodes"])
    page_info = connection["pageInfo"]
    cursor = page_info["endCursor"] if page_info["hasNextPage"] else None
    while cursor:
        data = graphql(COMMENTS_QUERY, {"id": thread_id, "after": cursor})
        connection = data["node"]["comments"]
        comments.extend(connection["nodes"])
        page_info = connection["pageInfo"]
        cursor = page_info["endCursor"] if page_info["hasNextPage"] else None
    return comments


def post_reply(
    repo_full: str,
    number: int,
    root_comment_id: int,
    reviewer: str,
    body: str,
) -> dict[str, Any]:
    endpoint = f"repos/{repo_full}/pulls/{number}/comments/{root_comment_id}/replies"
    completed = subprocess.run(
        ["gh", "api", endpoint, "-X", "POST", "-f", f"body={body}"],
        check=True,
        text=True,
        capture_output=True,
    )
    reply = json.loads(completed.stdout)
    reply_author = ((reply.get("user") or {}).get("login") or "").lower()
    if reply_author != reviewer.lower():
        raise SystemExit("error: acknowledgement was not posted by the configured reviewer")
    if (reply.get("body") or "").strip() != body:
        raise SystemExit("error: GitHub did not preserve the acknowledgement body")
    if reply.get("in_reply_to_id") != root_comment_id:
        raise SystemExit("error: acknowledgement did not attach to the intended review thread")
    if not nonempty(reply.get("html_url")):
        raise SystemExit("error: acknowledgement response has no URL")
    return reply


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely resolve a verified review thread")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    snapshot = load_object(args.snapshot)
    decision = load_object(args.decision)
    required = {
        "version",
        "pr_url",
        "thread_id",
        "head_sha",
        "decision",
        "trigger_kind",
        "trigger_url",
        "root_original_commit_sha",
        "reply_body",
        "evidence",
        "inspected_paths",
    }
    if set(decision) != required or decision.get("version") != 2:
        raise SystemExit("error: decision must use the exact version-2 schema")
    decision_kind = decision.get("decision")
    if decision_kind not in {"fixed", "author_reasonable", "author_unreasonable"}:
        raise SystemExit("error: unsupported decision")
    trigger_kind = decision.get("trigger_kind")
    if trigger_kind not in {"author_reply", "head_update"}:
        raise SystemExit("error: unsupported trigger_kind")
    if trigger_kind == "head_update" and decision_kind != "fixed":
        raise SystemExit("error: head_update can only support a fixed decision")
    if trigger_kind == "author_reply" and not nonempty(decision.get("trigger_url")):
        raise SystemExit("error: author_reply requires trigger_url")
    if trigger_kind == "head_update" and decision.get("trigger_url") is not None:
        raise SystemExit("error: head_update requires trigger_url=null")
    reply_body = decision.get("reply_body")
    if decision_kind == "author_unreasonable":
        if not nonempty(reply_body):
            raise SystemExit("error: author_unreasonable requires reply_body")
    elif reply_body is not None:
        raise SystemExit("error: reply_body must be null unless decision is author_unreasonable")
    if not nonempty(decision.get("evidence")):
        raise SystemExit("error: decision evidence is required")
    paths = decision.get("inspected_paths")
    if not isinstance(paths, list) or not paths or not all(nonempty(path) for path in paths):
        raise SystemExit("error: inspected_paths must be a non-empty string list")
    if decision.get("pr_url") != snapshot.get("pr_url") or decision.get("head_sha") != snapshot.get("head_sha"):
        raise SystemExit("error: decision does not match the snapshot PR/head")

    threads = {thread["id"]: thread for thread in snapshot.get("threads", [])}
    thread_id = decision["thread_id"]
    thread = threads.get(thread_id)
    if thread is None:
        raise SystemExit("error: decision thread is neither reviewer- nor automated-bot-owned in the snapshot")
    if thread.get("isResolved"):
        raise SystemExit("error: thread was already resolved in the snapshot")
    original_sha = thread.get("root_original_commit_sha") or ""
    if decision.get("root_original_commit_sha") != original_sha:
        raise SystemExit("error: decision root commit does not match the snapshot")
    if trigger_kind == "author_reply":
        snapshot_unified_urls = {
            reply.get("url")
            for reply in snapshot.get("unified_replies", [])
            if nonempty(reply.get("url"))
        }
        if decision.get("trigger_url") not in thread.get("author_reply_urls", []) and decision.get(
            "trigger_url"
        ) not in snapshot_unified_urls:
            raise SystemExit("error: trigger_url is neither a snapshot thread reply nor a unified reply from the PR author")
    else:
        if thread.get("author_reply_urls"):
            raise SystemExit("error: head_update requires no PR-author reply in the snapshot")
        if original_sha and original_sha == snapshot.get("head_sha"):
            raise SystemExit("error: snapshot head is unchanged since the comment; a fix cannot be confirmed")

    repo_full = snapshot["repo"]
    owner, repo = repo_full.split("/", 1)
    number = int(snapshot["number"])
    live = graphql(LIVE_QUERY, {"owner": owner, "repo": repo, "number": number, "id": thread_id})
    pull = live["repository"]["pullRequest"]
    live_thread = live["node"]
    if pull is None or live_thread is None:
        raise SystemExit("error: live PR or thread no longer exists")
    if pull["state"] != "OPEN":
        raise SystemExit("error: PR is no longer open")
    if pull["headRefOid"] != decision["head_sha"]:
        raise SystemExit("error: PR head changed after evaluation")
    reviewer = str(snapshot["reviewer"])
    viewer = ((live.get("viewer") or {}).get("login") or "")
    if viewer.lower() != reviewer.lower():
        raise SystemExit(f"error: authenticated GitHub viewer is {viewer!r}, expected {reviewer!r}")
    if live_thread["isResolved"]:
        print(json.dumps({"thread_id": thread_id, "resolved": True, "already_resolved": True}, sort_keys=True))
        return
    can_reply = live_thread.get("viewerCanReply") is True
    can_resolve = live_thread.get("viewerCanResolve") is True

    comments = complete_comments(thread_id, live_thread["comments"])
    if not comments:
        raise SystemExit("error: live thread has no comments")
    root_login = ((comments[0].get("author") or {}).get("login") or "").lower()
    reviewer_lower = reviewer.lower()
    if root_login != reviewer_lower and root_login not in {
        "copilot",
        "copilot-pull-request-reviewer",
        "chatgpt-codex-connector",
    }:
        raise SystemExit("error: live root comment is owned by neither the reviewer nor an automated reviewer")
    pr_author = (((pull.get("author") or {}).get("login")) or "").lower()
    live_thread_author_reply_urls = {
        comment["url"]
        for comment in comments[1:]
        if (((comment.get("author") or {}).get("login")) or "").lower() == pr_author
    }
    live_unified_urls: set[str] = set()
    issue_comments = (pull.get("comments") or {}).get("nodes") or []
    for node in issue_comments:
        node_author = ((node.get("author") or {}).get("login") or "").lower()
        body = node.get("body") or ""
        if node_author == pr_author and any(
            mentions_login(body, login)
            for login in [reviewer_lower, *AUTOMATED_REVIEW_LOGINS]
        ):
            if nonempty(node.get("url")):
                live_unified_urls.add(node["url"])
    live_author_reply_urls = live_thread_author_reply_urls | live_unified_urls
    if trigger_kind == "author_reply":
        if decision["trigger_url"] not in live_author_reply_urls:
            raise SystemExit("error: qualifying PR-author response is no longer present")
    elif live_thread_author_reply_urls:
        raise SystemExit("error: PR author replied after evaluation; re-evaluate the response")

    reviewer_comments = [
        comment
        for comment in comments[1:]
        if (((comment.get("author") or {}).get("login")) or "").lower() == reviewer_lower
    ]
    if decision_kind == "fixed":
        reply_text = RESOLVING_ACKNOWLEDGEMENT if can_resolve else FIXED_ACKNOWLEDGEMENT
        existing_ack = next(
            (comment for comment in reviewer_comments if is_fixed_acknowledgement(comment.get("body"))),
            None,
        )
    elif decision_kind == "author_reasonable":
        reply_text = (
            RESOLVING_AGREEMENT_ACKNOWLEDGEMENT
            if can_resolve
            else AGREEMENT_ACKNOWLEDGEMENT
        )
        existing_ack = next(
            (comment for comment in reviewer_comments if is_agreement_acknowledgement(comment.get("body"))),
            None,
        )
    else:
        reply_text = str(reply_body).strip()
        trigger_index = next(
            (
                index
                for index, comment in enumerate(comments)
                if comment.get("url") == decision.get("trigger_url")
            ),
            -1,
        )
        existing_ack = next(
            (
                comment
                for index, comment in enumerate(comments)
                if index > trigger_index
                and (((comment.get("author") or {}).get("login")) or "").lower()
                == reviewer_lower
            ),
            None,
        )

    should_resolve = decision_kind in {"fixed", "author_reasonable"} and can_resolve
    if not can_reply and not should_resolve:
        raise SystemExit("error: viewer cannot perform the required reply or resolution")

    existing_ack = existing_ack if can_reply else None

    if args.dry_run:
        action = "reply_only"
        if should_resolve:
            action = "reply_and_resolve" if can_reply else "resolve_only"
        print(
            json.dumps(
                {
                    "thread_id": thread_id,
                    "eligible": True,
                    "dry_run": True,
                    "decision": decision_kind,
                    "viewer_can_reply": can_reply,
                    "viewer_can_resolve": can_resolve,
                    "action": action,
                    "would_post_reply": can_reply and existing_ack is None,
                    "reply": reply_text if can_reply else None,
                },
                sort_keys=True,
            )
        )
        return

    reply_url = None
    if can_reply and existing_ack is None:
        root_comment_id = comments[0].get("databaseId")
        if not isinstance(root_comment_id, int) or root_comment_id <= 0:
            raise SystemExit("error: root review comment has no REST database ID")
        posted = post_reply(repo_full, number, root_comment_id, reviewer, reply_text)
        reply_url = posted["html_url"]
    elif existing_ack is not None:
        reply_url = existing_ack["url"]

    if not should_resolve:
        print(
            json.dumps(
                {
                    "thread_id": thread_id,
                    "decision": decision_kind,
                    "resolved": False,
                    "reply_only": True,
                    "reply_url": reply_url,
                    "reply_reused": existing_ack is not None,
                },
                sort_keys=True,
            )
        )
        return

    result = graphql(RESOLVE_MUTATION, {"id": thread_id})
    resolved = result["resolveReviewThread"]["thread"]
    if not resolved or resolved.get("isResolved") is not True:
        raise SystemExit("error: GitHub did not confirm thread resolution")
    print(
        json.dumps(
            {
                "thread_id": thread_id,
                "decision": decision_kind,
                "resolved": True,
                "already_resolved": False,
                "reply_url": reply_url,
                "reply_reused": existing_ack is not None,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
