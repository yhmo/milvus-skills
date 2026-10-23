#!/usr/bin/env python3
"""Unit tests for client-telemetry surface extraction."""

from __future__ import annotations

import unittest

from helpers import load_script


telemetry = load_script("extract_telemetry")


class ExtractTelemetryTests(unittest.TestCase):
    def test_java_telemetry_surface(self) -> None:
        sources = {
            "MilvusClientV2.java": (
                "public class MilvusClientV2 {\n"
                "    public ClientTelemetryManager getTelemetry() { return manager; }\n"
                "}\n"
            ),
            "TelemetryConfig.java": (
                "public class TelemetryConfig {\n"
                "    private boolean enabled = true;\n"
                "    private long heartbeatIntervalMs = 1000;\n"
                "}\n"
            ),
            "ClientTelemetryManager.java": (
                "public class ClientTelemetryManager {\n"
                "    public void heartbeat() {}\n"
                "    public void shutdown() {}\n"
                "}\n"
            ),
        }
        result = telemetry.telemetry_surface("java", sources)
        self.assertTrue(result["capabilities"]["config_type"])
        self.assertTrue(result["capabilities"]["manager_type"])
        self.assertTrue(result["capabilities"]["public_accessor"])
        self.assertTrue(result["capabilities"]["heartbeat"])
        self.assertEqual(
            [field["name"] for field in result["config"]["fields"]],
            ["enabled", "heartbeatIntervalMs"],
        )

    def test_unavailable_surface_is_explicit(self) -> None:
        result = telemetry.telemetry_surface("csharp", {"MilvusClientV2.cs": "public class MilvusClientV2 {}"})
        self.assertFalse(result["capabilities"]["config_type"])
        self.assertFalse(result["capabilities"]["manager_type"])
        self.assertFalse(result["capabilities"]["public_accessor"])
        self.assertIsNotNone(result["telemetry_sha256"])


if __name__ == "__main__":
    unittest.main()
