#!/usr/bin/env python3
"""Integration-style tests using a fake gh CLI for PR discovery."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER = REPO_ROOT / "scan-review" / "scripts" / "scan_recent_prs.sh"


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
    print(f"unexpected gh arguments: {args}", file=sys.stderr)
    raise SystemExit(64)

endpoint = next((argument for argument in args if argument.startswith("/")), "")
if args[1:2] == ["--paginate"] and endpoint.startswith("/orgs/milvus-io/repos"):
    print("test/repo")
    raise SystemExit(0)
if args[1:2] == ["--paginate"] and endpoint.startswith("/orgs/zilliztech/repos"):
    raise SystemExit(0)

if endpoint.startswith("/repos/test/repo/pulls"):
    association = "MEMBER" if mode == "association-member" else "NONE"
    login = "" if mode == "empty-author" else "externaluser"
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(json.dumps([
        {
            "html_url": "https://github.com/test/repo/pull/1",
            "user": {"login": login, "type": "User"},
            "author_association": association,
            "created_at": created_at,
            "base": {"repo": {"full_name": "test/repo"}},
            "state": "open",
            "title": "External PR",
        }
    ]))
    raise SystemExit(0)

if args[1:2] == ["--include"] and endpoint == "/orgs/milvus-io/members/externaluser":
    if mode in {"external", "association-member"}:
        print("HTTP/1.1 404 Not Found\n", end="")
        raise SystemExit(1)
    if mode == "member":
        print("HTTP/1.1 204 No Content\n", end="")
        raise SystemExit(0)
    if mode == "recover":
        counter_path = os.environ["FAKE_MEMBERSHIP_COUNTER"]
        calls = int(Path(counter_path).read_text() or "0")
        calls += 1
        Path(counter_path).write_text(str(calls))
        if calls == 1:
            print("HTTP/1.1 429 Too Many Requests\n", end="")
            raise SystemExit(1)
        print("HTTP/1.1 204 No Content\n", end="")
        raise SystemExit(0)
    if mode == "malformed":
        print('{"message":"response without an HTTP status line"}')
        raise SystemExit(0)
    print("HTTP/1.1 403 Forbidden\n", end="")
    raise SystemExit(1)

if args[1:2] == ["--include"] and endpoint == "/orgs/zilliztech/members/externaluser":
    print("HTTP/1.1 404 Not Found\n", end="")
    raise SystemExit(1)

print(f"unexpected endpoint: {endpoint}", file=sys.stderr)
raise SystemExit(64)
'''


class ScanRecentPrsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        fake_gh = self.bin_dir / "gh"
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
                "PATH": f"{self.bin_dir}:{environment.get('PATH', '')}",
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

    def test_author_association_member_is_skipped(self) -> None:
        result = self.run_scanner("association-member")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = (self.root / "association-member.tsv").read_text(encoding="utf-8")
        self.assertNotIn("pull/1", output)
        self.assertIn("skipping organization member externaluser", result.stderr)

    def test_explicit_204_membership_is_skipped(self) -> None:
        result = self.run_scanner("member")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = (self.root / "member.tsv").read_text(encoding="utf-8")
        self.assertNotIn("pull/1", output)
        self.assertIn("skipping organization member externaluser", result.stderr)

    def test_explicit_404_is_external(self) -> None:
        result = self.run_scanner("external")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = (self.root / "external.tsv").read_text(encoding="utf-8")
        self.assertIn("https://github.com/test/repo/pull/1", output)

    def test_transient_429_is_retried(self) -> None:
        result = self.run_scanner("recover")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.counter.read_text(encoding="utf-8"), "2")
        self.assertIn("returned HTTP 429", result.stderr)
        self.assertIn("skipping organization member externaluser", result.stderr)

    def test_persistent_403_fails_closed(self) -> None:
        result = self.run_scanner("forbidden")
        self.assertEqual(result.returncode, 2)
        self.assertIn("returned HTTP 403", result.stderr)
        self.assertIn("cannot continue safely", result.stderr)
        self.assertFalse((self.root / "forbidden.tsv").exists())

    def test_malformed_membership_response_fails_closed(self) -> None:
        result = self.run_scanner("malformed")
        self.assertEqual(result.returncode, 2)
        self.assertIn("returned HTTP unknown", result.stderr)
        self.assertIn("cannot continue safely", result.stderr)

    def test_empty_author_fails_closed(self) -> None:
        result = self.run_scanner("empty-author")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("has no author login", result.stderr)


if __name__ == "__main__":
    unittest.main()
