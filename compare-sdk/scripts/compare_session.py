#!/usr/bin/env python3
"""Compare normalized client-session artifacts from two Milvus SDKs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"error: cannot read {path}: {error}") from error
    if not isinstance(value, dict) or "capabilities" not in value:
        raise SystemExit(f"error: not a session extractor artifact: {path}")
    return value


def capability_rows(baseline: dict[str, Any], audited: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for capability in sorted(set(baseline["capabilities"]) | set(audited["capabilities"])):
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
        rows.append(
            {
                "capability": capability,
                "baseline": baseline_value,
                "audited": audited_value,
                "status": status,
            }
        )
    return rows


def method_rows(baseline: dict[str, Any], audited: dict[str, Any]) -> list[dict[str, Any]]:
    baseline_methods = set(baseline.get("normalized_methods", []))
    audited_methods = set(audited.get("normalized_methods", []))
    return [
        {
            "method": method,
            "baseline": method in baseline_methods,
            "audited": method in audited_methods,
        }
        for method in sorted(baseline_methods | audited_methods)
    ]


def compare(baseline: dict[str, Any], audited: dict[str, Any]) -> dict[str, Any]:
    result = {
        "version": 1,
        "baseline": baseline.get("sdk"),
        "audited": audited.get("sdk"),
        "baseline_session_sha256": baseline.get("session_sha256"),
        "audited_session_sha256": audited.get("session_sha256"),
        "capabilities": capability_rows(baseline, audited),
        "methods": method_rows(baseline, audited),
        "integration_keys": sorted(
            set(baseline.get("integration", {})) | set(audited.get("integration", {}))
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
    parser.add_argument("--baseline-session", type=Path, required=True)
    parser.add_argument("--audited-session", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(load(args.baseline_session), load(args.audited_session))
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
