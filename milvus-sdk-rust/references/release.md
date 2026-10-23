# Release

Use this reference for production release preparation, version bumps, release notes, crate packaging, and publish safety for the Milvus Rust SDK.

## Contents

- Release safety boundary
- Current repo state to verify
- Release history analysis
- Production release workflow
- Publishing workflow
- Yank / rollback guidance

All commands assume the current directory is the Milvus Rust SDK repo root unless stated otherwise.

## Release safety boundary

Never do these without explicit user confirmation for the exact version and command:

- `cargo publish`
- `cargo yank`
- creating or pushing git tags
- pushing branches
- creating GitHub releases
- modifying remote release state
- force-pushing release branches

Before any publish-like action, show:

- target version
- target branch/commit
- exact command
- expected external effect
- rollback/yank limitations

## Current repo state to verify

At the time this skill was written:

- Package version is in `Cargo.toml` under `[package]`.
- `CHANGELOG.md` records user-visible release contents and is the release-notes source of truth.
- `README.md` is the user-facing crate entry point; `DEVELOPMENT.md` owns maintainer setup, build,
  test, coverage, formatting, and protobuf-regeneration guidance.
- `.github/workflows/publish-release.yml` publishes tag-matched versions to crates.io, validates
  the standalone tutorials against the published crate, and then creates the GitHub release.
- The post-release job checks `tutorial/1_quickstart/Cargo.toml` for crates.io propagation before
  executing the complete dynamic tutorial set.
- No benchmark workflow was found.
- Generated protobuf bindings are emitted to Cargo `OUT_DIR`; `src/proto/mod.rs` is the tracked include glue.

Always verify current repo state before release work:

```bash
git status --short
git branch --show-current
git log --oneline --decorate -n 30
grep -n '^version' Cargo.toml
ls | grep -Ei 'change|release'
git ls-files Cargo.lock
git check-ignore tutorial/1_quickstart/Cargo.lock
git submodule status
```

## Release history analysis

Read `CHANGELOG.md` before inspecting commit diffs. Treat version-bump commits and commits named
`Prepare for vX.Y.Z` as release markers, not as the source of feature implementation.

Run the bundled helper from the Rust SDK repository root:

```bash
"$SKILL_DIR/scripts/release-window.sh" X.Y.Z
```

The helper lists release markers and prints the requested `CHANGELOG.md` entry. For implementation
detail, inspect commits between the adjacent release boundaries identified by tags, changelog
entries, version bumps, or release markers.

## Production release workflow

### 1. Confirm release scope

Clarify with the maintainer:

- release version, such as the next patch, minor, or major version
- release type: patch, minor, or major
- target branch
- whether this is release preparation only or actual publishing
- confirmation that `CHANGELOG.md` should be updated for the release
- whether to publish to crates.io
- whether to create/push a git tag

Do not infer publish approval from release-prep approval.

### 2. Inspect user-visible changes

Read the existing changelog first, then use git history and the current diff:

```bash
sed -n '1,240p' CHANGELOG.md
git status --short
git log --oneline --decorate <previous-release>..HEAD
git diff --stat <previous-release>..HEAD
```

If there is no clear previous release tag, inspect recent release marker commits or ask the maintainer for the comparison base.

Classify changes as:

- V1 compatibility changes
- V2 public request/response/type changes
- new public APIs
- breaking API changes
- bug fixes
- dependency/toolchain changes
- generated proto/API compatibility changes
- documentation/example changes
- internal-only changes

Derive release notes from the implementation commits in the release window. Do not copy commit
subjects mechanically, and do not infer the release contents only from a release-marker commit.

### 3. Choose the version with SemVer

Use Rust crate SemVer expectations:

- patch: compatible bug fixes and docs-only changes
- minor: backward-compatible public API additions
- major: breaking public API or behavior changes

For `0.x` crates, compatibility rules can be stricter in practice. Confirm the intended policy with the maintainer before a release that changes public API.

### 4. Update version metadata

On the current `main` line, use the repository's version-bump helper rather than editing the files
piecemeal:

```bash
./scripts/bump_version.sh X.Y.Z
```

It updates the root `Cargo.toml`, every `tutorial/*/Cargo.toml` exact dependency such as
`milvus-sdk-rust = "=X.Y.Z"`, and the existing tutorial README version references.

