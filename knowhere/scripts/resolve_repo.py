#!/usr/bin/env python3
"""Resolve, discover, or clone the repository used by the knowhere skill.

With --branch <ref>, the returned checkout is GUARANTEED to be on <ref>:
a fresh clone checks the ref out directly; an existing checkout is fetched
(depth 1) and switched automatically. Refuses to switch when the worktree
is dirty (commit, stash, or clean first).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


# Marker identifies a genuine zilliztech/knowhere checkout (not a same-named unrelated dir).
REPOSITORY = {
    "repository": "zilliztech/knowhere",
    "marker": "include/knowhere/binaryset.h",
    "remote": "source",  # remote name assigned to the automatic clone
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


def inspect_repository(path: Path, config: dict[str, str]) -> dict[str, Any]:
    repo_label = config["repository"]
    root = git_root(path)
    if root is None or not marker_matches(root, config):
        raise SystemExit(f"error: path is not the {repo_label} repository: {path}")

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
        if any(normalize_remote(url) == repo_label.lower() for url in urls):
            upstream_remote = remote
            break
    return {
        "repository": repo_label,
        "path": str(root.resolve()),
        "branch": branch_result.stdout.strip() or None,
        "commit": commit_result.stdout.strip(),
        "upstream_remote": upstream_remote,
        "upstream_url": f"https://github.com/{repo_label}.git",
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
        Path.cwd(),
        temp_root / "milvus-skills" / repository_name,
        temp_root / repository_name,
    ]
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace:
        candidates.append(Path(workspace) / repository_name)
        candidates.append(Path(workspace))
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in unique:
            unique.append(resolved)
    return unique


def clone_repository(
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
            f"error: temporary path already exists but is not a valid {config['repository']} repository: {target}"
        )
    parent.mkdir(parents=True, exist_ok=True)

    url = f"https://github.com/{config['repository']}.git"
    command = ["git", "clone", "-o", config["remote"]]
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

    result = inspect_repository(target, config)
    result["cloned"] = True
    result["shallow"] = not full
    return result


def local_ref_exists(root: Path, kind: str, ref: str) -> bool:
    result = run_git(
        root, "show-ref", "--verify", "--quiet", f"refs/{kind}/{ref}", check=False
    )
    return result.returncode == 0


def head_at(root: Path, rev: str) -> bool:
    head = run_git(root, "rev-parse", "HEAD", check=False).stdout.strip()
    target = run_git(root, "rev-parse", rev, check=False).stdout.strip()
    return bool(head) and bool(target) and head == target


def classify_remote_ref(root: Path, upstream: str, ref: str) -> str | None:
    """Ask the remote what <ref> is. Prefers tag when both exist."""
    result = run_git(root, "ls-remote", "--refs", upstream, ref, check=False)
    if result.returncode != 0:
        return None
    kinds = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2:
            if fields[1] == f"refs/tags/{ref}":
                kinds.append("tag")
            elif fields[1] == f"refs/heads/{ref}":
                kinds.append("branch")
    if "tag" in kinds:
        return "tag"
    if "branch" in kinds:
        return "branch"
    return None


def ensure_ref(
    root: Path,
    ref: str,
    config: dict[str, str],
    upstream_remote: str | None,
    fresh_clone: bool,
) -> dict[str, Any]:
    """Guarantee the checkout is on <ref>; returns ref metadata for the report."""
    upstream = upstream_remote or config["remote"]
    info: dict[str, Any] = {"ref_requested": ref, "upstream_remote": upstream}

    # 1. Already satisfied?
    if local_ref_exists(root, "tags", ref) and head_at(root, f"refs/tags/{ref}"):
        info.update(ref_type="tag", ref_action="already_on_ref")
        return info
    current_branch = run_git(root, "branch", "--show-current", check=False).stdout.strip()
    if current_branch == ref and local_ref_exists(root, "heads", ref):
        info.update(ref_type="branch", ref_action="already_on_ref")
        return info

    # 2. Never switch away with uncommitted changes.
    status = run_git(root, "status", "--short", check=False)
    if status.returncode == 0 and status.stdout.strip():
        raise SystemExit(
            "error: worktree is dirty; commit, stash, or clean it before switching refs "
            f"({root})"
        )

    # 3. Ask the remote what the ref is, then fetch it shallowly.
    kind = classify_remote_ref(root, upstream, ref)
    if kind == "tag":
        fetched = run_git(
            root,
            "fetch", "--force", "--depth", "1", upstream,
            f"refs/tags/{ref}:refs/tags/{ref}",
            check=False,
        )
        if fetched.returncode:
            detail = fetched.stderr.strip() or fetched.stdout.strip()
            raise SystemExit(f"error: failed to fetch tag {ref}: {detail}")
        checkout = run_git(root, "checkout", "--detach", ref, check=False)
        if checkout.returncode:
            detail = checkout.stderr.strip() or checkout.stdout.strip()
            raise SystemExit(f"error: failed to check out tag {ref}: {detail}")
        info.update(ref_type="tag", ref_action="switched_detached")
        return info
    if kind == "branch":
        fetched = run_git(
            root,
            "fetch", "--depth", "1", upstream,
            f"refs/heads/{ref}:refs/remotes/{upstream}/{ref}",
            check=False,
        )
        if fetched.returncode:
            detail = fetched.stderr.strip() or fetched.stdout.strip()
            raise SystemExit(f"error: failed to fetch branch {ref}: {detail}")
        checkout = run_git(
            root, "checkout", "-B", ref, f"refs/remotes/{upstream}/{ref}", check=False
        )
        if checkout.returncode:
            detail = checkout.stderr.strip() or checkout.stdout.strip()
            raise SystemExit(f"error: failed to check out branch {ref}: {detail}")
        run_git(
            root,
            "branch", "--set-upstream-to", f"refs/remotes/{upstream}/{ref}", ref,
            check=False,
        )
        info.update(ref_type="branch", ref_action="switched_branch")
        return info

    # 4. Offline (ls-remote failed): fall back to whatever exists locally.
    if not fresh_clone:
        if local_ref_exists(root, "tags", ref):
            checkout = run_git(root, "checkout", "--detach", ref, check=False)
            if checkout.returncode == 0:
                info.update(ref_type="tag", ref_action="switched_detached_offline")
                return info
        remote_ref = f"refs/remotes/{upstream}/{ref}"
        if run_git(root, "show-ref", "--verify", "--quiet", remote_ref, check=False).returncode == 0:
            checkout = run_git(root, "checkout", "-B", ref, remote_ref, check=False)
            if checkout.returncode == 0:
                info.update(ref_type="branch", ref_action="switched_branch_offline")
                return info
    raise SystemExit(
        f"error: cannot resolve ref {ref!r} on remote {upstream!r} "
        "(offline and no local ref available)"
    )


def resolve(
    explicit_repo: Path | None,
    branch: str | None,
    full: bool,
    no_clone: bool,
) -> dict[str, Any]:
    config = REPOSITORY
    result: dict[str, Any]
    fresh_clone = False

    if explicit_repo is not None:
        result = inspect_repository(explicit_repo, config)
    else:
        current_root = git_root(Path.cwd())
        matched: Path | None = None
        if current_root is not None and marker_matches(current_root, config):
            matched = current_root
        else:
            for candidate in candidate_paths(config):
                if matching_repository(candidate, config):
                    matched = candidate
                    break
        if matched is not None:
            result = inspect_repository(matched, config)
        else:
            if no_clone:
                raise SystemExit(
                    f"error: no local {config['repository']} repository found and --no-clone was set"
                )
            result = clone_repository(config, branch, full)
            fresh_clone = True

    if branch:
        ref_info = ensure_ref(
            Path(result["path"]),
            branch,
            config,
            result.get("upstream_remote"),
            fresh_clone,
        )
        result.update(ref_info)
        refreshed = inspect_repository(Path(result["path"]), config)
        result["branch"] = refreshed["branch"]
        result["commit"] = refreshed["commit"]
        if result.get("cloned"):
            result["cloned"] = True

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, help="explicit repository path")
    parser.add_argument(
        "--branch",
        help="branch or tag the returned checkout is guaranteed to be on; "
        "existing checkouts are fetched (depth 1) and switched automatically",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="clone complete history; default is a fast depth-1 clone",
    )
    parser.add_argument("--no-clone", action="store_true", help="fail instead of cloning")
    args = parser.parse_args()

    result = resolve(
        explicit_repo=args.repo,
        branch=args.branch,
        full=args.full,
        no_clone=args.no_clone,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
