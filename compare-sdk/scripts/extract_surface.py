#!/usr/bin/env python3
"""Extract a deterministic facade-method surface from a pinned Milvus SDK."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_SDKS = ("pymilvus", "java", "cpp", "csharp", "rust")
FACADE_PATHS = {
    "pymilvus": ("pymilvus/milvus_client/milvus_client.py",),
    "java": ("sdk-core/src/main/java/io/milvus/v2/client/MilvusClientV2.java",),
    "cpp": ("src/include/milvus/MilvusClientV2.h",),
}
def run_git(repo: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip() or f"git exited {error.returncode}"
        raise SystemExit(f"error: cannot extract from {repo} at {args[-1]}: {detail}") from error
    return completed.stdout


def strip_comments(source: str) -> str:
    """Remove comments while preserving newlines for useful source positions."""
    result: list[str] = []
    index = 0
    state = "code"
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
                result.append("  ")
                index += 2
                continue
            if char == '"' or char == "'":
                state = "string"
                quote = char
            result.append(char)
        elif state == "line":
            if char == "\n":
                result.append("\n")
                state = "code"
            else:
                result.append(" ")
        elif state == "block":
            if char == "*" and nxt == "/":
                result.append("  ")
                index += 2
                state = "code"
                continue
            result.append("\n" if char == "\n" else " ")
        elif state == "string":
            result.append(char)
            if char == "\\" and nxt:
                result.append(nxt)
                index += 2
                continue
            if char == quote:
                state = "code"
        index += 1
    return "".join(result)


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


def matching_delimiter(source: str, open_index: int, opening: str, closing: str) -> int:
    depth = 0
    quote = ""
    escaped = False
    for index in range(open_index, len(source)):
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
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
    return -1


def line_of_index(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def declaration_name_index(source: str, start: int, end: int, name: str) -> int:
    """Locate a declaration name in unnormalized source.

    Signatures are normalized for parsing, but their match offsets cannot be
    used against the original multiline source. Find the last identifier before
    the declaration's parameter list instead.
    """
    matches = list(
        re.finditer(rf"\b{re.escape(name)}\s*(?=\()", source[start:end])
    )
    if not matches:
        raise ValueError(f"declaration for {name!r} not found in source range")
    return start + matches[-1].start()


def previous_line(source: str, index: int) -> str:
    before = source[:index].rstrip().splitlines()
    return before[-1].strip() if before else ""


def unwrap_response_type(return_type: str) -> str:
    """Expose the payload inside common language async/result wrappers."""
    if return_type == "Task":
        return "void"
    for wrapper in ("Task<", "CompletableFuture<"):
        if return_type.startswith(wrapper) and return_type.endswith(">"):
            return return_type[len(wrapper) : -1].strip() or "void"
    if return_type.startswith("Result<") and return_type.endswith(">"):
        payload = return_type[len("Result<") : -1]
        parts = split_top_level(payload)
        return "void" if not parts or parts[0].strip() == "()" else parts[0].strip()
    return return_type or "void"


def request_type_from_parameters(parameters: list[dict[str, Any]]) -> str | None:
    for parameter in parameters:
        request_type = parameter["type"].strip()
        if request_type.startswith("impl Into<") and request_type.endswith(">"):
            request_type = request_type[len("impl Into<") : -1].strip()
        request_type = request_type.removeprefix("const ").removesuffix("&").strip()
        if request_type.endswith(("Req", "Request")):
            return request_type
    return None


def base_method(
    name: str,
    *,
    file: str,
    line: int,
    parameters: list[dict[str, Any]],
    return_type: str,
    deprecated: bool = False,
    is_async: bool = False,
    is_static: bool = False,
    overload_index: int = 0,
    response_parameter_type: str | None = None,
) -> dict[str, Any]:
    request_type = request_type_from_parameters(parameters)
    response_type = response_parameter_type or unwrap_response_type(return_type)
    return {
        "method_id": f"{name}#{overload_index}",
        "name": name,
        "file": file,
        "line": line,
        "parameters": parameters,
        "return_type": return_type or "void",
        "request_type": request_type,
        "response_type": response_type,
        "deprecated": deprecated,
        "is_async": is_async,
        "is_static": is_static,
        "overload_index": overload_index,
    }


def decorator_is_deprecated(decorator: ast.expr) -> bool:
    if isinstance(decorator, ast.Name):
        return decorator.id == "deprecated"
    if isinstance(decorator, ast.Attribute):
        return decorator.attr == "deprecated"
    return False


def extract_python(source: str, path: str = "pymilvus/milvus_client/milvus_client.py") -> list[dict[str, Any]]:
    tree = ast.parse(source)
    methods: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "MilvusClient":
            continue
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) or item.name.startswith("_"):
                continue
            parameters = []
            args = item.args
            positional = [*args.posonlyargs, *args.args]
            if positional:
                positional = positional[1:]  # skip self
            missing_defaults = max(0, len(positional) - len(args.defaults))
            for argument, default in zip(positional, [*[None] * missing_defaults, *args.defaults]):
                if argument.arg in {"args", "kwargs"}:
                    continue
                parameter: dict[str, Any] = {
                    "name": argument.arg,
                    "type": ast.unparse(argument.annotation) if argument.annotation else "",
                    "default": ast.unparse(default) if default is not None else None,
                }
                parameters.append(parameter)
            for argument, default in zip(args.kwonlyargs, args.kw_defaults):
                if argument.arg in {"args", "kwargs"}:
                    continue
                parameters.append(
                    {
                        "name": argument.arg,
                        "type": ast.unparse(argument.annotation) if argument.annotation else "",
                        "default": ast.unparse(default) if default is not None else None,
                    }
                )
            if args.vararg:
                parameters.append({"name": f"*{args.vararg.arg}", "type": "", "default": None})
            if args.kwarg:
                parameters.append({"name": f"**{args.kwarg.arg}", "type": "", "default": None})
            methods.append(
                base_method(
                    item.name,
                    file=path,
                    line=item.lineno,
                    parameters=parameters,
                    return_type=ast.unparse(item.returns) if item.returns else "void",
                    deprecated=any(decorator_is_deprecated(decorator) for decorator in item.decorator_list),
                    is_async=isinstance(item, ast.AsyncFunctionDef),
                )
            )
    return methods


JAVA_MODIFIERS = {"static", "final", "synchronized", "abstract", "default", "native", "strictfp"}


def parse_java_parameters(raw: str) -> list[dict[str, Any]]:
    parameters: list[dict[str, Any]] = []
    for part in split_top_level(raw):
        if not part:
            continue
        tokens = split_top_level(part, separator=" ")
        # Java default methods are rare in this facade; default arguments do not exist.
        if len(tokens) < 2:
            continue
        if tokens[0] in {"final"}:
            tokens = tokens[1:]
        parameter_type = " ".join(tokens[:-1]).strip()
        parameter_name = tokens[-1]
        parameters.append({"name": parameter_name, "type": parameter_type, "default": None})
    return parameters


def extract_java(source: str, path: str = "sdk-core/src/main/java/io/milvus/v2/client/MilvusClientV2.java") -> list[dict[str, Any]]:
    cleaned = strip_comments(source)
    methods: list[dict[str, Any]] = []
    overload_counts: dict[str, int] = {}
    for match in re.finditer(r"\bpublic\s+", cleaned):
        start = match.start()
        end = cleaned.find("{", start)
        semicolon = cleaned.find(";", start)
        if semicolon != -1 and (end == -1 or semicolon < end):
            end = semicolon
        if end == -1 or end - start > 20000:
            continue
        signature = " ".join(cleaned[start + len("public") : end].split()).strip()
        declaration = re.match(
            r"(?:(?:static|final|synchronized|abstract|default|native|strictfp)\s+)*"
            r"(?P<return>.+?)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<parameters>.*)\)\s*"
            r"(?:throws\s+[\w.$,\s<>]+)?$",
            signature,
        )
        if declaration is None:
            continue
        name = declaration.group("name")
        return_tokens = declaration.group("return").split()
        if not return_tokens:
            continue
        return_type = return_tokens[-1]
        before_name = signature[: signature.rfind(name)].strip()
        is_static = re.search(r"\bstatic\b", before_name) is not None
        is_async = return_type.startswith("CompletableFuture<")
        if return_type in JAVA_MODIFIERS or return_type in {"class", "interface", "enum"}:
            continue
        overload_counts[name] = overload_counts.get(name, 0)
        methods.append(
            base_method(
                name,
                file=path,
                line=line_of_index(
                    cleaned, declaration_name_index(cleaned, start, end, name)
                ),
                parameters=parse_java_parameters(declaration.group("parameters")),
                return_type=return_type,
                deprecated=previous_line(cleaned, start).startswith("@Deprecated"),
                is_static=is_static,
                is_async=is_async,
                overload_index=overload_counts[name],
            )
        )
        overload_counts[name] += 1
    return methods


def parse_cpp_parameters(raw: str) -> list[dict[str, Any]]:
    parameters: list[dict[str, Any]] = []
    for part in split_top_level(raw):
        if not part or part == "void":
            continue
        default = None
        if "=" in part:
            part, default_text = part.split("=", 1)
            default = default_text.strip()
        tokens = split_top_level(part.strip(), separator=" ")
        if len(tokens) < 2:
            continue
        parameter_type = " ".join(tokens[:-1])
        parameter_name = tokens[-1].lstrip("*&").strip()
        parameters.append({"name": parameter_name, "type": parameter_type, "default": default})
    return parameters


def extract_cpp(source: str, path: str = "src/include/milvus/MilvusClientV2.h") -> list[dict[str, Any]]:
    cleaned = strip_comments(source)
    methods: list[dict[str, Any]] = []
    overload_counts: dict[str, int] = {}
    position = 0
    while True:
        start = cleaned.find("virtual ", position)
        if start == -1:
            break
        semicolon = cleaned.find(";", start)
        body = cleaned.find("{", start)
        candidates = [candidate for candidate in (semicolon, body) if candidate != -1]
        if not candidates:
            break
        end = min(candidates)
        signature = cleaned[start + len("virtual") : end].strip()
        call = re.search(r"\((?P<parameters>.*)\)\s*(?:const\s*)?(?:noexcept\s*)?(?:override\s*)?(?:=\s*(?:0|default|delete)\s*)?$", signature, re.S)
        if call is None:
            position = end + 1
            continue
        before_call = signature[: call.start()].strip()
        name_match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", before_call)
        if name_match is None:
            position = end + 1
            continue
        name = name_match.group(1)
        return_type = " ".join(before_call[: name_match.start()].split())
        if not return_type or "~" in return_type or name.startswith("~"):
            position = end + 1
            continue
        overload_counts[name] = overload_counts.get(name, 0)
        methods.append(
            base_method(
                name,
                file=path,
                line=line_of_index(
                    cleaned, declaration_name_index(cleaned, start, end, name)
                ),
                parameters=(
                    cpp_parameters := parse_cpp_parameters(call.group("parameters"))
                ),
                return_type=return_type,
                deprecated="[[deprecated" in cleaned[max(0, start - 300) : start],
                response_parameter_type=next(
                    (
                        parameter["type"].removesuffix("&").strip()
                        for parameter in cpp_parameters
                        if parameter["name"].lower()
                        in {"response", "result", "resp", "results"}
                        and parameter["type"].removesuffix("&").strip()
                        not in {"Status", "bool"}
                    ),
                    None,
                ),
                overload_index=overload_counts[name],
            )
        )
        overload_counts[name] += 1
        if end == body:
            closing = matching_delimiter(cleaned, end, "{", "}")
            position = closing + 1 if closing != -1 else end + 1
        else:
            position = end + 1
    return methods


CSharp_MODIFIERS = {"static", "async", "sealed", "override", "virtual", "new"}


def parse_csharp_parameters(raw: str) -> list[dict[str, Any]]:
    parameters: list[dict[str, Any]] = []
    for part in split_top_level(raw):
        if not part:
            continue
        default = None
        if "=" in part:
            part, default_text = part.split("=", 1)
            default = default_text.strip()
        tokens = split_top_level(part.strip(), separator=" ")
        if len(tokens) < 2:
            continue
        modifiers_and_type = tokens[:-1]
        while modifiers_and_type and modifiers_and_type[0].strip() in {"ref", "out", "in", "params", "this"}:
            modifiers_and_type = modifiers_and_type[1:]
        if not modifiers_and_type:
            continue
        parameter_type = " ".join(modifiers_and_type)
        parameter_name = tokens[-1]
        parameters.append({"name": parameter_name, "type": parameter_type, "default": default})
    return parameters


def extract_csharp(source: str, path: str = "Milvus.Client.V2/MilvusClientV2.cs") -> list[dict[str, Any]]:
    cleaned = strip_comments(source)
    methods: list[dict[str, Any]] = []
    overload_counts: dict[str, int] = {}
    for match in re.finditer(r"\bpublic\s+", cleaned):
        start = match.start()
        brace = cleaned.find("{", start)
        semicolon = cleaned.find(";", start)
        end = min((x for x in (brace, semicolon) if x != -1), default=-1)
        if end == -1 or end - start > 20000:
            continue
        signature = " ".join(cleaned[start + len("public") : end].split()).strip()
        declaration = re.match(
            r"(?:(?:static|async|sealed|override|virtual|new)\s+)*"
            r"(?P<return>.+?)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<parameters>.*)\)\s*$",
            signature,
        )
        if declaration is None:
            continue
        name = declaration.group("name")
        tokens = declaration.group("return").split()
        if not tokens:
            continue
        return_type = tokens[-1]
        before_name = signature[: signature.rfind(name)].strip()
        is_async = re.search(r"\basync\b", before_name) is not None
        is_static = re.search(r"\bstatic\b", before_name) is not None
        if return_type in CSharp_MODIFIERS or return_type in {"class", "interface", "enum", "struct"}:
            continue
        overload_counts[name] = overload_counts.get(name, 0)
        methods.append(
            base_method(
                name,
                file=path,
                line=line_of_index(
                    cleaned, declaration_name_index(cleaned, start, end, name)
                ),
                parameters=parse_csharp_parameters(declaration.group("parameters")),
                return_type=return_type,
                deprecated=previous_line(cleaned, start).startswith("[Obsolete"),
                is_async=is_async,
                is_static=is_static,
                overload_index=overload_counts[name],
            )
        )
        overload_counts[name] += 1
    return methods


def parse_rust_parameters(raw: str) -> list[dict[str, Any]]:
    parameters: list[dict[str, Any]] = []
    for part in split_top_level(raw):
        if not part or part.strip() in {"&self", "&mut self", "self"}:
            continue
        default = None
        if "=" in part:
            part, default_text = part.split("=", 1)
            default = default_text.strip()
        if ":" not in part:
            continue
        name, parameter_type = part.split(":", 1)
        parameters.append({"name": name.strip(), "type": parameter_type.strip(), "default": default})
    return parameters


def extract_rust(source: str, path: str = "src/v2/client.rs") -> list[dict[str, Any]]:
    methods: list[dict[str, Any]] = []
    for match in re.finditer(r"\bpub\s+(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)", source):
        name = match.group(1)
        open_paren = source.find("(", match.end())
        if open_paren == -1:
            continue
        close_paren = open_paren + 1
        depth = 1
        quote = ""
        escaped = False
        while close_paren < len(source) and depth:
            char = source[close_paren]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
            elif char in "\"'":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
            close_paren += 1
        if close_paren >= len(source):
            continue
        parameters_raw = source[open_paren + 1 : close_paren]
        remainder_start = close_paren + 1
        remainder_end = min(
            (x for x in (source.find("{", remainder_start), source.find(";", remainder_start)) if x != -1),
            default=len(source),
        )
        remainder = source[remainder_start:remainder_end]
        return_match = re.search(r"->\s*(.+?)(?:\s+where\b|\s*$)", remainder, re.S)
        return_type = " ".join(return_match.group(1).split()) if return_match else "()"
        before = source[: match.start()].rstrip().splitlines()
        previous = before[-1].strip() if before else ""
        methods.append(
            base_method(
                name,
                file=path,
                line=line_of_index(source, match.start(1)),
                parameters=parse_rust_parameters(parameters_raw),
                return_type=return_type,
                deprecated=previous.startswith("#[deprecated"),
                is_async="pub async fn" in match.group(0),
            )
        )
    return methods


def list_ref_files(repo: Path, ref: str, directory: str, pattern: re.Pattern[str]) -> list[str]:
    output = run_git(repo, "ls-tree", "-r", "--name-only", ref, directory)
    return [line for line in output.splitlines() if pattern.fullmatch(line)]


def renumber_overloads(methods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep overload IDs unique across partial facade files."""
    counts: dict[str, int] = {}
    for method in methods:
        index = counts.get(method["name"], 0)
        method["overload_index"] = index
        method["method_id"] = f"{method['name']}#{index}"
        counts[method["name"]] = index + 1
    return methods


