# Branch differences: 2.6 vs 3.0 vs main

The other references describe the `main` baseline. The maintenance branches
differ only in top-level project files; the `cpp/`, `python/`, `java/`, and
`rust/` source trees are identical across branches. Read this overlay when
working on a maintenance branch.

Confirm the branch first:

```bash
git branch --show-current
```

## Differences

| Path | 2.6 | 3.0 | main |
| --- | --- | --- | --- |
| `Makefile` | absent | present | present |
| `codecov.yml` | absent | present | present |
| `docs/` | absent | present | present |
| `tests/` (top-level) | absent | present | present |
| `examples/` | absent | absent | present |
| `.gitattributes` | absent | present | present |

The `cpp/`, `python/`, `java/`, and `rust/` source trees are identical on
all three branches — no source-level overlay is needed.

## Rules when on a maintenance branch

1. Do not reference the files listed above as present — check the branch
   column first.
2. On `2.6`, build/test commands that rely on the top-level `Makefile` do
   not apply; use the per-language build system directly.
3. If a task references a symbol not found on this branch, check whether it
   belongs to the `main` line and inform the user rather than guessing.
