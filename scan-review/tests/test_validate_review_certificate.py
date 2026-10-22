#!/usr/bin/env python3
"""Unit tests for the scan-review version-2 completion certificate validator."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from helpers import load_script


validator = load_script("validate_review_certificate")


PR_URL = "https://github.com/test/repo/pull/1"
HEAD_SHA = "a" * 40
STARTED_AT = "2026-10-22T08:00:00Z"
ENDED_AT = "2026-10-22T08:20:00Z"


def make_files() -> list[dict[str, Any]]:
    return [
        {"filename": "src/a.rs", "additions": 10, "deletions": 2},
        {"filename": "src/b.rs", "additions": 5, "deletions": 1},
    ]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def base_certificate(files: list[dict[str, Any]], ledger: Path, notes: Path) -> dict[str, Any]:
    return {
        "version": 2,
        "pr_url": PR_URL,
        "reviewer_login": "reviewer",
        "head_sha_start": HEAD_SHA,
        "head_sha_end": HEAD_SHA,
        "started_at": STARTED_AT,
        "ended_at": ENDED_AT,
        "elapsed_seconds": 20 * 60,
        "reviewed_paths": [item["filename"] for item in files],
        "changed_file_count": len(files),
        "reviewed_file_count": len(files),
        "additions": sum(item["additions"] for item in files),
        "deletions": sum(item["deletions"] for item in files),
        "steps": {str(number): "completed" for number in range(1, 12)},
        "step5_docs": {
            "outcome": "All relevant documentation surfaces were inspected.",
            "surfaces": [
                {
                    "surface": "public rustdocs",
                    "evidence": "Compared each changed public rustdoc with behavior.",
                }
            ],
        },
        "step7_tests": {
            "behavior_evidence": [
                {
                    "behavior": "Validation and wire conversion behavior",
                    "path": files[0]["filename"],
                    "evidence": "Mapped changed behavior to existing focused tests.",
                    "disposition": "Coverage is adequate for the changed behavior.",
                }
            ]
        },
        "artifact_sha256": {
            "ledger": sha256_bytes(ledger.read_bytes()),
            "notes": sha256_bytes(notes.read_bytes()),
        },
        "surviving_findings": 0,
        "suppressed_existing_findings": 0,
        "posted_severity_counts": {"High": 0, "Medium": 0, "Low": 0},
        "posted_comments": [],
        "zero_finding_challenge": {
            "performed": True,
            "outcome": "No additional issue survived the challenge pass.",
            "lenses": [
                {
                    "lens": lens,
                    "outcome": f"{lens} completed",
                    "evidence": f"{lens} was independently checked and documented.",
                }
                for lens in sorted(validator.CHALLENGE_LENSES)
            ],
        },
        "result": "No inline comments to post",
    }


def online_comment(
    *,
    comment_id: int = 123,
    created_at: str = "2026-10-22T08:10:00Z",
    body: str = "path/to/file.rs line:1\nHigh ---- fixture body",
) -> dict[str, Any]:
    return {
        "id": comment_id,
        "user": {"login": "reviewer"},
        "html_url": f"{PR_URL}#discussion_r{comment_id}",
        "pull_request_url": "https://api.github.com/repos/test/repo/pulls/1",
        "path": "src/a.rs",
        "line": 12,
        "side": "RIGHT",
        "commit_id": HEAD_SHA,
        "original_commit_id": HEAD_SHA,
        "body": body,
        "created_at": created_at,
    }


class CertificateValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.files = make_files()
        self.ledger = self.root / "ledger.md"
        self.notes = self.root / "notes.md"
        self.ledger.write_text("# ledger\n| path | state |\n|---|---|\n", encoding="utf-8")
        for item in self.files:
            self.ledger.write_text(f"| {item['filename']} | reviewed |\n", encoding="utf-8")
        self.notes.write_text(
            "# notes\nAll numbered review steps contain persisted evidence.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def validate_certificate(
        self,
        certificate: dict[str, Any],
        comments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        files_path = self.root / "files.json"
        comments_path = self.root / "comments.json"
        certificate_path = self.root / "certificate.json"
        files_path.write_text(json.dumps(self.files), encoding="utf-8")
        comments_path.write_text(json.dumps(comments), encoding="utf-8")
        certificate_path.write_text(json.dumps(certificate), encoding="utf-8")
        namespace = argparse.Namespace(
            certificate=certificate_path,
            files_json=files_path,
            comments_json=comments_path,
            head_sha=HEAD_SHA,
            initial_head_sha=HEAD_SHA,
            pr_url=PR_URL,
            reviewer_login="reviewer",
            ledger_path=self.ledger,
            notes_path=self.notes,
        )
        return validator.validate(namespace)

    def test_valid_zero_finding_certificate_passes(self) -> None:
        certificate = base_certificate(self.files, self.ledger, self.notes)
        result = self.validate_certificate(certificate, [])
        self.assertTrue(result["valid"])
        self.assertEqual(result["posted_comments"], 0)

    def test_valid_one_comment_certificate_passes(self) -> None:
        online = online_comment()
        certificate = base_certificate(self.files, self.ledger, self.notes)
        certificate.update(
            surviving_findings=1,
            posted_severity_counts={"High": 1, "Medium": 0, "Low": 0},
            result="Posted 1 comment: High 1",
        )
        certificate["posted_comments"] = [
            {
                "id": online["id"],
                "url": online["html_url"],
                "path": online["path"],
                "line": online["line"],
                "side": online["side"],
                "severity": "High",
                "body_sha256": sha256_bytes(online["body"].encode("utf-8")),
            }
        ]
        result = self.validate_certificate(certificate, [online])
        self.assertTrue(result["valid"])
        self.assertEqual(result["posted_comments"], 1)

    def test_severity_count_mismatch_is_rejected(self) -> None:
        online = online_comment()
        certificate = base_certificate(self.files, self.ledger, self.notes)
        certificate.update(
            surviving_findings=1,
            posted_severity_counts={"High": 1, "Medium": 0, "Low": 0},
        )
        certificate["posted_comments"] = [
            {
                "id": online["id"],
                "url": online["html_url"],
                "path": online["path"],
                "line": online["line"],
                "side": online["side"],
                "severity": "Low",
                "body_sha256": sha256_bytes(online["body"].encode("utf-8")),
            }
        ]
        with self.assertRaisesRegex(ValueError, "severity counts do not match"):
            self.validate_certificate(certificate, [online])

    def test_nonexistent_comment_is_rejected(self) -> None:
        certificate = base_certificate(self.files, self.ledger, self.notes)
        certificate.update(
            surviving_findings=1,
            posted_severity_counts={"High": 1, "Medium": 0, "Low": 0},
        )
        certificate["posted_comments"] = [
            {
                "id": 999,
                "url": f"{PR_URL}#discussion_r999",
                "path": "src/a.rs",
                "line": 12,
                "side": "RIGHT",
                "severity": "High",
                "body_sha256": "0" * 64,
            }
        ]
        with self.assertRaisesRegex(ValueError, "posted comment IDs do not exactly match"):
            self.validate_certificate(certificate, [])

    def test_unreported_reviewer_comment_in_interval_is_rejected(self) -> None:
        reported = online_comment(comment_id=123)
        omitted = online_comment(comment_id=124, created_at="2026-10-22T08:15:00Z")
        certificate = base_certificate(self.files, self.ledger, self.notes)
        certificate.update(
            surviving_findings=1,
            posted_severity_counts={"High": 1, "Medium": 0, "Low": 0},
        )
        certificate["posted_comments"] = [
            {
                "id": reported["id"],
                "url": reported["html_url"],
                "path": reported["path"],
                "line": reported["line"],
                "side": reported["side"],
                "severity": "High",
                "body_sha256": sha256_bytes(reported["body"].encode("utf-8")),
            }
        ]
        with self.assertRaisesRegex(ValueError, "do not exactly match reviewer comments"):
            self.validate_certificate(certificate, [reported, omitted])

    def test_shallow_step5_evidence_is_rejected(self) -> None:
        certificate = base_certificate(self.files, self.ledger, self.notes)
        certificate["step5_docs"] = {"outcome": "x", "surfaces": ["x"]}
        with self.assertRaisesRegex(ValueError, "step5_docs"):
            self.validate_certificate(certificate, [])

    def test_artifact_hash_mismatch_is_rejected(self) -> None:
        certificate = base_certificate(self.files, self.ledger, self.notes)
        certificate["artifact_sha256"]["ledger"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "ledger artifact SHA-256"):
            self.validate_certificate(certificate, [])

    def test_stale_head_is_rejected(self) -> None:
        certificate = base_certificate(self.files, self.ledger, self.notes)
        certificate["head_sha_start"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "start SHA"):
            self.validate_certificate(certificate, [])


if __name__ == "__main__":
    unittest.main()
