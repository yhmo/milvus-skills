# Change and verification rules

## Error handling

Before changing error creation, wrapping, classification, or projection, read:

- `docs/dev/error_handling_guide.md`
- `docs/dev/error_handling_casebook.md`
- `docs/dev/error_sentinel_convention.md` when adding or changing sentinels/codes
- `pkg/util/merr/errors.go` and relevant helpers/tests

Apply these checks:

1. Decide Input versus System with the blame test: request content forces the branch only for Input; bugs, internal protocol violations, races, and transient/not-ready failures are System.
2. Use typed errors at component/client boundaries. Preserve an existing code with `merr.Wrap`/`Wrapf`; use a `WrapErr*Err` helper only when deliberately replacing classification.
3. Before marking an error as Input, trace callers and `retry.Do` consumers. Before converting a sentinel, audit every `errors.Is` guard.
4. Allocate codes only from current family ranges after scanning `pkg/util/merr/errors.go`; do not hand-pick native/segcore codes.
5. Audit wire projections, legacy-code mappings, REST conversion, metric labels, and retryability together.
6. For C++, audit `ThrowInfo`, `AssertInfo`, `SegcoreError`, Arrow/Knowhere/storage status creation, catch blocks, stringification, and `CStatus` conversion sites end to end.

## Observability

Before changing logs, metrics, or traces, read `docs/agent_guides/observability/README.md` and every relevant linked guide.

- Use the checkout's `mlog` package, never direct zap, the standard logger, `fmt.Println`, or legacy logging packages.
- Pass a real context by repository priority; use predefined fields before generic typed fields.
- Rate-limit logs on loops/hot paths and avoid payload logging or high-cardinality metric labels.
- Preserve metric names, label sets, config keys, log fields, and span semantics unless an explicit contract change is intended.
- For WAL tracing, read the streaming overview, relevant message semantics, and `wal/tracing.md` before editing source.

## Generated files and modules

- Do not hand-edit `internal/mocks/*`, `mock_*.go`, or generated protobuf output. Use the matching `make generate-mockery-*` or proto target.
- Add `pkg/` dependencies from `pkg/`; add `client/` dependencies from `client/`. Run module-specific tests from the owning module.
- Verify import paths from the current `go.mod`; module major versions can change across branches.
- Follow standard → third-party → `github.com/milvus-io` import grouping and repository formatters.
- Put configuration defaults in the established YAML/paramtable pipeline; search for the current parameter definition and watchers before adding a new key.

## Behavioral verification gate

For retry, classification, routing, error propagation, fallback, cache invalidation, recovery, or concurrency changes:

1. **Audit the input data.** Search every origin, constructor, throw, wrapper, fallback, and rewrite of the value being preserved or mapped across the whole repository.
2. **Trace real failure modes.** For each intended bucket—timeout, cancel, not-ready, corrupt data, storage throttle, OOM, retry exhaustion, race, or equivalent—trace origin to consumer or fault-inject it.
3. **Check negative and recovery paths.** Include restart/replay, stale cache, duplicate/idempotent calls, partial failure, rollback, and concurrent execution when relevant.
4. **Run an adversarial review.** Ask what an opposing reviewer would grep for, which origin was missed, and which claim lacks failure-path evidence.
5. **Limit claims.** State untraced behavior as unverified or follow-up work, even if compilation and success-path tests pass.

## Git and review

- Preserve dirty-tree changes that are outside scope.
- Do not modify remote state without explicit user authorization.
- When asked to commit, follow the checkout's DCO and commit-message instructions exactly.
- When drafting a PR, use the repository title type and issue/design-document requirements; keep the body non-empty and assert only verified benefits.
