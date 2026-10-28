#!/usr/bin/env python3
"""Unit tests for client-session comparison."""

from __future__ import annotations

import unittest

from helpers import load_script


module = load_script("compare_session")


def artifact(sdk: str, digest: str, capabilities: dict[str, bool], methods: list[str]) -> dict[str, object]:
    return {
        "sdk": sdk,
        "session_sha256": digest,
        "capabilities": capabilities,
        "normalized_methods": methods,
        "integration": {"cluster_id": []},
    }


class CompareSessionTests(unittest.TestCase):
    def test_capability_and_method_directions(self) -> None:
        baseline = artifact("java", "1" * 64, {"factory": True, "close": True}, ["search", "close", "cluster_id"])
        audited = artifact("cpp", "2" * 64, {"factory": True, "close": False}, ["search", "cluster_id", "query_iterator"])
        result = module.compare(baseline, audited)
        capabilities = {row["capability"]: row["status"] for row in result["capabilities"]}
        methods = {row["method"]: (row["baseline"], row["audited"]) for row in result["methods"]}
        self.assertEqual(capabilities["factory"], "same")
        self.assertEqual(capabilities["close"], "missing_on_audited")
        self.assertEqual(methods["search"], (True, True))
        self.assertEqual(methods["query_iterator"], (False, True))
        self.assertEqual(methods["query_iterator"], (False, True))
        self.assertEqual(result["baseline_session_sha256"], "1" * 64)
        self.assertTrue(result["comparison_sha256"])


if __name__ == "__main__":
    unittest.main()
