---
name: milvus-conanfiles
description: Analyze and modify the `milvus-io/conanfiles` repository, whose preferred local checkout is typically `$HOME/work/git-go/conanfiles`, for Conan 2.x recipes used by Milvus C++ dependencies. Use for recipe creation or upgrades, config.yml and conandata.yml changes, Conan dependency/version tracing, patches and test_package work, local build verification, CI workflow changes, Artifactory testing or production publishing, ConanCenter synchronization, bulk Milvus dependency builds, and troubleshooting recipe or package failures.
---

# Milvus Conanfiles

## Repository

- This skill is for the `milvus-io/conanfiles` repository.
- Locate the repository checkout in this order:
  1. `$HOME/work/git-go/conanfiles` when it exists on this machine;
  2. a directory named `conanfiles` among the parent directories of the current working directory;
  3. `/home/runner/work/conanfiles/conanfiles` (GitHub Actions runner `$GITHUB_WORKSPACE`).
- Confirm the checkout with `git rev-parse --show-toplevel` and `git remote -v` before relying on it. Do not assume the preferred path exists or is the correct repository without verification.
- **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.
- When committing, use `git commit -sm '<message>'` so the committer's email address is recorded; every commit in this repository must carry a Signed-off-by trailer.

## Establish repository context

1. Confirm the working tree is the `milvus-io/conanfiles` repository by locating `recipes/`, `scripts/build-and-push.sh`, and `.github/workflows/`.
2. Read repository-level `AGENTS.md` files if present.
3. Read `README.md` and `PUBLISH_GUIDELINE.md` before changing publishing behavior or adding a recipe.
4. Read `MILVUS_DEPENS.md` when dependency versions, custom channels, build order, or Milvus compatibility are relevant.
5. Inspect the target recipe and one nearby recipe with a similar build system before implementing changes.
6. Treat current repository code as authoritative when documentation and scripts disagree.

Read [references/repository-workflows.md](references/repository-workflows.md) for the command paths, CI triggers, remotes, and known workflow constraints.

## Classify the task

- For analysis or diagnosis, inspect files and report evidence without modifying them.
- For a new recipe or version, update recipe metadata, build logic, tests, and patches as needed.
- For dependency changes, trace direct requirements, transitive ranges, Milvus `force=True` overrides, options, and custom-channel availability.
- For CI changes, trace the complete workflow-to-script path and preserve manual, PR, merge, and dispatch behavior.
- For publishing requests, distinguish validation from remote mutation. Do not upload unless the user explicitly requests publishing.
- For release preparation, verify the testing-to-production sequence and dependency order.

## Work with recipes

Use the existing layout selected by `recipes/<package>/config.yml`:

```text
recipes/<package>/
├── config.yml
└── <folder>/
    ├── conanfile.py
    ├── conandata.yml
    ├── patches/            # when required
    └── test_package/
```

When adding or upgrading a recipe:

1. Inspect every version-to-folder mapping in `config.yml`.
2. Add the source URL and verified SHA-256 to `conandata.yml`.
3. Use Conan 2 APIs only: `from conan import ConanFile` and `conan.tools.*` helpers.
4. Preserve recipe conventions for `settings`, `options`, `default_options`, validation, layout, source retrieval, generation, build, packaging, and component metadata.
5. Keep package requirements compatible with versions forced by Milvus. Use `@milvus/dev` only for recipes that intentionally differ from upstream.
6. Apply patches through `conandata.yml` and Conan 2 patch helpers when practical.
7. Add or update `test_package` so it links or consumes the exported package rather than merely checking files.
8. Avoid broad mechanical conversions when the recipe contains package-specific compatibility logic.

Search first with `rg`; do not assume all recipes use `all/conanfile.py`. Common alternatives include version-specific folders such as `v2024/`, `2.28.0/`, or `v2/`.

## Trace dependency compatibility

For any requirement or option change:

