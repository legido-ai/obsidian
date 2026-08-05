#!/usr/bin/env python3
"""Capture renderer console/exceptions via CDP (127.0.0.1:9222) into a log.

Minimal websocket client (no deps): connects to the Obsidian page target,
enables Runtime/Console/Log, reloads the page, and records console messages
and exceptions for DURATION seconds. The plugin load error shows up here.
"""
import json, os, socket, base64, hashlib, struct, sys, time, urllib.request

HOST, PORT, DURATION = "127.0.0.1", 9222, int(os.environ.get("CDP_SECONDS", "35"))
OUT = "/data/cdp.log"

def http_get(path, timeout=5):
    with urllib.request.urlopen(f"http://{HOST}:{PORT}{path}", timeout=timeout) as r:
        return r.read().decode()

def ws_connect(url):
    # url like ws://127.0.0.1:9222/devtools/page/XXXX
    path = url.split("9222", 1)[1]
    s = socket.create_connection((HOST, PORT), timeout=10)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (f"GET {path} HTTP/1.1\r\nHost: {HOST}:{PORT}\r\n"
           f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
    s.sendall(req.encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += s.recv(4096)
    if b"101" not in resp.split(b"\r\n", 1)[0]:
        raise RuntimeError("ws handshake failed: " + resp[:120].decode(errors="replace"))
    return s

def ws_send(s, payload):
    data = payload.encode()
    mask = os.urandom(4)
    header = bytearray([0x81])
    ln = len(data)
    if ln < 126:
        header.append(0x80 | ln)
    elif ln < 65536:
        header.append(0x80 | 126)
        header += struct.pack(">H", ln)
    else:
        header.append(0x80 | 127)
        header += struct.pack(">Q", ln)
    header += mask
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    s.sendall(bytes(header) + masked)

def ws_recv(s, timeout=10):
    s.settimeout(timeout)
    hdr = s.recv(2)
    if len(hdr) < 2:
        return None
    opcode = hdr[0] & 0x0F
    ln = hdr[1] & 0x7F
    if ln == 126:
        ln = struct.unpack(">H", s.recv(2))[0]
    elif ln == 127:
        ln = struct.unpack(">Q", s.recv(8))[0]
    data = b""
    while len(data) < ln:
        chunk = s.recv(ln - len(data))
        if not chunk:
            break
        data += chunk
    if opcode == 8:  # close
        return None
    return data.decode(errors="replace")

def send_cmd(s, cmd_id, method, params=None):
    ws_send(s, json.dumps({"id": cmd_id, "method": method, "params": params or {}}))

def main():
    targets = json.loads(http_get("/json/list"))
    page = next((t for t in targets if t.get("type") == "page"), None)
    if not page:
        open(OUT, "a").write("[cdp] no page target\n")
        return 1
    ws_url = page["webSocketDebuggerUrl"]
    log = open(OUT, "a")
    log.write(f"[cdp] target: {page.get('url')} title={page.get('title')}\n")
    log.flush()
    s = ws_connect(ws_url)
    cid = 0
    for method in ("Runtime.enable", "Console.enable", "Log.enable", "Page.enable"):
        cid += 1
        send_cmd(s, cid, method)
    cid += 1
    send_cmd(s, cid, "Page.reload")
    log.write(f"[cdp] reload sent, capturing {DURATION}s\n")
    log.flush()
    start = time.time()
    while time.time() - start < DURATION:
        try:
            msg = ws_recv(s, timeout=5)
        except socket.timeout:
            continue
        if not msg:
            continue
        try:
            ev = json.loads(msg)
        except Exception:
            continue
        method = ev.get("method", "")
        if method in ("Runtime.consoleAPICalled", "Runtime.exceptionThrown", "Log.entryAdded", "Runtime.executionContextDestroyed"):
            log.write(f"[cdp:{method}] {json.dumps(ev.get('params', {}))[:2000]}\n")
            log.flush()
    log.write("[cdp] capture done\n")
    log.flush()
    return 0

if __name__ == "__main__":
    sys.exit(main())
