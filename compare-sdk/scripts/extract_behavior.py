#!/usr/bin/env python3
"""Extract deterministic input/output behavior evidence from an SDK surface."""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_SDKS = ("pymilvus", "java", "cpp", "csharp", "rust")
SOURCE_ROOTS = {
    "pymilvus": ("pymilvus/milvus_client",),
    "java": ("sdk-core/src/main/java",),
    "cpp": ("src/include/milvus", "src/impl"),
    "csharp": ("Milvus.Client.V2",),
    "rust": ("src/v2",),
}
SOURCE_SUFFIXES = {
    "pymilvus": ".py",
    "java": ".java",
    "cpp": (".h", ".cpp"),
    "csharp": ".cs",
    "rust": ".rs",
}
TYPE_BLOCK_CACHE: dict[tuple[str, str, tuple[str, ...]], dict[str, Any] | None] = {}


def run_git(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip() or f"git exited {error.returncode}"
        raise SystemExit(f"error: git command failed: {detail}") from error
    return result.stdout


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"error: cannot read {path}: {error}") from error
    if not isinstance(value, dict) or not isinstance(value.get("methods"), list):
        raise SystemExit(f"error: not an extractor surface: {path}")
    return value


def strip_comments(source: str) -> str:
    """Remove comments while preserving source line positions."""
    output: list[str] = []
    state = "code"
    quote = ""
    escaped = False
    index = 0
    while index < len(source):
        char = source[index]
        nxt = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == "/" and nxt == "/":
                state = "line"
                index += 2
                continue
            if char == "/" and nxt == "*":
                state = "block"
                output.append("  ")
                index += 2
                continue
            if char in "\"'":
                state = "string"
                quote = char
            output.append(char)
        elif state == "line":
            output.append("\n" if char == "\n" else " ")
            if char == "\n":
                state = "code"
        elif state == "block":
            if char == "*" and nxt == "/":
                output.append("  ")
                index += 2
                state = "code"
                continue
            output.append("\n" if char == "\n" else " ")
        elif state == "string":
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                state = "code"
        index += 1
    return "".join(output)


