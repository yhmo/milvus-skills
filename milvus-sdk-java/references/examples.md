# Running Examples

Use this when the user asks how to build or run examples in this repo.

## Key fact

`examples` is a standalone Maven project. It is not part of the root reactor build.

The examples project depends on SDK artifacts from the local Maven repository.

## Prerequisites

- Java 11 recommended for the full examples project because optional TensorFlow dependencies contain Java 11 classes
- Apache Maven
- Running Milvus instance, normally `localhost:19530` unless the example says otherwise

## Build examples

From repo root:

```bash
mvn -Dmaven.test.skip=true install
cd examples
mvn compile
```

Run the root install first if local SDK changes should be visible to examples.

## Run an example

From the `examples` directory:

```bash
mvn exec:java -Dexec.mainClass="io.milvus.v2.SimpleExample"
```

## Example layout

```text
examples/src/main/java/io/milvus/v2/
examples/src/main/java/io/milvus/v1/
examples/src/main/java/io/milvus/v2/bulkwriter/
```

- `io.milvus.v2`: examples using `MilvusClientV2`.
- `io.milvus.v1`: examples using legacy `MilvusServiceClient`.
- `io.milvus.v2.bulkwriter`: BulkWriter examples.

Most new examples should target V2. V1 examples are compatibility demonstrations.

## Service requirements

Some examples need extra services or setup, especially:

- BulkWriter examples
- MinIO/S3/Azure related examples
- external table/resource examples

Check comments at the top of the specific example file before running it.

## Rules

- Do not assume examples are covered by root `mvn install`.
- Confirm `examples/pom.xml` points at the intended published/local SDK revision before using examples as version validation.
- Do not run examples unless a Milvus server and any required external service are available.
- If examples fail due to missing Milvus or storage service, report the missing service instead of changing SDK code.
