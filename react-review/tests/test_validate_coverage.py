#!/usr/bin/env python3
"""Tests for complete open-thread disposition validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from helpers import load_script


coverage = load_script("validate_coverage")


class CoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_processed_and_unchanged_threads(self) -> None:
        snapshot = {
            "version": 3,
            "head_sha": "head",
            "threads": [
                {"id": "processed", "isResolved": False},
                {
                    "id": "unchanged",
                    "isResolved": False,
                    "author_replies": [],
                    "root_original_commit_sha": "head",
                },
                {"id": "resolved-before", "isResolved": True},
            ],
        }
        decision_dir = self.root / "decisions"
        result_dir = self.root / "results"
        decision_dir.mkdir()
        result_dir.mkdir()
        (decision_dir / "processed.json").write_text(json.dumps({"thread_id": "processed"}))
        (result_dir / "processed.json").write_text(
            json.dumps({"thread_id": "processed", "accepted": True})
        )
        ledger = {
            "version": 1,
            "head_sha": "head",
            "threads": {
                "processed": {"status": "processed", "note": "Accepted fixed result."},
                "unchanged": {
                    "status": "skipped_unchanged",
                    "note": "No reply and head is unchanged.",
                },
            },
        }
        result = coverage.validate(snapshot, ledger, decision_dir, result_dir)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["skipped_unchanged"], 1)

    def test_missing_thread_is_rejected(self) -> None:
        snapshot = {"version": 3, "head_sha": "head", "threads": [{"id": "thread"}]}
        ledger = {"version": 1, "head_sha": "head", "threads": {}}
        with self.assertRaises(SystemExit):
            coverage.validate(snapshot, ledger, self.root, self.root)


if __name__ == "__main__":
    unittest.main()
