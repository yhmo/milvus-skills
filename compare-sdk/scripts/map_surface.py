#!/usr/bin/env python3
"""Generate deterministic cross-SDK facade-method mapping candidates."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


SUPPORTED_SDKS = {"pymilvus", "java", "cpp", "csharp", "rust"}


# These interfaces do not follow ordinary snake/camel/Pascal naming or have a
# Java V2 wrapper that covers the same capability. Ordinary names are mapped by
# naming convention; this table is not a parity verdict.
MANUAL_ALIAS_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "canonical": "describe_replicas",
        "names": (
            "describe_replica",
            "describeReplicas",
            "DescribeReplicas",
            "DescribeReplicasAsync",
            "describe_replicas",
        ),
    },
    {
        "canonical": "list_persistent_segments",
        "names": (
            "list_persistent_segments",
            "list_segments",
            "getPersistentSegmentInfo",
            "ListPersistentSegments",
            "GetPersistentSegmentInfoAsync",
        ),
    },
    {
        "canonical": "list_query_segments",
        "names": (
            "list_loaded_segments",
            "getQuerySegmentInfo",
            "ListQuerySegments",
            "GetQuerySegmentInfoAsync",
            "list_query_segments",
        ),
    },
    {
        "canonical": "use_database",
        "names": (
            "using_database",
            "use_database",
            "useDatabase",
            "UseDatabase",
            "UseDatabaseAsync",
        ),
    },
    {
        "canonical": "get_server_version",
        "names": (
            "get_server_version",
            "getServerVersion",
            "getServerVersionV2",
            "GetServerVersion",
            "GetServerVersionV2",
            "GetServerVersionAsync",
            "server_version",
        ),
    },
    {
        "canonical": "sdk_version",
        "names": (
            "getSDKVersion",
            "GetSDKVersion",
            "sdk_version",
        ),
    },
    {
        "canonical": "get_partition_stats",
        "names": (
            "get_partition_stats",
            "getPartitionStats",
            "GetPartitionStatistics",
            "GetPartitionStatsAsync",
            "get_partition_statistics",
        ),
    },
    {
        "canonical": "close",
        "names": (
            "close",
            "Disconnect",
            "Dispose",
        ),
    },
    {
        "canonical": "get_load_state",
        "names": (
            "get_load_state",
            "getLoadState",
            "getLoadStateV2",
            "GetLoadState",
            "GetLoadStateAsync",
        ),
    },
    {
        "canonical": "list_collections",
        "names": (
            "list_collections",
            "listCollections",
            "listCollectionsV2",
            "ListCollections",
            "ListCollectionsAsync",
        ),
    },
    {
        "canonical": "search_iterator",
        "names": (
            "search_iterator",
            "searchIterator",
            "searchIteratorV2",
            "SearchIterator",
            "SearchIteratorAsync",
        ),
    },
)


def load_surface(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"error: cannot read surface {path}: {error}") from error
    if not isinstance(value, dict) or not isinstance(value.get("methods"), list):
        raise SystemExit(f"error: surface is not an extractor output: {path}")
    if value.get("sdk") not in SUPPORTED_SDKS:
        raise SystemExit(f"error: surface has an unsupported SDK: {path}")
    digest = value.get("surface_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise SystemExit(f"error: surface has an invalid SHA-256 digest: {path}")
    method_ids = set()
    for method in value["methods"]:
        if not isinstance(method, dict):
            raise SystemExit(f"error: surface method is not an object: {path}")
        method_id = method.get("method_id")
        name = method.get("name")
        if not isinstance(method_id, str) or not method_id or method_id in method_ids:
            raise SystemExit(f"error: surface has a missing or duplicate method ID: {path}")
        if not isinstance(name, str) or not name:
            raise SystemExit(f"error: surface method has no name: {path}")
        method_ids.add(method_id)
    return value


def normalize_name(name: str) -> str:
    # C# methods consistently carry Async; do not erase semantic V2 suffixes
    # such as grantPrivilegeV2 because they can denote a distinct interface.
    if name.lower().endswith("async"):
        name = name[: -len("async")].rstrip("_")
    return "".join(character for character in name.lower() if character.isalnum())


def alias_keys(method: dict[str, Any]) -> set[str]:
    name = str(method.get("name", ""))
    keys = {normalize_name(name)}
    for group in MANUAL_ALIAS_GROUPS:
        if name in group["names"]:
            keys.add(f"manual:{group['canonical']}")
            keys.update(normalize_name(alias) for alias in group["names"])
    return keys


def build_mapping(baseline: dict[str, Any], audited: dict[str, Any]) -> dict[str, Any]:
    baseline_sdk = str(baseline.get("sdk", ""))
    audited_sdk = str(audited.get("sdk", ""))
    baseline_methods = list(baseline.get("methods", []))
    audited_methods = list(audited.get("methods", []))

    audited_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    audited_keys: dict[str, set[str]] = {}
    for method in audited_methods:
        keys = alias_keys(method)
        audited_keys[str(method.get("method_id", ""))] = keys
        for key in keys:
            audited_by_key[key].append(method)

    rows: list[dict[str, Any]] = []
    used_audited_keys: set[str] = set()
    for baseline_method in baseline_methods:
        keys = alias_keys(baseline_method)
        used_audited_keys.update(keys)
        candidates_by_id: dict[str, dict[str, Any]] = {}
        for key in sorted(keys):
            for candidate in audited_by_key.get(key, []):
                candidates_by_id.setdefault(
                    str(candidate.get("method_id", "")),
                    {
                        "method_id": candidate.get("method_id"),
                        "name": candidate.get("name"),
                        "file": candidate.get("file"),
                        "line": candidate.get("line"),
                        "deprecated": candidate.get("deprecated", False),
                    },
                )
        candidates = sorted(
            candidates_by_id.values(),
            key=lambda item: (
                str(item["name"]),
                str(item["file"]),
                int(item["line"] or 0),
            ),
        )
        rows.append(
            {
                "baseline_method_id": baseline_method.get("method_id"),
                "baseline_name": baseline_method.get("name"),
                "candidate_count": len(candidates),
                "candidates": candidates,
            }
        )

    unmatched = [
        {
            "method_id": method.get("method_id"),
            "name": method.get("name"),
            "file": method.get("file"),
            "line": method.get("line"),
            "deprecated": method.get("deprecated", False),
        }
        for method in audited_methods
        if not (audited_keys.get(str(method.get("method_id", "")), set()) & used_audited_keys)
    ]
    return {
        "version": 1,
        "baseline": baseline_sdk,
        "audited": audited_sdk,
        "baseline_surface_sha256": baseline.get("surface_sha256"),
        "audited_surface_sha256": audited.get("surface_sha256"),
        "rows": rows,
        "unmatched_audited": unmatched,
        "statistics": {
            "baseline_methods": len(baseline_methods),
            "baseline_with_candidates": sum(row["candidate_count"] > 0 for row in rows),
            "audited_methods": len(audited_methods),
            "unmatched_audited": len(unmatched),
        },
    }


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-surface", type=Path, required=True)
    parser.add_argument("--audited-surface", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    mapping = build_mapping(load_surface(args.baseline_surface), load_surface(args.audited_surface))
    write_json_atomic(args.output, mapping)
    print(json.dumps(mapping["statistics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
