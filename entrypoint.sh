#!/usr/bin/env bash
# Obsidian container entrypoint (headless HTTP service):
#   - creates the me/raw and me/wiki vaults (idempotent)
#   - registers both vaults in Obsidian's config (persisted on the /data volume)
#   - seeds the Local REST API plugin into the wiki vault (API key from
#     $OBSIDIAN_API_KEY or auto-generated, persisted in the vault config)
#   - starts Xvfb (headless display) and Obsidian
#   - disables Restricted Mode via the bundled obsidian-cli (unix socket, no UI)
#     so the Local REST API plugin activates and serves plain HTTP on 27123
# Obsidian is ONLY a store + HTTP surface. All logic lives in the Hermes skill.
set -e

DATA_DIR="${DATA_DIR:-/data}"
RAW_VAULT="$DATA_DIR/me/raw"
WIKI_VAULT="$DATA_DIR/me/wiki"
CONFIG_HOME="${XDG_CONFIG_HOME:-$DATA_DIR/.config}"
OBSIDIAN_CONFIG="$CONFIG_HOME/obsidian"
BOOT_LOG="$DATA_DIR/boot.log"
APP_LOG="$DATA_DIR/obsidian.log"

# Everything is also captured into the shared volume so Hermes can read the
# boot log via a sidecar (the docker-agent exposes no logs endpoint).
exec > >(tee "$BOOT_LOG") 2>&1
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "=== boot start (image: obsidian arch64, entrypoint v2-diag) ==="
log "uname: $(uname -m) | data_dir: $DATA_DIR | api_key_env: $([ -n "$OBSIDIAN_API_KEY" ] && echo set || echo unset)"

# --- Vaults ---------------------------------------------------------------
mkdir -p "$RAW_VAULT/.obsidian" "$WIKI_VAULT/.obsidian"
log "vaults ensured: $RAW_VAULT, $WIKI_VAULT"

# --- Obsidian vault registration (stable across restarts) -----------------
mkdir -p "$OBSIDIAN_CONFIG"
if [ ! -f "$OBSIDIAN_CONFIG/obsidian.json" ]; then
  RAW_ID=$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')
  WIKI_ID=$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')
  NOW=$(date +%s)
  cat > "$OBSIDIAN_CONFIG/obsidian.json" <<EOF
{"vaults":{"$RAW_ID":{"path":"$RAW_VAULT","ts":$((NOW-10)),"open":false},"$WIKI_ID":{"path":"$WIKI_VAULT","ts":$NOW,"open":true}}}
EOF
  log "obsidian.json written (fresh)"
else
  log "obsidian.json exists (kept)"
fi

# --- Enable the command-line interface (required for obsidian-cli) ----------
# Obsidian 1.13 stores the CLI toggle in the global obsidian.json as
# {"cli": true} (config object D.cli); without it obsidian-cli answers
# "Command line interface is not enabled". Enable it idempotently via python3.
python3 - "$OBSIDIAN_CONFIG/obsidian.json" <<'PY'
import json, sys
p = sys.argv[1]
try:
    with open(p) as f:
        d = json.load(f)
except Exception:
    d = {}
d["cli"] = True
with open(p, "w") as f:
    json.dump(d, f)
PY
log "obsidian-cli enabled (cli:true set in $OBSIDIAN_CONFIG/obsidian.json)"

# --- Vault HTTP API key -----------------------------------------------------
API_KEY_FILE="$DATA_DIR/.obsidian-api-key"
if [ -n "$OBSIDIAN_API_KEY" ]; then
  API_KEY="$OBSIDIAN_API_KEY"
  echo "$API_KEY" > "$API_KEY_FILE"
  chmod 600 "$API_KEY_FILE"
  log "API key written from env"
elif [ -f "$API_KEY_FILE" ]; then
  API_KEY=$(cat "$API_KEY_FILE")
  log "API key read from $API_KEY_FILE"
else
  API_KEY=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)
  echo "$API_KEY" > "$API_KEY_FILE"
  chmod 600 "$API_KEY_FILE"
  log "API key generated (fresh)"
fi

# --- Local REST API plugin (the ONLY HTTP surface) ---------------------------
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
    log "plugin data.json written (fresh)"
  else
    log "plugin data.json exists (kept)"
  fi
  echo '["obsidian-local-rest-api"]' > "$WIKI_VAULT/.obsidian/community-plugins.json"
  log "community-plugins.json seeded"
