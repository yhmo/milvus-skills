# Running Examples

Use this reference when the user asks how to build or run the SDK examples.

## Key facts

- Examples live in `examples/` as separate TypeScript projects, each with its own `package.json`/`tsconfig.json`/`yarn.lock`.
- `examples/milvus/` uses `ts-node` to execute TypeScript directly; `examples/LangChain/` and `examples/nextjs/` are standalone application projects.
- A running Milvus instance (normally `localhost:19530`) is required for examples that mutate data or collections.

## Example layout

```text
examples/milvus/
  HelloMilvus.ts         basic create collection / insert / search
  Data.ts                data operations
  DataQuery.ts           query by filter
  Database.ts            multi-database usage
  DynamicSchema.ts       dynamic fields
  PartitionKey.ts        partition-key collections
  QueryIterator.ts       paginated query iteration
  Server.ts              simple server using the SDK
  BinarySearch.ts        binary vector search
  HelloSparse.ts         sparse vector search
  EntityTTL.ts           entity TTL
  test.ts                quick sanity script
examples/LangChain/      LangChain integration
examples/nextjs/         Next.js example
```

## Run an example

From `examples/milvus/`:

```bash
npm install       # or yarn
ts-node HelloMilvus.ts
```

Or from the repository root using the `example` script (`npx ts-node`):

```bash
npm run example -- examples/milvus/HelloMilvus.ts
```

## Service requirements

- Most examples connect to `localhost:19530` and require a running Milvus standalone.
- `HelloSparse.ts` and full-text examples require a server build that supports sparse vectors / analyzers.
- Check the top of each example file before running; some expect a specific Milvus version or features from `package.json` `milvusVersion`.

## Rules

- Do not run examples unless a Milvus server is available.
- Examples mutate server state (create/drop collections); confirm before running them in a shared environment.
- Do not change SDK source code to make an example pass; report a missing service or server feature instead.
