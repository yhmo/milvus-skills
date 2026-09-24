---
name: milvus-restful
description: Analyze and modify the Milvus RESTful (high-level) API service, implemented in `internal/distributed/proxy/httpserver/` inside the `milvus-io/milvus` repository (preferred checkout, typically `$HOME/work/git-go/milvus`). Use for the v1 (`/v1/vector/*`) and v2 (`/v2/vectordb/*`) HTTP endpoints, gin route registration and middleware chains (timeout, DQL admission, restful-size, trace ID, idempotency), JSON request parsing (`request.go`/`request_v2.go`) and the `code`/`message`/`data` response envelope with int64/JSON/Array rendering, request/result conversion in `utils.go`, HTTP configuration (`pkg/util/paramtable/http_param.go`), restful metrics (`pkg/metrics`), the route-to-gRPC mapping (`routeToMethod`), and repository-consistent reviews or fixes. Do not use for the proxy gRPC path (proxy to coordinators), for other components' HTTP handlers, or for client-side REST SDK work (PyMilvus, Node HttpClient, Java HttpClient) unless the server contract is the subject.
---

# Milvus RESTful API Service

The Milvus high-level RESTful API is served by the Proxy component as a gin HTTP server rooted inside the
`milvus-io/milvus` repository, not in a standalone repo. Use this skill only for the server-side REST implementation in
`internal/distributed/proxy/httpserver/` and its configuration/metrics. Do not use it for gRPC or client SDKs.

## Start every task

1. Resolve the repository root from the current directory; otherwise locate the checkout on this machine (for example `$HOME/work/git-go/milvus`).
2. Confirm it with `git rev-parse --show-toplevel` and `git remote -v`, and confirm the httpserver package at `$ROOT/internal/distributed/proxy/httpserver`.
3. Check `git branch --show-current`, `git status --short`, and the relevant upstream branch before assuming API behavior.
4. Preserve unrelated user changes. Use focused edits; never hand-edit generated files.
5. Search with `rg`, or run `scripts/api-trace.sh`; do not infer a route or handler from filenames alone.
6. **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.

## Load the relevant reference

Read each selected reference completely before acting:

- Architecture and dataflow: [references/technical-details.md](references/technical-details.md)
- Package and file routing: [references/source-layout.md](references/source-layout.md)
- Build, test, and lint: [references/build-and-test.md](references/build-and-test.md)
- Endpoint catalog and wire contract: [references/api-surface.md](references/api-surface.md)

For architecture or implementation work, normally read both `technical-details.md` and `api-surface.md`.

## Core workflows

### Trace an endpoint end-to-end

1. Run `scripts/api-trace.sh SYMBOL` from the milvus repo root (`SYMBOL` can be a route, e.g. `search`, or a handler,
   e.g. `handleSearch`).
2. Find the route string in `constant.go` (both the v2 category + action constants and the v1 `Vector*Path` constants),
   then its registration in `RegisterRoutesToV2`/`RegisterRoutesToV1`.
3. Note the middleware chain applied at registration: DQL endpoints (query/get/search/advanced_search/hybrid_search) pass
   `dqlAdmission`; entity data ops pass `restfulSizeMiddleware`; every v2 route passes `timeoutMiddleware` + `wrapperPost`.
4. Trace the handler: request type from `request.go`/`request_v2.go` then through `wrapperPost` decode/validation,
   the handler body, the `h.proxy.Method(ctx, req)` gRPC call, result conversion, then
   `HTTPReturn`/`HTTPAbortReturn`/`HTTPReturnStream`.
5. Verify against tests (`handler_v2_test.go`, `utils_test.go`, etc.) and the gRPC method it maps to via `routeToMethod`.

### Diagnose or change code

1. Decide whether the change is route/registration, middleware, request parsing, handler logic, or result conversion
   (`utils.go`). Keep each concern in its file.
2. Add a new v2 endpoint by: a new `Category`/`Action` constant in `constant.go`, a `RegisterRoutesToV2` entry in
   `handler_v2.go`, a request type in `request_v2.go` (implement `requestutil.DBNameGetter`/`CollectionNameGetter`), a
   handler that calls the right `types.ProxyComponent` RPC, and a `routeToMethod` entry for metrics.
3. Follow the response envelope: always build `gin.H{HTTPReturnCode: ..., HTTPReturnMessage: ..., HTTPReturnData: ...}`
   and ship it with `HTTPReturn` (or `HTTPAbortReturn` for early rejects, `HTTPReturnStream` for large bodies).
4. When changing JSON rendering of fields (int64, JSON, Array), check the `proxy.http.*` switches (`AcceptTypeAllowInt64`,
   `NativeJSONResponse`, `LegacyArrayResponse`, `CompatibilityMode`) before hardcoding a shape.
5. When changing error classification, read the repo error-handling guide; keep `merr` codes intact through the envelope.
6. Update focused tests beside the affected area. Unit tests use a `mockProxyComponent` (embed `types.ProxyComponent` and
   stub only the RPCs exercised). Run the narrowest suite first; never assume the repo-root test command works without tags.

## Compatibility rules

- v1 (`HandlersV1`, `/v1/vector/*`) is legacy and slated for deprecation; new work goes to v2 (`HandlersV2`, `/v2/vectordb/*`).
  Keep v1 behavior stable unless the task explicitly deprecates an endpoint.
- The v2 surface is the contract documented at https://milvus.io/api-reference/restful/v3.0.x/ (and v2.6.x/v2.5.x for
  maintenance branches). Changing a route, a request field, or a response field is a breaking change; verify the
  maintenance-branch behavior from source on the matching `2.x` branch, not from `master`.
- Do not hand-edit generated files. The httpserver package imports `milvus-proto/go-api/v3` protos and internal
  `milvus/pkg/v3` protos; proto changes are made upstream and regenerated.

## Conventions for committing and PRs

- When committing, use `git commit -sm 'message'` so the committer's email address is recorded; every commit in this
  repository must carry a Signed-off-by trailer.
- When creating a pull request, ensure each PR contains exactly one commit.

## Validation

- Prefer the narrowest relevant test first: `go test -tags dynamic,test -gcflags="all=-N -l" -count=1 ./internal/distributed/proxy/httpserver/... -run TestXxx`.
- State explicitly when a live Milvus instance or e2e was required and skipped.
- Run `scripts/validate-skill.sh` after changing this skill package.
- Prefer `path:line` references in technical explanations.

## Scripts

Run helpers from the milvus repo root (the script locates paths itself). `$SKILL_DIR` is this skill's base directory —
the directory that directly contains both `SKILL.md` and `scripts/` — as exposed by the host agent that loaded the skill
(or locate it yourself); never hardcode a `.opencode` or other agent-specific prefix.

```bash
"$SKILL_DIR/scripts/api-trace.sh" search
"$SKILL_DIR/scripts/validate-skill.sh"
```

## Related repositories

The RESTful service is server-side; related surfaces live in other skills. Local checkout paths follow the author's
machine layout; on other machines the repos may live elsewhere or be absent, so confirm with
`git rev-parse --show-toplevel` before relying on them:

- Milvus server (gRPC, proxy internals): `$HOME/work/git-go/milvus` (`milvus` skill)
- PyMilvus REST client: `$HOME/work/git-go/pymilvus` (`pymilvus` skill)
- Node.js SDK HTTP client: `$HOME/work/git-go/milvus-sdk-node` (`milvus-sdk-node` skill)
- Java SDK HTTP client: `$HOME/work/git-go/milvus-sdk-java` (`milvus-sdk-java` skill)
