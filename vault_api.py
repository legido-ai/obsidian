#!/usr/bin/env python3
"""Vault HTTP API + public wiki UI for the Obsidian vaults (/data).

Public (no auth) — wiki interface:
  GET /                -> HTML index (wiki + raw)
  GET /wiki/           -> rendered wiki index (README + all notes)
  GET /wiki/<path>     -> rendered markdown note (or dir listing)
  GET /raw/            -> raw sources listing
  GET /raw/<path>      -> raw file contents

Authenticated (Bearer key) — JSON API for Hermes:
  GET    /vault/<path>      -> file contents or directory listing (?recursive=1)
  PUT    /vault/<path>      -> create/overwrite a file
  DELETE /vault/<path>      -> delete a file (or empty directory)
"""
import os
import re
import json
import html as htmlmod
import hmac
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA = Path(os.environ.get("DATA_DIR", "/data")).resolve()
KEY = os.environ.get("OBSIDIAN_API_KEY", "")
PORT = int(os.environ.get("OBSIDIAN_API_PORT", "27123"))
WIKI = DATA / "me" / "wiki"
RAW = DATA / "me" / "raw"

CSS = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:860px;margin:0 auto;padding:24px;line-height:1.6;color:#1f2328;background:#fff}
h1,h2,h3{border-bottom:1px solid #e5e7eb;padding-bottom:.3em;margin-top:1.4em}
a{color:#0969da;text-decoration:none}a:hover{text-decoration:underline}
code{background:#f3f4f6;padding:.15em .35em;border-radius:4px;font-size:.9em}
pre{background:#f6f8fa;padding:14px;border-radius:6px;overflow-x:auto}pre code{background:none;padding:0}
blockquote{border-left:4px solid #d0d7de;margin:0;padding-left:14px;color:#57606a}
table{border-collapse:collapse}td,th{border:1px solid #d0d7de;padding:6px 10px}
.meta{color:#57606a;font-size:.9em}.note{background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;padding:10px 14px;margin:6px 0}
.breadcrumb{font-size:.9em;color:#57606a}
"""


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


def walk_files(root):
    """[(relpath, Path)] recursively."""
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out.append((p.relative_to(DATA).as_posix(), p))
    return out


# ---------------- markdown -> html ----------------

def inline_md(text):
    t = htmlmod.escape(text)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+|/[^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r'<a href="/wiki/\1.md">\2</a>', t)
    t = re.sub(r"\[\[([^\]]+)\]\]", r'<a href="/wiki/\1.md">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", t)
    return t


def render_md(md_text):
    out, i, lines = [], 0, md_text.split("\n")
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            block, i = [], i + 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i]); i += 1
            out.append("<pre><code>" + htmlmod.escape("\n".join(block)) + "</code></pre>")
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline_md(m.group(2))}</h{lvl}>")
        elif re.match(r"^\s*[-*]\s+", ln):
            items, i = [], i
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append("<li>" + inline_md(re.sub(r"^\s*[-*]\s+", "", lines[i])) + "</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif re.match(r"^\s*\d+\.\s+", ln):
            items, i = [], i
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append("<li>" + inline_md(re.sub(r"^\s*\d+\.\s+", "", lines[i])) + "</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        elif ln.strip().startswith(">"):
            out.append("<blockquote>" + inline_md(ln.strip()[1:].strip()) + "</blockquote>")
        elif re.match(r"^\s*---+\s*$", ln):
            out.append("<hr>")
        elif ln.strip() == "":
            pass
        else:
            out.append("<p>" + inline_md(ln) + "</p>")
        i += 1
    return "\n".join(out)


def page(title, body_html, breadcrumb=""):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{htmlmod.escape(title)}</title><style>{CSS}</style></head><body>
<div class="breadcrumb"><a href="/">🏠 índice</a>{breadcrumb}</div>
{body_html}</body></html>"""


def listing_html(entries, base_url, header):
    items = []
    for rel, p in sorted(entries):
        if p.is_dir():
            items.append(f'<div class="note">📁 <a href="{base_url}{rel}/">{rel}/</a></div>')
        else:
            items.append(f'<div class="note">📄 <a href="{base_url}{rel}">{rel}</a> <span class="meta">({p.stat().st_size} B)</span></div>')
    return f"<h1>{header}</h1>" + ("".join(items) if items else "<p><em>vacío</em></p>")


# ---------------- handler ----------------

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body=b"", ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj).encode(), "application/json")

    # ---- public wiki UI ----
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(u.path)
        if path in ("/", ""):
            return self._index()
        if path == "/wiki/" or path.startswith("/wiki/"):
            return self._wiki(path[len("/wiki/"):])
        if path == "/raw/" or path.startswith("/raw/"):
            return self._raw(path[len("/raw/"):])
        if path.startswith("/vault/"):
            return self._vault_api(u)
        return self._json(404, {"error": "not found"})

    def _index(self):
        notes = [p for p in WIKI.rglob("*.md")] if WIKI.exists() else []
        raws = [p for p in RAW.rglob("*") if p.is_file()] if RAW.exists() else []
        body = f"<h1>📚 Wiki de investigación</h1><p class=\"meta\">{len(notes)} notas · {len(raws)} fuentes en bruto</p>"
        body += f'<p><a href="/wiki/">📖 Ver wiki ({len(notes)} notas)</a> · <a href="/raw/">🗂 Ver raw ({len(raws)} fuentes)</a></p>'
        body += "<h2>Últimas notas</h2>"
        recent = sorted(notes, key=lambda p: p.stat().st_mtime, reverse=True)[:10]
        body += "".join(f'<div class="note">📄 <a href="/wiki/{p.relative_to(WIKI).as_posix()}">{p.relative_to(WIKI).as_posix()}</a></div>'
                        for p in recent)
        body += "<h2>Últimas fuentes</h2>"
        recent_raw = sorted(raws, key=lambda p: p.stat().st_mtime, reverse=True)[:10]
        body += "".join(f'<div class="note">🗂 <a href="/raw/{p.relative_to(RAW).as_posix()}">{p.relative_to(RAW).as_posix()}</a></div>'
                        for p in recent_raw)
        self._send(200, page("Wiki de investigación", body).encode())

    def _wiki(self, rel):
        if rel == "" or rel.endswith("/"):
            target = WIKI / rel
            if target.is_dir():
                entries = [(p.relative_to(DATA).as_posix(), p) for p in sorted(target.iterdir())]
                # if README.md exists in this dir, render it on top
                extra = ""
                readme = target / "README.md"
                if readme.is_file():
                    extra = render_md(readme.read_text(errors="replace"))
                return self._send(200, page(f"wiki/{rel}", extra + listing_html(entries, "/wiki/", f"📖 wiki/{rel}")).encode())
            return self._send(404, page("404", "<p>No encontrado</p>").encode())
        rp = safe_path("me/wiki/" + rel)
        if rp is None:
            return self._send(400, page("400", "<p>Ruta inválida</p>").encode())
        if rp.is_dir():
            entries = [(p.relative_to(DATA).as_posix(), p) for p in sorted(rp.iterdir())]
            return self._send(200, page(f"wiki/{rel}", listing_html(entries, "/wiki/", f"📖 wiki/{rel}")).encode())
        if rp.is_file():
            if rp.suffix == ".md":
                md_text = rp.read_text(errors="replace")
                body = render_md(md_text)
                return self._send(200, page(rp.stem, body, f" · <a href=\"/wiki/{rp.parent.relative_to(WIKI).as_posix()}/\">subir</a>").encode())
            return self._send(200, rp.read_bytes(), "application/octet-stream")
        return self._send(404, page("404", "<p>Nota no encontrada</p>").encode())

    def _raw(self, rel):
        if rel == "" or rel.endswith("/"):
            target = RAW / rel
            if target.is_dir():
                entries = [(p.relative_to(DATA).as_posix(), p) for p in sorted(target.iterdir())]
                return self._send(200, page(f"raw/{rel}", listing_html(entries, "/raw/", f"🗂 raw/{rel}")).encode())
            return self._send(404, page("404", "<p>No encontrado</p>").encode())
        rp = safe_path("me/raw/" + rel)
        if rp is not None and rp.is_file():
            return self._send(200, rp.read_bytes(), "text/plain; charset=utf-8" if rp.suffix == ".md" else "application/octet-stream")
        return self._send(404, page("404", "<p>No encontrado</p>").encode())

    # ---- authenticated JSON API ----
    def _vault_api(self, u):
        if not authorized(self):
            return self._json(401, {"error": "unauthorized"})
        rel = u.path[len("/vault/"):]
        if u.path in ("/vault/", "/vault"):
            entries = []
            for v in ("me/raw", "me/wiki"):
                d = DATA / v
                if d.is_dir():
                    entries.append(v)
            return self._json(200, {"service": "obsidian-vault-api", "port": PORT, "vaults": entries})
        rp = safe_path(rel)
        if rp is None:
            return self._json(400, {"error": "invalid path"})
        recursive = urllib.parse.parse_qs(u.query).get("recursive", ["0"])[0] == "1"
        if rp.is_dir():
            if recursive:
                items = [{"path": p.relative_to(DATA).as_posix(), "type": "file",
                          "size": p.stat().st_size} for p in sorted(rp.rglob("*")) if p.is_file()]
            else:
                items = [{"name": x.name, "type": "dir" if x.is_dir() else "file",
                          "size": x.stat().st_size if x.is_file() else 0} for x in sorted(rp.iterdir())]
            return self._json(200, {"path": str(rp.relative_to(DATA)), "entries": items})
        if rp.is_file():
            return self._send(200, rp.read_bytes(), "application/octet-stream")
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