1. Inspect the target recipe's `requirements()`, `build_requirements()`, `tool_requirements()`, and conditional option handling.
2. Search consumers and overrides across `recipes/`, `MILVUS_DEPENS.md`, and build scripts.
3. Identify whether the package is expected from this repository, ConanCenter, `@milvus/dev`, or another custom channel.
4. Check build and host contexts independently, including `compiler.cppstd` and shared/static options.
5. Determine whether a new custom dependency must be published before the target recipe can resolve.
6. Update dependency documentation when the effective Milvus graph or build order changes materially.

Do not assume PR or merged-recipe automation exercises the options used by Milvus. Compare recipe defaults and workflow arguments with package-specific options in `scripts/build-milvus-deps.sh`; add an explicit Try Build or local build when shared/static mode or optional features differ.

Do not solve a range conflict by widening constraints blindly. Confirm compatibility against upstream build files, existing Milvus pins, and dependent recipes.

## Validate changes

Use validation proportional to the change:

1. Run syntax and metadata checks first:

```bash
git diff --check
conan export recipes/<package>/<folder>/conanfile.py --version=<version>
```

2. Build the recipe without uploading:

```bash
./scripts/build-and-push.sh <package> <version> \
  --conanfile <folder>/conanfile.py \
  --repository testing \
  --no-upload
```

3. Add `--user-channel milvus/dev` for a custom reference and pass required settings/options through `--extra-options`.
4. Use `--settings-mode runner-default` for runner-native Linux, ARM, or macOS checks. Use `linux-gcc-11` only when matching the established Linux package configuration is intended.
5. Run focused recipe tests before broad bulk builds. Use `scripts/build-milvus-deps.sh` only when the dependency graph or coordinated package set warrants it.
6. Report the exact commands, environment assumptions, and failures. Never claim an upload occurred from a `--no-upload` build.

The normal single-recipe build path defaults to C++20, while bulk dependency and ConanCenter synchronization paths use C++17. Pass the intended standard explicitly when compatibility matters.

## Handle CI workflows

When modifying `.github/workflows/` or `scripts/`:

1. Trace input handling from the workflow into its script.
2. Preserve shell array argument construction so user inputs remain single arguments.
3. Keep Conan pinned consistently unless the task explicitly upgrades it.
4. Include relevant recipe, script, and workflow files in cache keys.
5. Preserve PR concurrency cancellation and bounded timeouts.
6. Check whether path filters and Mergify rules must change with the workflow.
7. Verify permissions are minimal but sufficient for checkout, PR inspection, workflow dispatch, or merge.
8. Treat repository-dispatch payloads and PR text as untrusted input; retain validation and quoting.

## Publish safely

Remote uploads are external state changes. Perform them only when explicitly authorized.

For custom recipes, follow this order:

1. Build locally or through Try Build without upload.
2. Publish the feature branch to the testing repository.
3. Verify the recipe revision and metadata in testing.
4. Merge into `master` after review and CI.
5. Publish from `master` to production.
6. Publish new custom dependencies before their dependents in both repositories.

Use `scripts/sync-to-artifactory.sh` only to mirror an upstream ConanCenter package and its resolved binaries. Use `scripts/build-and-push.sh` for repository recipes; it uploads recipe revisions only.

Never expose `JFROG_USERNAME2`, `JFROG_PASSWORD2`, or bot tokens in commands, logs, diffs, or responses. Do not bypass the production branch restriction.

## Review checklist

Before handing off a change, confirm:

- The requested version maps to an existing recipe folder.
- Source URLs and checksums match the intended release or commit.
- The recipe uses Conan 2 APIs and preserves package IDs and options.
- Custom user/channel references are deliberate and resolvable.
- Tests exercise the exported package.
- CI target detection will select the changed version.
- Verification covers the shared/static mode and optional features that Milvus actually uses, or the remaining gap is reported.
- The chosen C++ standard and build/host settings are explicit where needed.
- No upload was performed unless explicitly requested.
- Documentation reflects material dependency or workflow changes.
- Unrelated user changes remain untouched.
