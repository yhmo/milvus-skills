#!/usr/bin/env python3
"""Unit tests for scan-review report lifecycle behavior."""

from __future__ import annotations

import tempfile
import unittest
import contextlib
import io
from pathlib import Path

from helpers import load_script


report_module = load_script("report")


class ReportLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)
        self.report = report_module.new_report(self.output_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_new_report_is_explicitly_incomplete(self) -> None:
        lines = self.report.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[:2], report_module.HEADER.splitlines())
        self.assertIn(report_module.INCOMPLETE_MARKER, lines)

    def test_add_replace_and_remove_rows(self) -> None:
        url = "https://github.com/owner/repo/pull/1"
        report_module.append_row(self.report, url, "alice", "Failed: retry", "1m")
        report_module.replace_row(self.report, url, "alice", "No inline comments", "2m")
        with contextlib.redirect_stdout(io.StringIO()):
            rows = report_module.list_rows(self.report, as_json=False)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], url)
        self.assertIn("No inline comments", rows[0]["result"])

        second_url = "https://github.com/owner/repo/pull/2"
        report_module.append_row(self.report, second_url, "bob", "Posted 1 comment", "3m")
        report_module.remove_row(self.report, second_url)
        with contextlib.redirect_stdout(io.StringIO()):
            rows = report_module.list_rows(self.report, as_json=False)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], url)
        self.assertTrue(report_module.is_incomplete(report_module.read_report(self.report)))

    def test_add_rejects_duplicate_url(self) -> None:
        url = "https://github.com/owner/repo/pull/1"
        report_module.append_row(self.report, url, "alice", "result", "1m")
        with self.assertRaises(SystemExit):
            report_module.append_row(self.report, url, "alice", "duplicate", "2m")

    def test_finalize_locks_report_and_resume_creates_new_report(self) -> None:
        report_module.finalize_report(self.report)
        self.assertTrue(report_module.is_complete(report_module.read_report(self.report)))
        with self.assertRaises(SystemExit):
            report_module.append_row(
                self.report,
                "https://github.com/owner/repo/pull/2",
                "bob",
                "result",
                "1m",
            )
        resumed = report_module.resume_report(self.output_dir)
        self.assertNotEqual(resumed, self.report)
        self.assertTrue(report_module.is_incomplete(report_module.read_report(resumed)))

    def test_resume_prefers_unfinalized_report(self) -> None:
        old = report_module.new_report(self.output_dir)
        marker = report_module.INCOMPLETE_MARKER + "\n"
        old.write_text(report_module.HEADER + marker, encoding="utf-8")
        report_module.finalize_report(self.report)
        self.assertEqual(report_module.resume_report(self.output_dir), old.resolve())

    def test_markdown_cell_escaping_round_trips(self) -> None:
        url = "https://github.com/owner/repo/pull/1"
        author = "a\\b|c"
        result = "line1\nline2 | tail"
        report_module.append_row(self.report, url, author, result, "1m")
        with contextlib.redirect_stdout(io.StringIO()):
            rows = report_module.list_rows(self.report, as_json=True)
        # list_rows prints JSON; capture the returned value directly instead.
        parsed = rows
        self.assertEqual(parsed[0]["author"], author)
        self.assertEqual(parsed[0]["result"], "line1 line2 | tail")


if __name__ == "__main__":
    unittest.main()
