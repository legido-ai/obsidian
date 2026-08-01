#!/usr/bin/env bash
# Obsidian container entrypoint (headless HTTP service):
#   - creates the me/raw and me/wiki vaults (idempotent)
#   - registers both vaults in Obsidian's config (persisted on the /data volume)
#   - seeds the Local REST API plugin into the wiki vault (API key from
#     $OBSIDIAN_API_KEY or auto-generated, persisted in the vault config)
#   - starts Xvfb (headless display) and Obsidian; the vault is served over
#     pure HTTP on port 27123 by the Local REST API plugin
set -e

DATA_DIR="${DATA_DIR:-/data}"
RAW_VAULT="$DATA_DIR/me/raw"
WIKI_VAULT="$DATA_DIR/me/wiki"
CONFIG_HOME="${XDG_CONFIG_HOME:-$DATA_DIR/.config}"
OBSIDIAN_CONFIG="$CONFIG_HOME/obsidian"

# --- Vaults ---------------------------------------------------------------
mkdir -p "$RAW_VAULT/.obsidian" "$WIKI_VAULT/.obsidian"

# --- Obsidian vault registration (stable across restarts) -----------------
mkdir -p "$OBSIDIAN_CONFIG"
if [ ! -f "$OBSIDIAN_CONFIG/obsidian.json" ]; then
  RAW_ID=$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')
  WIKI_ID=$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')
  NOW=$(date +%s)
  cat > "$OBSIDIAN_CONFIG/obsidian.json" <<EOF
{"vaults":{"$RAW_ID":{"path":"$RAW_VAULT","ts":$((NOW-10)),"open":false},"$WIKI_ID":{"path":"$WIKI_VAULT","ts":$NOW,"open":true}}}
EOF
  echo "[obsidian] vaults registered: me/raw + me/wiki"
fi

# --- Vault HTTP API key -----------------------------------------------------
API_KEY_FILE="$DATA_DIR/.obsidian-api-key"
if [ -n "$OBSIDIAN_API_KEY" ]; then
  API_KEY="$OBSIDIAN_API_KEY"
  echo "$API_KEY" > "$API_KEY_FILE"
  chmod 600 "$API_KEY_FILE"
elif [ -f "$API_KEY_FILE" ]; then
  API_KEY=$(cat "$API_KEY_FILE")
else
  API_KEY=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)
  echo "$API_KEY" > "$API_KEY_FILE"
  chmod 600 "$API_KEY_FILE"
  echo "[obsidian] Vault API key generated on first boot: $API_KEY (persisted in $API_KEY_FILE; override with OBSIDIAN_API_KEY env)"
fi

# --- Local REST API plugin (optional, needs restricted mode disabled in UI) --
PLUGIN_ID="obsidian-local-rest-api"
PLUGIN_SRC="/opt/obsidian-local-rest-api"
PLUGIN_DIR="$WIKI_VAULT/.obsidian/plugins/$PLUGIN_ID"

if [ -d "$PLUGIN_SRC" ]; then
  mkdir -p "$PLUGIN_DIR"
  cp -f "$PLUGIN_SRC/main.js" "$PLUGIN_SRC/manifest.json" "$PLUGIN_SRC/styles.css" "$PLUGIN_DIR/" 2>/dev/null || true
  if [ ! -f "$PLUGIN_DIR/data.json" ]; then
    cat > "$PLUGIN_DIR/data.json" <<EOF
{"port":27123,"apiKey":"$API_KEY","enableWatch":true,"crypto":{"enabled":false,"cert":"","key":"","passphrase":""},"enableUserActivity":false}
EOF
  fi
  echo '["obsidian-local-rest-api"]' > "$WIKI_VAULT/.obsidian/community-plugins.json"
fi

# --- Headless display + Obsidian -------------------------------------------
export DISPLAY=:0
export XDG_CONFIG_HOME="$CONFIG_HOME"
export HOME="${HOME:-/root}"

# Vault HTTP API (pure HTTP, Bearer auth)
OBSIDIAN_API_KEY="$API_KEY" nohup python3 /vault_api.py >/tmp/vault-api.log 2>&1 &
API_PID=$!

Xvfb :0 -screen 0 1280x800x24 -nolisten tcp &
XVFB_PID=$!
sleep 1

OBSIDIAN_BIN=$(find /opt/obsidian -maxdepth 3 -type f -name obsidian 2>/dev/null | head -1)
if [ -z "$OBSIDIAN_BIN" ]; then
  echo "[obsidian] ERROR: obsidian binary not found under /opt/obsidian" >&2
  exit 1
fi
chmod +x "$OBSIDIAN_BIN"

cleanup() {
  kill "$OBS_PID" "$API_PID" "$XVFB_PID" 2>/dev/null || true
}
trap cleanup TERM INT

echo "[obsidian] starting Obsidian headless ($OBSIDIAN_BIN) with vault $WIKI_VAULT (HTTP API on :27123)"
"$OBSIDIAN_BIN" --no-sandbox --disable-gpu --disable-dev-shm-usage "$WIKI_VAULT" >/dev/null 2>&1 &
OBS_PID=$!
wait "$OBS_PID"
