#!/usr/bin/env python3
"""Minimal authenticated HTTP API for the Obsidian vaults (/data).

Endpoints (all require `Authorization: Bearer <OBSIDIAN_API_KEY>`):
  GET    /                  -> service info + vault list
  GET    /vault/<path>      -> file contents (bytes) or directory listing
  PUT    /vault/<path>      -> create/overwrite a file (body = file bytes)
  DELETE /vault/<path>      -> delete a file (or empty directory)

Serves /data (me/raw + me/wiki). Path traversal is rejected.
"""
import os
import json
import hmac
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA = Path(os.environ.get("DATA_DIR", "/data")).resolve()
KEY = os.environ.get("OBSIDIAN_API_KEY", "")
PORT = int(os.environ.get("OBSIDIAN_API_PORT", "27123"))


def authorized(handler):
    a = handler.headers.get("Authorization", "")
    if not a.startswith("Bearer "):
        return False
    return hmac.compare_digest(a[len("Bearer "):], KEY)


def safe_path(rel):
    rp = (DATA / rel.lstrip("/")).resolve()
    if rp == DATA or DATA in rp.parents:
        return rp
    return None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body=b"", ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj).encode())

    def _vault_root(self):
        entries = []
        for v in ("me/raw", "me/wiki"):
            d = DATA / v
            if d.is_dir():
                entries.append(v)
        return {"service": "obsidian-vault-api", "port": PORT, "vaults": entries}

    def do_GET(self):
        if not authorized(self):
            return self._json(401, {"error": "unauthorized"})
        u = urllib.parse.urlparse(self.path)
        if u.path in ("/", "/vault/", ""):
            return self._json(200, self._vault_root())
        if u.path.startswith("/vault/"):
            rp = safe_path(u.path[len("/vault/"):])
            if rp is None:
                return self._json(400, {"error": "invalid path"})
            if rp.is_dir():
                items = []
                for x in sorted(rp.iterdir()):
                    items.append({
                        "name": x.name,
                        "type": "dir" if x.is_dir() else "file",
                        "size": x.stat().st_size if x.is_file() else 0,
                    })
                return self._json(200, {"path": str(rp.relative_to(DATA)), "entries": items})
            if rp.is_file():
                return self._send(200, rp.read_bytes(), "application/octet-stream")
            return self._json(404, {"error": "not found"})
        return self._json(404, {"error": "not found"})

    def do_PUT(self):
        if not authorized(self):
            return self._json(401, {"error": "unauthorized"})
        u = urllib.parse.urlparse(self.path)
        if not u.path.startswith("/vault/"):
            return self._json(404, {"error": "not found"})
        rp = safe_path(u.path[len("/vault/"):])
        if rp is None:
            return self._json(400, {"error": "invalid path"})
        if rp.exists() and rp.is_dir():
            return self._json(400, {"error": "is a directory"})
        rp.parent.mkdir(parents=True, exist_ok=True)
        n = int(self.headers.get("Content-Length", 0) or 0)
        data = self.rfile.read(n) if n else b""
        rp.write_bytes(data)
        return self._json(200, {"ok": True, "path": str(rp.relative_to(DATA)), "bytes": len(data)})

    def do_DELETE(self):
        if not authorized(self):
            return self._json(401, {"error": "unauthorized"})
        u = urllib.parse.urlparse(self.path)
        if not u.path.startswith("/vault/"):
            return self._json(404, {"error": "not found"})
        rp = safe_path(u.path[len("/vault/"):])
        if rp is None:
            return self._json(400, {"error": "invalid path"})
        if not rp.exists():
            return self._json(404, {"error": "not found"})
        if rp.is_dir():
            if any(rp.iterdir()):
                return self._json(400, {"error": "directory not empty"})
            rp.rmdir()
        else:
            rp.unlink()
        return self._json(200, {"ok": True, "path": str(rp.relative_to(DATA))})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    if not KEY:
        raise SystemExit("OBSIDIAN_API_KEY not set")
    print(f"[vault-api] listening on :{PORT} serving {DATA}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
