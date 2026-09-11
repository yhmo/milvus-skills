# Repository workflows reference

## Contents

- [Repository model](#repository-model)
- [Single-recipe build and publish](#single-recipe-build-and-publish)
- [ConanCenter synchronization](#conancenter-synchronization)
- [Bulk Milvus dependency build](#bulk-milvus-dependency-build)
- [PR verification](#pr-verification)
- [Merged PR publishing](#merged-pr-publishing)
- [Try Build](#try-build)
- [Release dispatch automation](#release-dispatch-automation)
- [Mergify labels](#mergify-labels)
- [Artifactory and credentials](#artifactory-and-credentials)
- [Operational constraints](#operational-constraints)

## Repository model

- Repository purpose: maintain Conan 2.x source recipes for Milvus C++ dependencies.
- Recipe registry: `recipes/<package>/config.yml` maps versions to recipe folders.
- Recipe source metadata: `conandata.yml` holds URLs, SHA-256 values, and patch declarations.
- Recipe implementation: `conanfile.py` uses Conan 2 APIs.
- Consumer validation: `test_package/` builds a small package consumer.
- Custom packages normally use `@milvus/dev`; Arrow has historically used `@milvus/dev-2.6`.
- `MILVUS_DEPENS.md` records the resolved Milvus dependency graph, force overrides, custom packages, and phased build order.

## Single-recipe build and publish

Entry point: `scripts/build-and-push.sh`.

Inputs:

- package and version
- `--conanfile`, default `all/conanfile.py`
- `--user-channel`
- `--extra-options`
- `--settings-mode linux-gcc-11|runner-default`
- `--repository production|testing`
- `--no-upload`

Execution path:

1. Change to the repository root.
2. Resolve production or testing remote configuration.
3. Reject production uploads outside `master` or branches matching `3.x`.
4. Add production at remote index 0 and testing at index 1.
5. Export every version listed by local `recipes/*/config.yml` into the Conan cache. Export failures are currently ignored.
6. Run `conan create` with `--build=missing`, selected settings, six jobs, channel flags, and extra options.
7. Save the JSON build graph.
8. Generate a package list with `conan list --graph`.
9. If uploading, authenticate and run `conan upload --list ... --only-recipe`.
10. If the target revision was newly uploaded, set JFrog properties on its exported `conanfile.py` using the storage REST API.

Default settings:

- `linux-gcc-11`: GCC 11, `libstdc++11`, C++20 host/build, Release.
- `runner-default`: detected compiler/architecture, C++20 host/build, Release.
- `CMAKE_POLICY_VERSION_MINIMUM=3.5` for CMake 4 compatibility.

Build metadata:

- `build.branch`
- `build.commit`
- `build.datetime`
- `build.author`

GitHub workflow: `.github/workflows/build-and-push.yml`.

- Manual `workflow_dispatch` only.
- Runner: Ubuntu 22.04.
- Python 3.13 and Conan 2.25.1.
- C++ standard is parsed from `extra_options`, defaulting to 20.
- Conan package cache is keyed by runner, C++ standard, recipes, script, and workflow.
- JFrog credentials come from repository secrets.

## ConanCenter synchronization

Entry point: `scripts/sync-to-artifactory.sh`.

Use this path for an upstream package that should be mirrored without a custom local recipe.

Execution path:

1. Run `conan install --requires=<package>/<version>` with GCC 11, `libstdc++11`, C++17, Release.
2. Capture the JSON install graph.
3. Generate a graph-scoped package list.
4. Authenticate to the selected remote.
5. Upload recipes and binaries for the target and every resolved transitive dependency.

GitHub workflow: `.github/workflows/sync-to-artifactory.yml`.

- Manual dispatch.
- Selects production or testing.
- Uses `JFROG_USERNAME2` and `JFROG_PASSWORD2`.

## Bulk Milvus dependency build

Entry point: `scripts/build-milvus-deps.sh`.

- Builds the repository's coordinated Milvus dependency set in dependency order.
- Uses GCC 11, `libstdc++11`, C++17 host/build, Release, and six jobs.
- Uses `conan create --build=missing` for each explicit recipe.
- Some application recipes skip `test_package` with `-tf=""`.
- Applies Milvus-specific options for shared libraries and enabled features.
- Builds custom packages with their required user/channel.
- `--upload` uploads each explicitly built recipe to production with `--only-recipe`.
- It does not graph-scope the upload and does not attach build metadata.
- ConanCenter-only dependencies are resolved as missing packages but are not included in the explicit upload list.

Use this script sparingly: it is a full coordinated build, not the default verification path for one recipe.

## PR verification

Workflow: `.github/workflows/pr-verify-recipes.yml`.

Triggers on changes under:

- `recipes/**`
- `scripts/build-and-push.sh`
- `scripts/pr-detection.py`
- the verification workflow itself

Behavior:

1. Check out full history.
2. Install Python 3.13, Conan 2.25.1, and PyYAML.
3. Parse `recipe-verify-cppstd=<value>` from the PR body; default to C++20.
4. Run `scripts/pr-detection.py` against the base SHA.
5. Build every selected target with `build-and-push.sh`, `runner-default`, testing selection, and `--no-upload`.
6. Pass the selected standard for both host and build contexts.

Detection rules:

- New `config.yml` version: select that version.
- Changed folder mapping: select that version.
- Changed `conandata.yml`: select versions whose `sources` or `patches` entries changed.
- Other file under a recipe folder: select the highest version mapped to that folder.
- Duplicate package/version/folder targets are removed.
- A missing mapped `conanfile.py` fails detection.

The job uses PR-scoped concurrency and cancels superseded runs.

## Merged PR publishing

Workflow: `.github/workflows/publish-merged-recipes.yml`.

- Trigger: merged PR into `master` through `pull_request_target`.
- Uses GitHub API PR file data and the merge commit to run the same target detector.
- Reuses the PR body C++ standard marker.
- Dispatches `build-and-push.yml` on the base branch for each target.
- Selects production and sets `user_channel=milvus/dev` for every detected target.
- Dispatch calls are issued sequentially, but the resulting workflows are not awaited.

Consequences:

- A recipe intended without a user/channel may be published as `@milvus/dev` by this path.
- Multiple new custom packages with dependency relationships may race. Publish dependencies separately or change the automation to wait for completion in topological order.

## Try Build

Workflow: `.github/workflows/try-build.yml`.

Supported runners include Ubuntu x86, Ubuntu ARM, and macOS.

- Manual dispatch.
- Select `runner-default` for native runner compilers and architecture.
- Select `linux-gcc-11` only on a compatible Linux runner when matching established settings.
- Parses C++ standard from `extra_options`, defaulting to 20.
- Invokes `build-and-push.sh` with testing selection and `--no-upload`.
- Cache keys include runner, settings mode, C++ standard, recipes, script, and workflow.

## Release dispatch automation

Workflow: `.github/workflows/update-recipe-from-dispatch.yml`.

Trigger: repository dispatch event type `recipe-release`.

Supported source repositories are encoded in `scripts/update-recipe-from-dispatch.py`, including Milvus Common, Milvus C++ SDK, Knowhere, Cardinal, and Milvus Storage.

Execution path:

1. Validate bot token availability.
2. Validate source repository, tag format, and 40-character commit SHA.
3. Download the tag archive and calculate SHA-256.
4. Insert the new version into `config.yml` and `conandata.yml`, or accept an identical existing entry.
5. Run `git diff --check` and `conan export` as `@milvus/dev`.
6. Create or update a signed-off automation PR containing the C++ standard marker.
7. Poll for the `verify recipe versions` and `DCO` checks.
8. Rebase-merge and delete the branch after both checks succeed.
9. The merged-PR workflow then dispatches production publication.

The bot token is necessary because PRs created with the default workflow token do not reliably trigger downstream workflows.

## Mergify labels

Configuration: `.github/mergify.yml`.

- Add `needs-dco` when DCO fails and `dco-passed` when it succeeds.
- Add `ci-passed` when recipe verification succeeds.
- Add `ci-passed` automatically for changes outside recipe-verification paths.
- Remove `ci-passed` while required verification is not successful.

Update these path expressions when changing which files affect recipe verification.

## Artifactory and credentials

Production Conan remote:

- Name: `default-conan-local2`
- Endpoint: `https://milvus01.jfrog.io/artifactory/api/conan/default-conan-local2`

Testing Conan remote:

- Name: `testing2`
- Endpoint: `https://milvus01.jfrog.io/artifactory/api/conan/testing2`

Credentials:

- `JFROG_USERNAME2`
- `JFROG_PASSWORD2`
- `CONANFILES_BOT_TOKEN` for automation PR creation and merging

Never print credential values. Prefer workflow secrets or environment variables over command-line literals.

## Operational constraints

- Production recipe uploads are allowed only from `master` or `3.x` release branches.
- Testing builds may still resolve dependencies from production because production is the higher-priority remote.
- Local export does not make a no-channel recipe satisfy an `@milvus/dev` requirement.
- Publish each new custom dependency before building its dependent package.
- Custom build uploads are recipe-only; consumers build binaries with their own profiles.
- ConanCenter synchronization uploads binaries and can therefore be profile-specific.
- Single-recipe workflows default to C++20; bulk and sync scripts currently use C++17.
- PR verification and merged-recipe publishing normally pass only C++ standard settings; they do not automatically reproduce package-specific options from `build-milvus-deps.sh` such as `shared=True` or enabled optional features.
- CMake 4 compatibility is enabled through `CMAKE_POLICY_VERSION_MINIMUM=3.5`.
- Preserve exact quoting around `--extra-options`; it contains multiple shell tokens interpreted by the called script.