def extract_from_repo(sdk: str, repo: Path, ref: str) -> list[dict[str, Any]]:
    if sdk == "pymilvus":
        path = FACADE_PATHS[sdk][0]
        return extract_python(run_git(repo, "show", f"{ref}:{path}"), path)
    if sdk == "java":
        path = FACADE_PATHS[sdk][0]
        return extract_java(run_git(repo, "show", f"{ref}:{path}"), path)
    if sdk == "cpp":
        path = FACADE_PATHS[sdk][0]
        return extract_cpp(run_git(repo, "show", f"{ref}:{path}"), path)
    if sdk == "csharp":
        paths = list_ref_files(
            repo,
            ref,
            "Milvus.Client.V2",
            re.compile(r"Milvus\.Client\.V2/MilvusClientV2(?:\.[A-Za-z0-9_]+)?\.cs"),
        )
        methods: list[dict[str, Any]] = []
        for path in paths:
            methods.extend(extract_csharp(run_git(repo, "show", f"{ref}:{path}"), path))
        return renumber_overloads(
            sorted(methods, key=lambda method: (method["name"], method["file"], method["line"]))
        )
    if sdk == "rust":
        paths = ["src/v2/client.rs", *list_ref_files(repo, ref, "src/v2/client/", re.compile(r"src/v2/client/.+\.rs"))]
        methods = []
        for path in paths:
            methods.extend(extract_rust(run_git(repo, "show", f"{ref}:{path}"), path))
        return renumber_overloads(
            sorted(methods, key=lambda method: (method["name"], method["file"], method["line"]))
        )
    raise ValueError(f"unsupported SDK: {sdk}")


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", required=True, choices=SUPPORTED_SDKS)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    methods = extract_from_repo(args.sdk, args.repo.resolve(), args.ref)
    payload = "\n".join(json.dumps(method, sort_keys=True) for method in methods).encode("utf-8")
    result = {
        "version": 1,
        "sdk": args.sdk,
        "repo": str(args.repo.resolve()),
        "ref": args.ref,
        "commit": run_git(args.repo.resolve(), "rev-parse", args.ref).strip(),
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "method_count": len(methods),
        "surface_sha256": hashlib.sha256(payload).hexdigest(),
        "methods": methods,
    }
    write_json_atomic(args.output, result)
    print(json.dumps({key: result[key] for key in ("sdk", "ref", "commit", "method_count", "surface_sha256")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
