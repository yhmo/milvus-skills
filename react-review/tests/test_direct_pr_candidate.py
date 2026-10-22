#!/usr/bin/env python3
"""Fake-gh tests for direct PR target resolution."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "react-review" / "scripts" / "direct_pr_candidate.py"


FAKE_GH = r'''#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
mode = os.environ.get("FAKE_DIRECT_MODE", "external")
endpoint = args[-1] if args else ""
if endpoint == "repos/milvus-io/repo/pulls/1":
    association = "MEMBER" if mode == "association" else "NONE"
    print(json.dumps({
        "html_url": "https://github.com/milvus-io/repo/pull/1",
        "state": "open",
        "user": {"login": "author", "type": "User"},
        "author_association": association,
        "created_at": "2026-10-22T00:00:00Z",
        "base": {"repo": {"full_name": "milvus-io/repo"}},
        "number": 1,
        "title": "PR",
    }))
    raise SystemExit(0)
if args[1:3] == ["--include", "/orgs/milvus-io/members/author"]:
    if mode == "external":
        print("HTTP/1.1 404 Not Found\n", end="")
        raise SystemExit(1)
    if mode == "member":
        print("HTTP/1.1 204 No Content\n", end="")
        raise SystemExit(0)
    print("HTTP/1.1 403 Forbidden\n", end="")
    raise SystemExit(1)
if args[1:3] == ["--include", "/orgs/zilliztech/members/author"]:
    if mode == "external":
        print("HTTP/1.1 404 Not Found\n", end="")
        raise SystemExit(1)
    print("HTTP/1.1 403 Forbidden\n", end="")
    raise SystemExit(1)
raise SystemExit(64)
'''


class DirectCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "gh"
        fake.write_text(FAKE_GH, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_resolver(self, mode: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update(
            {
                "PATH": f"{self.bin}:{environment.get('PATH', '')}",
                "FAKE_DIRECT_MODE": mode,
            }
        )
        return subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--url",
                "https://github.com/milvus-io/repo/pull/1",
                "--output",
                str(self.root / f"{mode}.tsv"),
            ],
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_owner_or_member_association_is_internal(self) -> None:
        result = self.run_resolver("association")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"internal": "1"', result.stdout)

    def test_explicit_404_is_external(self) -> None:
        result = self.run_resolver("external")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"internal": "0"', result.stdout)

    def test_permission_failure_is_not_external(self) -> None:
        result = self.run_resolver("forbidden")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("indeterminate", result.stderr)


if __name__ == "__main__":
    unittest.main()
