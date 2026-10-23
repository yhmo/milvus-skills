#!/usr/bin/env python3
"""Tests for the shared Milvus SDK repository resolver."""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RESOLVER_PATH = REPOSITORY_ROOT / "pymilvus/scripts/resolve_repo.py"


def load_resolver():
    spec = importlib.util.spec_from_file_location("resolve_repo", RESOLVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load resolver: {RESOLVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResolveRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = load_resolver()

    def test_remote_normalization(self) -> None:
        cases = {
            "git@github.com:milvus-io/pymilvus.git": "milvus-io/pymilvus",
            "https://github.com/milvus-io/milvus-sdk-rust.git": "milvus-io/milvus-sdk-rust",
            "https://github.com/milvus-io/milvus": "milvus-io/milvus",
        }
        for remote, expected in cases.items():
            self.assertEqual(self.resolver.normalize_remote(remote), expected)

    def test_milvus_variants_use_distinct_markers(self) -> None:
        self.assertEqual(
            self.resolver.SDK_REPOSITORIES["milvus"]["marker"],
            "internal/distributed/proxy/httpserver/handler_v2.go",
        )
        self.assertEqual(
            self.resolver.SDK_REPOSITORIES["go"]["marker"],
            "client/go.mod",
        )

    def test_explicit_matching_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "pymilvus"
            root.mkdir()
            marker = root / self.resolver.SDK_REPOSITORIES["pymilvus"]["marker"]
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("{}", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(root), "-c", "init.defaultBranch=main", "init"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "-C", str(root), "commit", "--allow-empty", "-m", "init"],
                check=True,
                env=self.git_env(),
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "-C", str(root), "commit", "--allow-empty", "-m", "init"],
                check=True,
                env={
                    "GIT_AUTHOR_NAME": "test",
                    "GIT_AUTHOR_EMAIL": "test@example.com",
                    "GIT_COMMITTER_NAME": "test",
                    "GIT_COMMITTER_EMAIL": "test@example.com",
                    "PATH": "/usr/bin:/bin",
                },
                stdout=subprocess.DEVNULL,
            )
            result = self.resolver.resolve(
                sdk="pymilvus",
                explicit_repo=root,
                branch=None,
                full=False,
                no_clone=True,
            )
            self.assertEqual(Path(result["path"]), root.resolve())
            self.assertFalse(result["cloned"])

    def test_current_repository_takes_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "pymilvus"
            root.mkdir()
            marker = root / self.resolver.SDK_REPOSITORIES["pymilvus"]["marker"]
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("{}", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(root), "-c", "init.defaultBranch=main", "init"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "-C", str(root), "commit", "--allow-empty", "-m", "init"],
                check=True,
                env=self.git_env(),
                stdout=subprocess.DEVNULL,
            )
            with patch.object(Path, "cwd", lambda: root):
                result = self.resolver.resolve(
                    sdk="pymilvus",
                    explicit_repo=None,
                    branch=None,
                    full=False,
                    no_clone=True,
                )
            self.assertEqual(Path(result["path"]), root.resolve())

    @staticmethod
    def git_env() -> dict[str, str]:
        return {
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "PATH": "/usr/bin:/bin",
        }

    def test_resolver_copies_are_identical(self) -> None:
        expected = hashlib.sha256(RESOLVER_PATH.read_bytes()).hexdigest()
        paths = [
            REPOSITORY_ROOT / skill / "scripts/resolve_repo.py"
            for skill in (
                "compare-sdk",
                "milvus-restful",
                "milvus-sdk-cpp",
                "milvus-sdk-csharp",
                "milvus-sdk-go",
                "milvus-sdk-java",
                "milvus-sdk-node",
                "milvus-sdk-rust",
                "pymilvus",
            )
        ]
        for path in paths:
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected, str(path))

    def test_clone_is_used_when_no_candidate_exists(self) -> None:
        sentinel = {"path": "/tmp/sentinel", "cloned": True}
        with (
            patch.object(self.resolver, "candidate_paths", lambda config: []),
            patch.object(self.resolver, "clone_repository", return_value=sentinel) as clone,
        ):
            result = self.resolver.resolve(
                sdk="rust",
                explicit_repo=None,
                branch="main",
                full=False,
                no_clone=False,
            )
        self.assertEqual(result, sentinel)
        clone.assert_called_once_with(
            "rust",
            self.resolver.SDK_REPOSITORIES["rust"],
            "main",
            False,
        )

    def test_full_history_clone_is_opt_in(self) -> None:
        sentinel = {"path": "/tmp/sentinel", "cloned": True}
        with (
            patch.object(self.resolver, "candidate_paths", lambda config: []),
            patch.object(self.resolver, "clone_repository", return_value=sentinel) as clone,
        ):
            self.resolver.resolve(
                sdk="go",
                explicit_repo=None,
                branch="master",
                full=True,
                no_clone=False,
            )
        clone.assert_called_once_with(
            "go",
            self.resolver.SDK_REPOSITORIES["go"],
            "master",
            True,
        )


if __name__ == "__main__":
    unittest.main()
