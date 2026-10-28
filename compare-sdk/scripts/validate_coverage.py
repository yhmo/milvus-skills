#!/usr/bin/env python3
"""Validate complete comparison coverage for two extracted SDK surfaces."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROW_STATUSES = {"implemented", "partial", "missing", "not_applicable"}
CHECK_STATUSES = {"completed", "not_applicable"}
CHECKS = {
    "facade",
    "parameters",
    "defaults",
    "outputs",
    "validation",
    "wire",
    "deprecated",
}
GLOBAL_CHECKS = {
    "collection_ts_cache",
    "schema_cache",
    "retry",
    "client_telemetry",
    "client_session",
}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"error: cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"error: {path} must contain a JSON object")
    return value


def surface_ids(surface: dict[str, Any], sdk: str) -> set[str]:
    if surface.get("sdk") != sdk:
        raise SystemExit(f"error: surface SDK mismatch; expected {sdk}")
    methods = surface.get("methods")
    if not isinstance(methods, list):
        raise SystemExit(f"error: {sdk} surface has no methods list")
    result = {method.get("method_id") for method in methods}
    if None in result or len(result) != len(methods):
        raise SystemExit(f"error: {sdk} surface has missing or duplicate method IDs")
    return result


def validate_surface_digest(surface: dict[str, Any], sdk: str, role: str) -> str:
    digest = surface.get("surface_sha256")
    if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
        raise SystemExit(f"error: {role} surface has an invalid SHA-256 digest: {sdk}")
    return digest


def validate_behavior(
    behavior: dict[str, Any],
    surface: dict[str, Any],
    sdk: str,
    role: str,
) -> tuple[str, set[str]]:
    if behavior.get("sdk") != sdk:
        raise SystemExit(f"error: {role} behavior SDK mismatch; expected {sdk}")
    digest = behavior.get("behavior_sha256")
    if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
        raise SystemExit(f"error: {role} behavior has an invalid SHA-256 digest: {sdk}")
    if behavior.get("surface_sha256") != surface.get("surface_sha256"):
        raise SystemExit(f"error: {role} behavior is not bound to the extracted surface")
    for key in ("ref", "commit"):
        if behavior.get(key) != surface.get(key):
            raise SystemExit(
                f"error: {role} behavior {key} does not match extracted surface"
            )
    methods = behavior.get("methods")
    if not isinstance(methods, list):
        raise SystemExit(f"error: {role} behavior has no methods list")
    ids = {method.get("method_id") for method in methods}
    expected = surface_ids(surface, sdk)
    if None in ids or len(ids) != len(methods) or ids != expected:
        raise SystemExit(f"error: {role} behavior method IDs do not cover the surface")
    for method in methods:
        if not isinstance(method.get("input"), dict) or not isinstance(method.get("output"), dict):
            raise SystemExit(f"error: {role} behavior lacks input/output evidence: {method.get('method_id')}")
    return digest, ids
def validate_telemetry(
    telemetry: dict[str, Any],
    surface: dict[str, Any],
    sdk: str,
    role: str,
) -> str:
    if telemetry.get("sdk") != sdk:
        raise SystemExit(f"error: {role} telemetry SDK mismatch; expected {sdk}")
    digest = telemetry.get("telemetry_sha256")
    if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
        raise SystemExit(f"error: {role} telemetry has an invalid SHA-256 digest: {sdk}")
    if not isinstance(telemetry.get("capabilities"), dict):
        raise SystemExit(f"error: {role} telemetry has no capability map")
    for key in ("ref", "commit"):
        if telemetry.get(key) != surface.get(key):
            raise SystemExit(
                f"error: {role} telemetry {key} does not match extracted surface"
            )
    return digest


def validate_telemetry_comparison(
    comparison: dict[str, Any],
    baseline_sdk: str,
    audited_sdk: str,
    baseline_telemetry_digest: str,
    audited_telemetry_digest: str,
) -> str:
    if comparison.get("version") != 1:
        raise SystemExit("error: telemetry comparison must use version 1")
    if comparison.get("baseline") != baseline_sdk or comparison.get("audited") != audited_sdk:
        raise SystemExit("error: telemetry comparison SDK names do not match coverage")
    digest = comparison.get("comparison_sha256")
    if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
        raise SystemExit("error: telemetry comparison has an invalid SHA-256 digest")
    if comparison.get("baseline_telemetry_sha256") != baseline_telemetry_digest:
        raise SystemExit(
            "error: telemetry comparison is not bound to baseline telemetry artifact"
        )
    if comparison.get("audited_telemetry_sha256") != audited_telemetry_digest:
        raise SystemExit(
            "error: telemetry comparison is not bound to audited telemetry artifact"
        )
    for key in ("capabilities", "config", "public_apis", "integration_keys"):
        if not isinstance(comparison.get(key), list):
            raise SystemExit(f"error: telemetry comparison has no {key} rows")
    return digest


def validate_session(
    session: dict[str, Any],
    surface: dict[str, Any],
    sdk: str,
    role: str,
) -> str:
    if session.get("sdk") != sdk:
        raise SystemExit(f"error: {role} session SDK mismatch; expected {sdk}")
    digest = session.get("session_sha256")
    if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
        raise SystemExit(f"error: {role} session has an invalid SHA-256 digest: {sdk}")
    if not isinstance(session.get("capabilities"), dict):
        raise SystemExit(f"error: {role} session has no capability map")
    for key in ("ref", "commit"):
        if session.get(key) != surface.get(key):
            raise SystemExit(
                f"error: {role} session {key} does not match extracted surface"
            )
    return digest


def validate_session_comparison(
    comparison: dict[str, Any],
    baseline_sdk: str,
    audited_sdk: str,
    baseline_session_digest: str,
    audited_session_digest: str,
) -> str:
    if comparison.get("version") != 1:
        raise SystemExit("error: session comparison must use version 1")
    if comparison.get("baseline") != baseline_sdk or comparison.get("audited") != audited_sdk:
        raise SystemExit("error: session comparison SDK names do not match coverage")
    digest = comparison.get("comparison_sha256")
    if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
        raise SystemExit("error: session comparison has an invalid SHA-256 digest")
    if comparison.get("baseline_session_sha256") != baseline_session_digest:
        raise SystemExit(
            "error: session comparison is not bound to baseline session artifact"
        )
    if comparison.get("audited_session_sha256") != audited_session_digest:
        raise SystemExit(
            "error: session comparison is not bound to audited session artifact"
        )
    for key in ("capabilities", "methods", "integration_keys"):
        if not isinstance(comparison.get(key), list):
            raise SystemExit(f"error: session comparison has no {key} rows")
    return digest


def validate(
    baseline: dict[str, Any],
    audited: dict[str, Any],
    baseline_behavior: dict[str, Any],
    audited_behavior: dict[str, Any],
    baseline_telemetry: dict[str, Any],
    audited_telemetry: dict[str, Any],
    telemetry_comparison: dict[str, Any],
    baseline_session: dict[str, Any],
    audited_session: dict[str, Any],
    session_comparison: dict[str, Any],
    coverage: dict[str, Any],
) -> dict[str, Any]:
    if coverage.get("version") != 2:
        raise SystemExit("error: coverage must use version 2")
    baseline_sdk = coverage.get("baseline")
    audited_sdk = coverage.get("audited")
    if baseline_sdk != baseline.get("sdk") or audited_sdk != audited.get("sdk"):
        raise SystemExit("error: coverage SDK names do not match surfaces")
    validate_surface_digest(baseline, baseline_sdk, "baseline")
    validate_surface_digest(audited, audited_sdk, "audited")
    for role, surface in (("baseline", baseline), ("audited", audited)):
        digest_key = f"{role}_surface_sha256"
        if coverage.get(digest_key) != surface.get("surface_sha256"):
            raise SystemExit(f"error: coverage {digest_key} does not match extracted surface")
    baseline_behavior_digest, _ = validate_behavior(
        baseline_behavior, baseline, baseline_sdk, "baseline"
    )
    audited_behavior_digest, _ = validate_behavior(
        audited_behavior, audited, audited_sdk, "audited"
    )
    if coverage.get("baseline_behavior_sha256") != baseline_behavior_digest:
        raise SystemExit("error: coverage baseline behavior digest does not match artifact")
    if coverage.get("audited_behavior_sha256") != audited_behavior_digest:
        raise SystemExit("error: coverage audited behavior digest does not match artifact")
    baseline_telemetry_digest = validate_telemetry(
        baseline_telemetry, baseline, baseline_sdk, "baseline"
    )
    audited_telemetry_digest = validate_telemetry(
        audited_telemetry, audited, audited_sdk, "audited"
    )
    if coverage.get("baseline_telemetry_sha256") != baseline_telemetry_digest:
        raise SystemExit("error: coverage baseline telemetry digest does not match artifact")
    if coverage.get("audited_telemetry_sha256") != audited_telemetry_digest:
        raise SystemExit("error: coverage audited telemetry digest does not match artifact")
    telemetry_comparison_digest = validate_telemetry_comparison(
        telemetry_comparison,
        baseline_sdk,
        audited_sdk,
        baseline_telemetry_digest,
        audited_telemetry_digest,
    )
    if coverage.get("telemetry_comparison_sha256") != telemetry_comparison_digest:
        raise SystemExit(
            "error: coverage telemetry comparison digest does not match artifact"
        )
    baseline_session_digest = validate_session(
        baseline_session, baseline, baseline_sdk, "baseline"
    )
    audited_session_digest = validate_session(
        audited_session, audited, audited_sdk, "audited"
    )
    if coverage.get("baseline_session_sha256") != baseline_session_digest:
        raise SystemExit("error: coverage baseline session digest does not match artifact")
    if coverage.get("audited_session_sha256") != audited_session_digest:
        raise SystemExit("error: coverage audited session digest does not match artifact")
    session_comparison_digest = validate_session_comparison(
        session_comparison,
        baseline_sdk,
        audited_sdk,
        baseline_session_digest,
        audited_session_digest,
    )
    if coverage.get("session_comparison_sha256") != session_comparison_digest:
        raise SystemExit(
            "error: coverage session comparison digest does not match artifact"
        )

    baseline_ids = surface_ids(baseline, baseline_sdk)
    audited_ids = surface_ids(audited, audited_sdk)
    rows = coverage.get("rows")
    if not isinstance(rows, list):
        raise SystemExit("error: coverage rows must be a list")

    seen_baseline: set[str] = set()
    seen_audited: set[str] = set()
    counts = Counter()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SystemExit(f"error: coverage row {index} must be an object")
        scope = row.get("scope", "baseline")
        if scope == "extra":
            audited_id = row.get("audited_method_id")
            if audited_id not in audited_ids:
                raise SystemExit(f"error: extra audited method is unknown: {audited_id}")
            if audited_id in seen_audited:
                raise SystemExit(f"error: duplicate extra audited method: {audited_id}")
            seen_audited.add(audited_id)
            if row.get("status") not in {"extra", "not_applicable"}:
                raise SystemExit(f"error: invalid extra-row status for {audited_id}")
            continue

        baseline_id = row.get("baseline_method_id")
        if baseline_id not in baseline_ids:
            raise SystemExit(f"error: unknown baseline method: {baseline_id}")
        if baseline_id in seen_baseline:
            raise SystemExit(f"error: duplicate baseline method: {baseline_id}")
        seen_baseline.add(baseline_id)

        audited_id = row.get("audited_method_id")
        if audited_id is not None and audited_id not in audited_ids:
            raise SystemExit(f"error: unknown audited method: {audited_id}")
        if audited_id is not None:
            if audited_id in seen_audited:
                raise SystemExit(f"error: audited method used more than once: {audited_id}")
            seen_audited.add(audited_id)

        status = row.get("status")
        if status not in ROW_STATUSES:
            raise SystemExit(f"error: invalid status for {baseline_id}: {status}")
        if status == "implemented" and audited_id is None:
            raise SystemExit(f"error: implemented row requires an audited method: {baseline_id}")
        if status == "missing" and audited_id is not None:
            raise SystemExit(f"error: missing row cannot name an audited method: {baseline_id}")
        if status == "not_applicable" and not str(row.get("note", "")).strip():
            raise SystemExit(f"error: not_applicable row requires a note: {baseline_id}")
        counts[status] += 1
        checks = row.get("checks")
        if not isinstance(checks, dict) or set(checks) != CHECKS:
            raise SystemExit(f"error: check set is incomplete for {baseline_id}")
        for check, check_status in checks.items():
            if check_status not in CHECK_STATUSES:
                raise SystemExit(f"error: invalid {check} status for {baseline_id}")
            if check_status == "not_applicable" and not str(row.get("note", "")).strip():
                raise SystemExit(f"error: not_applicable {check} requires a note for {baseline_id}")

    missing = sorted(baseline_ids - seen_baseline)
    if missing:
        raise SystemExit(f"error: baseline methods missing coverage: {missing}")

    global_checks = coverage.get("global_checks")
    if not isinstance(global_checks, dict) or set(global_checks) != GLOBAL_CHECKS:
        raise SystemExit("error: global check set is incomplete")
    for check, status in global_checks.items():
        if status not in CHECK_STATUSES:
            raise SystemExit(f"error: invalid global {check} status")
        if status == "not_applicable" and not str(coverage.get("global_notes", {}).get(check, "")).strip():
            raise SystemExit(f"error: not_applicable global {check} requires a note")
    telemetry_relevant = any(
        bool(artifact.get("capabilities", {}).get("manager_type"))
        or bool(artifact.get("capabilities", {}).get("telemetry_service"))
        for artifact in (baseline_telemetry, audited_telemetry)
    )
    if telemetry_relevant and global_checks["client_telemetry"] == "not_applicable":
        raise SystemExit(
            "error: client_telemetry cannot be not_applicable when either SDK has telemetry"
        )
    session_relevant = any(
        bool(artifact.get("capabilities", {}).get("factory"))
        or bool(artifact.get("capabilities", {}).get("session_type"))
        for artifact in (baseline_session, audited_session)
    )
    if session_relevant and global_checks["client_session"] == "not_applicable":
        raise SystemExit(
            "error: client_session cannot be not_applicable when either SDK has a client session"
        )

    summary = coverage.get("summary")
    if isinstance(summary, dict):
        for status in ROW_STATUSES:
            if status in summary and summary[status] != counts[status]:
                raise SystemExit(f"error: summary count mismatch for {status}")

    return {
        "valid": True,
        "baseline": baseline_sdk,
        "audited": audited_sdk,
        "baseline_methods": len(baseline_ids),
        "audited_methods": len(audited_ids),
        "covered_baseline_methods": len(seen_baseline),
        "extra_audited_methods": len(seen_audited),
        "status_counts": dict(sorted(counts.items())),
        "global_checks": dict(sorted(global_checks.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-surface", type=Path, required=True)
    parser.add_argument("--audited-surface", type=Path, required=True)
    parser.add_argument("--baseline-behavior", type=Path, required=True)
    parser.add_argument("--audited-behavior", type=Path, required=True)
    parser.add_argument("--baseline-telemetry", type=Path, required=True)
    parser.add_argument("--audited-telemetry", type=Path, required=True)
    parser.add_argument("--telemetry-comparison", type=Path, required=True)
    parser.add_argument("--baseline-session", type=Path, required=True)
    parser.add_argument("--audited-session", type=Path, required=True)
    parser.add_argument("--session-comparison", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    args = parser.parse_args()
    result = validate(
        load_json(args.baseline_surface),
        load_json(args.audited_surface),
        load_json(args.baseline_behavior),
        load_json(args.audited_behavior),
        load_json(args.baseline_telemetry),
        load_json(args.audited_telemetry),
        load_json(args.telemetry_comparison),
        load_json(args.baseline_session),
        load_json(args.audited_session),
        load_json(args.session_comparison),
        load_json(args.coverage),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
