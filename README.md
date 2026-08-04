# Obsidian in Docker (headless HTTP service)

Obsidian runs headless in a Docker container (Xvfb framebuffer, no GUI exposed) and serves the wiki vault over **pure HTTP** via the official [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin. **Obsidian is only a store + HTTP surface — all logic lives in the Hermes `obsidian-ingest` skill** (raw → wiki synthesis, wikilinks, index). No custom code, no server-side rendering, no formatting decisions in this container.

## Vaults

- `me/raw` (`/data/me/raw`) — raw source documents: PDFs, videos, transcriptions, links, etc. (append-only)
- `me/wiki` (`/data/me/wiki`) — markdown wiki generated from the raw documents by the Hermes skill

Both are created automatically on first boot and registered in Obsidian's vault switcher.

## HTTP surface (the Local REST API plugin)

The container exposes port `27123` with the official plugin's API. All requests use the Bearer key at `/data/.obsidian-api-key` (or `$OBSIDIAN_API_KEY`):

- `GET /vault/<path>` — file contents or directory listing
- `PUT /vault/<path>` — create/overwrite a file
- `DELETE /vault/<path>` — delete a file
- `GET /active`, `/search/...`, `/command` — plugin extras (search, commands, MCP)

Example:

```bash
curl -H "Authorization: Bearer <key>" http://<container-ip>:27123/vault/
curl -X PUT -H "Authorization: Bearer <key>" --data-binary "# Note" http://<container-ip>:27123/vault/me/wiki/hello.md
```

### How the plugin activates with zero manual configuration

Community plugins normally require disabling Obsidian's Restricted Mode in the UI. Here it is done programmatically, headlessly:

1. The entrypoint seeds the plugin (`obsidian-local-rest-api`) + `community-plugins.json` + `data.json` (port 27123, key, crypto off → plain HTTP).
2. Obsidian starts under Xvfb.
3. The entrypoint runs the bundled **`obsidian-cli plugins:restrict off`** — `obsidian-cli` (shipped in the official tarball) talks to the running app over a unix socket and disables Restricted Mode; the app reloads and the plugin serves HTTP on 27123.
4. The entrypoint waits until `/active` responds.

No VNC, no browser, no manual configuration. Xvfb is only the invisible framebuffer the Electron app requires.

## Persistence

A docker volume is mounted at `/data`:

- `/data/me/raw` — raw documents
- `/data/me/wiki` — generated markdown notes (+ plugin config with the API key)
- `/data/.config` — Obsidian app config (vault registration, settings)
- `/data/.obsidian-api-key` — the Bearer key

Recreating the container keeps all data.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `/data` | Base directory holding the vaults |
| `OBSIDIAN_API_KEY` | *(generated)* | Fixed Local REST API key; otherwise generated once and persisted |

## Network

Deployed on the docker-agent networks: `network-reverse-proxy` (Traefik → public URL) + `network-docker-agent` (Hermes terminals reach the API by container IP). Public URL: `https://obsidian-http.test.legido.com`.

## Architecture rules (do not violate)

- **No custom code in this container** — no application server, no renderer, no formatting logic. If a one-off configuration is ever needed, do it in a throwaway sidecar container, never permanently.
- **Hermes owns the logic** — the `obsidian-ingest` skill fetches sources, stores raw copies, writes adapted wiki notes, updates the index. Obsidian only stores and exposes.
- **The vault files are the product** — Obsidian's own UI renders them; the HTTP layer only reads/writes.
