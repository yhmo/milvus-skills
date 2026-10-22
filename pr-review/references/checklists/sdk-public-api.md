# Public SDK API review checklist

Load for any PR that adds or modifies a public API surface: SDK repositories
(pymilvus, milvus-sdk-*, or the `client/` module inside the milvus server
repo), and public modules/headers in other repos (milvus `pkg/`,
milvus-common `include/`, knowhere `include/knowhere/`, milvus-storage FFI).

## Hostile-caller probes

- Try at least 3 caller inputs: intended valid input, malformed-but-type-valid
  input, and omitted/empty input.
- Treat SDK setters and callback registration points as hostile boundaries
  even if internal code usually passes valid values.
- Check whether invalid strings silently fall back to defaults instead of
  returning an error.
- Check whether optional callbacks / `std::function` / function pointers are
  invoked without an emptiness check.
- Check whether a helper assumes a value came from another SDK call, even
  though callers can construct that value manually.
- **Misuse level**: for any newly added or modified public API surface, ask
  how a caller can misuse it with still-type-correct input.

## Backward compatibility

- **Semantics level**: for every changed public method, builder, option,
  callback, raw-param shim, or request flag, ask whether the PR changed what
  an existing caller means when they pass the same source code as before, or
  whether it breaks old caller patterns without an explicit migration path.
- For backward-compatibility shims and low-level param APIs (`add_param`,
  raw key/value lists, deprecated setters, compatibility helpers), verify the
  PR still honors old caller escape hatches and explicit opt-outs rather than
  only the new typed path.
- When a boolean or option used to mean "force/disable/default" something,
  verify that each prior caller-visible state is still representable after
  the refactor and that no branch became impossible to express.
- For refactored request flag derivation, verify that explicit caller
  opt-outs, compatibility params, and deprecated setters are still honored
  consistently across all request paths.

## Lifecycle and long-lived APIs

- Check whether operational policy matches API lifecycle: a timeout, deadline,
  retry rule, buffer limit, or batching policy that is reasonable for short
  requests may be wrong for incremental or long-lived work.
- When an API is open-ended, high-volume, user-paced, or callback-driven, ask
  whether shared client defaults can truncate output, stop progress early, or
  turn normal operation into a timeout/error path.
- Treat examples or docs that imply unbounded, resumable, or progressive
  behavior as evidence that the API may outlive ordinary request assumptions.

## End-to-end wiring

- For every newly added request parameter, option, or builder field, trace
  whether the feature is also wired through response parsing and exposed back
  through the public result type when the server can return corresponding data.
- When a feature is described as user-visible, verify the PR implements the
  full path end to end rather than only request construction or only internal
  plumbing.

## Wire serialization safety

- For values serialized onto the wire as strings, verify the format is stable
  and protocol-safe: locale-independent, precision-safe, and consistent with
  existing project helpers for the same data type.

## Public contract

- Treat examples, tests, and docs as part of the public contract: if they
  demonstrate a value or pattern the server rejects, count that as a real SDK
  issue, not just a test-only mistake.

## Cache and shared-state scoping

- For caches, memoized defaults, and shared maps introduced by the PR, ask
  whether state is scoped correctly per client / session / database /
  collection (or the domain's equivalent ownership scopes) rather than
  silently becoming process-global or cross-tenant.
- For shared mutable state introduced by the PR, ask whether one client,
  session, database, collection, or request can clear, overwrite, or reuse
  another scope's cached state, timestamps, memoized defaults, or progress
  counters.
