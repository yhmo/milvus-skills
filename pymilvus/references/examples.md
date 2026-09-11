# Examples

Use this when explaining, adding, or running scripts under `examples/`.

## Location and role

Examples live in `examples/` at the repository root. They are standalone Python scripts that demonstrate user-facing SDK flows such as:

- Basic `MilvusClient` collection lifecycle: create, insert, query, search, delete/drop.
- Custom schemas and index params.
- Partitions, databases, aliases, resource groups, RBAC, privilege groups.
- Sparse vectors, hybrid search, reranking, group-by search, text match, function APIs.
- Bulk insert, local Milvus Lite, cloud/Zilliz/Azure/MinIO integrations, and performance experiments.

The examples are not the unit test suite. Many scripts create/drop collections and assume external services.

## Common MilvusClient pattern

Typical modern example flow:

```python
from pymilvus import MilvusClient, DataType

client = MilvusClient("http://localhost:19530")

schema = client.create_schema(enable_dynamic_field=True)
schema.add_field("id", DataType.INT64, is_primary=True)
schema.add_field("embeddings", DataType.FLOAT_VECTOR, dim=8)
schema.add_field("title", DataType.VARCHAR, max_length=64)

index_params = client.prepare_index_params()
index_params.add_index(field_name="embeddings", metric_type="L2")

client.create_collection("hello_milvus", schema=schema, index_params=index_params)
client.insert("hello_milvus", [{"id": 1, "embeddings": [0.1] * 8, "title": "t1"}])
client.load_collection("hello_milvus")
client.search("hello_milvus", [[0.1] * 8], limit=3, output_fields=["title"])
client.drop_collection("hello_milvus")
```

A quick-create variant also exists:

```python
client.create_collection("hello_milvus", dimension=8, metric_type="L2")
```

Check current examples for the exact argument names because the SDK evolves.

## Running examples

Most server-backed examples expect Milvus at `http://localhost:19530`:

```bash
uv run --group dev python examples/simple.py
```

Some examples use Milvus Lite with a local `.db` path, for example `MilvusClient("example.db")`. That requires the `milvus_lite` extra on supported platforms; the `make integration-lite` target uses `uv run --group dev --extra milvus-lite`:

```bash
uv sync --group dev --extra milvus-lite
```

Examples involving bulk insert, MinIO/S3/Azure, Zilliz Cloud, HuggingFace, LangChain, Llama, Flask, or cloud endpoints may require additional dependencies, credentials, buckets, endpoints, or external services.

## Rules before running examples

- Ask before running an example that creates, drops, deletes, or mutates data.
- Ask before running examples that require cloud credentials, object storage, external APIs, or large local datasets.
- Verify whether a local Milvus server is running before assuming `localhost:19530` works.
- Prefer setting a unique collection name when adapting examples to avoid deleting user data.
- If running from the repo checkout, use `uv run --group dev` (or install with `uv sync --group dev`) first.

## Adding or updating examples

Keep examples concise and user-facing:

- Prefer `MilvusClient` for new examples unless demonstrating legacy ORM behavior.
- Use explicit collection names and clean up collections when safe.
- Make external prerequisites obvious in the file or accompanying instructions.
- Avoid hard-coded real credentials, cloud endpoints, or user-specific paths.
- Use small data sizes unless the example is specifically a benchmark/performance script.
- For performance examples, print configuration, progress, elapsed time, throughput, and cleanup behavior.

## Troubleshooting examples

Common failures:

- `Connection refused` or timeout: Milvus is not running at the URI in the script.
- Missing optional dependency: install the related extra or package, e.g. `pymilvus[milvus_lite]`, `minio`, `azure-storage-blob`, model/ML dependencies.
- Auth or permission error: verify `user`, `password`, `token`, database name, and RBAC setup.
- Existing collection conflict: drop or rename the collection, but confirm before deleting user data.
- Generated proto/import mismatch: reinstall the local package or verify codegen/toolchain state.
