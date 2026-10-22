# Cross-repository consistency checklist

Load when the diff changes proto definitions, a proto submodule pin
(milvus-proto), shared error-code definitions, storage/segment formats, or
any wire contract consumed by sibling repositories.

## Identify the contract and its consumers

- Name the changed contract: a proto message/RPC, an error-code family
  (milvus `merr`, milvus-common `EasyAssert`), a storage format version, a
  REST route, or a public module.
- Map the consumers: for Milvus-family repositories, use milvus server
  (`pkg/`), the SDKs (pymilvus, milvus-sdk-java/cpp/csharp/node/rust, and
  the Go `client/` module), milvus-common, knowhere/cardinal, and
  birdwatcher. For any other repository, identify its consumers from the
  repository's own dependency graph, docs, or downstream importers instead
  of assuming the Milvus map.
- Record the dependency direction: server-to-SDK one-way, shared-library
  fan-out, or bidirectional.

## Checks

- **Proto bump intent**: if the PR bumps milvus-proto or edits proto files,
  confirm the bump is intentional and gated by the repository's update
  workflow rather than stray dependency drift, and that generated outputs
  match the new pin.
- **Sibling changes**: determine whether dependent repositories need
  synchronized changes. If a sibling PR is required but absent or unlinked,
  record it as a candidate (Medium when it blocks a release or wire
  compatibility).
- **Error codes**: new or changed codes must come from the owning family
  ranges; on repositories with code-generation targets (for example milvus
  `make generate-segcore-codes`), verify the generated code table was
  regenerated rather than hand-edited.
- **Wire/REST contract**: changing a REST route, request field, or response
  field is a breaking change; verify against the versioned API contract and
  the maintenance-branch behavior from source, not from the dev branch.
- **Storage formats**: format-version changes must either keep readers
  compatible with older segments or provide an explicit migration path.

## Recording

Record the dependency direction and consumer list in the Step 3 evidence
ledger. If no sibling change is required, state why in one sentence.
