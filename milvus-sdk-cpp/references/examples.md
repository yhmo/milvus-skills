# Examples

Use this reference before changing, building, or running Milvus C++ SDK examples.

## Layout and naming

- `examples/src/v1/*.cpp`: legacy `MilvusClient` sources.
- `examples/src/v2/*.cpp`: recommended `MilvusClientV2` sources.
- `examples/utils/ExampleUtils.h`: shared data-generation and status helpers.
- `examples/README.md`: authoritative binary list and special prerequisites.
- `examples/CMakeLists.txt`: globs each source directory and derives binary names.

A source such as `examples/src/v2/general.cpp` becomes:

```text
cmake_build/examples/v2/sdk_general_v2
```

Use V2 examples for new work. Keep V1 examples only for compatibility or when a V1 behavior is explicitly in scope.

## Building

Examples are controlled by `MILVUS_BUILD_EXAMPLES`, which defaults to `ON`; they do not require
`MILVUS_BUILD_TEST=ON`.

The common repository workflow builds them:

```bash
JOBS=4 bash scripts/build.sh -f -u
```

For an existing configured tree:

```bash
cmake --build cmake_build -j4
```

Disable examples in expensive test/coverage builds when they are unrelated:

```bash
CMAKE_BUILD_EXAMPLES=OFF JOBS=4 make test
```

When adding a new example, add one `.cpp` under the correct source directory and update `examples/README.md`. A newly
added source may require CMake reconfiguration because the build uses globs.

## Running safely

Examples generally connect to `http://localhost:19530` with `root:Milvus` and may create, load, mutate, and drop data.
Do not run them without confirming the target server and receiving permission for data-changing operations.

Suppress gRPC internal logs:

```bash
export GRPC_VERBOSITY=ERROR
./cmake_build/examples/v2/sdk_general_v2
```

Before running an example, inspect it for:

- fixed collection, database, alias, role, or user names;
- destructive cleanup such as `DropCollection`;
- authentication or cloud endpoint assumptions;
- external object-storage or multiple-server dependencies;
- server-version/configuration prerequisites.

Some examples require Milvus server settings documented in the corresponding example source, such as
schema-evolution support for `add_field.cpp`.

## Batch runner

Run all eligible built examples with:

```bash
scripts/run_examples.sh v2
scripts/run_examples.sh v1
```

The script sets `GRPC_VERBOSITY=ERROR`, discovers executable `sdk_*_<version>` files, prints every skipped example and
reason, fails if no runnable examples remain, stops at the first failure, and reports success only after all selected
examples pass.

On current master the V2 batch skip list includes examples requiring two servers, external storage, additional server
configuration, or explicit exclusion. Read `scripts/run_examples.sh` instead of hardcoding that list in a change.

## Choosing examples

Useful V2 starting points:

- `simple.cpp`: shortest collection creation flow.
- `general.cpp`: broad basic lifecycle.
- `dml.cpp`: insert, upsert, and delete.
- `iterator_query.cpp` / `iterator_search.cpp`: paging APIs.
- `hybrid_search.cpp`: multiple ANN requests and reranking.
- `add_field.cpp` / `struct_field.cpp`: schema evolution.
- `snapshot.cpp`, `cdc.cpp`, `external_table.cpp`, `optimize.cpp`: advanced server features.
- `rbac.cpp`: users, roles, and privileges.
- `full_text_match.cpp`, `multi_analyzer.cpp`, `highlighter.cpp`, `minhash_function.cpp`: text/function workflows.

Consult `examples/README.md` for the complete current list rather than assuming a binary exists.

## Example implementation conventions

- Include `milvus/MilvusClientV2.h` as the aggregate SDK header.
- Reuse `ExampleUtils.h` for generated vectors/data and `util::CheckStatus`.
- Check every meaningful `Status`; avoid printing success after a failed prerequisite.
- Use names that clearly distinguish V1 and V2 behavior through the generated binary convention.
- Keep examples focused on user-facing API usage, not internal implementation types.
- Document non-default Milvus configuration as prose with exact server-side keys only when verified.
