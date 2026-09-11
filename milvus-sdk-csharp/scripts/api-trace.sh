#!/usr/bin/env bash
set -euo pipefail

query="${1:-}"
if [[ -z "$query" ]]; then
  echo "usage: $0 <symbol>" >&2
  echo "example: $0 DescribeCollection" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" || ! -f "$repo_root/Milvus.Client.sln" || ! -d "$repo_root/Milvus.Client.V2" ]]; then
  echo "error: run this script from the milvus-sdk-csharp repo root" >&2
  exit 1
fi

cd "$repo_root"

search() {
  if command -v rg >/dev/null 2>&1; then
    rg -n "$query" "$@"
  else
    grep -RIn "$query" "$@"
  fi
}

echo "== V2 facade matches (MilvusClientV2.*.cs) =="
search Milvus.Client.V2/MilvusClientV2.cs Milvus.Client.V2/MilvusClientV2.*.cs || true

echo
echo "== V2 request/response DTO matches =="
search Milvus.Client.V2/Request Milvus.Client.V2/Response || true

echo
echo "== V2 types/utils matches =="
search Milvus.Client.V2/Types Milvus.Client.V2/Utils || true

echo
echo "== Tests matches =="
search Milvus.Client.V2.Tests Milvus.Client.Tests || true

echo
echo "== V1 legacy matches =="
search Milvus.Client || true

echo
echo "== Examples matches =="
search examples || true

echo
echo "== Generated proto references in build tree =="
if compgen -G "Milvus.Client.V2/obj/*/*/Milvus.Client.Grpc/*.cs" >/dev/null 2>&1; then
  search Milvus.Client.V2/obj/*/*/Milvus.Client.Grpc/*.cs 2>/dev/null | head -80 || true
else
  echo "generated protobuf output not found; run 'dotnet build -p:DeveloperBuild=True' first"
fi
