# Release

Use this reference for release preparation, version bumps, NuGet packaging, and publish safety for the Milvus C# SDK.

## Contents

- Release safety boundary
- Current repo state to verify
- Version sources
- Changelog
- NuGet packaging
- Publishing workflow
- Pre-release validation checklist

All commands assume the current directory is the Milvus C# SDK repo root unless stated otherwise.

## Release safety boundary

Never do these without explicit user confirmation for the exact version and command:

- `dotnet pack` / `dotnet nuget push`
- creating or pushing git tags
- pushing branches
- creating GitHub releases
- modifying remote release state

Before any publish-like action, show the target version, target branch/commit, exact command, and
expected external effect.

## Current repo state to verify

At the time this skill was written:

- `Version.props` contains the default build/package version and is imported via
  `Directory.Build.props`. During release preparation, set it to `X.Y.Z-beta.1` for the next stable
  release `X.Y.Z`. The stable publishing workflow later rewrites it to `X.Y.Z` from the `vX.Y.Z` tag.
- `CHANGELOG.md` records user-visible release history; it is the release-notes source of truth.
- Two NuGet packages are produced: `Milvus.Client` (V1) and `Milvus.Client.V2` (V2). Both multi-target
  `net8.0;netstandard2.0;net462`.
- `.github/workflows/NugetPublish.yml` is the tag-driven NuGet publishing workflow (triggered by `v*.*.*`
  tags). It verifies the tag points at a commit already on a remote branch with green CI and a matching
  CHANGELOG entry (`scripts/extract_changelog.sh`), builds `-c Release`, packs the two SDK projects to
  `Artifacts/`, logs in via NuGet Trusted Publishing (OIDC), pushes packages + symbols to nuget.org with
  `--skip-duplicate`, then creates the GitHub release.
- `.github/workflows/Build.yml` is the CI build/test workflow.

Always verify current repo state before release work:

```bash
git status --short
git branch --show-current
git log --oneline --decorate -n 30
cat Version.props
ls | grep -Ei 'change|release'
git submodule status
```

## Version sources

- `Version.props`: the default package version used by both projects. Treat the Git tag as the
  authoritative version for a release.
- `Milvus.Client.V2.csproj`: `PackageId=Milvus.Client.V2`, `AssemblyName`, `RootNamespace`.
- `CHANGELOG.md`: user-facing release history.
- Git tags such as `vX.Y.Z`: published version markers.

## Release version bump

When preparing a new release, determine the next stable version `X.Y.Z` and set `Version.props` to the
prerelease form of that version:

```xml
<Project>
  <PropertyGroup>
    <Version>X.Y.Z-beta.1</Version>
  </PropertyGroup>
</Project>
```

Important:

- Omit the leading `v` from `Version.props`. The Git tag is `vX.Y.Z`, but the MSBuild/NuGet version is
  `X.Y.Z`; the publishing workflow validates the tag version after stripping `v`.
- Use `X.Y.Z-beta.N` only if multiple beta validation packages are needed; otherwise use `beta.1`.
- This keeps local release-validation packages clearly distinct from the previous stable package while
  README and `CHANGELOG.md` can continue to describe the upcoming stable `X.Y.Z` release.
- The current `NugetPublish.yml` accepts stable `vX.Y.Z` tags only. Do not push a `vX.Y.Z-beta.N` tag
  unless the workflow is explicitly changed to support prerelease publishing.

## Changelog

`CHANGELOG.md` is the source of truth for user-visible release contents. When preparing a release:

1. Read the existing changelog before adding an entry.
2. Add a new heading near the top using the current V2 format:

   ```markdown
   ## milvus-sdk-csharp X.Y.Z (YYYY-MM-DD)

   ### Breaking Change

   - ...

   ### Feature

   - ...
   ```

   Include only sections that have entries. Do not use the legacy bullet format
   `- YYYY-MM-DD **X.Y.Z**` for a new release: `scripts/extract_changelog.sh` recognizes version
   headings, not legacy bullet entries.
