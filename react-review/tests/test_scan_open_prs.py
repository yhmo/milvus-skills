#!/usr/bin/env python3
"""Fake-gh integration tests for react-review PR discovery."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER = REPO_ROOT / "react-review" / "scripts" / "scan_open_prs.sh"


FAKE_GH = r'''#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

args = sys.argv[1:]
mode = os.environ.get("FAKE_MEMBERSHIP_MODE", "external")
if args[:2] == ["auth", "status"]:
    raise SystemExit(0)
if args[:1] != ["api"]:
    raise SystemExit(64)
endpoint = next((argument for argument in args if argument.startswith("/")), "")
if args[1:2] == ["--paginate"] and endpoint.startswith("/orgs/milvus-io/repos"):
    print("test/repo")
    raise SystemExit(0)
if args[1:2] == ["--paginate"] and endpoint.startswith("/orgs/zilliztech/repos"):
    raise SystemExit(0)
if endpoint.startswith("/repos/test/repo/pulls"):
    association = "MEMBER" if mode == "association-member" else "NONE"
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(json.dumps([{
        "html_url": "https://github.com/test/repo/pull/1",
        "user": {"login": "externaluser", "type": "User"},
        "author_association": association,
        "number": 1,
        "created_at": created,
        "base": {"repo": {"full_name": "test/repo"}},
        "state": "open",
        "title": "External PR",
    }]))
    raise SystemExit(0)
if args[1:2] == ["--include"] and endpoint == "/orgs/milvus-io/members/externaluser":
    if mode in {"external", "association-member"}:
        print("HTTP/1.1 404 Not Found\n", end="")
        raise SystemExit(1)
    if mode == "member":
        print("HTTP/1.1 204 No Content\n", end="")
        raise SystemExit(0)
    if mode == "recover":
        counter = Path(os.environ["FAKE_MEMBERSHIP_COUNTER"])
        calls = int(counter.read_text() or "0") + 1
        counter.write_text(str(calls))
        if calls == 1:
            print("HTTP/1.1 429 Too Many Requests\n", end="")
            raise SystemExit(1)
        print("HTTP/1.1 204 No Content\n", end="")
        raise SystemExit(0)
    if mode == "malformed":
        print("no http status")
        raise SystemExit(0)
    print("HTTP/1.1 403 Forbidden\n", end="")
    raise SystemExit(1)
if args[1:2] == ["--include"] and endpoint == "/orgs/zilliztech/members/externaluser":
    print("HTTP/1.1 404 Not Found\n", end="")
    raise SystemExit(1)
raise SystemExit(64)
'''


class ScanOpenPrsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake_gh = self.bin / "gh"
        fake_gh.write_text(FAKE_GH, encoding="utf-8")
        fake_gh.chmod(fake_gh.stat().st_mode | stat.S_IXUSR)
        self.counter = self.root / "counter"
        self.counter.write_text("0", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_scanner(self, mode: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update(
            {
                "PATH": f"{self.bin}:{environment.get('PATH', '')}",
                "FAKE_MEMBERSHIP_MODE": mode,
                "FAKE_MEMBERSHIP_COUNTER": str(self.counter),
            }
        )
        output = self.root / f"{mode}.tsv"
        return subprocess.run(
            [str(SCANNER), "--lookback", "1 day", "--output", str(output)],
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_association_member_is_internal(self) -> None:
        result = self.run_scanner("association-member")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("pull/1", (self.root / "association-member.tsv").read_text())
        self.assertIn("internal-author skipped", result.stderr)

    def test_explicit_204_is_internal(self) -> None:
        result = self.run_scanner("member")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("pull/1", (self.root / "member.tsv").read_text())

    def test_explicit_404_is_external(self) -> None:
        result = self.run_scanner("external")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pull/1", (self.root / "external.tsv").read_text())

    def test_429_is_retried(self) -> None:
        result = self.run_scanner("recover")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.counter.read_text(encoding="utf-8"), "2")
        self.assertIn("returned HTTP 429", result.stderr)

    def test_403_fails_closed(self) -> None:
        result = self.run_scanner("forbidden")
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot continue safely", result.stderr)

    def test_malformed_status_fails_closed(self) -> None:
        result = self.run_scanner("malformed")
        self.assertEqual(result.returncode, 2)
        self.assertIn("returned HTTP unknown", result.stderr)


if __name__ == "__main__":
    unittest.main()
