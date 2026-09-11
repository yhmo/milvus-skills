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

- Package version is in `Version.props` (`<Version>X.Y.Z</Version>`), imported via `Directory.Build.props`.
- `Changelog.md` records user-visible release history; it is the release-notes source of truth.
- Two NuGet packages are produced: `Milvus.Client` (V1) and `Milvus.Client.V2` (V2). Both multi-target
  `net8.0;netstandard2.0;net462`.
- `.github/workflows/NugetPublish.yml.disabled` contains the tag-driven NuGet publishing workflow; it
  is currently disabled. When enabled, it derives the package version from the git tag via
  `dotnetCampus.TagToVersion` (`-f Version.props`), builds `-c Release`, packs to `Artifacts/`, and
  pushes to nuget.org.
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

- `Version.props`: the package version used by both projects.
- `Milvus.Client.V2.csproj`: `PackageId=Milvus.Client.V2`, `AssemblyName`, `RootNamespace`.
- `Changelog.md`: user-facing release history.
- Git tags such as `vX.Y.Z`: published version markers.

## Changelog

`Changelog.md` is the source of truth for user-visible release contents. It lists dated version
entries with feature/fix bullet points. When preparing a release:

1. Read the existing changelog before adding an entry.
2. Add a new dated entry near the top following the repository's existing format, e.g.
   `- YYYY-MM-DD **X.Y.Z**` with concise user-visible bullets.
3. Keep ordinary feature and bug-fix work out of `Changelog.md` unless the user explicitly asks for
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

## Publishing workflow

Only perform this section after explicit maintainer approval.

The tag-driven `NugetPublish.yml.disabled` workflow (when enabled) performs these phases in order:

1. Checkout with `submodules: recursive` and `fetch-depth: 0`.
2. Set the version from the git tag into `Version.props` via `dotnetCampus.TagToVersion`.
3. `dotnet build -c Release`.
4. `dotnet pack -c Release -o Artifacts`.
5. Upload `Artifacts/*.nupkg` and `*.snupkg`.
6. `dotnet nuget push Artifacts/*.nupkg --api-key ${{ secrets.NugetKey }} --source https://api.nuget.org/v3/index.json`.

If publishing manually, confirm authentication and use the repository's `nuget.config` source mapping.

## Pre-release validation checklist

1. Confirm the release branch and cleanly separate unrelated user changes.
2. Inspect the previous tag/marker and all commits in the release window.
3. Update `Changelog.md` and any version metadata.
4. Run the test suites (unit, mock integration, and server-backed system when authorized).
5. Build `-c Release` and run `dotnet pack` to validate artifacts.
6. Do not mutate remote state (tags, branches, NuGet, GitHub releases) without explicit authorization.
