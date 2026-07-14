# Deployment plan: self-hosted Kubernetes

This document describes the proposed deployment architecture for
`nhl-legacy-fantasy`, covering both the maintainer's self-hosted cluster and
third-party self-deployment from the public repo.

## Core principle

**Decouple "publish artifacts" from "deploy to my cluster."** Publishing is
done from public CI and produces consumable artifacts (container images + Helm
chart). Deploying to a specific cluster is the cluster's responsibility,
handled by GitOps, so no cluster credentials ever touch GitHub Actions and
third parties can trivially deploy their own instances.

## Artifacts

- **Container images** — published to `ghcr.io/moults31/nhl-legacy-fantasy/*`
  on each semver tag (`vX.Y.Z` + git-sha). Two images:
  - `ghcr.io/moults31/nhl-legacy-fantasy/api` — Fastify backend + mule binary
  - `ghcr.io/moults31/nhl-legacy-fantasy/web` — nginx serving the Vite built
    frontend
- **Helm chart** — published as an OCI artifact to
  `oci://ghcr.io/moults31/nhl-legacy-fantasy/helm`. Third parties consume it
  with `helm install`.

## Dockerfile strategy

| App | Base | Builder stages | Notes |
|---|---|---|---|
| `apps/api/Dockerfile` | `node:22-slim` | 1. Rust builder: `cargo install roster-cli` from nhl-db-studio-mule git dep. 2. Node builder: `pnpm install` + `turbo build`. | `better-sqlite3` is a native module — use a glibc base (Debian-slim), not Alpine. Vanilla roster `.bin` is **never** baked into the image; it's mounted at runtime from a Secret. |
| `apps/web/Dockerfile` | `nginx:alpine` | Node builder: `pnpm install` + `vite build`. | Copies `dist/` into nginx html dir. |

`.dockerignore` files exclude `_local/`, `.cargo-bin/`, `node_modules/`, and
`data/*.db` from the build context.

## Helm chart (`deploy/helm/nhl-legacy-fantasy/`)

Published as an OCI artifact to ghcr.io on release. Key templates:

| Template | What it creates |
|---|---|
| `api-deployment` | Single-replica Deployment for the API. Sets `VANILLA_ROSTER_BIN` env from the roster Secret, `DATABASE_URL` to the PVC path, `CORS_ORIGIN` from values. |
| `api-*-pvc` | PersistentVolumeClaim for SQLite data (`/data/apps/api/data`). |
| `api-*-seed-job` | `post-install`/`post-upgrade` hook Job that runs `db:seed`. |
| `api-*-secret` | Creates a Secret from `api.vanillaRosterBin.content` (when supplied via `--set-file`) or references `api.vanillaRosterBin.existingSecret`. |
| `web-deployment` | nginx Deployment serving the built frontend. |
| `ingress` | Standard Ingress, hostname from values. |
| `configmap` | Shared env vars (API URL for web, etc.). |

### Vanilla roster `.bin` storage

User supplies the `.bin` via `--set-file api.vanillaRosterBin.content=./roster.bin`.
The chart creates a Secret from this content and mounts it in the api pod.
Advanced users can pre-create a Secret and pass its name as
`api.vanillaRosterBin.existingSecret`.

## Workflows

### `.github/workflows/release.yml`

Trigger: push of a semver tag (`v*`).

1. Build and push `api` and `web` images (SHA-pinned `docker/build-push-action`)
2. Package and push Helm chart as OCI artifact to ghcr.io
3. Create GitHub Release with changelog

### `.github/workflows/bump-argocd.yml`

Trigger: release published.

Commits updated image tag(s) to a **separate private `nlf-deploy` repo** (or a
`deploy/envs/prod/values.yaml` in this repo) that Argo CD watches. Argo CD
auto-syncs and performs the rollout. Review trade-off below.

## Maintainer deploy flow (Argo CD)

1. Push tag `v0.2.0`
2. `release.yml` publishes images + Helm chart
3. `bump-argocd.yml` updates the image tag in the deploy manifest
4. Argo CD (running in-cluster) detects drift → performs `helm upgrade` locally
5. No kubeconfig or cluster credentials ever touch GitHub Actions
6. Rollout is local to the cluster (same locality benefit as a self-hosted runner)

## Third-party self-deploy

One-command install:

```bash
helm install nlf oci://ghcr.io/moults31/nhl-legacy-fantasy \
  --version 0.2.0 \
  --set-file api.vanillaRosterBin.content=./roster.bin \
  --set ingress.host=nlf.example.com \
  --set api.corsOrigin=https://nlf.example.com
```

Third parties supply their own vanilla `.bin` (copyright-safe), own ingress
host/domain. Forks that build custom images override `api.image.repository`.

## Project-specific constraints

| Concern | Mitigation |
|---|---|
| **SQLite + multi-replica** | `api.replicaCount: 1`. SQLite data on a `PersistentVolumeClaim`. If scaling is ever needed, the DB layer must switch to Postgres. |
| **Mule binary at build time** | Rust stage runs `cargo install --git` during Docker build. The image is self-contained — end users never need Rust. |
| **Database seed** | Helm `post-install` hook Job runs `pnpm db:seed` against the same PVC. On upgrades the job is idempotent. |
| **CORS / ingress** | `CORS_ORIGIN` and ingress hostname are Helm values, not hardcoded. |

## Security for a public repo

- All GitHub Actions pinned by commit SHA, not by version tag.
- `permissions:` scoped to minimum; elevated (`packages: write`) only in the
  release job.
- No `latest` image tag — only explicit semver + git-sha tags (reproducibility,
  supply-chain verification).
- Argo CD in-cluster RBAC means CI never holds cluster credentials.
- Vanilla roster `.bin` is never baked into images — it's a runtime mount,
  kept out of the public artifact.

## Open question

**Where should Argo CD watch?** Two options:

1. **Separate private `nlf-deploy` repo** — cleaner separation of secrets/deploy
   config from public app code. Deploy config can reference an internal registry
   mirror, have environment overlays (staging/prod), etc. The `bump-argocd.yml`
   Pushes the new image tag to this repo.
2. **Path in this repo** (e.g., `deploy/envs/prod/values.yaml`) — simpler,
   single repo, but means deploy-specific values live in the public repo and
   the Argo CD app source is public (fine if no secrets are in values).

Recommendation: **separate deploy repo** for flexibility and to keep operational
state private. In the short term, starting with an in-repo path is fine and can
be extracted later.