Older maintenance branches may not carry this helper; verify with `git ls-files
scripts/bump_version.sh` first. If it is absent, make the same focused edits manually and keep the
root crate and every tutorial pin on the target version.

All tutorial manifests must use the same exact version as the root package and release tag. This is
required because the post-release `run-tutorial` workflow resolves the tutorials from crates.io
rather than patching them to the repository checkout.

Use a focused audit after editing:

```bash
grep -n '^version' Cargo.toml
grep -R -n '^milvus-sdk-rust = ' tutorial/*/Cargo.toml
grep -R -n 'milvus-sdk-rust.*version' tutorial/*/README.md
```

After dependency/version work, inspect lockfile policy:

```bash
git ls-files Cargo.lock
git status --short Cargo.lock
```

Tutorial lockfiles are currently ignored/untracked even though local generated copies may exist.
Do not add them unless the maintainer explicitly changes that policy. If the policy changes and
they become tracked, regenerate them after changing the exact SDK version.

### 5. Update `CHANGELOG.md`

For every release preparation, add a new entry near the top of `CHANGELOG.md` using the existing
repository format:

```markdown
## milvus-sdk-rust X.Y.Z (YYYY-MM-DD)

### Breaking change

- ...

### Feature

- ...

### Improvement

- ...

### Bug

- ...
```

Only include sections that have entries. Preserve the blank-line style already used by the Rust
changelog.

Do not classify a newly deprecated but still callable API or enum variant as a breaking change.
Put that deprecation under `Improvement` and name the replacement or migration path. For example,
deprecating `ConsistencyLevel::Customized` while it still encodes and decodes as proto value 4 is
not a breaking change. Classify an item as breaking only when it is removed, renamed without a
compatible alias, has an incompatible signature or type, or changes previously valid behavior in a
way that requires callers to change code. If deprecation is accompanied by such a change, split
the deprecation notice and the incompatible change into separate entries.

Changelog entries must be concise and user-visible. Include, when applicable:

- breaking API or behavior changes with migration guidance;
- new public APIs and supported Milvus capabilities;
- user-visible improvements to behavior, performance, reliability, or ergonomics;
- bug fixes visible to SDK users;
- dependency, toolchain, MSRV, TLS, packaging, or runtime requirement changes;
- generated proto/API changes when they alter user-visible compatibility;
- tested or required Milvus server versions when relevant.

Do not list every internal refactor, test addition, CI cleanup, or code movement unless it changes
the user experience. Do not update `CHANGELOG.md` during ordinary implementation work unless the
user explicitly requests release preparation or a changelog edit.

### 6. Generated proto consistency

This repo generates protobuf Rust files under Cargo `OUT_DIR` and includes them from `src/proto/mod.rs`.

If proto sources, `build.rs`, `prost`, `tonic-build`, `protoc`, or vendored-protoc configuration changed, rebuild and validate compilation:

```bash
cargo clean
cargo build
cargo check --all-targets
```

Inspect generated output under `target/*/build/milvus-sdk-rust-*/out` when diagnosing field/RPC changes, but do not commit or edit it.

Do not manually edit generated files for release cleanup. Change proto/codegen inputs instead.

### 7. Local validation before release PR

Run cheap checks first:

```bash
cargo fmt --all -- --check
cargo build
cargo build --examples
cargo test --no-run
cargo test --test v2_ut
./scripts/run_tests.sh --no-server
```

If tutorial Rust sources changed, also check formatting per standalone manifest:

```bash
for manifest in tutorial/*/Cargo.toml; do
  cargo fmt --manifest-path "$manifest" -- --check
done
```

Run targeted tests for changed areas. Examples:

```bash
cargo test --test v2_ut
cargo test --test utility -- --nocapture
```

Run the repository-managed full test suite only with approval to start Docker:

```bash
./scripts/run_tests.sh
```

For a focused server-backed test, let the script own the container lifecycle:

```bash
./scripts/run_tests.sh cargo test --test v2_st -- --nocapture
```

### 8. Crate package validation

Validate what will be uploaded to crates.io without publishing:

```bash
cargo package --list
cargo publish --dry-run
```

