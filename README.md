# Obsidian in Docker

Obsidian (desktop) running in a Docker container, exposed in the browser via noVNC and deployed through docker-agent.

## URL

`https://obsidian.test.legido.com`

## Vaults

| Vault | Path | Purpose |
|-------|------|---------|
| `me/raw` | `/data/me/raw` | Raw source documents: PDFs, videos, transcriptions, links, etc. |
| `me/wiki` | `/data/me/wiki` | Markdown wiki generated from the raw documents (exposed vault, opened by default) |

Both vaults are created automatically on first boot and registered in Obsidian's vault switcher.

## Access

- Open the URL in a browser; noVNC will ask for the VNC password.
- The VNC password is generated on first boot and printed to the container logs (`[obsidian] VNC password generated on first boot: ...`).
- To set a fixed password, pass the `VNC_PASSWORD` environment variable to the container.

## Persistence

A docker volume is mounted at `/data`:

- `/data/me/raw` — raw documents
- `/data/me/wiki` — generated markdown notes
- `/data/.config` — Obsidian app config (vault registration, settings)
- `/data/.vncpass` — generated VNC password

Recreating the container keeps all data.

## HTTP API (Local REST API plugin)

The wiki vault runs the [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin, exposing an HTTP API on port `27123` inside the container (reachable from the Hermes terminal / DinD network by container IP, not published publicly):

- **Auth:** `Authorization: Bearer <OBSIDIAN_API_KEY>`
- **Key source:** `$OBSIDIAN_API_KEY` env var at first boot, else auto-generated and persisted in `/data/me/wiki/.obsidian/plugins/obsidian-local-rest-api/data.json` (copy at `/data/.obsidian-api-key`)

Useful endpoints (v5):

- `GET /vault/` — list all files in the vault
- `GET /vault/<path>` / `PUT /vault/<path>` / `DELETE /vault/<path>` — read/write/delete notes
- `POST /command/` — execute Obsidian commands
- `GET /active-note/` — current note
- `POST /search/` — full-text search

Example from a terminal:

```bash
curl -H "Authorization: Bearer $OBSIDIAN_API_KEY" http://<container-ip>:27123/vault/
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `/data` | Base directory holding the vaults |
| `VNC_PASSWORD` | *(generated)* | Fixed VNC password; otherwise generated once and persisted |
| `OBSIDIAN_API_KEY` | *(generated)* | Fixed Local REST API key; otherwise generated once and persisted |

## Next steps (planned)

The wiki markdown will be generated from the raw documents by Hermes in a later step (the article-based pipeline: links, PDFs, videos, transcriptions → markdown in `me/wiki`).
