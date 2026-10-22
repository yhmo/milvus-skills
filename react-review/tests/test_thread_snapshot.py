#!/usr/bin/env python3
"""Tests for complete reviewer-thread snapshots."""

from __future__ import annotations

import tempfile
import unittest
from typing import Any

from helpers import load_script


snapshot_module = load_script("thread_snapshot")


class ThreadSnapshotTests(unittest.TestCase):
    def test_mentions_login_is_bounded(self) -> None:
        self.assertTrue(snapshot_module.mentions_login("Please review @alice", "alice"))
        self.assertTrue(snapshot_module.mentions_login("See https://github.com/alice", "alice"))
        self.assertFalse(snapshot_module.mentions_login("@alice-suffix", "alice"))
        self.assertTrue(snapshot_module.mentions_login("https://github.com/alice/example", "alice"))

    def test_fetch_extra_comments_paginates(self) -> None:
        pages = {
            "c1": [ {"url": "comment-2"} ],
            "c2": [ {"url": "comment-3"} ],
        }

        def fake_graphql(query: str, fields: dict[str, Any]) -> dict[str, Any]:
            self.assertEqual(fields["id"], "thread")
            cursor = fields["after"]
            page = pages[cursor]
            has_next = cursor != "c2"
            return {
                "node": {
                    "comments": {
                        "nodes": page,
                        "pageInfo": {
                            "hasNextPage": has_next,
                            "endCursor": "c2" if cursor == "c1" else None,
                        },
                    }
                }
            }

        original = snapshot_module.gh_graphql
        snapshot_module.gh_graphql = fake_graphql
        try:
            self.assertEqual(
                snapshot_module.fetch_extra_comments("thread", "c1"),
                [{"url": "comment-2"}, {"url": "comment-3"}],
            )
        finally:
            snapshot_module.gh_graphql = original

    def test_snapshot_filters_root_owners_and_records_hashes(self) -> None:
        pull = {
            "url": "https://github.com/test/repo/pull/1",
            "state": "OPEN",
            "headRefOid": "b" * 40,
            "author": {"login": "author"},
            "reviewThreads": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {
                        "id": "reviewer-thread",
                        "isResolved": False,
                        "path": "src/a.rs",
                        "comments": {
                            "nodes": [
                                {
                                    "author": {"login": "reviewer"},
                                    "body": "Root finding",
                                    "createdAt": "2026-10-22T08:00:00Z",
                                    "url": "root",
                                    "originalCommit": {"oid": "a" * 40},
                                },
                                {
                                    "author": {"login": "author"},
                                    "body": "Fixed it",
                                    "createdAt": "2026-10-22T08:01:00Z",
                                    "url": "reply",
                                },
                            ],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        },
                    },
                    {
                        "id": "other-thread",
                        "isResolved": False,
                        "path": "src/b.rs",
                        "comments": {
                            "nodes": [{"author": {"login": "other"}, "body": "other"}],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        },
                    },
                ],
            },
        }

        original_graphql = snapshot_module.gh_graphql
        original_unified = snapshot_module.fetch_unified_replies
        snapshot_module.gh_graphql = lambda query, fields: {
            "repository": {"pullRequest": pull}
        }
        snapshot_module.fetch_unified_replies = lambda *args: [
            {"url": "unified", "body": "reply", "createdAt": "later"}
        ]
        try:
            result = snapshot_module.snapshot("test/repo", 1, "reviewer")
        finally:
            snapshot_module.gh_graphql = original_graphql
            snapshot_module.fetch_unified_replies = original_unified

        self.assertEqual(result["version"], 3)
        self.assertEqual(result["total_comments"], 1)
        self.assertEqual(result["open_threads"], 1)
        self.assertEqual(result["threads"][0]["id"], "reviewer-thread")
        self.assertEqual(result["threads"][0]["author_reply_urls"], ["reply"])
        self.assertTrue(result["threads"][0]["head_changed_since_comment"])
        self.assertEqual(
            result["threads"][0]["root_body_sha256"],
            snapshot_module.body_sha256("Root finding"),
        )
        self.assertEqual(result["unified_replies"][0]["url"], "unified")


if __name__ == "__main__":
    unittest.main()
