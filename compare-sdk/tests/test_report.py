#!/usr/bin/env python3
"""Unit tests for compare-sdk report lifecycle and validation."""

from __future__ import annotations

import tempfile
import unittest
import subprocess
from pathlib import Path

from helpers import load_script


report_module = load_script("report")


class ReportTests(unittest.TestCase):
    def test_report_lifecycle_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = report_module.new_report(root, "Java", "PyMilvus", "release/2.3")
            self.assertIn("java_pymilvus_release-2.3_gaps_", report.name)
            content = """# Java vs pymilvus
Source files compared:
- java master ({})
- pymilvus master ({})
Scope:
## Summary
## Main gaps
## Coverage validation
## API Comparison
## Defaults and Coercion Comparison
## Input Validation Comparison
## Wire-expressiveness audit
## Client Telemetry Comparison
## Internal Mechanisms Comparison
## Reproducibility
""".format("a" * 40, "b" * 40)
            content_path = root / "content.md"
            content_path.write_text(content, encoding="utf-8")
            report_module.write_atomic(report, content)
            report_module.finalize_report(report)
            result = report_module.validate_report(report)
            self.assertTrue(result["valid"])
            self.assertEqual(len(result["sdk_commits"]), 2)

    def test_safe_filename_and_missing_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = report_module.new_report(root, "cpp", "csharp", "feature/x")
            self.assertIn("cpp_csharp_feature-x_gaps_", report.name)
            report_module.finalize_report(report)
            with self.assertRaisesRegex(SystemExit, "required sections"):
                report_module.validate_report(report)

    def test_repository_local_report_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            repository.mkdir()
            subprocess.run(
                ["git", "-C", str(repository), "-c", "init.defaultBranch=main", "init"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            with self.assertRaisesRegex(SystemExit, "repository-local report"):
                report_module.new_report(repository, "java", "pymilvus", "master")
            self.assertEqual(list(repository.iterdir()), [repository / ".git"])


if __name__ == "__main__":
    unittest.main()
