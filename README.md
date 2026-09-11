# Milvus Skills

A collection of [opencode](https://opencode.ai) skills for working with Milvus-family projects. Each skill provides specialized instructions and workflows for a specific repository or task, helping AI agents (and humans) navigate, analyze, build, test, and review Milvus-related codebases.

## Skills

### Milvus server & core

| Skill | Description |
| --- | --- |
| [milvus](milvus/SKILL.md) | The `milvus-io/milvus` server: architecture, coordinators/nodes, streaming/WAL, protobuf, build & test. |
| [milvus-common](milvus-common/SKILL.md) | The `zilliztech/milvus-common` C++ library bridging Milvus and Knowhere (caching, filemanager, thread pools). |
| [milvus-restful](milvus-restful/SKILL.md) | The Milvus RESTful API service (`/v1/vector/*`, `/v2/vectordb/*`) inside the milvus server repo. |
| [milvus-storage](milvus-storage/SKILL.md) | The `milvus-io/milvus-storage` columnar storage engine (Parquet/Vortex/Lance/Iceberg, cloud backends). |
| [milvus-conanfiles](milvus-conanfiles/SKILL.md) | Conan 2.x recipes for Milvus C++ dependencies, packaging and CI publishing. |

### ANN index libraries

| Skill | Description |
| --- | --- |
| [knowhere](knowhere/SKILL.md) | The `zilliztech/knowhere` ANN engine (HNSW, IVF/SCANN, DISKANN/AISAQ, GPU/cuVS, SIMD). |
| [cardinal](cardinal/SKILL.md) | The private `zilliztech/cardinal` ANN index library (MemGraph/DiskGraph/IVF, quantization, storage backends). |

### SDKs

| Skill | Description |
| --- | --- |
| [pymilvus](pymilvus/SKILL.md) | The PyMilvus Python SDK (MilvusClient, AsyncMilvusClient, legacy ORM). |
| [milvus-sdk-go](milvus-sdk-go/SKILL.md) | The Go SDK (`github.com/milvus-io/milvus/client/v3`). |
| [milvus-sdk-java](milvus-sdk-java/SKILL.md) | The Milvus Java SDK. |
| [milvus-sdk-cpp](milvus-sdk-cpp/SKILL.md) | The Milvus C++ SDK. |
| [milvus-sdk-csharp](milvus-sdk-csharp/SKILL.md) | The Milvus .NET SDK. |
| [milvus-sdk-node](milvus-sdk-node/SKILL.md) | The Milvus Node.js/TypeScript SDK. |
| [milvus-sdk-rust](milvus-sdk-rust/SKILL.md) | The Milvus Rust SDK (V1 compatibility + validated ClientV2). |

### Tooling & review workflows

| Skill | Description |
| --- | --- |
| [birdwatcher](birdwatcher/SKILL.md) | CLI debug tool for Milvus 2.0+ etcd/TiKV metastore inspection and repair. |
| [compare-sdk](compare-sdk/SKILL.md) | Compare two Milvus SDKs on a branch and export a parity-gap report. |
| [vectordbbench](vectordbbench/SKILL.md) | The `zilliztech/VectorDBBench` benchmark tool (CLI, Streamlit UI, REST API, backend clients). |
| [pr-review](pr-review/SKILL.md) | Exhaustive GitHub PR review with complete changed-file accounting. |
| [react-review](react-review/SKILL.md) | React to reviewers' unresolved inline threads on PRs. |
| [scan-review](scan-review/SKILL.md) | Scan milvus-io/zilliztech orgs for recent external PRs and run isolated reviews. |
| [scan-runner](scan-runner/SKILL.md) | Scan GitHub Actions jobs for queued/in-progress runners by platform label. |
| [weekly-report-generator](weekly-report-generator/SKILL.md) | Generate a weekly engineering report (周报) in Markdown. |

## Layout

Each skill is a self-contained directory with a `SKILL.md` entry point, optionally followed by `references/`, `scripts/`, and `agents/` subdirectories:

```
skill-name/
├── SKILL.md          # entry point with instructions and workflow
├── references/       # in-depth technical docs, build/test guides
├── scripts/          # helper scripts (api-trace, validate-skill, release-window, ...)
└── agents/           # optional agent definitions (e.g. openai.yaml)
```

## Usage

Skills are designed for AI agents (e.g. opencode, Claude) and are loaded on demand when a task matches a skill's description. They can also be read directly as reference documentation. Most skills assume the corresponding upstream repository is checked out locally — see the preferred checkout paths mentioned in each skill.

## License

Private repository — internal use only.
