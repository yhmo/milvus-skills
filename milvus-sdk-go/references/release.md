# Go SDK Release

Versioning, tagging, and release preparation for the Go SDK.

## Version identity

- SDK version constant: `client/common/version.go` -> `common.SDKVersion` (currently `3.0.0`). Bumped in the same PR/commit
  that cuts a release.
- Go module path: `github.com/milvus-io/milvus/client/v3` (major version v3). Releases are consumed via `go get
  github.com/milvus-io/milvus/client/v3@vX.Y.Z`.
- The module is **not** a standalone repo: it is tagged inside the milvus repo using the `client/` prefix.

## Tags

- SDK releases are Git tags of the form `client/vX.Y.Z` on the `milvus-io/milvus` repo. Examples: `client/v2.5.x`,
  `client/v2.6.x`, `client/v3.0.0-beta`.
- `client/v2.6.x` tracks the Milvus 2.6 server line; `client/v3.0.0-beta` and later track 3.0 (`master`).
- Confirm the exact set of tags before release work:

```bash
git -C $ROOT tag -l 'client/*' | sort -V
```

## Release workflow

1. Confirm the target server/proto version the SDK should pair with (see build-and-test.md for the proto bump).
2. Bump `client/common/version.go` (`SDKVersion`) to the target release.
3. Optionally bump `tests/go_client/go.mod` dependency pins if e2e should track the released SDK.
4. Open a PR; follow repo conventions: PR type in `{feat|fix|enhance|test|doc|auto|build(deps)}:`, `-s` sign-off, DCO, and link
   the required issue/design-doc for `fix:`/`feat:`.
5. After merge, create and push the `client/vX.Y.Z` tag:

```bash
git tag client/vX.Y.Z <commit>
git push source client/vX.Y.Z
```

6. Do NOT create tags, push, or publish without explicit user authorization.

## Change summaries

Use `scripts/release-window.sh` to summarize what changed between the last SDK release and now. It prints release markers and
the commits touching `client/` (and `tests/go_client/`) since the given tag.

```bash
"$SKILL_DIR/scripts/release-window.sh" v2.6.4
```

## Dependency bump (milvus-proto)

Releases that need new server APIs first bump `github.com/milvus-io/milvus-proto/go-api/v3`:

```bash
make update-milvus-api PROTO_API_VERSION=<tag-or-commit>
```

from the repo root (see build-and-test.md). This updates `client/go.mod`, `pkg/go.mod`, `tests/go_client/go.mod`, and the root
`go.mod` together.

## Parity and compatibility

- Treat `client/v2.6.x` vs `client/v3.x` API surfaces separately when comparing with other SDKs (C++/Java/Rust have parallel
  `2.6`/`master` lines). `/home/myh/Videos/*lack*.md` notes (author-machine only) hold parity audits; source is authoritative.
- Public API is the option-pattern `milvusclient` surface. Do not remove or change signatures in a patch/minor release without
  a deprecation story.
