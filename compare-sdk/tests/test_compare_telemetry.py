#!/usr/bin/env python3
"""Unit tests for telemetry artifact comparison."""

from __future__ import annotations

import unittest

from helpers import load_script


comparator = load_script("compare_telemetry")


def telemetry(sdk: str, fields: list[dict], enabled: bool) -> dict:
    return {
        "sdk": sdk,
        "capabilities": {"config_type": bool(fields), "heartbeat": enabled},
        "config": {"fields": fields},
        "public_apis": [],
        "integration": {"heartbeat": []},
    }


class CompareTelemetryTests(unittest.TestCase):
    def test_units_and_defaults_are_normalized(self) -> None:
        java = telemetry(
            "java",
            [
                {"name": "heartbeatIntervalMs", "default": "10_000", "type": "long"},
                {"name": "samplingRate", "default": "1.0", "type": "double"},
            ],
            True,
        )
        rust = telemetry(
            "rust",
            [
                {
                    "name": "heartbeat_interval",
                    "default": "Duration::from_secs(10)",
                    "type": "Duration",
                },
                {"name": "sampling_rate", "default": "1", "type": "f64"},
            ],
            True,
        )
        result = comparator.compare(java, rust)
        heartbeat = next(row for row in result["config"] if row["field"] == "heartbeat_interval_ms")
        sampling = next(row for row in result["config"] if row["field"] == "sampling_rate")
        self.assertEqual(heartbeat["status"], "same")
        self.assertEqual(sampling["status"], "same")

    def test_missing_capability_direction(self) -> None:
        java = telemetry("java", [{"name": "enabled", "default": "true"}], True)
        csharp = telemetry("csharp", [], False)
        result = comparator.compare(java, csharp)
        self.assertEqual(
            next(row for row in result["capabilities"] if row["capability"] == "heartbeat")["status"],
            "missing_on_audited",
        )
        self.assertEqual(
            next(row for row in result["config"] if row["field"] == "enabled")["status"],
            "missing_on_audited",
        )


if __name__ == "__main__":
    unittest.main()
