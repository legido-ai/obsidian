#!/usr/bin/env bash
# Obsidian container entrypoint:
#   - creates the me/raw and me/wiki vaults (idempotent)
#   - registers both vaults in Obsidian's config (persisted on the /data volume)
#   - starts Xvfb + fluxbox + x11vnc + noVNC (websockify) and launches Obsidian
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

# --- VNC password ---------------------------------------------------------
VNC_PASS_FILE="$DATA_DIR/.vncpass"
if [ -n "$VNC_PASSWORD" ]; then
  echo "$VNC_PASSWORD" > "$VNC_PASS_FILE"
  chmod 600 "$VNC_PASS_FILE"
fi
if [ ! -f "$VNC_PASS_FILE" ]; then
  GEN_PASS=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 16)
  echo "$GEN_PASS" > "$VNC_PASS_FILE"
  chmod 600 "$VNC_PASS_FILE"
  echo "[obsidian] VNC password generated on first boot: $GEN_PASS (persisted in $VNC_PASS_FILE; set VNC_PASSWORD env to override)"
fi

# --- Display stack --------------------------------------------------------
export DISPLAY=:0
export XDG_CONFIG_HOME="$CONFIG_HOME"
export HOME="${HOME:-/root}"

Xvfb :0 -screen 0 1600x1000x24 -nolisten tcp &
XVFB_PID=$!
sleep 1

fluxbox >/dev/null 2>&1 &
x11vnc -display :0 -forever -shared -rfbport 5900 -passwdfile "$VNC_PASS_FILE" -noxdamage >/dev/null 2>&1 &
X11VNC_PID=$!
websockify --web /usr/share/novnc 6080 localhost:5900 >/dev/null 2>&1 &
WS_PID=$!

# --- Obsidian -------------------------------------------------------------
OBSIDIAN_BIN=$(find /opt/obsidian -maxdepth 3 -type f -name obsidian 2>/dev/null | head -1)
if [ -z "$OBSIDIAN_BIN" ]; then
  echo "[obsidian] ERROR: obsidian binary not found under /opt/obsidian" >&2
  exit 1
fi
chmod +x "$OBSIDIAN_BIN"

cleanup() {
  kill "$OBS_PID" "$WS_PID" "$X11VNC_PID" "$XVFB_PID" 2>/dev/null || true
}
trap cleanup TERM INT

echo "[obsidian] starting Obsidian ($OBSIDIAN_BIN) with vault $WIKI_VAULT"
"$OBSIDIAN_BIN" --no-sandbox "$WIKI_VAULT" >/dev/null 2>&1 &
OBS_PID=$!
wait "$OBS_PID"
