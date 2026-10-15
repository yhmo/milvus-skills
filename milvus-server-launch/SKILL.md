---
name: milvus-server-launch
description: Launch, stop, switch, and health-check a local Milvus standalone server via Docker Compose. Two variants are provided — a stable 2.6 release (milvusdb/milvus:v2.6.25) and a master nightly build (milvusdb/milvus:master-*) — each with its own docker-compose.yml and milvus.yaml. Use when the user asks to start/restart/stop a local Milvus server, switch between the 2.6 and master standalone deployments, check whether the local Milvus is healthy, or reset local Milvus data. Also use whenever another skill or workflow needs a live local Milvus standalone instance (e.g. real-run verification against localhost:19530).
---

# Launch Local Milvus Standalone Server

Each variant is a self-contained Docker Compose project (etcd + MinIO + Milvus
standalone) with its own `milvus.yaml` mounted into the container.

## Layout

- `2.6/` — `milvusdb/milvus:v2.6.25`
- `master/` — `milvusdb/milvus:master-20260825-dd1ee671` (nightly)

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

## Pre-start check (mandatory)

Before any `docker compose up -d`, check whether a Milvus server (plus its
etcd/MinIO) is already running — this includes servers started from outside
this skill:

```bash
docker ps --filter name=milvus-
```

Then decide:

- **A Milvus server container is up and healthy**
  (`curl -sf http://localhost:9091/healthz`) → **do NOT start anything.**
  Reuse the running server and tell the user which one is active (the image
  tag identifies the variant). If it is not the variant the user wanted, ask
  before switching — never stop a healthy server on your own initiative.
- **A Milvus server container is up but unhealthy** → report the failure and
  inspect `docker logs milvus-standalone --tail 100` before considering a
  restart; do not blindly start another instance.
- **Nothing Milvus-related is running** → proceed to start the requested
  variant. If stray `milvus-etcd`/`milvus-minio` containers linger from a
  previous run, `cd` into the variant directory that owns them and
  `docker compose down` first (their data volumes are preserved):

  ```bash
  cd <owning-variant-dir> && docker compose down
  ```

## Start a variant

```bash
cd milvus-server-launch/2.6     # or milvus-server-launch/master
docker compose up -d
```

Then wait for health (compose healthcheck has a 90s start period):

```bash
curl -sf http://localhost:9091/healthz   # prints OK when ready
```

When healthy, Milvus is reachable at `localhost:19530`.

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
