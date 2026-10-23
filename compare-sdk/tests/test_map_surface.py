#!/usr/bin/env python3
"""Unit tests for deterministic cross-SDK mapping candidates."""

from __future__ import annotations

import unittest

from helpers import load_script


mapper = load_script("map_surface")


def surface(sdk: str, digest: str, names: list[str]) -> dict:
    return {
        "sdk": sdk,
        "surface_sha256": digest,
        "methods": [
            {
                "method_id": f"{name}#{index}",
                "name": name,
                "file": f"{sdk}/{name}",
                "line": index + 1,
                "deprecated": False,
            }
            for index, name in enumerate(names)
        ],
    }


class MapSurfaceTests(unittest.TestCase):
    def test_automatic_mapping_preserves_semantic_v2(self) -> None:
        result = mapper.build_mapping(
            surface("pymilvus", "python-digest", ["create_collection", "grant_privilege", "grant_privilege_v2"]),
            surface("java", "java-digest", ["createCollection", "grantPrivilege", "grantPrivilegeV2"]),
        )
        by_name = {row["baseline_name"]: row for row in result["rows"]}
        self.assertEqual(by_name["create_collection"]["candidates"][0]["method_id"], "createCollection#0")
        self.assertEqual(
            [candidate["name"] for candidate in by_name["grant_privilege"]["candidates"]],
            ["grantPrivilege"],
        )
        self.assertEqual(
            [candidate["name"] for candidate in by_name["grant_privilege_v2"]["candidates"]],
            ["grantPrivilegeV2"],
        )
        self.assertEqual(result["unmatched_audited"], [])

    def test_manual_aliases_and_async_suffix(self) -> None:
        result = mapper.build_mapping(
            surface("pymilvus", "python-digest", ["list_loaded_segments"]),
            surface("csharp", "csharp-digest", ["GetQuerySegmentInfoAsync", "DisposeAsync"]),
        )
        self.assertEqual(
            [candidate["method_id"] for candidate in result["rows"][0]["candidates"]],
            ["GetQuerySegmentInfoAsync#0"],
        )
        self.assertEqual(
            [method["name"] for method in result["unmatched_audited"]],
            ["DisposeAsync"],
        )


if __name__ == "__main__":
    unittest.main()
