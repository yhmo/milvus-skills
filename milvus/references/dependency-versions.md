# Pinned native dependency versions

Milvus does not always consume `knowhere`, `cardinal`, `milvus-common`, and `milvus-storage` from the branch checked out in `$HOME/work/git-go`. The integrated native build has its own pins. When tracing or reviewing code across these repositories, first derive the exact version from the Milvus commit under review and read that dependency at that commit.

## Dependency graph

```text
milvus-io/milvus internal/core
├── zilliztech/knowhere at KNOWHERE_VERSION
│   └── zilliztech/cardinal at CARDINAL_VERSION, only when Cardinal is enabled
├── milvus-io/milvus-storage at milvus-storage_VERSION
└── zilliztech/milvus-common
    ├── master/3.0: Conan package requirement in internal/core/conanfile.py
    └── 2.6: FetchContent pin in internal/core/thirdparty/milvus-common/CMakeLists.txt
```

The dependency graph alone is not a version source of truth. Paths and variable names can differ by Milvus branch, so read the files at the exact Milvus ref.

## Resolve pins from an exact Milvus ref

Use `git show` against a verified Milvus commit, upstream remote-tracking ref, or PR head SHA. Do not use the current contents of a dirty or unrelated checkout without checking `git status` and the ref.

### Knowhere

```bash
git -C "$MILVUS_REPO" show \
  "$MILVUS_REF:internal/core/thirdparty/knowhere/CMakeLists.txt" |
  rg 'KNOWHERE_VERSION|GIT_REPOSITORY'
```

This file uses FetchContent with `GIT_TAG ${KNOWHERE_VERSION}`. The value may be either a short commit SHA or a tag depending on the Milvus branch. Resolve it in the repository named by `GIT_REPOSITORY` before reading Knowhere code.

If the trace reaches Cardinal, fetch Knowhere's `CMakeLists.txt`, `conanfile.py`, and the applicable Cardinal wrapper at the just-resolved Knowhere ref. Cardinal is selected by `WITH_CARDINAL`; Milvus enables it when `INDEX_ENGINE=cardinal`, and it is not part of the default engine build.

```bash
gh api -H 'Accept: application/vnd.github.raw' \
  "repos/zilliztech/knowhere/contents/cmake/libs/cardinal/v1/CMakeLists.txt?ref=$KNOWHERE_REF"
gh api -H 'Accept: application/vnd.github.raw' \
  "repos/zilliztech/knowhere/contents/cmake/libs/cardinal/v2/CMakeLists.txt?ref=$KNOWHERE_REF"
```

Read `CARDINAL_VERSION`, `CARDINAL_REPO_URL`, and the `WITH_CARDINAL` selection from those exact files. Cardinal has both v1 and v2 wrappers on current Knowhere lines. Also note that Knowhere caches a cloned Cardinal working tree and only force-checkouts the requested version when `CARDINAL_VERSION_FORCE_CHECKOUT` is enabled; a stale build cache is not evidence of the reviewed Cardinal version. Resolve the Cardinal tag/commit explicitly before reading source.

### milvus-storage

```bash
git -C "$MILVUS_REPO" show \
  "$MILVUS_REF:internal/core/thirdparty/milvus-storage/CMakeLists.txt" |
  rg 'milvus-storage_VERSION|GIT_REPOSITORY'
```

The current wrapper uses FetchContent with `GIT_TAG ${milvus-storage_VERSION}` and builds the dependency's `cpp/` source subdirectory. Resolve the commit/tag in the repository named by `GIT_REPOSITORY` before tracing storage behavior.

### milvus-common

On `master` and `3.0`, resolve the integrated Conan requirement:

```bash
git -C "$MILVUS_REPO" show \
  "$MILVUS_REF:internal/core/conanfile.py" |
  rg 'milvus-common/'
```

The requirement has the form:

```text
milvus-common/<package-version>-<source-commit-prefix>@milvus/dev#<recipe-revision>
```

The source-commit prefix identifies the `zilliztech/milvus-common` commit to inspect; the Conan recipe revision is also part of the binary-package identity. Resolve the short source commit to its full SHA before reading files. Do not substitute the standalone `milvus-common` requirement from Knowhere's own `conanfile.py`: a Knowhere commit may list a different version for standalone Knowhere development, while the integrated Milvus native build is anchored by Milvus's `internal/core/conanfile.py`.

On `2.6`, milvus-common is instead fetched from source through:

```text
internal/core/thirdparty/milvus-common/CMakeLists.txt
```

Read `MILVUS-COMMON-VERSION` and `GIT_REPOSITORY` at the exact Milvus 2.6 ref.

## Review and trace rules

1. Record the Milvus ref before resolving dependencies: checked-out commit, remote branch ref, or PR head SHA.
2. Extract each pin from that exact ref with `git show`; do not infer it from the preferred local dependency checkout or its current branch.
3. Resolve short SHAs and tags in the named upstream repository with `git rev-parse`, `git show`, or `gh api`.
4. Read dependency code at the resolved ref. If a local checkout contains that object, `git show <ref>:<path>` is preferred because it does not require switching a possibly dirty worktree. Otherwise fetch the file through `gh api` or use a clean temporary worktree.
5. When reporting cross-repository conclusions, cite both the Milvus ref and each resolved dependency ref.
6. Treat existing FetchContent/build caches as potentially stale. Build-cache source directories are not authoritative unless their `git rev-parse HEAD` exactly matches the extracted pin.
7. Do not compare a Milvus change against the `master`/`main` implementation of a pinned dependency when the pin points to a maintenance branch or older commit. First establish the dependency ref, then compare like with like.

## Example evidence format

```text
Milvus: 17d017a56bc073049aebbe8dada68bc9963a1115
Knowhere: 2868882b02fd31fb658e276b20ad4309446e8173
milvus-storage: e7f447763e6054be8c28f10cbe82b0bbfc43fe05
milvus-common: 7d67e14eae701d99227eed582e3af851fa51bee4 (Conan 1.0.0-7d67e14@milvus/dev)
```

The values above are only an example snapshot. Recompute them for every task; do not reuse them as skill constants.
