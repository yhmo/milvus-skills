# Benchmark Project

Use this when the user asks about the `benchmark` folder, performance comparison, or measuring SDK performance across versions.

## Key fact

`benchmark` is an independent Maven project, not part of the root reactor.

It compares performance between different published versions of the Java SDK by changing the Maven `revision` property.

Artifact:

```text
io.milvus:milvus-sdk-java-benchmark
```

Default benchmark SDK version in `benchmark/pom.xml` may lag behind the root repo version. Treat it as the benchmark default, not the current SDK release version.

## Prerequisites

- Java 8 or higher
- Maven 3.x in `PATH`
- Running Milvus instance, default `http://localhost:19530`

## Run all benchmarks

From repo root:

```bash
cd benchmark
./run_benchmarks.sh
```

Default behavior compares configured SDK versions (for example `X.Y.Z,W.X.Y`) against `localhost:19530`.

Useful variants:

```bash
./run_benchmarks.sh -v X.Y.Z
./run_benchmarks.sh -v X.Y.Z,W.X.Y,U.V.W
./run_benchmarks.sh -v X.Y.Z -u http://myhost:19530
./run_benchmarks.sh -v X.Y.Z,W.X.Y -u http://myhost:19530 -t root:Milvus
```

The script runs `mvn clean compile` before each benchmark to avoid class incompatibility between SDK versions.

## Run individual benchmarks

`PoolBenchmark` compares `MilvusClientV2Pool` against one shared `MilvusClientV2` under concurrent search, query, and insert workloads.

```bash
cd benchmark
mvn clean compile exec:java -Dexec.mainClass="io.milvus.benchmark.PoolBenchmark"
mvn clean compile exec:java -Dexec.mainClass="io.milvus.benchmark.PoolBenchmark" -Drevision=X.Y.Z
mvn clean compile exec:java -Dexec.mainClass="io.milvus.benchmark.PoolBenchmark" -Dexec.args="http://myhost:19530 root:Milvus"
```

`SearchBenchmark` measures search latency across multiple vector field types and output/topK variants.

```bash
cd benchmark
mvn clean compile exec:java -Dexec.mainClass="io.milvus.benchmark.SearchBenchmark"
mvn clean compile exec:java -Dexec.mainClass="io.milvus.benchmark.SearchBenchmark" -Drevision=X.Y.Z
mvn clean compile exec:java -Dexec.mainClass="io.milvus.benchmark.SearchBenchmark" -Dexec.args="http://myhost:19530 root:Milvus"
```

## Inputs and outputs

Individual benchmarks accept URI and token through `-Dexec.args`:

```text
first arg: Milvus URI, default http://localhost:19530
second arg: token, default root:Milvus
```

Results are written as timestamped Markdown files under:

```text
benchmark/results/
```

The results directory is git-ignored.

## Config files

Benchmarks can load optional JSON configs from:

```text
benchmark/config/PoolBenchmark.json
benchmark/config/SearchBenchmark.json
```

If a config file is missing, hardcoded defaults are used. Missing keys keep defaults.

## Rules

- Do not describe `benchmark` as part of the root Maven reactor.
- Use `-Drevision` or `run_benchmarks.sh -v` to compare SDK versions.
- Always run `mvn clean compile` when switching benchmarked SDK versions.
- Do not run benchmarks unless the user confirms a Milvus instance is available and benchmark data creation is acceptable.
- Benchmark runs create/drop/load collections and can be time/resource intensive; confirm before executing.
