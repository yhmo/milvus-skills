# Branch differences: 2.6 vs master

The other references describe the `master` baseline. The `2.6` maintenance
branch differs minimally. Read this overlay in addition to the baseline
references when working on `2.6`.

Confirm the branch first:

```bash
git branch --show-current
```

## Differences

| Path | 2.6 | master |
| --- | --- | --- |
| `aquila/` | absent | present |
| `Makefile` | absent | present |
| `cmake/` | present | absent |
| `include/cardinal/version.h` | present (generated on master) | absent (build-generated) |

The `src/` and `include/` (aside from `version.h`) trees are identical.

## Rules when on 2.6

1. Do not reference the `aquila/` directory — it does not exist on this
   branch.
2. CMake configuration comes from `cmake/` (present on 2.6, absent on
   master where the Makefile drives configuration).
3. If a task references a symbol not found on this branch, check whether it
   belongs to the `master` line and inform the user rather than guessing.
