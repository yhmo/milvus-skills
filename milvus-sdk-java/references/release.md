# Release Workflow

Use this when the user asks about release history, `Prepare for vX.Y.Z` commits, or how to prepare a new version.

## Release history analysis

`CHANGELOG.md` is the source of truth for user-visible release contents.

`Prepare for vX.Y.Z` commits are release markers. They normally bump versions and update release docs. Do not treat them as the source of feature implementation.

Keep the shell working directory at the SDK repo root, and execute this skill's bundled script from the installed skill directory. The script discovers the repo with `git rev-parse --show-toplevel`.

Global skill install example:

```bash
"$SKILL_DIR/scripts/release-window.sh" X.Y.Z
```

For implementation detail, inspect commits between adjacent release markers.

## Prepare-for-version commit contents

A `Prepare for vX.Y.Z` commit usually changes only release metadata/docs:

- root `pom.xml` revision
- module or standalone Maven project versions if applicable
- `README.md` dependency snippets and compatibility matrix
- `CHANGELOG.md`
- generated/flattened release POM files if this repo tracks them

Avoid mixing feature implementation into this release-prep commit.

## Changelog expectations

For a new release, add a new entry near the top of `CHANGELOG.md` using the repo's existing format:

```markdown
## milvus-sdk-java X.Y.Z (YYYY-MM-DD)
### Feature
- ...

### Improvement
- ...

### Bug
- ...
```

Only include sections that have entries.

Use concise user-visible descriptions, not internal implementation details.

## Version update checklist

When preparing a release:

1. Find current version in root `pom.xml` `revision`.
2. Update version references in `README.md` install snippets and compatibility table.
3. Update `CHANGELOG.md` with fixes/features/improvements.
4. Check whether any standalone project POM version needs updating.
5. Run a build or the release-required validation requested by the maintainer.
6. Review diff to confirm no unrelated source changes are included.

## Maven publishing configuration

The root POM has release/publishing setup:

- release profile attaches sources, javadocs, and GPG signatures
- `maven-release-plugin` uses release profile and deploy goal
- `central-publishing-maven-plugin` publishes to Central with `autoPublish=true`
- snapshots point at Central Portal snapshots

The tag-driven workflow is `.github/workflows/publish-release.yaml`:

1. Its validation job checks that the tag commit is contained in `master` or a numeric release
   branch, resolves the PR that produced the commit, and requires successful `Build and test on
   ubuntu` and `Build and test on windows` checks on that PR's head commit.
2. Its publish job checks out the exact `vX.Y.Z` tag, verifies that the tag version matches the
   root `revision`, and requires a matching `CHANGELOG.md` entry.
3. It sets up Temurin Java 8 and Maven Central/GPG credentials, then deploys the Java 8 reactor
   (the parent POM, `sdk-core`, and `sdk-bulkwriter`) with tests skipped and waits for Central
   state `PUBLISHED`.
4. It switches to Temurin Java 17 and separately deploys `sdk-spring-boot-starter`; that module is
   excluded from the Java 8 reactor because Spring Boot requires Java 17.
5. Only after both Maven deployments succeed does it create/update the non-draft GitHub release.
6. Publishing that GitHub release triggers `.github/workflows/release_event.yml`, which dispatches
   `milvus-io/web-content` to refresh the published API reference.

When reviewing a release run, confirm both Maven deploy steps reached `successfully published`,
public Maven URLs resolve for `milvus-sdk-java`, `milvus-sdk-java-bulkwriter`, and
`milvus-sdk-java-spring-boot-starter`, the GitHub release job ran after the publish job, and the
web-content dispatch succeeded.

Do not run release publishing commands unless the user explicitly asks and confirms credentials/environment are ready.

## PR/review expectations

Contribution docs expect:

- issue filed for the reason/plan
- `CHANGELOG.md` updated
- PR targets current active branch
- PR description references the issue

Review docs expect PRs to have:

- DCO passed
- tests and coverage passed with `ci-passed`
- `lgtm` reviewer label
- `approved` approver label

Approver guidance expects a single squashed commit whose message starts with a capital letter and does not end with punctuation.

## Rules

- For release questions, read `CHANGELOG.md` before commit diffs.
- For release-prep edits, keep changes limited to versions/docs/release metadata unless the user requests otherwise.
- Do not publish to Maven Central or push tags without explicit user confirmation.
- Treat release tags and Maven coordinates as immutable. If Central accepted a deployment before a later step failed, reconcile external state before rerunning.
