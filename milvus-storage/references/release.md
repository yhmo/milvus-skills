# Release

Use this reference for release preparation, version metadata, tags, package workflows, and release-note investigation.

## Version sources

- `cpp/conanfile.py`: recipe version (currently `0.1.0`); `cpp/CMakeLists.txt`: `project(milvus-storage VERSION 0.1.0)`.
- `python/pyproject.toml`: Python package version, overwritten by the release workflow.
- `java/build.sbt`: Java/Scala version (currently `0.1.0-SNAPSHOT`), overwritten by the release workflow.
- Git tags `vX.Y.Z` (and prerelease `vX.Y.Z-*`): published version markers.

Inspect before editing:

```bash
git branch --show-current
git status --short
git tag --list 'v*' --sort=-version:refname | head
git log --oneline --decorate --grep='Prepare for v' --all
```

Treat marker commits as metadata boundaries, not as the source of feature implementation. For release notes, inspect
commits between adjacent tags and summarize user-visible changes. Commit style in this repository is
`<type>: <summary> (#PR)` such as `enhance:`, `feat:`, `fix:`, `chore:`.

## GitHub release flow

`.github/workflows/release.yml`:

- Triggers on `workflow_dispatch` (with `version`, `publish_python` = none/testpypi/pypi, `publish_java` =
  none/github/maven-central/both, `skip_tests`) and on `vX.Y.Z` tag pushes.
- Python: `make python-lib`, copies `libmilvus-storage.so` into `python/milvus_storage/lib/`, sets the version in
  `pyproject.toml`, builds wheel + sdist, repairs the wheel with `auditwheel`, then publishes to TestPyPI or PyPI.
- Java: `make java-lib`, stages native libraries under `java/native/linux-x86_64` with
  `java/patch_native_runpath.sh` + `java/verify_native_dependencies.sh`, sets the version in `build.sbt`,
  `sbt test` (unless skipped), `sbt assembly package`, then publishes to GitHub Packages or Maven Central (via the
  Central Portal bundle upload).
- Creates a GitHub release with the Python wheels and Java jars attached. Python artifact group is `com.zilliz`
  `milvus-storage`; Java artifact is `com.zilliz:milvus-storage-jni`.

## Local preparation and verification

- Build and test in proportion to the change; run focused gtests before full suites.
- For Python packaging: `cd cpp && make python-lib`, copy the library, then `python -m build` and `auditwheel repair`.
- For Java: build the JNI lib, verify `libmilvus-storage-jni.so` with `java/verify_native_dependencies.sh`, then `sbt assembly package`.
- Never claim a package was published unless the publish step actually ran.

## Release-prep checklist

1. Confirm the release branch and cleanly separate unrelated user changes.
2. Inspect the previous tag and all commits in the release window; summarize user-visible changes by type.
3. Update version metadata where required (`cpp/conanfile.py`, `python/pyproject.toml`, `java/build.sbt`).
4. Verify README usage and the `libstorage.pc.in`/pkg-config output still match the build.
5. Build and test the exact tag locally when practical.
6. Do not mutate remote state (push tags, publish packages, create releases, dispatch workflows) without explicit
   authorization.