else
  log "WARNING: plugin source missing at $PLUGIN_SRC"
fi

# --- Headless display + Obsidian -------------------------------------------
export DISPLAY=:0
export XDG_CONFIG_HOME="$CONFIG_HOME"
export HOME="${HOME:-/root}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/obsidian-runtime}"
mkdir -p "$XDG_RUNTIME_DIR" && chmod 700 "$XDG_RUNTIME_DIR"
log "env: DISPLAY=$DISPLAY XDG_CONFIG_HOME=$XDG_CONFIG_HOME HOME=$HOME XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"

Xvfb :0 -screen 0 1280x800x24 -nolisten tcp >> "$APP_LOG" 2>&1 &
XVFB_PID=$!
sleep 1
log "Xvfb started (pid $XVFB_PID)"

OBSIDIAN_BIN=$(find /opt/obsidian -maxdepth 3 -type f -name obsidian 2>/dev/null | head -1)
if [ -z "$OBSIDIAN_BIN" ]; then
  log "ERROR: obsidian binary not found under /opt/obsidian"
  exit 1
fi
chmod +x "$OBSIDIAN_BIN"
log "obsidian binary: $OBSIDIAN_BIN"
log "obsidian-cli present: $([ -x /opt/obsidian/obsidian-cli ] && echo yes || echo NO)"
log "plugin files: $(ls "$PLUGIN_DIR" 2>/dev/null | tr '\n' ' ')"

echo "--- Obsidian app output follows ---" >> "$APP_LOG"
"$OBSIDIAN_BIN" --no-sandbox --disable-gpu --disable-dev-shm-usage "$WIKI_VAULT" >> "$APP_LOG" 2>&1 &
OBS_PID=$!
log "Obsidian started (pid $OBS_PID)"

# --- Activate the plugin: disable Restricted Mode via obsidian-cli ----------
# The tarball extracts to a per-arch subdirectory (obsidian-1.13.4/ on amd64,
# obsidian-1.13.4-arm64/ on arm64), so locate the CLI dynamically like the app.
CLI_BIN=$(find /opt/obsidian -maxdepth 3 -type f -name obsidian-cli 2>/dev/null | head -1)
if [ -x "$CLI_BIN" ]; then
  log "obsidian-cli: $CLI_BIN"
  log "disabling Restricted Mode via obsidian-cli (up to 60 tries, 2s apart)"
  CLI_OK=0
  for i in $(seq 1 60); do
    # The CLI exits 0 even when it prints an error, so success is detected by
    # the output ("Restricted mode disabled. Reloading..." or "already
    # disabled"). Early tries may report "Command ... not found" while the
    # renderer is still initializing its command registry.
    OUT=$("$CLI_BIN" plugins:restrict off 2>&1 || true)
    case "$OUT" in
      *"Restricted mode"*)
        log "obsidian-cli OK on try $i: $(echo "$OUT" | head -1)"
        CLI_OK=1
        break
        ;;
    esac
    log "obsidian-cli try $i: $(echo "$OUT" | head -1)"
    sleep 2
  done
  if [ "$CLI_OK" != "1" ]; then
    log "WARNING: Restricted Mode could not be disabled via obsidian-cli"
  fi
else
  log "WARNING: obsidian-cli not found at $CLI_BIN"
fi

# --- Wait for the plugin HTTP surface on 27123 ------------------------------
log "waiting for plugin HTTP on 127.0.0.1:27123 (up to 60s)"
for i in $(seq 1 60); do
  if curl -s -o /dev/null -m 2 -H "Authorization: Bearer $API_KEY" "http://127.0.0.1:27123/active"; then
    log "plugin HTTP responding on try $i"
    break
  fi
  sleep 1
done
log "plugin wait loop finished (last try $i)"

log "=== boot complete; waiting on Obsidian pid $OBS_PID ==="
cleanup() {
  log "shutdown signal received"
  kill "$OBS_PID" "$XVFB_PID" 2>/dev/null || true
}
trap cleanup TERM INT

set +e
wait "$OBS_PID"
RC=$?
log "=== Obsidian exited with code $RC ==="
exit "$RC"
