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
| `src/cachinglayer/LoadingOverhead.cpp` | absent | present |
| `Makefile` (top-level) | absent | present |
| `OWNERS` | absent | present |
| `docs/` | absent | present |

## Rules when on 2.6

1. Do not reference `LoadingOverhead.cpp` — it does not exist on this branch.
2. The `cachinglayer/` manager, `Executor`, `ListBatch`, and per-chunk
   policies are structurally the same on both branches.
3. If a task references a symbol not found on this branch, check whether it
   belongs to the `master` line and inform the user rather than guessing.
