#!/usr/bin/env python3
"""Static file server for the Obsidian volume (replaces `python3 -m http.server`).

Everything is served like http.server, with ONE extra rule: a request for a
`.md` file WITHOUT `?raw=1` gets a 302 redirect to the wiki viewer
(/me/wiki/viewer/index.html#<path>), so ANY markdown link opens rendered in the
browser. Requests WITH `?raw=1` (used by the viewer's own fetches) return the
raw markdown. No other logic — directory listings and static files unchanged.
"""
import http.server
import sys
import urllib.parse

PORT = int(sys.argv[1])
ROOT = sys.argv[2]
VIEWER = "/me/wiki/viewer/index.html"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def send_head(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = parsed.query
        if path.endswith(".md") and "raw=1" not in query:
            rel = path.lstrip("/")
            if rel.startswith("me/wiki/"):
                fragment = rel[len("me/wiki/"):]
            else:
                fragment = rel  # me/raw/... or anything else
            target = VIEWER + "#" + urllib.parse.quote(fragment)
            self.send_response(302)
            self.send_header("Location", target)
            self.end_headers()
            return None
        return super().send_head()

    def log_message(self, fmt, *args):
        pass  # keep the app log quiet


http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
