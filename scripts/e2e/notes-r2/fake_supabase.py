"""
A tiny in-memory stand-in for the parts of Supabase Storage the API uses (signed upload, signed read with Range,
info, list, delete, bucket). Local checks only: no auth, nothing persisted. `python fake_supabase.py 54321`.
"""

from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

OBJECTS: dict[tuple[str, str], bytes] = {}
BASE = "/storage/v1"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # quiet
        pass

    def _body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("content-length") or 0))

    def _send(
        self,
        status: int,
        data: bytes = b"",
        ctype: str = "application/json",
        extra: dict | None = None,
    ):
        self.send_response(status)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, obj) -> None:
        self._send(status, json.dumps(obj).encode())

    def _split(self, path: str, prefix: str):
        rest = path[len(BASE) + len(prefix) :]
        bucket, _, key = rest.partition("/")
        return bucket, key

    def do_POST(self):
        p = urlparse(self.path).path
        raw = self._body()
        if p.startswith(f"{BASE}/object/upload/sign/"):
            bucket, key = self._split(p, "/object/upload/sign/")
            return self._json(
                200,
                {"url": f"/object/upload/sign/{bucket}/{key}?token=t", "token": "t"},
            )
        if p.startswith(f"{BASE}/object/sign/"):
            bucket, key = self._split(p, "/object/sign/")
            return self._json(200, {"signedURL": f"/object/sign/{bucket}/{key}?token=t"})
        if p.startswith(f"{BASE}/object/list/"):
            bucket = p.rsplit("/", 1)[1]
            prefix = json.loads(raw or b"{}").get("prefix", "")
            names = [k[len(prefix) + 1 :] for (b, k) in OBJECTS if b == bucket and k.startswith(prefix + "/")]
            return self._json(200, [{"name": n} for n in names if "/" not in n])
        if p == f"{BASE}/bucket":
            return self._json(200, {"name": json.loads(raw)["id"]})
        if p.startswith(f"{BASE}/object/"):
            bucket, key = self._split(p, "/object/")
            if (bucket, key) in OBJECTS:
                return self._json(409, {"error": "Duplicate"})
            OBJECTS[(bucket, key)] = raw
            return self._json(200, {"Key": f"{bucket}/{key}"})
        self._json(404, {"error": "unknown"})

    def do_PUT(self):
        p = urlparse(self.path).path
        raw = self._body()
        if p.startswith(f"{BASE}/object/upload/sign/"):
            bucket, key = self._split(p, "/object/upload/sign/")
            OBJECTS[(bucket, key)] = raw
            return self._json(200, {"Key": f"{bucket}/{key}"})
        self._json(404, {"error": "unknown"})

    def do_DELETE(self):
        p = urlparse(self.path).path
        raw = self._body()
        bucket = p.rsplit("/", 1)[1]
        for key in json.loads(raw or b"{}").get("prefixes", []):
            OBJECTS.pop((bucket, key), None)
        self._json(200, [])

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/__objects":
            return self._json(200, sorted(f"{b}/{k}" for b, k in OBJECTS))
        m = re.match(rf"{BASE}/object/(sign|public|info)/(.*)$", p)
        if not m:
            return self._json(404, {"error": "unknown"})
        kind, rest = m.groups()
        bucket, _, key = rest.partition("/")
        data = OBJECTS.get((bucket, key))
        if data is None:
            return self._json(404, {"error": "Not found"})
        if kind == "info":
            return self._json(200, {"name": key, "size": len(data)})
        rng = self.headers.get("range")
        if rng and (r := re.match(r"bytes=(\d+)-(\d*)", rng)):
            start = int(r.group(1))
            end = int(r.group(2)) if r.group(2) else len(data) - 1
            if start >= len(data):
                return self._send(416, b"", extra={"content-range": f"bytes */{len(data)}"})
            end = min(end, len(data) - 1)
            return self._send(
                206,
                data[start : end + 1],
                "application/octet-stream",
                {
                    "content-range": f"bytes {start}-{end}/{len(data)}",
                    "accept-ranges": "bytes",
                },
            )
        self._send(200, data, "application/octet-stream", {"accept-ranges": "bytes"})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 54321
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
