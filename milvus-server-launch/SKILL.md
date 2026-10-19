---
name: milvus-server-launch
description: Launch, stop, switch, and health-check a local Milvus standalone server via Docker Compose. Two variants are provided — a stable 2.6 release (milvusdb/milvus:v2.6.25) and a 3.0 release (milvusdb/milvus:v3.0.3) — each with its own docker-compose.yml and milvus.yaml. Use when the user asks to start/restart/stop a local Milvus server, switch between the 2.6 and 3.0 standalone deployments, check whether the local Milvus is healthy, or reset local Milvus data. Also use whenever another skill or workflow needs a live local Milvus standalone instance (e.g. real-run verification against localhost:19530).
---

# Launch Local Milvus Standalone Server

Each variant is a self-contained Docker Compose project (etcd + MinIO + Milvus
standalone) with its own `milvus.yaml` mounted into the container.

## Layout

- `2.6/` — `milvusdb/milvus:v2.6.25`
- `3.0/` — `milvusdb/milvus:v3.0.3`

Both variants mount `<variant>/milvus.yaml` to `/milvus/configs/milvus.yaml`
and persist data under `<variant>/volumes/`. That `volumes/` directory is
created on startup and holds runtime data (etcd, MinIO, and Milvus files) —
it is gitignored and must never be committed.

## Critical rule: variants are mutually exclusive

Both compose projects use the **same fixed container names**
(`milvus-etcd`, `milvus-minio`, `milvus-standalone`), the **same ports**
(19530, 9091, 2379, 9000/9001), and the same `milvus` Docker network.
Only one variant can run at a time. **Never start a second server while one
is already running.**

## Auto-switch policy (decide before doing anything)

Always start from the *requested variant* (what the caller needs: `2.6` or
`3.0`), then inspect what is actually running:

```bash
docker ps --filter name=milvus-
```

A running `milvus-standalone` container is identified by its image tag
(`milvusdb/milvus:v2.6.25` → `2.6` variant, `milvusdb/milvus:v3.0.3` → `3.0`
variant). Then decide:

| Running variant | Requested variant | Action |
|---|---|---|
| `2.6` (healthy) | `3.0` | **Auto-switch**: `cd 2.6 && docker compose down`, then start `3.0`. Do not ask. |
| `3.0` (healthy) | `2.6` | **Do NOT switch.** Reuse the running `3.0` server — 3.0 is backward compatible and supports every 2.6 feature. |
| same as requested | same as requested | Reuse; do nothing. |
| nothing running | either | Start the requested variant. |
| any variant, unhealthy | either | Do not start another instance. Report and inspect `docker logs milvus-standalone --tail 100` first. |

A server is healthy when `curl -sf http://localhost:9091/healthz` prints OK.

## Start a variant

```bash
cd milvus-server-launch/2.6     # or milvus-server-launch/3.0
docker compose up -d
```

Wait for health (compose healthcheck has a 90s start period):

```bash
curl -sf http://localhost:9091/healthz   # prints OK when ready
```

When healthy, Milvus is reachable at `localhost:19530`.

If stray `milvus-etcd`/`milvus-minio` containers linger from a previous run,
`cd` into the variant directory that owns them and `docker compose down`
first (their data volumes are preserved).

## Common operations

```bash
# Follow server logs
docker compose logs -f standalone

# Stop (data under ./volumes is preserved)
docker compose down

# Full data reset for this variant (destroys that variant's local data)
docker compose down && rm -rf volumes
```

## Troubleshooting

- **Port/name conflicts on start** — the other variant (or a stale container)
  is still up; `docker ps --filter name=milvus-`, then `docker compose down`
  in the owning variant's directory.
- **Health check failing after ~90s** — inspect
  `docker compose logs --tail 100 standalone` and confirm etcd/MinIO are
  healthy (`docker ps --filter name=milvus-`).
- **Config changes** — edit `<variant>/milvus.yaml`, then
  `docker compose restart standalone` (the file is bind-mounted, no rebuild
  needed).