Review the package list for:

- required source files
- `README.md`
- `LICENSE` or `license-file`
- `src/proto/mod.rs`, `build.rs`, and the proto source/dependency inputs required to generate bindings
- no local-only artifacts, credentials, logs, or large build outputs
- no accidental `target/`, `.env`, or editor files

If `cargo publish --dry-run` fails, fix the underlying packaging or metadata issue instead of bypassing it.

### 9. Release PR preparation

A production release PR should usually include:

- version bump in `Cargo.toml`
- target-version pins in every `tutorial/*/Cargo.toml` and matching tutorial README text
- intentional generated proto updates, if any
- `CHANGELOG.md` entry for the target version
- README/docs updates for user-visible changes
- validation summary

Suggested PR test plan:

```markdown
## Test plan
- cargo fmt --all -- --check
- ./scripts/run_tests.sh --no-server
- cargo publish --dry-run
- ./scripts/run_tests.sh  # starts Docker and runs V1/V2 server suites
```

If a command was not run, say why.

### 10. Release-prep commit convention

Milvus SDK repos often use release marker commits such as:

```text
Prepare for vX.Y.Z
```

Do not assume this repo follows that convention unless git history confirms it. If it does:

- Treat release-prep commits as release markers, not as the source of feature implementation.
- Inspect commits between release markers for implementation detail.
- Keep release-prep changes separate from feature implementation changes.

A release-prep commit should normally contain only version, changelog, README, and other release
metadata changes. Avoid mixing feature implementation into it.

## Publishing workflow

Only perform this section after explicit maintainer approval.

The current repository uses a tag-driven workflow. For a normal release, do **not** run
`cargo publish` manually: publishing first would make the version immutable and then make the
tag-triggered workflow fail on the duplicate upload, potentially preventing the tutorial and
GitHub-release jobs from running.

### 1. Final release-state checks

Verify clean release state:

```bash
git status --short
git branch --show-current
grep -n '^version' Cargo.toml
cargo publish --dry-run
```

Confirm the commit being published is the intended release commit.

Also confirm the release commit is already on `main` or the intended numeric release branch with
the required CI checks successful; the workflow rejects a tag that does not satisfy those gates.

### 2. Trigger the tag-driven publication

Show and confirm the exact version, commit, and tag command before mutating remote state:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

Pushing the stable tag starts `.github/workflows/publish-release.yml`. Do not create or push the
tag without explicit confirmation.

Only run `cargo publish` manually if a maintainer explicitly requires bypassing the workflow. In
that case, also confirm how the GitHub release and post-release tutorial validation will be created
without re-triggering the duplicate publish. If authentication is missing, ask the user to run
login/token setup themselves. Do not ask for or store crates.io tokens.

### 3. Post-release verification

After publishing, verify:

- crate version appears on crates.io
- docs.rs build starts or completes
- GitHub release/tag state matches project policy
- README install command still works for the released crate name/version
- the post-release `run-tutorial` job resolves the published crate and runs every tutorial against
  Milvus

If docs.rs fails, inspect build logs and prepare a follow-up fix rather than republishing the same version. Crate versions cannot be overwritten on crates.io.

The tag-driven `.github/workflows/publish-release.yml` performs these phases in order:

1. validate tag ancestry and required CI checks, check formatting, and run the tutorials against
   the local checkout;
2. validate the tag, root crate version, every tutorial dependency pin, and changelog entry; run
   library and V2 unit tests; then dry-run and publish the crate;
3. retry `cargo check` on `tutorial/1_quickstart/Cargo.toml` up to 20 times at 15-second intervals
   while crates.io propagates, then run `scripts/run_tutorials.sh`, which starts Milvus and executes
   every tutorial under `tutorial/`;
4. create the GitHub release only after the published-crate tutorial run succeeds.

## Yank / rollback guidance

Rust crates.io versions cannot be deleted or overwritten after publish.

If a bad version is published, the usual mitigation is yanking:

```bash
cargo yank --vers X.Y.Z
```

Yanking prevents new dependency resolution to that version but does not remove the crate or break existing lockfiles. Only yank with explicit maintainer confirmation.

A fixed release usually requires a new version, such as `X.Y.(Z+1)`.
