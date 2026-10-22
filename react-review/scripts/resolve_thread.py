#!/usr/bin/env python3
"""Validate a react-review decision and safely apply its thread mutation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
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
      id isResolved viewerCanReply viewerCanResolve path
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
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
DECISION_FIELDS = {
    "version",
    "pr_url",
    "thread_id",
    "head_sha",
    "decision",
    "trigger_kind",
    "trigger_url",
    "trigger_body_sha256",
    "thread_association",
    "root_original_commit_sha",
    "root_body_sha256",
    "reply_body",
    "evidence",
    "inspected_paths",
}
AUTOMATED_REVIEW_LOGINS = {
    "copilot",
    "copilot-pull-request-reviewer",
    "chatgpt-codex-connector",
}


def normalize_body(body: Any) -> str:
    if not isinstance(body, str):
        return ""
    return " ".join(body.casefold().split())


def is_fixed_acknowledgement(body: Any) -> bool:
    normalized = normalize_body(body)
    return re.fullmatch(
        r"(?:the|this) issue is confirmed fixed[.!]?(?: resolving this conversation[.!]?)?",
        normalized,
    ) is not None


def is_agreement_acknowledgement(body: Any) -> bool:
    normalized = normalize_body(body)
    return normalized in {
        normalize_body(AGREEMENT_ACKNOWLEDGEMENT),
        normalize_body(RESOLVING_AGREEMENT_ACKNOWLEDGEMENT),
    }


def is_exact_reply(body: Any, expected: str) -> bool:
    return normalize_body(body) == normalize_body(expected)


def body_sha256(body: Any) -> str:
    return hashlib.sha256(str(body or "").encode("utf-8")).hexdigest()


def parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"error: {field} timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SystemExit(f"error: invalid {field} timestamp: {value}") from error
    if parsed.tzinfo is None:
        raise SystemExit(f"error: {field} timestamp has no timezone")
    return parsed


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"error: cannot read {path}: {error}") from error
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
    if not body or not login:
        return False
    literal = re.escape(login)
    if re.search(rf"(?<![@\w-])@{literal}(?![\w-])", body, re.IGNORECASE):
        return True
    return re.search(rf"https?://github\.com/{literal}(?![\w-])", body, re.IGNORECASE) is not None


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


def complete_issue_comments(
    owner: str, repo: str, number: int, connection: dict[str, Any]
) -> list[dict[str, Any]]:
    comments = list(connection["nodes"])
    page_info = connection["pageInfo"]
    cursor = page_info["endCursor"] if page_info["hasNextPage"] else None
    while cursor:
        data = graphql(
            ISSUE_COMMENTS_QUERY,
            {"owner": owner, "repo": repo, "number": number, "after": cursor},
        )
        connection = data["repository"]["pullRequest"]["comments"]
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


def validate_thread_association(
    association: Any,
    thread: dict[str, Any],
    trigger_body: str,
) -> None:
    if not isinstance(association, dict) or set(association) != {"kind", "value"}:
        raise SystemExit("error: unified-reply decision requires exact thread_association fields")
    kind = association.get("kind")
    value = association.get("value")
    if not nonempty(value):
        raise SystemExit("error: thread_association.value must be non-empty")
    root_body = str(thread.get("root_body") or "")
    if kind == "path":
        if value != thread.get("path"):
            raise SystemExit("error: path thread_association does not match the thread path")
        if value not in trigger_body:
            raise SystemExit("error: unified reply does not mention the associated thread path")
        return
    if kind == "quote":
        if len(value.strip()) < 12:
            raise SystemExit("error: quote thread_association is too short")
        normalized_value = normalize_body(value)
        if normalized_value not in normalize_body(root_body) or normalized_value not in normalize_body(trigger_body):
            raise SystemExit("error: quote thread_association does not link the root and unified reply")
        return
    raise SystemExit("error: unsupported thread_association.kind")


def write_result(path: Path | None, value: dict[str, Any]) -> None:
    if path is None:
        return
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--result", type=Path, help="durable JSON result output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    snapshot = load_object(args.snapshot)
    decision = load_object(args.decision)
    if snapshot.get("version") != 3:
        raise SystemExit("error: snapshot must use version 3")
    if decision.get("version") != 3 or set(decision) != DECISION_FIELDS:
        raise SystemExit("error: decision must use the exact version-3 schema")

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
    if decision.get("root_original_commit_sha") != thread.get("root_original_commit_sha"):
        raise SystemExit("error: decision root commit does not match the snapshot")
    if decision.get("root_body_sha256") != thread.get("root_body_sha256"):
        raise SystemExit("error: decision root body hash does not match the snapshot")
    if not HEX_SHA256.fullmatch(str(decision.get("root_body_sha256", ""))):
        raise SystemExit("error: decision root body hash is invalid")

    trigger_body = ""
    if trigger_kind == "author_reply":
        trigger_hash = decision.get("trigger_body_sha256")
        if not isinstance(trigger_hash, str) or not HEX_SHA256.fullmatch(trigger_hash):
            raise SystemExit("error: author_reply requires a valid trigger_body_sha256")
        inline = next(
            (
                reply
                for reply in thread.get("author_replies", [])
                if reply.get("url") == decision.get("trigger_url")
            ),
            None,
        )
        unified = next(
            (
                reply
                for reply in snapshot.get("unified_replies", [])
                if reply.get("url") == decision.get("trigger_url")
            ),
            None,
        )
        if inline is None and unified is None:
            raise SystemExit("error: trigger_url is neither a snapshot thread reply nor a unified reply")
        trigger = inline or unified
        if trigger.get("body_sha256") != trigger_hash:
            raise SystemExit("error: trigger body hash does not match the snapshot")
        trigger_body = str(trigger.get("body") or "")
        if unified is not None:
            if parse_timestamp(trigger.get("createdAt"), "unified reply") <= parse_timestamp(
                thread.get("root_created_at"), "root comment"
            ):
                raise SystemExit("error: unified reply predates the root comment")
            validate_thread_association(decision.get("thread_association"), thread, trigger_body)
        elif decision.get("thread_association") is not None:
            raise SystemExit("error: thread_association must be null for an inline author reply")
    else:
        if decision.get("trigger_body_sha256") is not None:
            raise SystemExit("error: head_update requires trigger_body_sha256=null")
        if decision.get("thread_association") is not None:
            raise SystemExit("error: head_update requires thread_association=null")
        if thread.get("author_replies"):
            raise SystemExit("error: head_update requires no PR-author reply in the snapshot")
        original_sha = thread.get("root_original_commit_sha") or ""
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
    if live_thread.get("path") != thread.get("path"):
        raise SystemExit("error: live thread path changed after evaluation")
    reviewer = str(snapshot["reviewer"])
    viewer = ((live.get("viewer") or {}).get("login") or "")
    if viewer.lower() != reviewer.lower():
        raise SystemExit(f"error: authenticated GitHub viewer is {viewer!r}, expected {reviewer!r}")
    if live_thread["isResolved"]:
        result = {
            "thread_id": thread_id,
            "accepted": False,
            "resolved": True,
            "already_resolved": True,
        }
        print(json.dumps(result, sort_keys=True))
        write_result(args.result, result)
        return

    can_reply = live_thread.get("viewerCanReply") is True
    can_resolve = live_thread.get("viewerCanResolve") is True
    comments = complete_comments(thread_id, live_thread["comments"])
    if not comments:
        raise SystemExit("error: live thread has no comments")
    root = comments[0]
    root_login = ((root.get("author") or {}).get("login") or "").lower()
    if root_login != reviewer.lower() and root_login not in AUTOMATED_REVIEW_LOGINS:
        raise SystemExit("error: live root comment is owned by neither the reviewer nor an automated reviewer")
    if body_sha256(root.get("body")) != decision.get("root_body_sha256"):
        raise SystemExit("error: root comment body changed after evaluation")
    if ((root.get("originalCommit") or {}).get("oid") or "") != decision.get("root_original_commit_sha"):
        raise SystemExit("error: live root original commit changed after evaluation")

    pr_author = (((pull.get("author") or {}).get("login")) or "").lower()
    live_inline = {
        comment["url"]: comment
        for comment in comments[1:]
        if (((comment.get("author") or {}).get("login")) or "").lower() == pr_author
    }
    issue_comments = complete_issue_comments(
        owner, repo, number, pull["comments"]
    )
    live_unified = {
        node["url"]: node
        for node in issue_comments
        if (((node.get("author") or {}).get("login")) or "").lower() == pr_author
        and any(
            mentions_login(node.get("body") or "", login)
            for login in [reviewer.lower(), *AUTOMATED_REVIEW_LOGINS]
        )
    }

    if trigger_kind == "author_reply":
        live_trigger = live_inline.get(str(decision.get("trigger_url"))) or live_unified.get(
            str(decision.get("trigger_url"))
        )
        if live_trigger is None:
            raise SystemExit("error: qualifying PR-author response is no longer present")
        if body_sha256(live_trigger.get("body")) != decision.get("trigger_body_sha256"):
            raise SystemExit("error: qualifying PR-author response changed after evaluation")
        if live_unified.get(str(decision.get("trigger_url"))) is not None:
            if parse_timestamp(live_trigger.get("createdAt"), "live unified reply") <= parse_timestamp(
                root.get("createdAt"), "live root comment"
            ):
                raise SystemExit("error: live unified reply predates the root comment")
            validate_thread_association(
                decision.get("thread_association"), {"path": thread.get("path"), "root_body": root.get("body")}, str(live_trigger.get("body") or "")
            )
    elif live_inline:
        raise SystemExit("error: PR author replied after evaluation; re-evaluate the response")

    reviewer_comments = [
        comment
        for comment in comments[1:]
        if (((comment.get("author") or {}).get("login")) or "").lower() == reviewer.lower()
    ]
    if decision_kind == "fixed":
        reply_text = RESOLVING_ACKNOWLEDGEMENT if can_resolve else FIXED_ACKNOWLEDGEMENT
        existing_ack = next(
            (comment for comment in reviewer_comments if is_fixed_acknowledgement(comment.get("body"))),
            None,
        )
    elif decision_kind == "author_reasonable":
        reply_text = (
            RESOLVING_AGREEMENT_ACKNOWLEDGEMENT if can_resolve else AGREEMENT_ACKNOWLEDGEMENT
        )
        existing_ack = next(
            (comment for comment in reviewer_comments if is_agreement_acknowledgement(comment.get("body"))),
            None,
        )
    else:
        reply_text = str(reply_body).strip()
        existing_ack = next(
            (
                comment
                for comment in reviewer_comments
                if is_exact_reply(comment.get("body"), reply_text)
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
        result = {
            "thread_id": thread_id,
            "accepted": False,
            "eligible": True,
            "dry_run": True,
            "decision": decision_kind,
            "viewer_can_reply": can_reply,
            "viewer_can_resolve": can_resolve,
            "action": action,
            "would_post_reply": can_reply and existing_ack is None,
            "reply": reply_text if can_reply else None,
        }
        print(json.dumps(result, sort_keys=True))
        write_result(args.result, result)
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
        result = {
            "thread_id": thread_id,
            "accepted": True,
            "decision": decision_kind,
            "resolved": False,
            "reply_only": True,
            "reply_url": reply_url,
            "reply_reused": existing_ack is not None,
        }
        print(json.dumps(result, sort_keys=True))
        write_result(args.result, result)
        return

    result = graphql(RESOLVE_MUTATION, {"id": thread_id})
    resolved = result["resolveReviewThread"]["thread"]
    if not resolved or resolved.get("isResolved") is not True:
        raise SystemExit("error: GitHub did not confirm thread resolution")
    result = {
        "thread_id": thread_id,
        "accepted": True,
        "decision": decision_kind,
        "resolved": True,
        "already_resolved": False,
        "reply_url": reply_url,
        "reply_reused": existing_ack is not None,
    }
    print(json.dumps(result, sort_keys=True))
    write_result(args.result, result)


if __name__ == "__main__":
    main()
