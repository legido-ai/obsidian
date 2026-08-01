# Implementation Plan: Obsidian in Docker with me/raw and me/wiki vaults

**Branch**: `001-obsidian-vaults` | **Date**: 2026-08-01 | **Spec**: `specs/001-obsidian-vaults/spec.md`

**Input**: Feature specification from `/specs/001-obsidian-vaults/spec.md`

## Summary

Run Obsidian (desktop, Linux) inside a Docker container and expose it in the browser via noVNC, deployed through docker-agent with Traefik routing. The container creates and persists two vaults — `/data/me/raw` (raw documents: PDFs, videos, transcriptions, links) and `/data/me/wiki` (generated markdown, the exposed vault) — and pre-registers both in Obsidian's vault list so the user can switch between them. The markdown-generation pipeline from raw documents is a later step driven from Hermes; this iteration delivers the container, the vault structure, persistence, and the web UI.

## Technical Context

**Language/Version**: Shell (entrypoint), Dockerfile (Ubuntu 24.04 base)

**Primary Dependencies**: Obsidian Linux arm64 `.deb` (official GitHub releases, pinned version), Xvfb, fluxbox, x11vnc, noVNC + websockify, wget/tar for install

**Storage**: Docker volume mounted at `/data` → `/data/me/raw` and `/data/me/wiki` (each with `.obsidian/` vault metadata); Obsidian config at `~/.config/obsidian/obsidian.json`

**Testing**: Container build + smoke test (port 6080 responds, vault dirs exist, obsidian.json registers both vaults) — validated in CI/registry and via the deploy URL

**Target Platform**: Linux arm64 (production VPS); amd64 also built by CI (`latest`/`amd64` tags)

**Project Type**: containerized desktop-app-with-web-access (HTTP via noVNC)

**Performance Goals**: Obsidian UI responsive over the public URL; single-user session

**Constraints**: Must run on arm64; must be deployable via docker-agent (HTTP, Traefik auto-routing, `service_port`); vault data must survive container recreation; no bind mounts or docker socket mounts (docker-agent policy)

**Scale/Scope**: Single user, two vaults, one container

## Constitution Check

*GATE: Passed.* Single container project; no multi-service complexity; secrets (none required by the app itself) are handled via env vars by convention; no data outside the `/data` volume.

## Project Structure

### Documentation (this feature)

```text
specs/001-obsidian-vaults/
├── spec.md              # This feature (/speckit.specify output)
├── plan.md              # This file (/speckit.plan output)
└── tasks.md             # Phase 2 output (/speckit.tasks output)
```

### Source Code (repository root)

```text
Dockerfile              # Multi-stage-ish single stage: ubuntu 24.04 + Obsidian arm64 + noVNC stack
entrypoint.sh           # Idempotent vault creation, obsidian.json seeding, X/VNC/websockify startup
README.md               # Usage: URL, vaults layout, persistence, how to generate wiki markdown later
.github/workflows/      # Existing template CI (builds ghcr.io/legido-ai/obsidian:arch64 on push)
```

**Structure Decision**: Single-project layout — the whole feature is a container image (Dockerfile + entrypoint + docs). No application code beyond the entrypoint script is required.

## Implementation Steps

1. **Dockerfile**: base `ubuntu:24.04`; install `xvfb fluxbox x11vnc novnc websockify wget ca-certificates`; download pinned Obsidian arm64 `.deb` from GitHub releases and `dpkg -i` it; create user `obsidian` (uid 1000); copy `entrypoint.sh`; `EXPOSE 6080`; `CMD ["/entrypoint.sh"]`. Honor the `DOCKER_GID` build arg passed by CI (used for the docker socket group; not required at runtime here).
2. **entrypoint.sh**: create `/data/me/raw` and `/data/me/wiki` with `.obsidian/` dirs if missing; write `obsidian.json` registering both vaults; start `Xvfb :0`, `fluxbox`, `x11vnc` (rfbport 5900), then `websockify --web /usr/share/novnc 6080 localhost:5900`; launch Obsidian with the wiki vault as the active workspace; trap TERM for graceful shutdown.
3. **README.md**: document the deploy URL, vault layout, persistence volume, and the planned markdown-generation workflow.
4. **Validation**: local image build check (via CI pipeline on push), then deploy through docker-agent.

## Deployment

- Image: `ghcr.io/legido-ai/obsidian:arch64` (arm64 production tag, built by the existing template workflow on push)
- docker-agent `run` args: `container_name: obsidian`, `networks: [network-reverse-proxy]`, `service_port: 6080`, `volumes: [{name: obsidian-data, target: /data}]`, `restart_policy: unless-stopped`
- Public URL: `https://obsidian.test.legido.com` (Traefik auto-routing by docker-agent)

## Complexity Tracking

> No constitution violations — single container, standard layout, no additional projects or abstractions required.
