# Build and Test

Use this when the user asks how to build the project, generate proto code, or run tests.

## Prerequisites

- Java 8 or higher
- Apache Maven
- Git submodule initialized for Milvus proto files

The published artifacts target Java 8. The release workflow currently builds with Temurin Java 8 (check the exact JDK in the workflow). Local test/example tooling may require Java 11: on the current branch `sdk-core` test sources do not compile under a Java 8 JDK (for example `BloomFilterUtilsTest` uses `String.repeat`, a Java 11 API).

## First-time setup

If the repo was not cloned recursively:

```bash
git submodule update --init
```

Milvus proto files are managed under:

```text
sdk-core/src/main/milvus-proto
```

## Main build

From repo root:

```bash
mvn install
```

This builds the root reactor modules and generates protobuf/gRPC Java code.

The root reactor modules are:

```text
sdk-core
sdk-bulkwriter
```

## Fast local install for examples or dependent projects

When examples need local SDK changes but tests are not the goal:

```bash
mvn -Dmaven.test.skip=true install
```

The root Surefire configuration sets `skipTests` to false, so `-DskipTests` is not a reliable skip flag in this repository. Use `-Dmaven.test.skip=true` when test compilation and execution must both be skipped.

## Test locations

Primary module tests live under:

```text
sdk-core/src/test
sdk-bulkwriter/src/test
```

There are additional standalone TestNG projects under `tests/`, but they are not root reactor modules.

## Targeted test commands

Prefer the narrowest useful command first.

Run all `sdk-core` unit tests (default; integration/system are excluded by tag):

```bash
mvn -pl sdk-core test
```

Run `sdk-core` unit + integration tests:

```bash
mvn -pl sdk-core -Pintegration test
```

Run the full `sdk-core` suite (unit + integration + system, launches Docker Milvus):

```bash
mvn -pl sdk-core -Psystem test
```

Run all `sdk-bulkwriter` tests:

```bash
mvn -pl sdk-bulkwriter test
```

Run one test class from the repo root:

```bash
mvn -pl sdk-core -Dtest=MilvusClientV2Test test
```

Pre-v3.0.9 layout: on the current design baseline (master and this branch) the
`DockerTest` classes auto-launched a local Milvus server via
`TestUtils.startMilvusStandalone`, which ran `docker compose` against
`sdk-core/src/test/java/io/milvus/docker-compose.yml` and waited for the containers to
become healthy, so a pre-running server was not required:

```bash
mvn -pl sdk-core -Dtest=MilvusClientV2DockerTest test
```

On maintenance branches the same test names instead launch a Milvus container through
`org.testcontainers.milvus.MilvusContainer`, with the image version pinned by
`TestUtils.MilvusDockerImageID`.

## Test dependency notes

The modules use both JUnit 4 and JUnit Jupiter dependencies. The root
`maven-surefire-plugin` config explicitly wires JUnit Platform/Jupiter support.

How `DockerTest` classes obtain a Milvus server is branch-dependent.

Pre-v3.0.9 behavior:

- master / current design: `TestUtils.startMilvusStandalone(DockerComposeFile, DockerComposeVolumeDirectory, DockerComposeContainerNames)` runs `docker compose -f sdk-core/src/test/java/io/milvus/docker-compose.yml down -v` then `up -d`, and waits for the containers (`milvus-javasdk-etcd`, `milvus-javasdk-minio`, `milvus-javasdk-standalone`) to be healthy. Tests connect to `TestUtils.MilvusStandaloneUri`, normally `http://localhost:19530`.
- maintenance branches: `TestUtils.MilvusDockerImageID` pins the Milvus image version and the `DockerTest` classes launch it via `org.testcontainers.milvus.MilvusContainer`.

v3.0.9+ behavior:

- The compose files moved to `sdk-core/src/test/resources/docker/`
  (`docker-compose.yml` and `docker-compose-multi.yml`). `TestUtils.dockerComposeFile`
  resolves them from `src/test/resources/docker` (module-relative) with a
  `sdk-core/src/test/resources/docker` fallback.
- `TestUtils.startMilvusStandalone` behavior is unchanged: it runs
  `docker compose down -v` then `up -d` and waits for the containers to be healthy.
- Test classes are grouped by test type and tagged: `unit` (default), `integration`,
  and `system`. `*DockerTest` classes are `@Tag("system")` and only run with
  `-Psystem` (or by explicitly selecting the class). `mvn -pl sdk-core test` runs only
  unit tests; `-Pintegration` adds integration; `-Psystem` runs the full suite.
- Docker system tests extend shared base classes under `support/`
  (`MilvusV2DockerTestBase`, `MilvusV1DockerTestBase`, `MilvusMultiDockerTestBase`).
  Their `@BeforeAll`/`@AfterAll` use reference counting so split test classes share a
  single Milvus start/stop instead of each class restarting the server.
- White-box tests that access package-private production members (for example
  `io.milvus.v2.client.globalcluster.*`, `io.milvus.telemetry.*`) stay in their
  original production package.

Note that starting these tests binds the compose file's host ports (19530/9000/etc.), so a Milvus server already running on those ports will prevent startup.

## Common troubleshooting

If proto-generated classes are missing:

1. Confirm submodule exists.
2. Run `git submodule update --init`.
3. Run `mvn install` from repo root.

If a test needs a Milvus server:

1. On master / current design, the targeted `DockerTest` class starts its own server via docker compose; ensure no Milvus server is already bound to the compose host ports (19530/9000/2379).
2. On maintenance branches, the targeted `DockerTest` class launches a testcontainers Milvus container; confirm the pinned image is pullable.
3. Do not call server-backed tests “unit tests” in summaries.
4. On v3.0.9+, `mvn -pl sdk-core test` runs only unit tests; use `-Pintegration` and `-Psystem` to include integration and system (Docker-backed) tests. If Docker is unavailable, system tests skip via `Assumptions.assumeTrue(dockerAvailable())`.

## Rules

- Prefer targeted tests before full builds.
- State explicitly when tests were not run.
- Use `-Dmaven.test.skip=true`, not `-DskipTests`, for a deliberate no-test build.
- Do not skip tests for final validation unless the user only asked for packaging/local install.
