#!/usr/bin/env python3
"""Resolve and hash the proto anchor used by a pinned Milvus SDK."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import tarfile
from pathlib import Path
from typing import Any


SUPPORTED_SDKS = ("pymilvus", "java", "cpp", "csharp", "rust")
SUBMODULE_PATHS = {
    "java": "sdk-core/src/main/milvus-proto",
    "rust": "milvus-proto",
    "csharp": "Protos",
}
PROTO_FILES = (
    "proto/common.proto",
    "proto/feder.proto",
    "proto/msg.proto",
    "proto/milvus.proto",
    "proto/rg.proto",
    "proto/schema.proto",
)


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def parse_gitlink(ls_tree_line: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"160000 commit ([0-9a-f]{40})\s+(.+)", ls_tree_line.strip())
    return (match.group(2), match.group(1)) if match else None


def parse_cmake_proto_commit(source: str) -> str:
    match = re.search(r"set\s*\(\s*PROTO_COMMIT\s+([0-9a-f]{40})\s*\)", source)
    if not match:
        raise SystemExit("error: PROTO_COMMIT not found in cmake/MilvusProtoGen.cmake")
    return match.group(1)


def blob_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def proto_files_from_github_archive(commit: str) -> list[dict[str, Any]]:
    completed = subprocess.run(
        ["gh", "api", f"repos/milvus-io/milvus-proto/tarball/{commit}"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    files = []
    with tempfile.TemporaryDirectory(prefix="compare-sdk-proto.") as temporary_dir:
        archive = Path(temporary_dir) / "proto.tar.gz"
        archive.write_bytes(completed.stdout)
        with tarfile.open(archive, "r:gz") as tar:
            members = {member.name.split("/", 1)[-1]: member for member in tar.getmembers()}
            for path in PROTO_FILES:
                member = members.get(path)
                if member is None or not member.isfile():
                    continue
                handle = tar.extractfile(member)
                if handle is None:
                    continue
                content = handle.read().decode("utf-8")
                files.append({"path": path, "sha256": blob_sha256(content)})
    if not any(file["path"] == "proto/milvus.proto" for file in files):
        raise SystemExit(f"error: GitHub archive for {commit} has no proto/milvus.proto")
    return files


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def resolve(sdk: str, repo: Path, ref: str) -> dict[str, Any]:
    parent_commit = run_git(repo, "rev-parse", ref).stdout.strip()
    base = {
        "version": 1,
        "sdk": sdk,
        "repo": str(repo),
        "repo_ref": ref,
        "repo_commit": parent_commit,
        "anchor_kind": "",
        "anchor_path": "",
        "proto_commit": None,
        "proto_files": [],
    }

    if sdk == "pymilvus":
        listing = run_git(repo, "ls-tree", "-r", "--name-only", ref, "pymilvus/grpc_gen").stdout.splitlines()
        generated = sorted(path for path in listing if re.search(r"(?:_pb2|_pb2_grpc)\.py$", path))
        files = []
        for path in generated:
            result = run_git(repo, "show", f"{ref}:{path}")
            files.append({"path": path, "sha256": blob_sha256(result.stdout)})
        base.update(
            {
                "anchor_kind": "generated-python",
                "anchor_path": "pymilvus/grpc_gen",
                "proto_commit": None,
                "proto_files": files,
                "note": "PyMilvus does not vendor .proto files; generated descriptors are the available anchor.",
            }
        )
        return base

    if sdk == "cpp":
        cmake = run_git(repo, "show", f"{ref}:cmake/MilvusProtoGen.cmake").stdout
        proto_commit = parse_cmake_proto_commit(cmake)
        base.update(
            {
                "anchor_kind": "cmake-fetchcontent",
                "anchor_path": "cmake/MilvusProtoGen.cmake",
                "proto_repo": "https://github.com/milvus-io/milvus-proto.git",
                "proto_commit": proto_commit,
            }
        )
    else:
        submodule_path = SUBMODULE_PATHS[sdk]
        result = run_git(repo, "ls-tree", ref, submodule_path)
        gitlink = parse_gitlink(result.stdout)
        if gitlink is None:
            raise SystemExit(f"error: unable to read gitlink at {sdk}:{submodule_path}")
        _, proto_commit = gitlink
        submodule_repo = repo / submodule_path
        local_object_available = (submodule_repo / ".git").exists()
        if local_object_available:
            object_result = run_git(
                submodule_repo,
                "cat-file",
                "-e",
                f"{proto_commit}^{{commit}}",
                check=False,
            )
            local_object_available = object_result.returncode == 0
        base.update(
            {
                "anchor_kind": "git-submodule",
                "anchor_path": submodule_path,
                "proto_repo": str(submodule_repo)
                if local_object_available
                else "https://github.com/milvus-io/milvus-proto.git",
                "proto_artifact": "local" if local_object_available else "github-archive",
                "proto_commit": proto_commit,
            }
        )

    proto_commit = base["proto_commit"]
    if base.get("proto_artifact") == "github-archive" or base["anchor_kind"] == "cmake-fetchcontent":
        files = proto_files_from_github_archive(proto_commit)
    else:
        proto_repo = Path(base["proto_repo"])
        files = []
        for path in PROTO_FILES:
            result = run_git(proto_repo, "show", f"{proto_commit}:{path}", check=False)
            if result.returncode != 0:
                continue
            files.append({"path": path, "sha256": blob_sha256(result.stdout)})
        if not any(file["path"] == "proto/milvus.proto" for file in files):
            files = proto_files_from_github_archive(proto_commit)
            base["proto_artifact"] = "github-archive"
            base["proto_repo"] = "https://github.com/milvus-io/milvus-proto.git"
    base["proto_files"] = files
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", required=True, choices=SUPPORTED_SDKS)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = resolve(args.sdk, args.repo.resolve(), args.ref)
    write_json_atomic(args.output, result)
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("sdk", "repo_ref", "repo_commit", "anchor_kind", "proto_commit")
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
