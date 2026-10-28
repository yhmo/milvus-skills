#!/usr/bin/env python3
"""Unit tests for comparison coverage validation."""

from __future__ import annotations

import unittest
from typing import Any

from helpers import load_script


coverage_module = load_script("validate_coverage")


def surface(sdk: str, method_id: str, digest: str) -> dict[str, Any]:
    return {
        "sdk": sdk,
        "ref": "source/test",
        "commit": "a" * 40,
        "surface_sha256": digest,
        "methods": [{"method_id": method_id}],
    }


def behavior(sdk: str, method_id: str, surface_digest: str, digest: str) -> dict[str, Any]:
    return {
        "sdk": sdk,
        "ref": "source/test",
        "commit": "a" * 40,
        "surface_sha256": surface_digest,
        "behavior_sha256": digest,
        "methods": [
            {
                "method_id": method_id,
                "input": {"facade_parameters": []},
                "output": {"return_type": "void"},
            }
        ],
    }


def telemetry(sdk: str, digest: str) -> dict[str, Any]:
    return {
        "sdk": sdk,
        "ref": "source/test",
        "commit": "a" * 40,
        "telemetry_sha256": digest,
        "capabilities": {},
    }


def telemetry_comparison() -> dict[str, Any]:
    return {
        "version": 1,
        "baseline": "pymilvus",
        "audited": "java",
        "baseline_telemetry_sha256": "3" * 64,
        "audited_telemetry_sha256": "4" * 64,
        "capabilities": [],
        "config": [],
        "public_apis": [],
        "integration_keys": [],
        "comparison_sha256": "5" * 64,
    }


def session(sdk: str, digest: str) -> dict[str, Any]:
    return {
        "sdk": sdk,
        "ref": "source/test",
        "commit": "a" * 40,
        "session_sha256": digest,
        "capabilities": {},
    }


def session_comparison() -> dict[str, Any]:
    return {
        "version": 1,
        "baseline": "pymilvus",
        "audited": "java",
        "baseline_session_sha256": "6" * 64,
        "audited_session_sha256": "7" * 64,
        "capabilities": [],
        "methods": [],
        "integration_keys": [],
        "comparison_sha256": "8" * 64,
    }


def fixtures() -> tuple[dict[str, Any], ...]:
    baseline = surface("pymilvus", "insert#0", "a" * 64)
    audited = surface("java", "insert#0", "b" * 64)
    baseline_behavior = behavior("pymilvus", "insert#0", "a" * 64, "1" * 64)
    audited_behavior = behavior("java", "insert#0", "b" * 64, "2" * 64)
    baseline_telemetry = telemetry("pymilvus", "3" * 64)
    audited_telemetry = telemetry("java", "4" * 64)
    baseline_session = session("pymilvus", "6" * 64)
    audited_session = session("java", "7" * 64)
    return (
        baseline,
        audited,
        baseline_behavior,
        audited_behavior,
        baseline_telemetry,
        audited_telemetry,
        telemetry_comparison(),
        baseline_session,
        audited_session,
        session_comparison(),
    )


def valid_coverage() -> dict[str, Any]:
    return {
        "version": 2,
        "baseline": "pymilvus",
        "audited": "java",
        "baseline_surface_sha256": "a" * 64,
        "audited_surface_sha256": "b" * 64,
        "baseline_behavior_sha256": "1" * 64,
        "audited_behavior_sha256": "2" * 64,
        "baseline_telemetry_sha256": "3" * 64,
        "audited_telemetry_sha256": "4" * 64,
        "telemetry_comparison_sha256": "5" * 64,
        "baseline_session_sha256": "6" * 64,
        "audited_session_sha256": "7" * 64,
        "session_comparison_sha256": "8" * 64,
        "rows": [
            {
                "baseline_method_id": "insert#0",
                "audited_method_id": "insert#0",
                "status": "implemented",
                "checks": {name: "completed" for name in coverage_module.CHECKS},
            }
        ],
        "global_checks": {name: "completed" for name in coverage_module.GLOBAL_CHECKS},
    }


