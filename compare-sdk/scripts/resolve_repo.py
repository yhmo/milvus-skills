#!/usr/bin/env python3
"""Resolve, discover, or clone the repository used by a Milvus SDK skill."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


SDK_REPOSITORIES = {
    "milvus": {
        "repository": "milvus-io/milvus",
        "marker": "internal/distributed/proxy/httpserver/handler_v2.go",
    },
    "pymilvus": {
        "repository": "milvus-io/pymilvus",
        "marker": "pymilvus/__init__.py",
    },
    "java": {
        "repository": "milvus-io/milvus-sdk-java",
        "marker": "sdk-core/pom.xml",
    },
    "cpp": {
        "repository": "milvus-io/milvus-sdk-cpp",
        "marker": "src/include/milvus/MilvusClient.h",
    },
    "csharp": {
        "repository": "milvus-io/milvus-sdk-csharp",
        "marker": "Milvus.Client/MilvusClient.cs",
    },
    "node": {
        "repository": "milvus-io/milvus-sdk-node",
        "marker": "package.json",
        "marker_content": "@zilliz/milvus2-sdk-node",
    },
    "rust": {
        "repository": "milvus-io/milvus-sdk-rust",
        "marker": "Cargo.toml",
        "marker_content": "milvus-sdk-rust",
    },
    "go": {
        "repository": "milvus-io/milvus",
        "marker": "client/go.mod",
        "marker_content": "github.com/milvus-io/milvus/client/v3",
    },
}


def run_git(
    repo: Path | None, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    command = ["git"]
    if repo is not None:
        command.extend(["-C", str(repo)])
    command.extend(args)
    return subprocess.run(
        command,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_root(path: Path) -> Path | None:
    result = run_git(path, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        return None
    root = Path(result.stdout.strip())
    return root if root.is_dir() else None


def marker_matches(path: Path, config: dict[str, str]) -> bool:
    marker = path / config["marker"]
    if not marker.is_file():
        return False
    expected_content = config.get("marker_content")
    if expected_content is None:
        return True
    try:
        return expected_content in marker.read_text(encoding="utf-8")
    except OSError:
        return False


def matching_repository(path: Path, config: dict[str, str]) -> bool:
    root = git_root(path)
    return root is not None and marker_matches(root, config)


def normalize_remote(url: str) -> str:
    value = url.strip().lower()
    value = re.sub(r"^[a-z0-9+.-]+://", "", value)
    value = re.sub(r"^[^@/]+@", "", value)
    if value.startswith("github.com:"):
        value = value.replace(":", "/", 1)
    value = value.removesuffix(".git")
    value = value.removeprefix("github.com/")
    return value


def inspect_repository(path: Path, sdk: str, config: dict[str, str]) -> dict[str, Any]:
    root = git_root(path)
    if root is None or not marker_matches(root, config):
        raise SystemExit(f"error: path is not the {sdk} SDK repository: {path}")

    branch_result = run_git(root, "branch", "--show-current", check=False)
    commit_result = run_git(root, "rev-parse", "HEAD", check=False)
    remote_result = run_git(root, "remote", "-v", check=False)
    status_result = run_git(root, "status", "--short", check=False)
    if branch_result.returncode or commit_result.returncode or remote_result.returncode:
        detail = (
            remote_result.stderr.strip()
            or commit_result.stderr.strip()
            or branch_result.stderr.strip()
        )
        raise SystemExit(f"error: cannot inspect Git repository {root}: {detail}")

    remotes: dict[str, list[str]] = {}
    for line in remote_result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[-1] == "(fetch)":
            remotes.setdefault(fields[0], []).append(fields[1])

    upstream_remote = None
    for remote, urls in remotes.items():
        if any(normalize_remote(url) == config["repository"].lower() for url in urls):
            upstream_remote = remote
            break
    return {
        "sdk": sdk,
        "repository": config["repository"],
        "path": str(root.resolve()),
        "branch": branch_result.stdout.strip() or None,
        "commit": commit_result.stdout.strip(),
        "upstream_remote": upstream_remote,
        "upstream_url": f"https://github.com/{config['repository']}.git",
        "remotes": remotes,
        "dirty": bool(status_result.stdout.strip()),
        # Keep resolver output bounded; callers should run `git status --short`
        # themselves when they need the complete worktree state.
        "status_preview": status_result.stdout.strip().splitlines()[:20],
        "cloned": False,
    }


def candidate_paths(config: dict[str, str]) -> list[Path]:
    repository_name = config["repository"].split("/", 1)[1]
    temp_root = Path(os.environ.get("TMPDIR", "/tmp"))
    candidates = [
        Path.home() / "work/git-go" / repository_name,
        Path.home() / "work" / repository_name,
        Path.cwd() / repository_name,
        Path.cwd().parent / repository_name,
        temp_root / "milvus-skills" / repository_name,
        temp_root / repository_name,
    ]
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace:
        candidates.append(Path(workspace))
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in unique:
            unique.append(resolved)
    return unique


def clone_repository(
    sdk: str,
    config: dict[str, str],
    branch: str | None,
    full: bool,
) -> dict[str, Any]:
    repository_name = config["repository"].split("/", 1)[1]
    temp_root = Path(os.environ.get("TMPDIR", "/tmp")).resolve()
    parent = temp_root / "milvus-skills"
    target = parent / repository_name
    if target.exists():
        raise SystemExit(
            f"error: temporary path already exists but is not a valid {sdk} repository: {target}"
        )
    parent.mkdir(parents=True, exist_ok=True)

    url = f"https://github.com/{config['repository']}.git"
    command = ["git", "clone", "-o", "source"]
    if branch:
        command.extend(["--branch", branch])
    if not full:
        command.extend(["--depth", "1"])
    command.extend([url, str(target)])
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SystemExit(f"error: failed to clone {config['repository']}: {detail}")

    result = inspect_repository(target, sdk, config)
    result["cloned"] = True
    result["shallow"] = not full
    return result


def resolve(
    sdk: str,
    explicit_repo: Path | None,
    branch: str | None,
    full: bool,
    no_clone: bool,
) -> dict[str, Any]:
    config = SDK_REPOSITORIES[sdk]
    if explicit_repo is not None:
        result = inspect_repository(explicit_repo, sdk, config)
        if branch and result["branch"] and result["branch"] != branch:
            result["warning"] = (
                f"explicit repository is on {result['branch']}, not requested {branch}"
            )
        return result

    current_root = git_root(Path.cwd())
    if current_root is not None and marker_matches(current_root, config):
        result = inspect_repository(current_root, sdk, config)
        if branch and result["branch"] and result["branch"] != branch:
            result["warning"] = (
                f"current repository is on {result['branch']}, not requested {branch}"
            )
        return result

    for candidate in candidate_paths(config):
        if matching_repository(candidate, config):
            result = inspect_repository(candidate, sdk, config)
            if branch and result["branch"] and result["branch"] != branch:
                result["warning"] = (
                    f"candidate is on {result['branch']}, not requested {branch}"
                )
            return result

    if no_clone:
        raise SystemExit(f"error: no local {sdk} SDK repository found and --no-clone was set")
    return clone_repository(sdk, config, branch, full)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", required=True, choices=sorted(SDK_REPOSITORIES))
    parser.add_argument("--repo", type=Path, help="explicit repository path")
    parser.add_argument(
        "--branch",
        help="branch or tag to clone when a new repository is needed",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="clone complete history; default is a fast depth-1 clone",
    )
    parser.add_argument("--no-clone", action="store_true", help="fail instead of cloning")
    args = parser.parse_args()

    result = resolve(
        sdk=args.sdk,
        explicit_repo=args.repo,
        branch=args.branch,
        full=args.full,
        no_clone=args.no_clone,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
