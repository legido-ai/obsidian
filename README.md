# Obsidian in Docker (headless HTTP service)

Obsidian runs headless in a Docker container (Xvfb, no GUI exposed) and serves the wiki vault over **pure HTTP** via the [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin. Hermes (and any container on the shared docker network) talks to it with plain HTTP requests.

## Vaults

| Vault | Path | Purpose |
|-------|------|---------|
| `me/raw` | `/data/me/raw` | Raw source documents: PDFs, videos, transcriptions, links, etc. |
| `me/wiki` | `/data/me/wiki` | Markdown wiki generated from the raw documents (served over HTTP) |

Both vaults are created automatically on first boot and registered in Obsidian's vault switcher.

## HTTP API (vault API)

The container exposes a minimal authenticated HTTP API on port `27123` (internal only — deployed on `network-docker-agent`, the network shared with Hermes and docker-agent; no public exposure). It serves the vault data directly; Obsidian runs headless and picks up file changes automatically.

- **Auth:** `Authorization: Bearer <OBSIDIAN_API_KEY>`
- **Key source:** `$OBSIDIAN_API_KEY` env var at first boot; otherwise auto-generated and persisted in `/data/.obsidian-api-key`

Endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Service info + vault list (`me/raw`, `me/wiki`) |
| `GET` | `/vault/<path>` | File contents (bytes) or directory listing (JSON) |
| `PUT` | `/vault/<path>` | Create/overwrite a file (body = file bytes) |
| `DELETE` | `/vault/<path>` | Delete a file (or empty directory) |

Example from the Hermes terminal:

```bash
curl -H "Authorization: Bearer $OBSIDIAN_API_KEY" http://<container-ip>:27123/vault/
curl -X PUT -H "Authorization: Bearer $OBSIDIAN_API_KEY" --data-binary "# Note" http://<container-ip>:27123/vault/me/wiki/hello.md
```

The official Local REST API plugin is also pre-seeded in the wiki vault (`obsidian-local-rest-api`, same port/key) — it activates if restricted mode is ever disabled in the Obsidian UI, adding search/commands/MCP endpoints.

## Persistence

A docker volume is mounted at `/data`:

- `/data/me/raw` — raw documents
- `/data/me/wiki` — generated markdown notes (+ plugin config with the API key)
- `/data/.config` — Obsidian app config (vault registration, settings)

Recreating the container keeps all data.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `/data` | Base directory holding the vaults |
| `OBSIDIAN_API_KEY` | *(generated)* | Fixed Local REST API key; otherwise generated once and persisted |

## Network

Deployed on `network-docker-agent` (the docker network shared with the Hermes container and docker-agent), so Hermes terminals can reach the API directly by container IP. No Traefik route / public URL is required — this is an internal HTTP service.

## Next steps (planned)

The wiki markdown will be generated from the raw documents by Hermes in a later step (the article-based pipeline: links, PDFs, videos, transcriptions → markdown in `me/wiki`), written via the HTTP API above.
