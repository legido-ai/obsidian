# Obsidian in Docker (headless HTTP service)

Obsidian runs headless in a Docker container (Xvfb, no GUI exposed) and serves the wiki vault over **pure HTTP** via the [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin. Hermes (and any container on the shared docker network) talks to it with plain HTTP requests.

## Vaults

| Vault | Path | Purpose |
|-------|------|---------|
| `me/raw` | `/data/me/raw` | Raw source documents: PDFs, videos, transcriptions, links, etc. |
| `me/wiki` | `/data/me/wiki` | Markdown wiki generated from the raw documents (served over HTTP) |

Both vaults are created automatically on first boot and registered in Obsidian's vault switcher.

## HTTP API

The container listens on port `27123` (internal only — deployed on `network-docker-agent`, the network shared with Hermes and docker-agent; no public exposure).

- **Auth:** `Authorization: Bearer <OBSIDIAN_API_KEY>`
- **Key source:** `$OBSIDIAN_API_KEY` env var at first boot; otherwise auto-generated and persisted in `/data/me/wiki/.obsidian/plugins/obsidian-local-rest-api/data.json` (copy at `/data/.obsidian-api-key`)

Useful endpoints (plugin v5):

- `GET /vault/` — list all files in the vault
- `GET /vault/<path>` / `PUT /vault/<path>` / `DELETE /vault/<path>` — read/write/delete notes
- `POST /command/` — execute Obsidian commands
- `GET /active-note/` — current note
- `POST /search/` — full-text search

Example from the Hermes terminal:

```bash
curl -H "Authorization: Bearer $OBSIDIAN_API_KEY" http://<container-ip>:27123/vault/
```

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
