#!/usr/bin/env python3
"""Compare two extracted client-telemetry artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


CONFIG_FIELDS = {
    "enabled": ("enabled",),
    "heartbeat_interval_ms": (
        "heartbeatIntervalMs",
        "heartbeat_interval_ms",
        "heartbeat_interval",
    ),
    "sampling_rate": ("samplingRate", "sampling_rate"),
    "error_max_count": ("errorMaxCount", "error_max_count"),
    "client_id": ("clientId", "client_id"),
}


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(
            f"error: cannot read telemetry artifact {path}: {error}"
        ) from error
    if not isinstance(value, dict) or not isinstance(value.get("capabilities"), dict):
        raise SystemExit(f"error: invalid telemetry artifact: {path}")
    return value


def normalize_default(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if field == "heartbeat_interval_ms":
        seconds = re.fullmatch(r"Duration::from_secs\((\d+)\)", text)
        if seconds:
            return f"{int(seconds.group(1)) * 1000}ms"
        millis = re.fullmatch(r"(\d+(?:_\d+)*)", text)
        if millis:
            return f"{int(millis.group(1).replace('_', ''))}ms"
    if field == "sampling_rate":
        try:
            return f"{float(text):g}"
        except ValueError:
            return text
    if field in {"enabled", "error_max_count"}:
        return text.replace("_", "")
    if field == "client_id":
        return "empty" if text in {'""', "String::new()", ""} else text
    return text


def config_values(telemetry: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    fields = {
        field.get("name"): field
        for field in telemetry.get("config", {}).get("fields", [])
        if isinstance(field, dict)
    }
    for canonical, aliases in CONFIG_FIELDS.items():
        selected = next((fields[name] for name in aliases if name in fields), None)
        values[canonical] = {
            "field_name": selected.get("name") if selected else None,
            "default": normalize_default(
                selected.get("default") if selected else None, canonical
            ),
            "type": selected.get("type") if selected else None,
        }
    return values


def method_names(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    names: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("name"), str):
            names.append(item["name"])
            continue
        expression = str(item.get("expression", ""))
        match = re.search(
            r"\b(?:startTelemetry|getTelemetry|GetTelemetry|telemetry)\s*\(",
            expression,
        )
        if match:
            names.append(re.match(r"[A-Za-z_][A-Za-z0-9_]*", match.group(0)).group(0))
    return sorted(set(names))


def compare(baseline: dict[str, Any], audited: dict[str, Any]) -> dict[str, Any]:
    baseline_values = config_values(baseline)
    audited_values = config_values(audited)
    capability_rows = []
    for capability in sorted(
        set(baseline["capabilities"]) | set(audited["capabilities"])
    ):
        baseline_value = baseline["capabilities"].get(capability)
        audited_value = audited["capabilities"].get(capability)
        if baseline_value == audited_value:
            status = "same"
        elif baseline_value and not audited_value:
            status = "missing_on_audited"
        elif audited_value and not baseline_value:
            status = "extra_on_audited"
        else:
            status = "different"
        capability_rows.append(
            {
                "capability": capability,
                "baseline": baseline_value,
                "audited": audited_value,
                "status": status,
            }
        )

    config_rows = []
    for field in sorted(CONFIG_FIELDS):
        left = baseline_values[field]
        right = audited_values[field]
        if (
            left["field_name"] is not None
            and right["field_name"] is not None
            and left["default"] == right["default"]
        ):
            status = "same"
        elif left["field_name"] is None and right["field_name"] is not None:
            status = "extra_on_audited"
        elif right["field_name"] is None and left["field_name"] is not None:
            status = "missing_on_audited"
        else:
            status = "different"
        config_rows.append(
            {"field": field, "baseline": left, "audited": right, "status": status}
        )

    baseline_public = method_names(baseline.get("public_apis"))
    audited_public = method_names(audited.get("public_apis"))
    public_rows = [
        {
            "api": name,
            "baseline": name in baseline_public,
            "audited": name in audited_public,
        }
        for name in sorted(set(baseline_public) | set(audited_public))
    ]
    result = {
        "version": 1,
        "baseline": baseline.get("sdk"),
        "audited": audited.get("sdk"),
        "baseline_telemetry_sha256": baseline.get("telemetry_sha256"),
        "audited_telemetry_sha256": audited.get("telemetry_sha256"),
        "capabilities": capability_rows,
        "config": config_rows,
        "public_apis": public_rows,
        "integration_keys": sorted(
            set(baseline.get("integration", {}))
            | set(audited.get("integration", {}))
        ),
    }
    result["comparison_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return result


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
    parser.add_argument("--baseline-telemetry", type=Path, required=True)
    parser.add_argument("--audited-telemetry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(load(args.baseline_telemetry), load(args.audited_telemetry))
    write_json_atomic(args.output, result)
    print(
        json.dumps(
            {
                "baseline": result["baseline"],
                "audited": result["audited"],
                "comparison_sha256": result["comparison_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
