#!/usr/bin/env python3
"""Extract a deterministic client-telemetry surface from a pinned Milvus SDK."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import extract_behavior
except ModuleNotFoundError:
    import importlib.util

    _behavior_path = Path(__file__).with_name("extract_behavior.py")
    _behavior_spec = importlib.util.spec_from_file_location("extract_behavior", _behavior_path)
    if _behavior_spec is None or _behavior_spec.loader is None:
        raise RuntimeError(f"cannot load dependency: {_behavior_path}")
    extract_behavior = importlib.util.module_from_spec(_behavior_spec)
    sys.modules.setdefault("extract_behavior", extract_behavior)
    _behavior_spec.loader.exec_module(extract_behavior)


SUPPORTED_SDKS = ("pymilvus", "java", "cpp", "csharp", "rust")
TELEMETRY_TYPE_NAMES = {
    "java": {"config": "TelemetryConfig", "manager": "ClientTelemetryManager"},
    "cpp": {"config": "TelemetryConfig", "manager": "ClientTelemetryManager"},
    "rust": {"config": "TelemetryConfig", "manager": "ClientTelemetry"},
}
PUBLIC_API_PATTERNS = {
    "java": re.compile(r"\bpublic\s+[^\n{;]*\b(?:startTelemetry|getTelemetry)\s*\("),
    "cpp": re.compile(r"\bvirtual\s+[\s\S]{0,300}?\bGetTelemetry\s*\("),
    "rust": re.compile(r"\bpub\s+(?:async\s+)?fn\s+telemetry\s*\("),
}
INTEGRATION_SYMBOLS = (
    "ClientTelemetryService",
    "TelemetryInterceptor",
    "heartbeat",
    "Heartbeat",
    "on_transport_rebound",
    "OnTransportRebound",
    "AttachChannel",
    "GlobalStub",
    "update_username",
    "UpdateUsername",
    "ResetUserCredentials",
    "useDatabase",
    "UseDatabase",
    "use_database",
    "command",
    "Command",
    "shutdown",
    "Shutdown",
    "Stop",
    "RecordOperation",
    "recordOperation",
    "record_operation",
    "OperationMetrics",
    "TelemetryMetrics",
    "RecentErrors",
    "recent_errors",
    "last_heartbeat_error",
    "collection_metrics",
    "TelemetryMetric",
)


def symbol_occurrences(
    sources: dict[str, str], symbol: str | re.Pattern[str]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path, content in sources.items():
        matches = (
            re.finditer(re.escape(symbol), content)
            if isinstance(symbol, str)
            else symbol.finditer(content)
        )
        for match in matches:
            line_start = content.rfind("\n", 0, match.start()) + 1
            line_end = content.find("\n", match.end())
            if line_end == -1:
                line_end = len(content)
            result.append(
                {
                    "file": path,
                    "line": content.count("\n", 0, match.start()) + 1,
                    "expression": " ".join(content[line_start:line_end].split()),
                }
            )
    return result


def public_methods(sdk: str, block: dict[str, Any]) -> list[dict[str, Any]]:
    patterns = {
        "java": re.compile(
            r"\bpublic\s+(?:static\s+)?[^\n{;]*?\s(?P<name>[A-Za-z_]\w*)\s*\([^;{)]*\)",
            re.S,
        ),
        "cpp": re.compile(
            r"(?:virtual\s+)?[A-Za-z_][\w:<>,\s&*]*?\s+(?P<name>[A-Z]\w*)\s*\([^;{}()]*\)\s*(?:const\s*)?(?:;|\{)",
            re.S,
        ),
        "rust": re.compile(r"\bpub\s+(?:async\s+)?fn\s+(?P<name>[A-Za-z_]\w*)"),
    }
    pattern = patterns.get(sdk)
    if pattern is None:
        return []
    return [
        {
            "name": match.group("name"),
            "line": block["text"].count("\n", 0, match.start()) + block["line"],
        }
        for match in pattern.finditer(block["text"])
    ]


def rust_impl_methods(sources: dict[str, str], type_name: str) -> list[dict[str, Any]]:
    methods: list[dict[str, Any]] = []
    for path, content in sources.items():
        for match in re.finditer(
            rf"\bimpl\s+(?:Default\s+for\s+)?{re.escape(type_name)}\b\s*\{{", content
        ):
            opening = content.find("{", match.start())
            closing = extract_behavior.matching_brace(content, opening)
            if closing == -1:
                continue
            body = content[opening : closing + 1]
            for method in re.finditer(r"\bpub\s+(?:async\s+)?fn\s+(?P<name>[A-Za-z_]\w*)", body):
                methods.append(
                    {
                        "name": method.group("name"),
                        "file": path,
                        "line": content.count("\n", 0, match.start() + method.start()) + 1,
                    }
                )
    return methods


def rust_defaults(sources: dict[str, str], type_name: str) -> dict[str, str]:
    defaults: dict[str, str] = {}
    for content in sources.values():
        for match in re.finditer(
            rf"\bimpl\s+(?:Default\s+for\s+)?{re.escape(type_name)}\b\s*\{{", content
        ):
            opening = content.find("{", match.start())
            closing = extract_behavior.matching_brace(content, opening)
            if closing == -1:
                continue
            body = content[opening : closing + 1]
            for constructor in re.finditer(r"\bSelf\s*\{", body):
                object_end = extract_behavior.matching_brace(body, constructor.start())
                if object_end == -1:
                    continue
                for field in re.finditer(
                    r"(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<value>[^,\n}]+)", body[constructor.start() : object_end]
                ):
                    defaults.setdefault(field.group("name"), field.group("value").strip())
    return defaults


def java_builder_defaults(sources: dict[str, str], type_name: str) -> dict[str, str]:
    defaults: dict[str, str] = {}
    for path, content in sources.items():
        enclosing = extract_behavior.find_type_block("java", type_name, {path: content})
        if enclosing is None:
            continue
        builder = extract_behavior.find_type_block("java", "Builder", {path: content})
        if builder is None:
            continue
        for match in re.finditer(
            r"\bprivate\s+(?:volatile\s+|final\s+)?[^\n=;]+\s+"
            r"(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<value>[^;\n]+);",
            builder["text"],
        ):
            defaults.setdefault(match.group("name"), match.group("value").strip())
    return defaults


def telemetry_surface(sdk: str, sources: dict[str, str]) -> dict[str, Any]:
    config_name = TELEMETRY_TYPE_NAMES.get(sdk, {}).get("config")
    manager_name = TELEMETRY_TYPE_NAMES.get(sdk, {}).get("manager")
    config = (
        extract_behavior.type_members(sdk, config_name, sources)
        if config_name
        else {"name": None, "file": None, "line": None, "fields": [], "accessors": []}
    )
    manager_block = (
        extract_behavior.find_type_block(sdk, manager_name, sources)
        if manager_name
        else None
    )
    manager_methods = public_methods(sdk, manager_block) if manager_block else []
    config_methods = []
    if sdk == "rust" and config_name:
        config_methods = rust_impl_methods(sources, config_name)
        defaults = rust_defaults(sources, config_name)
        for field in config.get("fields", []):
            field["default"] = defaults.get(field["name"])
    elif sdk == "java" and config_name:
        config_methods = public_methods(sdk, extract_behavior.find_type_block(sdk, config_name, sources) or {"text": "", "line": 1})
        defaults = java_builder_defaults(sources, config_name)
        for field in config.get("fields", []):
            field["default"] = defaults.get(field["name"])
    elif sdk == "cpp" and config_name:
        config_block = extract_behavior.find_type_block(sdk, config_name, sources)
        config_methods = public_methods(sdk, config_block) if config_block else []
    telemetry_files = [
        path
        for path, content in sources.items()
        if re.search(r"telemetry", path, re.I)
        or re.search(r"ClientTelemetry|TelemetryInterceptor", content)
    ]
    telemetry_sources = {path: sources[path] for path in telemetry_files}
    public_api = (
        symbol_occurrences(sources, PUBLIC_API_PATTERNS[sdk])
        if sdk in PUBLIC_API_PATTERNS
        else []
    )
    integration = {
        symbol: symbol_occurrences(telemetry_sources, symbol)
        for symbol in INTEGRATION_SYMBOLS
        if symbol_occurrences(telemetry_sources, symbol)
    }
    capabilities = {
        "config_type": bool(config.get("file")),
        "manager_type": bool(manager_block),
        "public_accessor": bool(public_api),
        "telemetry_service": bool(
            symbol_occurrences(telemetry_sources, "ClientTelemetryService")
        ),
        "heartbeat": bool(integration.get("heartbeat") or integration.get("Heartbeat")),
        "transport_or_cluster_handoff": bool(
            integration.get("on_transport_rebound")
            or integration.get("OnTransportRebound")
            or integration.get("AttachChannel")
            or integration.get("GlobalStub")
        ),
        "database_or_username_update": bool(
            integration.get("update_username")
            or integration.get("UpdateUsername")
            or integration.get("ResetUserCredentials")
            or integration.get("useDatabase")
            or integration.get("UseDatabase")
            or integration.get("use_database")
        ),
        "server_command_handling": bool(
            integration.get("command") or integration.get("Command")
        ),
        "operation_metrics": bool(
            integration.get("RecordOperation")
            or integration.get("recordOperation")
            or integration.get("record_operation")
            or integration.get("OperationMetrics")
            or integration.get("TelemetryMetrics")
            or integration.get("TelemetryMetric")
        ),
        "error_metrics": bool(
            integration.get("RecentErrors")
            or integration.get("recent_errors")
            or integration.get("last_heartbeat_error")
            or (integration.get("RecordOperation") and integration.get("TelemetryMetric"))
        ),
        "per_collection_metrics": bool(integration.get("collection_metrics")),
        "shutdown_or_close_integration": bool(
            integration.get("shutdown")
            or integration.get("Shutdown")
            or integration.get("Stop")
            or integration.get("close")
            or integration.get("Close")
        ),
    }
    payload = {
        "capabilities": capabilities,
        "config": config,
        "config_methods": config_methods,
        "manager": None
        if manager_block is None
        else {
            "name": manager_name,
            "file": manager_block["file"],
            "line": manager_block["line"],
            "methods": manager_methods,
        },
        "public_apis": public_api,
        "integration": integration,
        "telemetry_files": telemetry_files,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {"version": 1, "sdk": sdk, **payload, "telemetry_sha256": digest}


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", choices=SUPPORTED_SDKS, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = extract_behavior.load_sources(args.repo.resolve(), args.ref, args.sdk)
    result = telemetry_surface(args.sdk, sources)
    result.update(
        {
            "repo": str(args.repo.resolve()),
            "ref": args.ref,
            "commit": extract_behavior.run_git(
                args.repo.resolve(), "rev-parse", args.ref
            ).strip(),
            "generated_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
    )
    write_json_atomic(args.output, result)
    print(
        json.dumps(
            {
                "sdk": result["sdk"],
                "commit": result["commit"],
                "capabilities": result["capabilities"],
                "telemetry_sha256": result["telemetry_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
