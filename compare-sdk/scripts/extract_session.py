#!/usr/bin/env python3
"""Extract a deterministic client-session surface from a pinned Milvus SDK."""

from __future__ import annotations

import argparse
import ast
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
SESSION_TYPE_NAMES = {
    "pymilvus": "MilvusClientSession",
    "java": "MilvusClientV2Session",
    "cpp": "MilvusClientV2Session",
    "csharp": "MilvusClientV2Session",
    "rust": "MilvusClientV2Session",
}
FACTORY_PATTERNS = {
    "pymilvus": re.compile(r"\bdef\s+session\s*\("),
    "java": re.compile(r"\bpublic\s+[^\n{;]*\bsession\s*\(", re.I),
    "cpp": re.compile(r"\bvirtual\s+[\s\S]{0,300}?\bSession\s*\("),
    "csharp": re.compile(r"\bpublic\s+[^\n{;]*\bsession\s*\(", re.I),
    "rust": re.compile(r"\bpub\s+fn\s+session\s*\("),
}
SESSION_INJECTION_SYMBOLS = (
    "cluster_id",
    "clusterId",
    "ClusterID",
    "set_cluster_param",
    "_with_cluster",
    "with_cluster",
)
CLOSE_ITERATOR_SYMBOLS = (
    "bind_session_close",
    "bindSessionClose",
    "bind_session",
)
DQL_METHODS = {
    "search",
    "hybrid_search",
    "query",
    "get",
    "query_iterator",
    "search_iterator",
    "search_iterator_v2",
}


def symbol_occurrences(
    sources: dict[str, str], symbol: str | re.Pattern[str], limit: int = 200
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path, content in sources.items():
        matches = (
            re.finditer(re.escape(symbol), content)
            if isinstance(symbol, str)
            else symbol.finditer(content)
        )
        for match in matches:
            if len(result) >= limit:
                return result
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


def public_methods(sdk: str, block: dict[str, Any] | None) -> list[dict[str, Any]]:
    if block is None:
        return []
    if sdk == "pymilvus":
        try:
            tree = ast.parse(block["text"])
        except SyntaxError:
            return []
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef)), None
        )
        if class_node is None:
            return []
        return [
            {"name": item.name, "line": block["line"] + item.lineno - 1}
            for item in class_node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not item.name.startswith("_")
        ]
    patterns = {
        "java": re.compile(
            r"\bpublic\s+(?:static\s+)?[^\n{;]*?\s(?P<name>[A-Za-z_]\w*)\s*\([^;{)]*\)",
            re.S,
        ),
        "cpp": re.compile(
            r"\bvirtual\s+(?:const\s+)?[A-Za-z_][\w:<>,\s&*]*?\s+(?P<name>[A-Z]\w*)\s*\([^;]*?\)\s*(?:const\s*)?(?:noexcept\s*)?(?:=\s*0\s*)?(?:;|\{)",
            re.S,
        ),
        "csharp": re.compile(
            r"\bpublic\s+(?:async\s+)?[^\n{;]*?\s(?P<name>[A-Za-z_]\w*)\s*\([^;{)]*\)",
            re.S,
        ),
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


def python_class(type_name: str, sources: dict[str, str]) -> dict[str, Any] | None:
    for path, content in sources.items():
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == type_name:
                lines = content.splitlines()
                return {
                    "name": node.name,
                    "file": path,
                    "line": node.lineno,
                    "text": "\n".join(lines[node.lineno - 1 : node.end_lineno]),
                }
    return None


def rust_impl_methods(sources: dict[str, str], type_name: str) -> list[dict[str, Any]]:
    methods: list[dict[str, Any]] = []
    for path, content in sources.items():
        for match in re.finditer(
            rf"\bimpl\s+{re.escape(type_name)}\b\s*\{{", content
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
                        "line": content.count("\n", 0, match.start() + method.start()) + 1,
                    }
                )
    return methods


def normalize_method(name: str) -> str:
    value = name.strip()
    is_async = value.lower().endswith("async")
    if is_async:
        value = value[: -len("async")]
    value = re.sub(r"^get(?=[A-Z])", "", value)
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).lower()
    value = value.replace("-", "_")
    if value == "clusterid":
        value = "cluster_id"
    return value