def matching_brace(source: str, opening: int) -> int:
    depth = 0
    quote = ""
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in "\"'":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def matching_paren(source: str, opening: int) -> int:
    depth = 0
    quote = ""
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def split_top_level(value: str, separator: str = ",") -> list[str]:
    parts: list[str] = []
    start = 0
    angle = paren = bracket = brace = 0
    quote = ""
    escaped = False
    for index, char in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in "\"'":
            quote = char
        elif char == "<":
            angle += 1
        elif char == ">":
            angle = max(0, angle - 1)
        elif char == "(":
            paren += 1
        elif char == ")":
            paren = max(0, paren - 1)
        elif char == "[":
            bracket += 1
        elif char == "]":
            bracket = max(0, bracket - 1)
        elif char == "{":
            brace += 1
        elif char == "}":
            brace = max(0, brace - 1)
        elif char == separator and angle == paren == bracket == brace == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    tail = value[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def signature_parameter_names(source: str, opening_parenthesis: int) -> list[str]:
    closing = matching_paren(source, opening_parenthesis)
    if closing == -1:
        return []
    raw = source[opening_parenthesis + 1 : closing]
    names = []
    for part in split_top_level(raw):
        tokens = split_top_level(part, separator=" ")
        if len(tokens) < 2:
            continue
        names.append(tokens[-1].lstrip("*&").removeprefix("this ").strip())
    return names


def source_files(repo: Path, ref: str, sdk: str) -> list[str]:
    files: list[str] = []
    suffixes = SOURCE_SUFFIXES[sdk]
    for root in SOURCE_ROOTS[sdk]:
        listing = run_git(repo, "ls-tree", "-r", "--name-only", ref, root)
        for path in listing.splitlines():
            if path.endswith(suffixes) and not path.endswith("AssemblyInfo.cs"):
                files.append(path)
    return sorted(set(files))


def load_sources(repo: Path, ref: str, sdk: str) -> dict[str, str]:
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", ref, *SOURCE_ROOTS[sdk]],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    suffixes = SOURCE_SUFFIXES[sdk]
    result: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.endswith(suffixes):
                continue
            if member.name.endswith("AssemblyInfo.cs"):
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            result[member.name] = strip_comments(handle.read().decode("utf-8"))
    return result


def type_declaration(sdk: str, type_name: str) -> re.Pattern[str]:
    escaped = re.escape(type_name)
    if sdk in {"java", "csharp"}:
        return re.compile(
            rf"\b(?:class|record|interface|struct)\s+{escaped}\b[^;{{]*\{{"
        )
    if sdk == "cpp":
        return re.compile(
            rf"\b(?:class|struct)\s+(?:[A-Z][A-Z0-9_]*\s+)?{escaped}\b[^;{{]*\{{"
        )
    if sdk == "rust":
        return re.compile(rf"\bstruct\s+{escaped}\b[^;{{]*\{{")
    raise ValueError(sdk)


def short_type_name(type_name: str) -> str:
    if not type_name:
        return ""
    value = type_name.strip()
    if value.startswith("impl Into<") and value.endswith(">"):
        value = value[len("impl Into<") : -1]
    value = value.removeprefix("const ").removesuffix("&").strip()
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", value)
    return tokens[-1] if tokens else ""


def find_type_block(
    sdk: str, type_name: str, sources: dict[str, str]
) -> dict[str, Any] | None:
    type_name = short_type_name(type_name)
    if not type_name or type_name in {
        "void", "None", "dict", "list", "bool", "str", "int", "float", "Status"
    }:
        return None
    cache_key = (sdk, type_name, tuple(sorted(sources)))
    if cache_key in TYPE_BLOCK_CACHE:
        return TYPE_BLOCK_CACHE[cache_key]
    if sdk in {"cpp", "rust"}:
        alias_pattern = re.compile(
            rf"\b(?:pub\s+type|using)\s+{re.escape(type_name)}\s*=\s*(?P<target>[^;]+);"
        )
        for content in sources.values():
            alias = alias_pattern.search(content)
            if alias is None:
                continue
            target = short_type_name(alias.group("target"))
            if target and target != type_name:
                resolved = find_type_block(sdk, target, sources)
                TYPE_BLOCK_CACHE[cache_key] = resolved
                return resolved
    pattern = type_declaration(sdk, type_name)
    for path, content in sources.items():
        match = pattern.search(content)
        if match is None:
            continue
        opening = content.find("{", match.start())
        closing = matching_brace(content, opening)
        if closing == -1:
            continue
        result = {
            "name": type_name,
            "file": path,
            "line": content.count("\n", 0, match.start()) + 1,
            "text": content[match.start() : closing + 1],
            "declaration": " ".join(content[match.start() : opening].split()),
        }
        TYPE_BLOCK_CACHE[cache_key] = result
        return result
    TYPE_BLOCK_CACHE[cache_key] = None
    return None


def parse_java_members(block: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fields: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []
    body_start = block["text"].find("{") + 1
    body_end = block["text"].rfind("}")
    direct_text = (
        block["text"][:body_start]
        + mask_nested_and_method_blocks(block["text"][body_start:body_end])
        + block["text"][body_end:]
    )
    for line_number, line in enumerate(direct_text.splitlines(), block["line"]):
        text = line.strip()
        if not text or "(" in text or not text.endswith(";"):
            continue
        field = re.match(
            r"(?:(?:public|protected|private|static|final|transient|volatile)\s+)*"
            r"(?P<type>[^=;]+?)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*(?P<default>.+?))?\s*;",
            text,
        )
        if field and field.group("type").strip() not in {"return", "package", "import"}:
            fields.append(
                {
                    "name": field.group("name"),
                    "type": field.group("type").strip(),
                    "default": field.group("default"),
                    "line": line_number,
                }
            )
    for match in re.finditer(
        r"(?:public\s+)?(?:static\s+)?(?P<type>[A-Za-z_][\w.<>,\[\]? ]*?)\s+"
        r"(?P<name>get[A-Z]\w*|is[A-Z]\w*)\s*\((?P<parameters>[^)]*)\)",
        block["text"],
    ):
        accessors.append(
            {
                "name": match.group("name"),
                "type": match.group("type").strip(),
                "line": block["text"].count("\n", 0, match.start()) + block["line"],
            }
        )
    return fields, accessors


def mask_nested_and_method_blocks(text: str) -> str:
    """Mask method/nested-type bodies while preserving line/column layout."""
    output: list[str] = []
    index = 0
    statement_start = 0
    while index < len(text):
        char = text[index]
        if char != "{":
            output.append(char)
            if char in ";\n":
                statement_start = index + 1
            index += 1
            continue
        prefix = text[statement_start:index].strip()
        closing = matching_brace(text, index)
        if closing == -1:
            output.append(char)
            index += 1
            continue
        nested_or_method = "(" in prefix or re.search(
            r"\b(?:class|interface|record|enum)\b", prefix
        )
        if nested_or_method:
            output.extend(" " if text[position] != "\n" else "\n" for position in range(index, closing + 1))
            statement_start = closing + 1
            index = closing + 1
        else:
            output.append(char)
            statement_start = index + 1
            index += 1
    return "".join(output)


def parse_csharp_members(block: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fields: list[dict[str, Any]] = []
    for line_number, line in enumerate(block["text"].splitlines(), block["line"]):
        text = line.strip()
        if not text or text.startswith("using "):
            continue
        property_match = re.match(
            r"(?:public|internal)\s+(?P<type>[^\s=;]+(?:\s*<[^=\n]+>)?)\s+"
            r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\{[^\n]*\}|=)\s*(?P<default>[^;\n]*)",
            text,
        )
        if property_match:
            default = property_match.group("default").strip()
            if default.startswith("="):
                default = default[1:].strip()
            fields.append(
                {
                    "name": property_match.group("name"),
                    "type": property_match.group("type").strip(),
                    "default": default or None,
                    "line": line_number,
                }
            )
    return fields, fields


def parse_cpp_members(block: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fields: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []
    body_start = block["text"].find("{") + 1
    body_end = block["text"].rfind("}")
    direct_text = (
        block["text"][:body_start]
        + mask_nested_and_method_blocks(block["text"][body_start:body_end])
        + block["text"][body_end:]
    )
    for line_number, line in enumerate(direct_text.splitlines(), block["line"]):
        text = line.strip()
        if not text.endswith(";") or "(" in text:
            continue
        field = re.match(
            r"(?:const\s+)?(?P<type>[^=;]+?)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
            r"(?:\{(?P<inline_default>[^}]*)\})?\s*(?:=\s*(?P<default>[^;]+))?\s*;",
            text,
        )
        if field:
            fields.append(
                {
                    "name": field.group("name").removesuffix("_"),
                    "type": field.group("type").strip(),
                    "default": field.group("inline_default") or field.group("default"),
                    "line": line_number,
                }
            )
    for match in re.finditer(
        r"(?P<return>[A-Za-z_][\w:<>,\s&*]*?)\s+(?P<name>[A-Z][A-Za-z0-9_]*)\s*"
        r"\((?P<parameters>[^;{}()]*)\)\s*(?:const\s*)?(?:noexcept\s*)?(?:override\s*)?(?:;|\{)",
        block["text"],
        re.S,
    ):
        accessors.append(
            {
                "name": match.group("name"),
                "type": " ".join(match.group("return").split()),
                "parameters": " ".join(match.group("parameters").split()),
                "line": block["text"].count("\n", 0, match.start()) + block["line"],
            }
        )
    return fields, accessors


def parse_rust_members(block: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fields: list[dict[str, Any]] = []
    for line_number, line in enumerate(block["text"].splitlines(), block["line"]):
        text = line.strip()
        field = re.match(
            r"(?:pub(?:\(crate\))?\s+)?(?:pub\s+)?(?:mut\s+)?"
            r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<type>[^,]+),",
            text,
        )
        if field:
            fields.append(
                {
                    "name": field.group("name"),
                    "type": field.group("type").strip(),
                    "default": None,
                    "line": line_number,
                }
            )
    return fields, fields


def java_builder_defaults(block: dict[str, Any]) -> dict[str, str]:
    builder_match = re.search(
        r"\b(?:public\s+)?(?:static\s+)?(?:final\s+)?class\s+\w*Builder\b[^;{]*\{",
        block["text"],
    )
    if builder_match is None:
        return {}
    opening = block["text"].find("{", builder_match.start())
    closing = matching_brace(block["text"], opening)
    if closing == -1:
        return {}
    builder = block["text"][opening : closing + 1]
    defaults: dict[str, str] = {}
    for match in re.finditer(
        r"\bprivate\s+(?:volatile\s+|final\s+)?[^\n=;]+\s+"
        r"(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<value>[^;\n]+);",
        builder,
    ):
        defaults.setdefault(match.group("name"), match.group("value").strip())
    return defaults


def rust_constructor_defaults(
    sources: dict[str, str], type_name: str
) -> dict[str, str]:
    short_name = short_type_name(type_name)
    defaults: dict[str, str] = {}
    for content in sources.values():
        for implementation in re.finditer(
            rf"\bimpl\s+(?:Default\s+for\s+)?{re.escape(short_name)}\b\s*\{{",
            content,
        ):
            opening = content.find("{", implementation.start())
            closing = matching_brace(content, opening)
            if closing == -1:
                continue
            body = content[opening : closing + 1]
            for constructor in re.finditer(r"\bSelf\s*\{", body):
                object_end = matching_brace(body, constructor.start())
                if object_end == -1:
                    continue
                for field in re.finditer(
                    r"(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<value>[^,\n}]+)",
                    body[constructor.start() : object_end],
                ):
                    defaults.setdefault(
                        field.group("name"), field.group("value").strip()
                    )
    return defaults


def type_members(
    sdk: str, type_name: str, sources: dict[str, str], seen: set[str] | None = None
) -> dict[str, Any]:
    seen = seen or set()
    if type_name in seen:
        return {"name": type_name, "file": None, "line": None, "fields": [], "accessors": []}
    seen.add(type_name)
    block = find_type_block(sdk, type_name, sources)
    if block is None:
        return {"name": type_name, "file": None, "line": None, "fields": [], "accessors": []}
    if sdk == "java":
        fields, accessors = parse_java_members(block)
    elif sdk == "csharp":
        fields, accessors = parse_csharp_members(block)
    elif sdk == "cpp":
        fields, accessors = parse_cpp_members(block)
    elif sdk == "rust":
        fields, accessors = parse_rust_members(block)
    else:
        raise ValueError(sdk)
    if sdk == "java":
        defaults = java_builder_defaults(block)
        for field in fields:
            field["default"] = defaults.get(str(field["name"]))
    elif sdk == "rust":
        defaults = rust_constructor_defaults(sources, type_name)
        for field in fields:
            field["default"] = defaults.get(str(field["name"]))
    if sdk in {"java", "cpp", "csharp"}:
        for base_name in re.findall(
            r"(?:\bextends|:)\s+(?:public\s+)?([A-Za-z_][A-Za-z0-9_]*)",
            block["declaration"],
        ):
            base = type_members(sdk, base_name, sources, seen)
            fields.extend(base["fields"])
            accessors.extend(base["accessors"])
    return {
        "name": type_name,
        "file": block["file"],
        "line": block["line"],
        "fields": fields,
        "accessors": accessors,
    }


def method_block(
    sdk: str, method: dict[str, Any], sources: dict[str, str]
) -> dict[str, Any] | None:
    name = re.escape(str(method["name"]))
    patterns = {
        "java": rf"\bpublic\s+[^;{{}}]*?\b{name}\s*\(",
        "csharp": rf"\bpublic\s+(?:async\s+)?[^;{{}}]*?\b{name}\s*\(",
        "rust": rf"\bpub\s+(?:async\s+)?fn\s+{name}\s*\(",
        "cpp": rf"\b(?:MilvusClientV2Impl|MilvusClientV2)::\s*{name}\s*\(",
    }
    pattern = patterns.get(sdk)
    if pattern is None:
        return None
    facade_path = str(method.get("file", ""))
    ordered_paths = [facade_path] + [
        path for path in sources if path != facade_path
    ]
    for path in ordered_paths:
        content = sources.get(path)
        if content is None:
            continue
        for match in re.finditer(pattern, content):
            if sdk != "rust" and isinstance(method.get("parameters"), list):
                expected_names = [
                    str(parameter.get("name"))
                    for parameter in method["parameters"]
                    if isinstance(parameter, dict)
                ]
                actual_names = signature_parameter_names(content, match.end() - 1)
                if len(actual_names) != len(expected_names):
                    continue
            opening = content.find("{", match.start())
            if opening == -1:
                continue
            closing = matching_brace(content, opening)
            if closing == -1:
                continue
            return {
                "file": path,
                "line": content.count("\n", 0, match.start()) + 1,
                "text": content[match.start() : closing + 1],
            }
    return None


def line_signal(text: str, line_number: int, path: str, role: str) -> dict[str, Any]:
    return {"role": role, "file": path, "line": line_number, "expression": " ".join(text.split())}


def generic_validation_signals(block: dict[str, Any] | None, role: str) -> list[dict[str, Any]]:
    if block is None:
        return []
    signals: list[dict[str, Any]] = []
    lines = block["text"].splitlines()
    validation_pattern = re.compile(
        r"\b(?:throw|raise|assert|check|validate|ensure|require|ok_or|"
        r"Objects\.requireNonNull|isNullOrEmpty|isNullOrWhiteSpace|isBlank|"
        r"Error::validation|IllegalArgumentException|ArgumentNullException)\b",
        re.I,
    )
    for offset, text in enumerate(lines):
        if validation_pattern.search(text) or re.match(r"\s*if\s*\(", text):
            expression = text
            if re.match(r"\s*if\s*\(", text):
                following = offset + 1
                while following < len(lines) and expression.count("{") != expression.count("}") + 1:
                    expression += " " + lines[following]
                    following += 1
                    if following - offset > 5:
                        break
            signals.append(
                line_signal(expression, block["line"] + offset, block["file"], role)
            )
    return signals


def python_function(source: str, method: dict[str, Any]) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "MilvusClient":
            for item in node.body:
                if (
                    isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name == method["name"]
                ):
                    return item
    return None


def python_validation_signals(function: ast.AST, path: str) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for node in source_order_walk(function):
        expression = None
        if isinstance(node, ast.If) and any(isinstance(child, ast.Raise) for child in ast.walk(node)):
            expression = ast.unparse(node.test)
        elif isinstance(node, ast.Raise):
            expression = ast.unparse(node.exc) if node.exc else "raise"
        elif isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if any(token in name.lower() for token in ("check", "validate", "assert")):
                expression = ast.unparse(node)
        if expression:
            signals.append(
                {"role": "facade", "file": path, "line": getattr(node, "lineno", 0), "expression": expression}
            )
    return signals


def python_return_values(function: ast.AST) -> list[str]:
    values: list[str] = []
    for node in source_order_walk(function):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        if isinstance(node.value, ast.Dict):
            for key in node.value.keys:
                if key is None:
                    values.append("**dynamic**")
                elif isinstance(key, ast.Constant):
                    values.append(str(key.value))
                else:
                    values.append(ast.unparse(key))
        else:
            values.append(ast.unparse(node.value))
    return values


def source_order_walk(node: ast.AST):
    yield node
    for child in ast.iter_child_nodes(node):
        yield from source_order_walk(child)


def python_kwargs_names(function: ast.AST) -> list[str]:
    names: set[str] = set()
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "kwargs"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            names.add(str(node.args[0].value))
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "kwargs"
            and isinstance(node.slice, ast.Constant)
        ):
            names.add(str(node.slice.value))
    return sorted(names)


def facade_block_for_method(
    sdk: str,
    method: dict[str, Any],
    sources: dict[str, str],
    python_source: str,
) -> dict[str, Any] | None:
    if sdk == "pymilvus":
        function = python_function(python_source, method)
        if function is None:
            return None
        return {
            "file": str(method["file"]),
            "line": function.lineno,
            "text": ast.unparse(function),
            "function": function,
        }
    return method_block(sdk, method, sources)


def build_behavior(
    sdk: str,
    surface: dict[str, Any],
    repo: Path,
    ref: str,
) -> dict[str, Any]:
    if surface.get("sdk") != sdk:
        raise SystemExit(f"error: surface SDK mismatch; expected {sdk}")
    sources = load_sources(repo, ref, sdk)
    python_source = ""
    if sdk == "pymilvus":
        python_source = run_git(repo, "show", f"{ref}:pymilvus/milvus_client/milvus_client.py")
    methods: list[dict[str, Any]] = []
    for method in surface["methods"]:
        request = (
            type_members(sdk, str(method.get("request_type") or ""), sources)
            if sdk != "pymilvus"
            else {"file": None, "line": None, "fields": [], "accessors": []}
        )
        response = (
            type_members(sdk, str(method.get("response_type") or ""), sources)
            if sdk != "pymilvus"
            else {"file": None, "line": None, "fields": [], "accessors": []}
        )
        facade = facade_block_for_method(sdk, method, sources, python_source)
        facade_signals = (
            python_validation_signals(facade["function"], facade["file"])
            if sdk == "pymilvus" and facade
            else generic_validation_signals(facade, "facade")
        )
        request_block = find_type_block(sdk, str(method.get("request_type") or ""), sources)
        request_signals = generic_validation_signals(request_block, "request-definition")
        record = {
            "method_id": method["method_id"],
            "name": method["name"],
            "input": {
                "facade_parameters": method.get("parameters", []),
                "request_type": method.get("request_type"),
                "request_fields": request["fields"],
                "request_accessors_or_builders": request["accessors"],
                "kwargs_names": (
                    python_kwargs_names(facade["function"])
                    if sdk == "pymilvus" and facade
                    else []
                ),
                "validation_signals": facade_signals + request_signals,
            },
            "output": {
                "return_type": method.get("return_type"),
                "response_type": method.get("response_type"),
                "response_fields": response["fields"],
                "response_accessors": response["accessors"],
                "python_return_values": (
                    python_return_values(facade["function"])
                    if sdk == "pymilvus" and facade
                    else []
                ),
            },
            "evidence": {
                "request": {
                    "file": request["file"],
                    "line": request["line"],
                },
                "response": {
                    "file": response["file"],
                    "line": response["line"],
                },
                "facade": None
                if facade is None
                else {"file": facade["file"], "line": facade["line"]},
            },
        }
        methods.append(record)
    payload = "\n".join(json.dumps(method, sort_keys=True) for method in methods).encode()
    return {
        "version": 1,
        "sdk": sdk,
        "repo": str(repo.resolve()),
        "ref": ref,
        "commit": run_git(repo, "rev-parse", ref).strip(),
        "surface_sha256": surface.get("surface_sha256"),
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "method_count": len(methods),
        "behavior_sha256": hashlib.sha256(payload).hexdigest(),
        "methods": methods,
    }


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
    parser.add_argument("--surface", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    surface = load_json(args.surface)
    behavior = build_behavior(args.sdk, surface, args.repo.resolve(), args.ref)
    write_json_atomic(args.output, behavior)
    print(
        json.dumps(
            {
                key: behavior[key]
                for key in ("sdk", "ref", "commit", "method_count", "behavior_sha256")
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
