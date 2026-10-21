---
name: milvus-storage
description: Analyze and modify the `milvus-io/milvus-storage` repository, whose preferred local checkout is typically `$HOME/work/git-go/milvus-storage`. Use for the Milvus columnar storage engine: C++ core under `cpp/` (column groups, writer/reader, manifest/transaction, filesystem, FFI), Parquet/Vortex/Lance/Iceberg formats, cloud backends (S3/GCS/Azure/Aliyun/Tencent/Huawei/Talon), Python/Java/Rust/C++ bindings, Conan 2 + CMake build and test workflows, benchmarks, integration/stress tests, releases, and repository-consistent reviews or fixes.
---

# Milvus Storage

Work in the standalone `milvus-io/milvus-storage` repository. Do not use this skill for the Milvus server, Conanfiles,
or a client SDK except when comparing behavior.

## Start every task

1. Locate the repository checkout in this order: `$HOME/work/git-go/milvus-storage` when it exists on this machine; a directory named `milvus-storage` among the parent directories of the current working directory; `/home/runner/work/milvus-storage/milvus-storage` (GitHub Actions runner `$GITHUB_WORKSPACE`).
2. Confirm it with `git rev-parse --show-toplevel` and `git remote -v`. `source` is the upstream `milvus-io/milvus-storage`
   remote; `origin` is usually the user's fork.
3. Check `git branch --show-current`, `git status --short`, and the relevant upstream branch before assuming behavior.
4. Read repository-level `AGENTS.md` files if present; preserve unrelated user changes.
5. Classify the request as explanation, diagnosis, targeted change, cross-component change, or generation before acting.
   Do not implement a fix for a diagnosis-only request.
6. Search with `rg` or run `scripts/api-trace.sh`; do not infer an implementation path from filenames alone.
- **Version branch model**: `main` is the active development line; `3.0` and `2.6` are the current released maintenance lines. The `cpp/`, `python/`, `java/`, and `rust/` source trees are identical across branches — differences are limited to top-level project files (`2.6` lacks `Makefile`, `codecov.yml`, `docs/`, `tests/`, and `examples/`; `3.0` additionally lacks `examples/`). See [references/branch-differences.md](references/branch-differences.md).
- **Branch overlay**: the other references describe the `main` baseline. If `git branch --show-current` returns `3.0` or `2.6`, read [references/branch-differences.md](references/branch-differences.md) for top-level files that differ. On `2.6`, build/test commands that rely on the top-level `Makefile` do not apply — use the per-language build system directly (`cpp/Makefile` for C++).
7. **Stale-working-tree guard**: the checked-out branch (even after `git fetch`) may be old while fetched upstream refs are current. For analysis and tracing, prefer reading source pinned to the relevant upstream branch — `git show refs/remotes/[remote]/[branch]:[path]` and `git ls-tree -r --name-only refs/remotes/[remote]/[branch] [dir]` — where `[remote]` is the remote that points at the native repo (milvus-io or zilliztech), whether it is named `source` or `origin`; confirm it with `git remote -v`, and check the branch set with `git branch --show-current`. Fetch the native remote first when freshness matters (`git fetch [remote]`), because remote-tracking refs can themselves be stale. Before editing, make sure the working tree is on the intended branch and in sync; never edit blindly on an old branch.

## Load the relevant reference

- Read [references/technical-details.md](references/technical-details.md) for architecture layers, source layout, the
  FFI (`extern "C"`) boundary and error taxonomy, format and filesystem layers, and change checklists.
- Read [references/build-and-test.md](references/build-and-test.md) before configuring, building, testing, linting, or
  debugging CI. C++ builds go through Conan 2 + CMake via the `cpp/Makefile`.
- Read [references/branch-differences.md](references/branch-differences.md) when working on the `3.0`/`2.6` maintenance
  branches.
- Read [references/examples.md](references/examples.md) before changing or running benchmarks or examples.
- Read [references/release.md](references/release.md) for version preparation, package metadata, tags, and release
  workflows.

## Repository rules

- The C++ core in `cpp/` is authoritative; every other language reaches it through the FFI layer (`extern "C"`
  functions declared under `cpp/include/milvus-storage/`, mostly `ffi_*_c.h`). Keep FFI headers, implementations under
  `cpp/src/ffi/`, and language bindings synchronized.
- C++20 is the required language level (`CMAKE_CXX_STANDARD 20`). Dependencies come from Conan 2 packages declared in
  `cpp/conanfile.py`, resolved from the `milvus01.jfrog.io` remote.
- The Rust format bridge at `cpp/src/format/bridge/rust` (Vortex/Lance formats) is always built. Preserve its feature
  gating (`s3-crt-async`, `talon`) and Cargo.lock. Never hand-edit generated bridge headers.
- With `WITH_PYTHON_BINDING`, only FFI symbols are exported via the version scripts `cpp/ffi_exports.map`
  (Linux) and `cpp/ffi_exports_mac.map` (macOS); add new FFI symbols there when Python packaging is affected.
- Preserve the error taxonomy: C error codes are `loon_errcode_*` in `cpp/include/milvus-storage/ffi_c.h`, mapped in
  `cpp/src/common/extend_status.cpp`. Do not bypass the `scripts/error_handling_ratchet.sh` baseline
  (`scripts/error_handling_baseline.tsv`).
- Prefer focused tests: gtest `milvus_test`, the C FFI tests `Test_FFI`, then Python integration/stress tests. Ask
  before running cloud-provider tests, Talon integration tests, or anything that starts Docker or mutates remote state.
- Do not commit, push, publish, start external services, or run destructive workflows unless the user authorizes it.
- When committing, use `git commit -sm '<message>'` so the committer's email address is recorded; every commit in this
  repository must carry a Signed-off-by trailer.
- When creating a pull request, ensure each PR contains exactly one commit.

## Bindings at a glance

- Python (`python/milvus_storage/`): ctypes wrapper `_ffi.py` plus per-domain modules; managed with `uv`.
- Java/Scala (`java/`): JNI bindings backed by `cpp/src/jni/`, Scala 2.13 sbt build; native libraries are staged under
  `java/native/linux-x86_64` for packaging.
- Rust (`rust/`): DataFusion `TableProvider` crate over the FFI (`rust/src/ffi.rs`), distinct from the format bridge in
  `cpp/src/format/bridge/rust`.

## Helpers

Run bundled helpers from the skill base directory. `$SKILL_DIR` is this skill's base directory — the directory that
directly contains both `SKILL.md` and `scripts/` — as exposed by the host agent that loaded the skill (or locate it
yourself); never hardcode a `.codex`, `.opencode`, or other agent-specific prefix.

```bash
"$SKILL_DIR/scripts/api-trace.sh" SegmentWriter
"$SKILL_DIR/scripts/validate-skill.sh"
```

## Typical triggers

- Trace how a write, scan, or column-group read flows through the storage engine into Parquet/Vortex/Lance.
- Diagnose manifest/transaction, filesystem, chunk-management, or FFI error-mapping behavior.
- Add or fix an FFI entry point and its Python/Java/Rust binding.
- Build/test with the `cpp/Makefile` (Conan 2 + CMake), investigate CI, or run benchmarks.
- Prepare a release, update the Rust format bridge, or review a milvus-storage PR.
