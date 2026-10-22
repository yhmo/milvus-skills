#!/usr/bin/env python3
"""Tests for react-review report lifecycle."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from helpers import load_script


report = load_script("report")


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_cwd = Path.cwd()
        os.chdir(self.temp_dir.name)

    def tearDown(self) -> None:
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_new_add_replace_remove_and_finalize(self) -> None:
        path = report.new_report()
        self.assertTrue(path.read_text(encoding="utf-8").endswith(report.INCOMPLETE_MARKER + "\n"))
        url = "https://github.com/owner/repo/pull/1"
        report.append_row(path, url, "alice", 3, 1, 2)
        with self.assertRaises(SystemExit):
            report.append_row(path, url, "alice", 3, 1, 2)
        report.replace_row(path, url, "alice", 3, 2, 3)
        report.append_row(path, "https://github.com/owner/repo/pull/2", "bob", 2, 0, 0)
        report.remove_row(path, "https://github.com/owner/repo/pull/2")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            rows = report.list_rows(path, as_json=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["fixed_comments"], 2)
        self.assertTrue(output.getvalue().strip())
        report.finalize_report(path)
        with self.assertRaises(SystemExit):
            report.append_row(path, "https://github.com/owner/repo/pull/3", "carol", 1, 0, 0)
        self.assertIn(report.COMPLETE_MARKER, path.read_text(encoding="utf-8"))

    def test_resume_uses_incomplete_and_rejects_bad_counts(self) -> None:
        incomplete = report.new_report()
        completed = report.new_report()
        report.finalize_report(completed)
        self.assertEqual(report.resume_report(), incomplete)
        with self.assertRaises(SystemExit):
            report.append_row(incomplete, "https://github.com/o/r/pull/1", "alice", 1, 2, 0)
        with self.assertRaises(SystemExit):
            report.append_row(incomplete, "https://github.com/o/r/pull/1", "alice", 1, 0, 2)

    def test_explicit_output_dir_keeps_current_repository_clean(self) -> None:
        repository_dir = Path.cwd()
        report_dir = repository_dir / ".react-review-temporary-reports"
        path = report.new_report(report_dir)
        self.assertEqual(path.parent, report_dir.resolve())
        self.assertTrue(path.exists())
        self.assertEqual(report.resume_report(report_dir), path)
        report.finalize_report(path)
        self.assertFalse(list(repository_dir.glob("react_*.md")))


if __name__ == "__main__":
    unittest.main()
