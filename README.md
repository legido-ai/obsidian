# Obsidian in Docker (headless HTTP service)

Obsidian runs headless in a Docker container (Xvfb, no GUI exposed) and serves the wiki vault over **pure HTTP** via the [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin. Hermes (and any container on the shared docker network) talks to it with plain HTTP requests.

## Vaults

| Vault | Path | Purpose |
|-------|------|---------|
| `me/raw` | `/data/me/raw` | Raw source documents: PDFs, videos, transcriptions, links, etc. |
| `me/wiki` | `/data/me/wiki` | Markdown wiki generated from the raw documents (served over HTTP) |

Both vaults are created automatically on first boot and registered in Obsidian's vault switcher.

## HTTP API + public wiki UI

The container exposes port `27123` with two faces:

**Public wiki UI (no auth)** — the consultable interface:

- `GET /` — index (latest notes + sources)
- `GET /wiki/` — rendered wiki index (README + all notes)
- `GET /wiki/<topic>/<note>.md` — rendered note (markdown → HTML, `[[wikilinks]]` resolve)
- `GET /raw/` and `GET /raw/<file>` — raw sources

**Authenticated JSON API (Bearer key)** — for Hermes:

- `GET /vault/<path>` — file contents or directory listing (`?recursive=1`)
- `PUT /vault/<path>` — create/overwrite a file
- `DELETE /vault/<path>` — delete a file

Auth header: `Authorization: Bearer <OBSIDIAN_API_KEY>` (key at `/data/.obsidian-api-key`).

Example:

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
