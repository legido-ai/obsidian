# Tasks: Obsidian in Docker with me/raw and me/wiki vaults

**Branch**: `001-obsidian-vaults` | **Date**: 2026-08-01 | **Spec**: `specs/001-obsidian-vaults/spec.md` | **Plan**: `specs/001-obsidian-vaults/plan.md`

## Phase 1 — Container image (Dockerfile)

- [ ] T001 Write `Dockerfile`:
  - Base `ubuntu:24.04`; `ARG DOCKER_GID=998` (accepted, unused at runtime)
  - Install: `xvfb fluxbox x11vnc novnc websockify curl ca-certificates` + Electron runtime libs (`libgtk-3-0 libnss3 libasound2t64 libxss1 libxtst6 libgbm1 libdrm2 libxkbcommon0 libatk-bridge2.0-0 libcups2t64 libsecret-1-0 fonts-liberation`)
  - Download Obsidian tarball by `TARGETARCH` (arm64 → `obsidian-1.13.4-arm64.tar.gz`, amd64 → `obsidian-1.13.4.tar.gz`) from GitHub releases `v1.13.4`, extract to `/opt/obsidian`
  - Copy `entrypoint.sh`, `chmod +x`; `EXPOSE 6080`; `HEALTHCHECK` against `http://localhost:6080`; `CMD ["/entrypoint.sh"]`

## Phase 2 — Entrypoint

- [ ] T002 Write `entrypoint.sh`:
  - Create `/data/me/raw` and `/data/me/wiki` with `.obsidian/` metadata dirs (idempotent)
  - Set `XDG_CONFIG_HOME=/data/.config` (persist Obsidian config on the volume)
  - Generate `obsidian.json` registering both vaults with stable random 16-hex IDs
  - VNC password: use `$VNC_PASSWORD` if set, else generate once and persist to `/data/.vncpass`; log it on first boot
  - Start `Xvfb :0`, `fluxbox`, `x11vnc -forever -shared -rfbport 5900 -passwdfile`, `websockify --web /usr/share/novnc 6080 localhost:5900`
  - Launch `/opt/obsidian/obsidian --no-sandbox <wiki vault>`; trap TERM/INT for graceful shutdown

## Phase 3 — Docs

- [ ] T003 Write `README.md`: deploy URL, vault layout (`me/raw`, `me/wiki`), persistence volume, VNC password handling, and the planned Hermes-driven markdown generation workflow

## Phase 4 — Deploy

- [ ] T004 Push branch `001-obsidian-vaults`; confirm CI builds `ghcr.io/legido-ai/obsidian:arch64`
- [ ] T005 Deploy via docker-agent: `container_name: obsidian`, `service_port: 6080`, volume `obsidian-data:/data`, `restart_policy: unless-stopped`; verify public URL loads

## Acceptance mapping

- US1 (UI reachable) → T004/T005
- US2 (raw vault) → T002
- US3 (wiki vault exposed) → T002/T005
- US4 (persistence) → T002 (volume-mounted `/data`) + T005