def direct_session_files(sources: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path, content in sources.items():
        lowered = path.lower()
        if (
            "session" in lowered
            or "MilvusClientV2Session" in content
            or "MilvusClientV2SessionImpl" in content
            or "MilvusClientSession" in content
        ):
            result[path] = content
    return result


def routing_files(sources: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    markers = (
        "MilvusClientV2Session",
        "MilvusClientSession",
        "set_cluster_param",
        "_with_cluster",
        "with_cluster",
        "cluster_id_",
        "clusterId",
        "ClusterID",
    )
    for path, content in sources.items():
        if any(marker in content for marker in markers):
            result[path] = content
    return result


def session_surface(sdk: str, sources: dict[str, str]) -> dict[str, Any]:
    type_name = SESSION_TYPE_NAMES.get(sdk)
    if sdk == "pymilvus":
        session_block = python_class(type_name, sources) if type_name else None
    else:
        session_block = (
            extract_behavior.find_type_block(sdk, type_name, sources)
            if type_name
            else None
        )
    if sdk == "rust":
        session_methods = rust_impl_methods(sources, type_name) if type_name else []
    else:
        session_methods = public_methods(sdk, session_block)

    factory_pattern = FACTORY_PATTERNS.get(sdk)
    factory = symbol_occurrences(sources, factory_pattern, limit=10) if factory_pattern else []
    direct_sources = direct_session_files(sources)
    routing_sources = routing_files(sources)
    integration: dict[str, list[dict[str, Any]]] = {}
    for symbol in ("parent", "parent_", "client", "cluster_id", "clusterId", "ClusterID", "closed"):
        occurrences = symbol_occurrences(direct_sources, symbol, limit=100)
        if occurrences:
            integration[symbol] = occurrences
    for symbol in SESSION_INJECTION_SYMBOLS[3:]:
        occurrences = symbol_occurrences(routing_sources, symbol, limit=100)
        if occurrences:
            integration[symbol] = occurrences

    raw_methods = [method["name"] for method in session_methods]
    normalized_methods = [normalize_method(name) for name in raw_methods]
    dql_methods = sorted(set(normalized_methods) & DQL_METHODS)
    close_iterator_hits = (
        symbol_occurrences(routing_sources, CLOSE_ITERATOR_SYMBOLS[0], limit=10)
        or symbol_occurrences(routing_sources, CLOSE_ITERATOR_SYMBOLS[1], limit=10)
    )
    validation_text = "\n".join(direct_sources.values())
    validates_cluster_id = bool(
        re.search(
            r"(?:cluster[_ ]?id|Cluster ID)[^\n]{0,160}(?:cannot be empty|must not be empty|empty)|"
            r"(?:cannot be empty|must not be empty)[^\n]{0,160}cluster[_ ]?id",
            validation_text,
            re.I,
        )
        or re.search(
            r"validate_param\(\s*[\"']cluster_id[\"']|"
            r"Verify\.NotNullOrWhiteSpace\(\s*clusterId",
            validation_text,
            re.I,
        )
    )

    dql_only = bool(session_block or session_methods)
    if dql_only:
        session_verb_methods = set(normalized_methods) - {
            "cluster_id",
            "close",
            "to_string",
            "dispose",
        }
        dql_only = bool(session_verb_methods) and session_verb_methods.issubset(DQL_METHODS)

    capabilities = {
        "factory": bool(factory),
        "session_type": bool(session_block),
        "dql_surface": bool(dql_methods),
        "dql_only": dql_only,
        "cluster_id_accessor": "cluster_id" in normalized_methods
        or bool(
            session_block
            and re.search(
                r"\bClusterId\s*\{\s*get;\s*\}|\bClusterID\s*\(",
                session_block["text"],
            )
        ),
        "empty_cluster_id_validation": validates_cluster_id,
        "parent_client_sharing": bool(
            integration.get("parent")
            or integration.get("parent_")
            or integration.get("client")
        ),
        "cluster_parameter_routing": bool(
            (factory or session_block)
            and (
                integration.get("cluster_id")
                or integration.get("clusterId")
                or integration.get("ClusterID")
                or integration.get("set_cluster_param")
                or integration.get("_with_cluster")
                or integration.get("with_cluster")
            )
        ),
        "query_iterator": "query_iterator" in normalized_methods,
        "search_iterator": bool(
            {"search_iterator", "search_iterator_v2"} & set(normalized_methods)
        ),
        "async_dql": any(name.lower().endswith("async") for name in raw_methods),
        "close": "close" in normalized_methods or "dispose" in normalized_methods,
        "close_stops_iterators": bool(close_iterator_hits),
    }
    payload = {
        "capabilities": capabilities,
        "factory": factory,
        "session_type": None
        if session_block is None
        else {
            "name": session_block.get("name"),
            "file": session_block.get("file"),
            "line": session_block.get("line"),
        },
        "methods": session_methods,
        "normalized_methods": sorted(set(normalized_methods)),
        "dql_methods": dql_methods,
        "integration": integration,
        "session_files": sorted(direct_sources),
        "routing_files": sorted(routing_sources),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {"version": 1, "sdk": sdk, **payload, "session_sha256": digest}


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
    result = session_surface(args.sdk, sources)
    result.update(
        {
            "repo": str(args.repo.resolve()),
            "ref": args.ref,
            "commit": extract_behavior.run_git(
                args.repo.resolve(), "rev-parse", args.ref
            ).strip(),
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    )
    write_json_atomic(args.output, result)
    print(
        json.dumps(
            {
                "sdk": result["sdk"],
                "commit": result["commit"],
                "capabilities": result["capabilities"],
                "session_sha256": result["session_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
