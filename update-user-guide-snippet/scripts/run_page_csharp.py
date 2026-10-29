#!/usr/bin/env python3
"""Run the C# snippets of a user-guide page against a live Milvus server.

Extracts every ```c# block, hoists using directives, removes repeated client
initialization, assembles the blocks into one document-scope Program.cs, and
runs it with the Milvus.Client.V2 package.

Usage: python3 run_page_csharp.py <page.md> [dotnet-package-version]
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TAG = sys.argv[2] if len(sys.argv) > 2 else "v3.0.0"
PAGE = sys.argv[1]
REPO = Path(__file__).resolve().parents[2]
PROJ = REPO / "sdk-tmp" / "snippet-run" / "csharp"


def depth(line: str) -> int:
    d = 0
    quoted = False
    escaped = False
    for ch in line:
        if quoted:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        else:
            if ch == '"':
                quoted = True
            elif ch in "{(":
                d += 1
            elif ch in "})":
                d -= 1
    return d


def unwrap_milvus_branches(text: str) -> str:
    """Unwrap Milvus branches in a temporary harness copy.

    Zilliz-only branches are removed for the local open-source run. The Feishu
    source itself must continue to preserve both product-branch includes.
    """
    text = re.sub(
        r'<include target="milvus">\s*(.*?)\s*</include>',
        lambda m: m.group(1),
        text,
        flags=re.S,
    )
    text = re.sub(
        r'<include target="zilliz">\s*.*?\s*</include>\n?',
        "",
        text,
        flags=re.S,
    )
    return text


def main() -> int:
    md = unwrap_milvus_branches(Path(PAGE).read_text())
    blocks = re.findall(r"```c#\n(.*?)```", md, re.S)
    usings = []

    def add_using(line: str) -> None:
        line = line.strip()
        if line and line not in usings:
            usings.append(line)

    cleaned = []
    seen_vars = {"client", "config"}

    for block in blocks:
        out = []
        skip = False
        brace_depth = 0
        for line in block.splitlines():
            stripped = line.strip()
            if skip:
                out.append("")
                brace_depth += depth(line)
                if brace_depth <= 0 and line.rstrip().endswith(";"):
                    skip = False
                    brace_depth = 0
                continue

            # Hoist namespace imports. Do not strip using-variable declarations.
            if (stripped.startswith("using ") and stripped.endswith(";")
                    and not re.match(r"^using\s+(?:var\s+|@?[A-Za-z_][\w.<>,?\[\]]*\s+\w+\s*=)", stripped)):
                add_using(stripped)
                out.append("")
                continue

            # Remove repeated client/config initialization; one shared client
            # is emitted below per the document-scope client rule.
            if (re.match(r"^(?:using\s+var\s+|var\s+|MilvusClientV2\s+)client\s*=\s*new\s+MilvusClientV2\s*\(", stripped)
                    or re.match(r"^MilvusClientV2\s+client\s*=\s*new\s*\(\s*new\s+ConnectConfig", stripped)
                    or re.match(r"^(?:var\s+|ConnectConfig\s+)config\s*=\s*new\s+ConnectConfig", stripped)):
                d = depth(line)
                out.append("")
                brace_depth = d
                if not line.rstrip().endswith(";"):
                    skip = True
                continue

            if re.match(r"^await\s+client\.ConnectAsync\s*\(\s*\)\s*;", stripped):
                out.append("")
                continue

            # Convert a duplicate declaration into an assignment when blocks
            # intentionally reuse a variable (for example `filter`).
            m = re.match(
                r"^\s*(?:var\s+|(?:[A-Za-z_][\w.<>,?\[\]]*(?:<[^=;]+>)?)\s+)"
                r"([A-Za-z_]\w*)\s*=(?!=)",
                line,
            )
            if m:
                name = m.group(1)
                start = m.start(1)
                if name in seen_vars:
                    line = name + line[start + len(name):]
                else:
                    seen_vars.add(name)

            out.append(line)

        cleaned.append("\n".join(out))

    if "using Milvus.Client.V2;" not in usings:
        usings.insert(0, "using Milvus.Client.V2;")
    if "using Milvus.Client.V2.Types;" not in usings:
        usings.append("using Milvus.Client.V2.Types;")

    program = "\n".join(usings) + "\n\n"
    program += 'var client = new MilvusClientV2(new ConnectConfig { Uri = "http://localhost:19530", ApiKey = "root:Milvus" });\n'
    program += "await client.ConnectAsync();\n\n"
    for i, block in enumerate(cleaned):
        program += f"// ===== block {i} =====\n{block}\n\n"

    PROJ.mkdir(parents=True, exist_ok=True)
    (PROJ / "Program.cs").write_text(program)
    (PROJ / "MilvusSnippetRun.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk">\n'
        "  <PropertyGroup>\n"
        "    <OutputType>Exe</OutputType>\n"
        "    <TargetFramework>net8.0</TargetFramework>\n"
        "    <ImplicitUsings>enable</ImplicitUsings>\n"
        "    <Nullable>disable</Nullable>\n"
        "  </PropertyGroup>\n"
        "  <ItemGroup>\n"
        f'    <PackageReference Include="Milvus.Client.V2" Version="{TAG.lstrip("v")}" />\n'
        "  </ItemGroup>\n"
        "</Project>\n"
    )

    for item in ("bin", "obj"):
        shutil.rmtree(PROJ / item, ignore_errors=True)

    print(f"csharp blocks: {len(blocks)} | Milvus.Client.V2 {TAG}")
    result = subprocess.run(
        ["dotnet", "run", "--project", str(PROJ)],
        text=True,
        capture_output=True,
    )
    sys.stdout.write(result.stdout)
    if result.returncode:
        sys.stderr.write(result.stderr[-10000:])

    status = "OK" if result.returncode == 0 else "FAILED"
    print(f"\n=== {PAGE} === csharp run {status} ({len(blocks)} blocks)")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
