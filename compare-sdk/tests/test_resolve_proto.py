#!/usr/bin/env python3
"""Unit tests for compare-sdk proto anchor parsing."""

from __future__ import annotations

import unittest
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from helpers import load_script


resolver = load_script("resolve_proto")


class ResolveProtoTests(unittest.TestCase):
    def test_parse_gitlink(self) -> None:
        line = "160000 commit ae7fea6ab2f4e958f2feef0f0edb9a0d23fa7e0c\tProtos\n"
        self.assertEqual(
            resolver.parse_gitlink(line),
            ("Protos", "ae7fea6ab2f4e958f2feef0f0edb9a0d23fa7e0c"),
        )
        self.assertIsNone(resolver.parse_gitlink("100644 blob abc\tProtos\n"))

    def test_parse_cmake_proto_commit(self) -> None:
        source = "include_guard(GLOBAL)\nset(PROTO_COMMIT ae7fea6ab2f4e958f2feef0f0edb9a0d23fa7e0c)\n"
        self.assertEqual(
            resolver.parse_cmake_proto_commit(source),
            "ae7fea6ab2f4e958f2feef0f0edb9a0d23fa7e0c",
        )
        with self.assertRaises(SystemExit):
            resolver.parse_cmake_proto_commit("set(OTHER 1)")

    def test_missing_submodule_checkout_falls_back_to_github(self) -> None:
        with TemporaryDirectory() as temporary:
            repo = Path(temporary)

            def fake_run_git(repository: Path, *args: str, check: bool = True):
                if args == ("rev-parse", "ref"):
                    return subprocess.CompletedProcess(args, 0, "a" * 40, "")
                if args == ("ls-tree", "ref", "sdk-core/src/main/milvus-proto"):
                    return subprocess.CompletedProcess(
                        args,
                        0,
                        "160000 commit " + "b" * 40 + "\tsdk-core/src/main/milvus-proto\n",
                        "",
                    )
                raise AssertionError(f"unexpected git arguments: {args}")

            with (
                patch.object(resolver, "run_git", side_effect=fake_run_git),
                patch.object(
                    resolver,
                    "proto_files_from_github_archive",
                    return_value=[{"path": "proto/milvus.proto", "sha256": "c" * 64}],
                ) as archive,
            ):
                result = resolver.resolve("java", repo, "ref")

            self.assertEqual(result["proto_artifact"], "github-archive")
            self.assertEqual(result["proto_commit"], "b" * 40)
            archive.assert_called_once_with("b" * 40)


if __name__ == "__main__":
    unittest.main()