3. Keep ordinary feature and bug-fix work out of `CHANGELOG.md` unless the user explicitly asks for
   release preparation or a changelog update.
4. Derive entries from implementation commits since the preceding release, not only version-bump or
   marker commits.

## NuGet packaging

Build and pack locally for artifact validation:

```bash
dotnet build -c Release
dotnet pack -c Release -o Artifacts
```

Inspect `Artifacts/*.nupkg` / `*.snupkg` and verify:

- required source files and the package README are included;
- no local-only artifacts, credentials, logs, or build outputs are packed;
- `TreatWarningsAsErrors` is satisfied (warnings fail the build).

The projects set `PublishRepositoryUrl`, `IncludeSymbols` (`snupkg`), and `EmbedUntrackedSources` in
`Directory.Build.props`, so packages carry source-link and symbol metadata automatically.

### Local package versions

Outside release preparation, do not edit `Version.props` merely to make a local test package look
current. Override the version on the command line:

```bash
local_version="2.6.1-local.$(date +%Y%m%d%H%M%S)"
dotnet pack -c Release -o Artifacts -p:Version="$local_version"
```

This produces clearly distinguishable local artifacts, such as `Milvus.Client.V2.2.6.1-local.20261020...`
and its symbol package, without dirtying the source tree. Verify the resulting nupkg version with
`ls Artifacts` or by inspecting the package metadata.

During release preparation, `dotnet pack -c Release -o Artifacts` should produce `X.Y.Z-beta.1`
packages from the version bump described above.

## Publishing workflow

Only perform this section after explicit maintainer approval.

The tag-driven `NugetPublish.yml` workflow performs these phases in order:

1. Validate: check out the tag (`submodules: recursive`, `fetch-depth: 0`) and verify the tag's commit is
   already on some remote branch (main, 2.6, ...) with a green CI run on that commit — a tag can never
   publish code that did not pass the required checks.
2. Set the package version from the tag: install `dotnetCampus.TagToVersion` and run
   `dotnet TagToVersion -t <tag> -f Version.props`, then assert the tag version equals the resulting
   `Version.props` version and that a matching CHANGELOG entry exists (`scripts/extract_changelog.sh`).
3. `dotnet build -c Release`.
4. `dotnet pack Milvus.Client/Milvus.Client.csproj` and `Milvus.Client.V2/Milvus.Client.V2.csproj`
   (release config) into `Artifacts/` — examples/test projects are not packaged.
5. NuGet login via Trusted Publishing (OIDC, `NuGet/login@v1`) which issues a temporary API key.
6. `dotnet nuget push Artifacts/*.nupkg` and `Artifacts/*.snupkg` to nuget.org with `--skip-duplicate`
   (idempotent re-runs).
7. Create the GitHub release from the extracted changelog, with the compatible Milvus version in the body.

If publishing manually, confirm authentication and use the repository's `nuget.config` source mapping.

## Pre-release validation checklist

1. Confirm the release branch and cleanly separate unrelated user changes.
2. Inspect the previous tag/marker and all commits in the release window.
3. Set `Version.props` to `<Version>X.Y.Z-beta.1</Version>` for the next stable version `X.Y.Z`.
4. Update `CHANGELOG.md`, README compatibility/NuGet version metadata, and consumer examples or
   tutorials when their pinned package version is part of the release preparation. Unless explicitly
   preparing a beta release, user-facing docs should reference the upcoming stable `X.Y.Z`, not
   `X.Y.Z-beta.1`.
5. Run the test suites (unit, mock integration, and server-backed system when authorized).
6. Build `-c Release` and run `dotnet pack` to validate artifacts; verify the artifact version is
   `X.Y.Z-beta.1`.
7. Do not mutate remote state (tags, branches, NuGet, GitHub releases) without explicit authorization.
