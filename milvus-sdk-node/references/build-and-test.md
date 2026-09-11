# Build, Proto Generation, and Tests

Use this reference when the user asks how to build the SDK, regenerate proto JSON, run tests, or understand CI.

## Prerequisites

- Node.js 18+ (CI uses Node 22 for tests, Node 24 for release; `package.json` `engines` may restrict further).
- `yarn` (dependencies and lockfile are managed with yarn).
- Git submodule initialized for Milvus proto files (`proto/`, branch `3.0` of `milvus-io/milvus-proto`).

## First-time setup

```bash
yarn
git submodule update --init --recursive
yarn pre
```

`yarn pre` initializes the submodule descriptor path and copies
`node_modules/protobufjs/google/protobuf/descriptor.proto` into `proto/proto/google/protobuf/`.

## Build

Full build (clean `dist/`, compile TypeScript with declarations, run `build.js`):

```bash
npm run build
# or
yarn build
```

`build.js` post-processes the `tsc` output (for example it generates/embeds `sdk.json` used by `MilvusClient.sdkInfo`).

## Proto JSON generation

Proto files are the `proto/` submodule. When the submodule is updated:

```bash
yarn pre
yarn proto:json
```

`yarn proto:json` runs `NODE_ENV=dev jest test/utils/ProtoJson.spec.ts`, which converts the `.proto` definitions into protobuf.js JSON TypeScript files under `milvus/proto-json/` (`milvus.base.ts`, `schema.base.ts`, `milvus.ts`). Do not hand-edit these generated files.

## Tests (Jest)

- Run all tests: `npm test` (equivalently `NODE_ENV=dev jest`).
- Run a single test file:

  ```bash
  NODE_ENV=dev npx jest test/utils/Data.spec.ts
  NODE_ENV=dev npx jest test/grpc/Collection.spec.ts
  ```

  Always set `NODE_ENV=dev` so tests pick up the correct configuration.
- Run with coverage: `npm run coverage`.
- Run the HTTP-only suite: `npm run test-cloud` (`NODE_ENV=dev jest test/http`).
- Run benchmarks: `npm run bench` (uses `ts-node test/tools/bench.ts`).
- Build then run the build smoke test: `npm run build-test` (`yarn build && jest test/build/Collection.spec.ts`).

### Which tests need a Milvus server

- `test/utils/*` unit tests are self-contained and can run without a server.
- `test/grpc/*` and most `test/http/*` specs connect to a live Milvus at `localhost:19530` and create/drop collections and data. Running them requires a Milvus standalone (or the CI-provided instance). `test/grpc/GlobalCluster.spec.ts` additionally needs a global-cluster environment.
- `test/telemetry/*` may require the server's `ClientTelemetryService` to be reachable.
- Tests may use `test/tools` helpers (`data.ts`, `const.ts`, `utils.ts`) for fixtures and assertions.
- If a test fails with a connection error, it is likely server-backed; report the missing service instead of changing SDK code.

## CI behavior (.github/workflows/test.yml)

CI on push/PR to `main`, `2.4`, `2.5`:

1. Reads `package.json` `milvusVersion`.
2. Downloads the matching `milvusdb/milvus:<milvusVersion>` standalone via docker compose with an override enabling rocksmq, SiliconFlow (when the secret is present, required by Text fields), LoonFFI storage, and compaction schema-version/storage bumps.
3. Runs `yarn`, `git submodule init`, `yarn pre`.
4. Runs `yarn build-test`, then `NODE_ENV=dev npx jest test/grpc/FunctionFieldBackfill.e2e.spec.ts --runInBand`, then `yarn coverage`.
5. Uploads coverage to codecov.

So the CI gates on a real Milvus server started from docker compose; local equivalents should follow the same `milvusVersion` from `package.json`.

## Lint and formatting

- There is no `lint` script. Follow the existing code style: strict TypeScript (`strict: true`), 2-space indent, single quotes, semicolons, ES5 trailing commas.
- Prettier is configured in `.prettierrc`. Check with `npx prettier --check <files>` and fix with `npx prettier --write <files>`.
- Run `git diff --check` before handoff.

## Common troubleshooting

- Missing generated proto classes: run `git submodule update --init --recursive`, then `yarn pre`, then `yarn proto:json`.
- TypeScript declaration build fails on a new public export: ensure the symbol is reachable from `milvus/index.ts` and declared under `milvus/types.ts` where applicable.
- Build output stale after editing `sdk.json` inputs: `npm run build` regenerates `dist/`.