class ValidateCoverageTests(unittest.TestCase):
    def run_validate(
        self, coverage: dict[str, Any], *artifacts: dict[str, Any]
    ) -> None:
        values = artifacts or fixtures()
        coverage_module.validate(*values, coverage)

    def test_valid_complete_coverage(self) -> None:
        result = coverage_module.validate(*fixtures(), valid_coverage())
        self.assertTrue(result["valid"])
        self.assertEqual(result["covered_baseline_methods"], 1)
        self.assertIn("client_telemetry", result["global_checks"])

    def test_missing_or_invalid_checks_are_rejected(self) -> None:
        coverage = valid_coverage()
        coverage["rows"] = []
        with self.assertRaisesRegex(SystemExit, "missing coverage"):
            self.run_validate(coverage)

        coverage["rows"] = [
            {
                "baseline_method_id": "insert#0",
                "audited_method_id": "insert#0",
                "status": "implemented",
                "checks": {name: "pending" for name in coverage_module.CHECKS},
            }
        ]
        with self.assertRaisesRegex(SystemExit, r"invalid .* status"):
            self.run_validate(coverage)

        coverage["rows"][0]["status"] = "missing"
        with self.assertRaisesRegex(SystemExit, "missing row cannot name"):
            self.run_validate(coverage)

        coverage["rows"][0] = {
            "baseline_method_id": "insert#0",
            "status": "implemented",
            "checks": {name: "completed" for name in coverage_module.CHECKS},
        }
        with self.assertRaisesRegex(SystemExit, "implemented row requires"):
            self.run_validate(coverage)

    def test_behavior_and_telemetry_digests_are_required(self) -> None:
        coverage = valid_coverage()
        coverage["baseline_behavior_sha256"] = "0" * 64
        with self.assertRaisesRegex(SystemExit, "behavior digest"):
            self.run_validate(coverage)

        coverage = valid_coverage()
        coverage["audited_telemetry_sha256"] = "0" * 64
        with self.assertRaisesRegex(SystemExit, "telemetry digest"):
            self.run_validate(coverage)

        coverage = valid_coverage()
        coverage["telemetry_comparison_sha256"] = "0" * 64
        with self.assertRaisesRegex(SystemExit, "telemetry comparison digest"):
            self.run_validate(coverage)

    def test_present_telemetry_cannot_be_marked_not_applicable(self) -> None:
        coverage = valid_coverage()
        coverage["global_checks"]["client_telemetry"] = "not_applicable"
        coverage["global_notes"] = {"client_telemetry": "not relevant"}
        artifacts = list(fixtures())
        artifacts[4] = {
            **artifacts[4],
            "capabilities": {"manager_type": True},
        }
        with self.assertRaisesRegex(SystemExit, "client_telemetry cannot"):
            self.run_validate(coverage, *artifacts)

    def test_session_digests_are_required(self) -> None:
        coverage = valid_coverage()
        coverage["baseline_session_sha256"] = "0" * 64
        with self.assertRaisesRegex(SystemExit, "baseline session digest"):
            self.run_validate(coverage)

        coverage = valid_coverage()
        coverage["session_comparison_sha256"] = "0" * 64
        with self.assertRaisesRegex(SystemExit, "session comparison digest"):
            self.run_validate(coverage)

    def test_present_session_cannot_be_marked_not_applicable(self) -> None:
        coverage = valid_coverage()
        coverage["global_checks"]["client_session"] = "not_applicable"
        coverage["global_notes"] = {"client_session": "not relevant"}
        artifacts = list(fixtures())
        artifacts[7] = {
            **artifacts[7],
            "capabilities": {"factory": True},
        }
        with self.assertRaisesRegex(SystemExit, "client_session cannot"):
            self.run_validate(coverage, *artifacts)


if __name__ == "__main__":
    unittest.main()
