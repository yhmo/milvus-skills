# Release

Use this reference for release preparation, changelog summaries, tags, package workflows, and release-window analysis.

## Version sources

- `CHANGELOG.md`: user-facing release history.
- `README.md`: Milvus/SDK compatibility table and current consumption instructions.
- `src/impl/version.h.in`: template for the SDK version compiled into the library.
- `MILVUS_SDK_VERSION`: build override passed through `scripts/build.sh`/CMake.
- Git tags such as `vX.Y.Z`: published version markers.

If no version override is supplied, CMake uses the latest reachable tag. For a release artifact, build the exact tag and
pass the intended version explicitly.

## Branches and release markers

- `master` is the active development line.
- Legacy release lines (such as `2.6`) are maintained separately.
- Release preparation commits normally use `Prepare for vX.Y.Z`.

Inspect before editing:

```bash
git branch --show-current
git status --short
git tag --list 'v*' --sort=-version:refname | head
git log --oneline --decorate --grep='Prepare for v' --all
"$SKILL_DIR/scripts/release-window.sh" vX.Y.Z
```

Treat marker commits as metadata boundaries, not as the source of feature implementation. For release notes, inspect the
commits between adjacent markers/tags and summarize user-visible changes.

## Changelog style

Current sections use:

```markdown
## milvus-sdk-cpp X.Y.Z (YYYY-MM-DD)
### Feature
- ...

### Improvement
- ...

### Bug
- ...
```

Include only sections that have entries. Keep wording concise and user-facing; mention breaking package target changes,
required Milvus configuration, or compatibility changes explicitly.

## Package identity

Current source/package consumption uses:

```cmake
find_package(milvus_sdk CONFIG REQUIRED)
target_link_libraries(app PRIVATE milvus_sdk::milvus_sdk)
```

The built library is named `milvus_sdk`; CPack artifacts are named `libmilvus-<version>-<arch>-<distro>` and are written
under `cmake_build/Pack`.

Conan metadata uses:

- recipe name: `milvus-sdk-cpp`;
- CMake package name: `milvus_sdk`;
- CMake target: `milvus_sdk::milvus_sdk`;
- library: `milvus_sdk`.

## GitHub release flow

Current workflows:

- `.github/workflows/create-release.yaml` runs on exact `vX.Y.Z` tag pushes, creates/updates the GitHub release, and
  dispatches `release.yaml` with the same tag.
- `.github/workflows/release.yaml` is manually dispatchable, validates the tag, builds selected platform packages, and
  checks out `needs.select-targets.outputs.tag` in every build job. Package source therefore comes from the exact tag.
- `.github/workflows/notify-conanfiles.yaml` dispatches the tag and resolved commit to `milvus-io/conanfiles`.

When changing these workflows, preserve repository context for `gh`, exact-tag checkout, platform matrix selection,
package verification, and artifact attachment semantics.

## Local preparation and verification

Typical release build:

```bash
MILVUS_SDK_VERSION=X.Y.Z JOBS=4 bash scripts/build.sh -f -u -t Release
cmake --build cmake_build --target package --parallel 4
```

`-f` prevents the release build from formatting and mutating the source tree. Verify package contents with the platform
script before considering artifacts ready:

```bash
sh scripts/verify_package_linux.sh cmake_build/Pack
```

Ask before packaging if it is materially expensive, and always ask before publishing, pushing a tag, creating/updating a
release, uploading artifacts, or dispatching another repository.

## Release-prep checklist

1. Confirm the release branch and cleanly separate unrelated user changes.
2. Inspect the previous tag/marker and all commits in the release window.
3. Update `CHANGELOG.md`, compatibility/version metadata, and any release note required by the user.
4. Verify README linking instructions still match `milvus_sdk::milvus_sdk`.
5. Build/test in proportion to the change with at most four jobs.
6. Verify generated package contents and CMake consumer smoke tests.
7. Do not mutate remote state without explicit authorization.
