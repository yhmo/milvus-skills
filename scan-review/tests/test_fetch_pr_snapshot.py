#!/usr/bin/env python3
"""Unit tests for complete PR snapshot pagination and consistency checks."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, parse_qs

from helpers import load_script


snapshot_module = load_script("fetch_pr_snapshot")


PR_URL = "https://github.com/test/repo/pull/1"


def make_files(
    count: int,
    *,
    additions: int = 2,
    deletions: int = 1,
    index_offset: int = 0,
) -> list[dict[str, Any]]:
    return [
        {
            "filename": f"file-{index + index_offset:03}.rs",
            "additions": additions,
            "deletions": deletions,
        }
        for index in range(count)
    ]


def make_metadata(files: list[dict[str, Any]], review_comments: int = 0) -> dict[str, Any]:
    return {
        "html_url": PR_URL,
        "head": {"sha": "a" * 40},
        "state": "open",
        "merged_at": None,
        "changed_files": len(files),
        "additions": sum(item["additions"] for item in files),
        "deletions": sum(item["deletions"] for item in files),
        "review_comments": review_comments,
    }


class SnapshotPaginationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.original_gh_api = snapshot_module.gh_api

    def tearDown(self) -> None:
        snapshot_module.gh_api = self.original_gh_api
        self.temp_dir.cleanup()

    def install_fake_api(
        self,
        files_pages: list[list[dict[str, Any]]],
        *,
        final_metadata_override: dict[str, Any] | None = None,
        metadata_override: dict[str, Any] | None = None,
    ) -> dict[str, int]:
        metadata = metadata_override or make_metadata(
            [item for page in files_pages for item in page]
        )
        calls = {"metadata": 0, "files": 0, "comments": 0}

        def fake_gh_api(endpoint: str, label: str) -> Any:
            path, _, query = endpoint.partition("?")
            params = parse_qs(query)
            page = int(params.get("page", ["1"])[0])
            if path == "/repos/test/repo/pulls/1":
                calls["metadata"] += 1
                if calls["metadata"] == 2 and final_metadata_override is not None:
                    return final_metadata_override
                return metadata
            if path == "/repos/test/repo/pulls/1/files":
                calls["files"] += 1
                return files_pages[page - 1]
            if path == "/repos/test/repo/pulls/1/comments":
                calls["comments"] += 1
                return []
            raise AssertionError(f"unexpected endpoint: {endpoint}")

        snapshot_module.gh_api = fake_gh_api
        return calls

    def test_canonical_pr_parts_rejects_non_canonical_url(self) -> None:
        for value in (
            "https://github.com/test/repo/pulls/1",
            "https://github.com/test/repo/pull/abc",
            "https://example.com/test/repo/pull/1",
        ):
            with self.assertRaises(snapshot_module.SnapshotError):
                snapshot_module.canonical_pr_parts(value)

    def test_exact_full_page_then_short_page_is_merged(self) -> None:
        first_page = make_files(snapshot_module.PER_PAGE)
        second_page = make_files(1, index_offset=snapshot_module.PER_PAGE)
        self.install_fake_api([first_page, second_page])
        output = self.root / "snapshot"
        manifest = snapshot_module.snapshot_pr(PR_URL, output, overwrite=False)

        files = json.loads((output / "files.json").read_text(encoding="utf-8"))
        self.assertEqual(len(files), snapshot_module.PER_PAGE + 1)
        self.assertEqual(manifest["files_count"], len(files))
        self.assertEqual(
            manifest["pagination"]["files"],
            {
                "strategy": "rest-page-loop-until-short-page",
                "per_page": snapshot_module.PER_PAGE,
                "pages": 2,
                "stop_reason": "short_page",
                "fetched_items": len(files),
            },
        )

    def test_metadata_file_count_mismatch_is_rejected(self) -> None:
        only_page = make_files(1)
        metadata = make_metadata(only_page)
        metadata["changed_files"] = 2
        self.install_fake_api([only_page], metadata_override=metadata)
        output = self.root / "snapshot"
        with self.assertRaises(snapshot_module.SnapshotError) as context:
            snapshot_module.snapshot_pr(PR_URL, output, overwrite=False)
        self.assertIn("files pagination merged 1 entries", str(context.exception))
        self.assertFalse((output / "snapshot.json").exists())

    def test_pr_change_during_fetch_is_rejected(self) -> None:
        files = make_files(1)
        final = make_metadata(files)
        final["changed_files"] = 100
        self.install_fake_api([files], final_metadata_override=final)
        output = self.root / "snapshot"
        with self.assertRaises(snapshot_module.SnapshotError) as context:
            snapshot_module.snapshot_pr(PR_URL, output, overwrite=False)
        self.assertIn("PR metadata changed while pages were fetched", str(context.exception))
        self.assertFalse((output / "snapshot.json").exists())

    def test_duplicate_file_path_is_rejected(self) -> None:
        files = [
            {"filename": "same.rs", "additions": 1, "deletions": 0},
            {"filename": "same.rs", "additions": 1, "deletions": 0},
        ]
        with self.assertRaises(snapshot_module.SnapshotError):
            snapshot_module.validate_files(files)


if __name__ == "__main__":
    unittest.main()
