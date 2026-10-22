#!/usr/bin/env python3
"""Tests for guarded react-review thread mutations."""

from __future__ import annotations

import hashlib
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from helpers import load_script


resolver = load_script("resolve_thread")


HEAD = "b" * 40
ROOT_BODY = "Root finding in src/a.rs"
TRIGGER_BODY = "src/a.rs is fixed by the new guard"


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def make_snapshot() -> dict[str, Any]:
    return {
        "version": 3,
        "repo": "test/repo",
        "number": 1,
        "pr_url": "https://github.com/test/repo/pull/1",
        "state": "OPEN",
        "head_sha": HEAD,
        "pr_author": "author",
        "reviewer": "reviewer",
        "threads": [
            {
                "id": "thread",
                "isResolved": False,
                "path": "src/a.rs",
                "root_body": ROOT_BODY,
                "root_body_sha256": sha(ROOT_BODY),
                "root_created_at": "2026-10-22T08:00:00Z",
                "root_original_commit_sha": "a" * 40,
                "author_replies": [],
            }
        ],
        "unified_replies": [
            {
                "url": "unified",
                "body": TRIGGER_BODY,
                "body_sha256": sha(TRIGGER_BODY),
                "createdAt": "2026-10-22T08:05:00Z",
            }
        ],
    }


def make_decision(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "version": 3,
        "pr_url": "https://github.com/test/repo/pull/1",
        "thread_id": "thread",
        "head_sha": HEAD,
        "decision": "author_unreasonable",
        "trigger_kind": "author_reply",
        "trigger_url": "unified",
        "trigger_body_sha256": sha(TRIGGER_BODY),
        "thread_association": {"kind": "path", "value": "src/a.rs"},
        "root_original_commit_sha": "a" * 40,
        "root_body_sha256": sha(ROOT_BODY),
        "reply_body": "The guard still permits the original failure.",
        "evidence": "The current implementation still reaches the failing branch.",
        "inspected_paths": ["src/a.rs"],
    }
    value.update(overrides)
    return value


def live_payload(*, trigger_body: str = TRIGGER_BODY, reviewer_comments: list[str]) -> dict[str, Any]:
    comments: list[dict[str, Any]] = [
        {
            "databaseId": 1,
            "author": {"login": "reviewer"},
            "body": ROOT_BODY,
            "createdAt": "2026-10-22T08:00:00Z",
            "url": "root",
            "originalCommit": {"oid": "a" * 40},
        },
        {
            "databaseId": 2,
            "author": {"login": "author"},
            "body": trigger_body,
            "createdAt": "2026-10-22T08:05:00Z",
            "url": "unified",
        },
    ]
    comments.extend(
        {
            "databaseId": 100 + index,
            "author": {"login": "reviewer"},
            "body": body,
            "createdAt": "2026-10-22T08:06:00Z",
            "url": f"reviewer-{index}",
        }
        for index, body in enumerate(reviewer_comments)
    )
    return {
        "viewer": {"login": "reviewer"},
        "repository": {
            "pullRequest": {
                "url": "https://github.com/test/repo/pull/1",
                "state": "OPEN",
                "headRefOid": HEAD,
                "author": {"login": "author"},
                "comments": {
                    "nodes": [
                        {
                            "databaseId": 2,
                            "author": {"login": "author"},
                            "body": trigger_body,
                            "url": "unified",
                            "createdAt": "2026-10-22T08:05:00Z",
                        }
                    ],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                },
            }
        },
        "node": {
            "id": "thread",
            "isResolved": False,
            "viewerCanReply": True,
            "viewerCanResolve": False,
            "path": "src/a.rs",
            "comments": {"nodes": comments, "pageInfo": {"hasNextPage": False, "endCursor": None}},
        },
    }


class ResolveThreadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.snapshot_path = self.root / "snapshot.json"
        self.decision_path = self.root / "decision.json"
        self.result_path = self.root / "result.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_resolver(
        self,
        snapshot: dict[str, Any],
        decision: dict[str, Any],
        live: dict[str, Any],
        posted: list[str],
    ) -> dict[str, Any]:
        self.snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
        self.decision_path.write_text(json.dumps(decision), encoding="utf-8")

        def fake_graphql(query: str, fields: dict[str, Any]) -> dict[str, Any]:
            if query == resolver.LIVE_QUERY:
                return live
            raise AssertionError(f"unexpected GraphQL query: {query[:40]}")

        def fake_post(*args: Any) -> dict[str, Any]:
            body = args[-1]
            posted.append(body)
            return {
                "html_url": "posted-reply",
                "in_reply_to_id": 1,
                "body": body,
            }

        with mock.patch.object(resolver, "graphql", fake_graphql), mock.patch.object(
            resolver, "post_reply", fake_post
        ), mock.patch(
            "sys.argv",
            [
                "resolve_thread.py",
                "--snapshot",
                str(self.snapshot_path),
                "--decision",
                str(self.decision_path),
                "--result",
                str(self.result_path),
            ],
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                resolver.main()
        return json.loads(self.result_path.read_text(encoding="utf-8"))

    def test_unified_reply_must_be_newer_than_root(self) -> None:
        snapshot = make_snapshot()
        snapshot["unified_replies"][0]["createdAt"] = "2026-10-22T07:00:00Z"
        with self.assertRaises(SystemExit) as context:
            self.run_resolver(snapshot, make_decision(), live_payload(reviewer_comments=[]), [])
        self.assertIn("predates the root comment", str(context.exception))

    def test_edited_live_trigger_is_rejected(self) -> None:
        with self.assertRaises(SystemExit) as context:
            self.run_resolver(
                make_snapshot(),
                make_decision(),
                live_payload(trigger_body="edited body", reviewer_comments=[]),
                [],
            )
        self.assertIn("response changed after evaluation", str(context.exception))

    def test_rebuttal_does_not_reuse_an_arbitrary_later_reviewer_comment(self) -> None:
        posted: list[str] = []
        result = self.run_resolver(
            make_snapshot(),
            make_decision(),
            live_payload(reviewer_comments=["unrelated clarification"]),
            posted,
        )
        self.assertEqual(posted, [make_decision()["reply_body"]])
        self.assertTrue(result["accepted"])

    def test_rebuttal_is_idempotent_for_exact_body(self) -> None:
        posted: list[str] = []
        exact = make_decision()["reply_body"]
        result = self.run_resolver(
            make_snapshot(),
            make_decision(),
            live_payload(reviewer_comments=[exact]),
            posted,
        )
        self.assertEqual(posted, [])
        self.assertTrue(result["accepted"])
        self.assertTrue(result["reply_reused"])


if __name__ == "__main__":
    unittest.main()
