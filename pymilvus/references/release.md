# Release and publish

Use this for release/version/publishing questions. Never publish or modify remote release state without explicit user confirmation.

## Branches and remotes

For the local PyMilvus repo (for example at `$HOME/work/git-go/pymilvus`), `master` is the active development line and additional
major release branches are maintained for prior release lines. Verify the current branch set with `git branch -a`.

Version branch model: `master` targets the newest supported Milvus major (currently 3.0); `2.6` (and older `2.x`) branches
serve the previous server lines, and a `3.0` branch exists today for 3.0-line stabilization (it tracks `master` until the
dev line moves to a newer Milvus major such as 3.1/4.0).

The `source` git remote points to upstream `milvus-io/pymilvus`:

```bash
git remote -v
# source  git@github.com:milvus-io/pymilvus.git (fetch)
# source  git@github.com:milvus-io/pymilvus.git (push)
```

When release branch or upstream state matters, verify with:

```bash
git remote -v
git branch -a
```

The `.github/workflows/update-milvus-pymilvus-dev.yml` schedule maintains branch pairs for the current release lines,
confirming which lines are active.

## Packaging system

PyMilvus uses `pyproject.toml` with the `hatchling` build backend and dynamic SCM versioning:

```toml
[build-system]
requires = [
  "hatchling>=1.27,<1.28",
  "setuptools_scm[toml]>=8",
  "vcs-versioning<2",
]
build-backend = "hatchling.build"

[project]
name = "pymilvus"
requires-python = ">=3.9"
dynamic = ["version"]

[tool.hatch.version]
source = "code"
path = "pymilvus/_version.py"
expression = "get_version()"
```

Build package artifacts locally with:

```bash
uv build --sdist --wheel --out-dir dist/ .
# or
make package
```

Install local editable package with:

```bash
uv sync
```

## Versioning

Dynamic versioning is implemented in `pymilvus/_version.py`, which builds on `setuptools_scm` with a custom `rc_version_scheme` and `{guessed}rc{distance}` formatting. `vcs-versioning` is pinned below 2.x because 2.x changes `.dev0` handling away from PyMilvus' intended dev line.

Observed behavior:

- Exact tags produce the tag version.
- Release or maintenance branches named like `2.6` or `3.0` produce patch/rc-style next versions when the branch minor matches the latest tag minor.
- Development branches produce the next minor version with an `rc` distance suffix.
- A dev-line checkout version looks like `vX.Y.Z.dev0-N-g<hash>`, i.e. a dev line after the latest tag. The `-N-g<hash>` suffix drifts with every commit; expect a new distance rather than a fixed string.

When answering version questions, prefer verifying with:

```bash
make version
# or
uv run --no-project --with "hatchling>=1.27,<1.28" --with "setuptools-scm[toml]>=8" --with "vcs-versioning<2" python -m hatchling version
```

## TestPyPI publishing

Workflow file: `.github/workflows/publish_dev_package.yml`.

Trigger:

- Push to `master`.

Behavior:

1. Checkout.
2. Fetch history and tags for SCM versioning.
3. Set up Python 3.13 and `astral-sh/setup-uv`.
4. Build sdist and wheel with `uv build` into `dist/`.
5. Validate with `twine check` and `check-wheel-contents` via the `release` dependency group.
6. Publish to TestPyPI with `uv publish --index testpypi --trusted-publishing always`.

Do not manually push to `master` for publishing unless the user explicitly asks and confirms the scope.

## PyPI release publishing

Workflow file: `.github/workflows/publish_on_release.yml`.

Trigger:

- GitHub Release published.

Behavior:

1. Checkout.
2. Fetch history and tags for SCM versioning.
3. Set up Python 3.13 and `astral-sh/setup-uv`.
4. Build sdist and wheel with `uv build` into `dist/`.
5. Validate with `twine check` and `check-wheel-contents` via the `release` dependency group.
6. Publish to PyPI with `uv publish --trusted-publishing always` if the ref starts with `refs/tags`.

The workflow uses trusted publishing permissions (`id-token: write`).

## Release guidance rules

- Do not publish artifacts, create GitHub releases, push tags, push branches, or modify remote release state without explicit confirmation.
- Before advising on a release, verify current tags, branch, `pymilvus/_version.py`, and workflow files.
- Build locally with `make package` only when the user wants artifact validation.
- Treat TestPyPI publishing on `master` as shared remote state.
- Treat PyPI publishing on GitHub Release as production release state.
- No top-level CHANGELOG file was observed during skill authoring; verify current repo state before claiming where user-visible release notes live.

## Local release validation checklist

Before a release PR or release prep:

1. Verify branch and tag state.
2. Verify dynamic version output with `make version`.
3. Sync dev dependencies: `uv sync --group dev`.
4. Run lint: `make lint`.
5. Run coverage/tests: `make coverage` (unit) and, if desired, `make integration-lite`.
6. If proto changed, run `git submodule update --init`, `make gen_proto`, `make check_proto_product`.
7. Build artifacts: `make package`.
8. Inspect `dist/` artifacts if needed.
9. Do not publish unless explicitly confirmed.
