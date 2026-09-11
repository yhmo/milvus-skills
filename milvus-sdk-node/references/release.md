# Release Workflow

Use this reference when the user asks about release history, version bumps, npm publishing, or how to prepare a new SDK release.

## Version and compatibility

- The SDK version lives in `package.json` `version`; the target server line lives in `milvusVersion` (e.g. `v3.0.0`).
- Compatibility with server lines is documented in `README.md` (Milvus 3.0 → SDK `3.0.x`, Milvus 2.6 → `2.6.x`, etc.) and in `docs/src/content/docs/reference/migration-compatibility.mdx`.
- Git tags follow `vX.Y.Z` (e.g. `v3.0.5`, `v2.6.17`, `v2.4.9`). `main` is the active line; `2.4`, `2.5`, `2.6`, and `v1.x` are maintenance branches with their own tags.

## Version bump convention

A release usually starts with a `chore: bump version to X.Y.Z` commit that only changes `package.json` `version` (see commit `854b78d` for `3.0.5`). Feature work stays in separate commits before the bump.

## User-visible release notes

- Release notes are written in `docs/src/content/docs/reference/release-notes.mdx` (not a root `CHANGELOG.md`).
- Each release section lists user-visible features/improvements/fixes and links to the GitHub compare URL (`compare/v<PREV>...v<NEXT>`).
- Documentation updates that describe new features usually land with or right after the feature commits (for example `docs: update guides for SDK 3.0.5`).
- Derive notes from implementation commits and docs diffs since the previous tag, not only from the version-bump commit.
- Keep ordinary feature/bug-fix work out of release metadata unless the user explicitly asks for release preparation.

## GitHub release and npm publishing (.github/workflows/release.yml)

The npm publish workflow is tag-driven (`release` event with `released`/`prereleased`, or manual `workflow_dispatch`):

1. Checks out the tag, runs `yarn`, `git submodule init`, `yarn pre`, `yarn proto:json`, `yarn build`.
2. For `workflow_dispatch` with `dry_run=true`, it only runs `npm publish --dry-run`.
3. Otherwise it computes the npm dist-tag:
   - `prerelease` → `next`
   - the tag equals the latest GitHub release → `latest`
   - otherwise → `release-X.Y` (e.g. `release-3.0`)
4. Publishes with `npm publish --tag <dist-tag>` using OIDC trusted publishing.

Do not publish, tag, or push without explicit user authorization.

## Rules

- For release questions, read `docs/src/content/docs/reference/release-notes.mdx` and `README.md` before commit diffs.
- For release-prep edits, keep changes limited to `package.json` version, docs release notes, and compatibility tables unless the user requests otherwise.
- Treat release tags and npm versions as immutable; reconcile external state before rerunning a failed publish.
- Confirm the intended npm dist-tag for the target line before publishing a maintenance-branch release.
