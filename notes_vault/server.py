"""HTTP server: static allowlist, security headers, lifecycle."""

import json
import re
import sys
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import api
from .storage import Store

STATIC_DIR = Path(__file__).resolve().parent / "static"
# Exact allowlist: request path -> (fixed file name, content type).
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/static/app.css": ("app.css", "text/css; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
       "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
_CT_RE = re.compile(r"application/json\s*(;\s*charset\s*=\s*\"?utf-8\"?\s*)?", re.I)
_ERROR_CODES = {400: "invalid_request", 408: "request_timeout", 414: "uri_too_long",
                431: "header_too_large", 501: "not_implemented", 505: "version_not_supported"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "OfflineNotesVault"
    sys_version = ""
    timeout = 10

    def log_message(self, fmt, *args):
        pass

    # --- response helpers -------------------------------------------------
    def _send(self, status, body=b"", ctype="application/json; charset=utf-8", headers=None, html=False):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if html:
            self.send_header("Content-Security-Policy", CSP)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, payload, headers=None):
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers)

    def _error(self, err):
        self._json(err.status, err.payload(), err.headers)

    def send_error(self, code, message=None, explain=None):
        self.close_connection = True
        name = _ERROR_CODES.get(code, "http_error")
        try:
            msg = HTTPStatus(code).phrase
        except ValueError:
            msg = "Error"
        self._error(api.ApiError(code, name, msg))

    # --- request handling -------------------------------------------------
    def _read_json(self, allow_empty=False):
        raw_len = self.headers.get("Content-Length")
        if raw_len is None or self.headers.get("Transfer-Encoding"):
            raise self._unread(api.ApiError(411, "length_required", "Content-Length is required"))
        if not raw_len.isascii() or not raw_len.isdigit():
            raise self._unread(api.ApiError(400, "invalid_request", "Invalid Content-Length"))
        length = int(raw_len)
        if length > api.MAX_REQUEST_BYTES:
            raise self._unread(api.ApiError(413, "payload_too_large", "Request body too large"))
        if length == 0 and allow_empty:
            return {}
        if not _CT_RE.fullmatch(self.headers.get("Content-Type", "").strip()):
            raise self._unread(api.ApiError(415, "unsupported_media_type", "Content-Type must be application/json"))
        raw = self.rfile.read(length)
        self._consumed = True
        if len(raw) != length:
            self.close_connection = True
            raise api.ApiError(400, "invalid_json", "Request body truncated")
        return api.parse_json_object(raw)

    def _unread(self, err):
        return err

    def _settle_body(self):
        """After an error response path, keep the connection in sync: discard a small
        declared body, otherwise close so leftover bytes are never parsed as a request."""
        raw = self.headers.get("Content-Length", "")
        if (self.command in ("POST", "PUT", "PATCH", "DELETE") and not self._consumed
                and not self.close_connection):
            if (raw.isascii() and raw.isdigit() and 0 < int(raw) <= 65536
                    and not self.headers.get("Transfer-Encoding")):
                self.rfile.read(int(raw))
                self._consumed = True
            elif raw != "0":
                self.close_connection = True

    def _handle(self):
        self._consumed = False
        method = self.command
        try:
            # Keep the original leading slashes for the exact route allowlist.
            target = self.requestline.split(maxsplit=2)[1].split("#", 1)[0]
            path, _, query = target.partition("?")
            api.check_origin(self.headers, self.server.server_address[1], method in ("POST", "PUT"))
            if not path.startswith("/") or path.startswith("//"):
                raise api.ApiError(404, "not_found", "Not found")
            if method == "OPTIONS":
                raise api.ApiError(405, "method_not_allowed", "Method not allowed",
                                   headers={"Allow": "GET, HEAD, POST, PUT"})
            if path in STATIC:
                return self._static(path)
            if not path.startswith("/api/"):
                raise api.ApiError(404, "not_found", "Not found")
            status, payload, headers = api.handle(self.server.store, method, path, query, self._read_json)
            self._json(status, payload, headers)
        except api.ApiError as err:
            self._settle_body()
            self._error(err)
        except (TimeoutError, ConnectionError):
            self.close_connection = True
        except Exception:
            self.close_connection = True
            traceback.print_exc(file=sys.stderr)
            self._error(api.ApiError(500, "internal_error", "Internal server error"))

    def _static(self, path):
        if self.command not in ("GET", "HEAD"):
            raise api.ApiError(405, "method_not_allowed", "Method not allowed", headers={"Allow": "GET, HEAD"})
        name, ctype = STATIC[path]
        try:
            data = (STATIC_DIR / name).read_bytes()
        except OSError:
            raise api.ApiError(404, "not_found", "Not found") from None
        self._send(200, data, ctype, html=ctype.startswith("text/html"))

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _handle


class NotesServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 64

    def __init__(self, address, store):
        self.store = store
        self._serving = False
        self._closed = False
        super().__init__(address, Handler)

    def serve_forever(self, poll_interval=0.5):
        self._serving = True
        super().serve_forever(poll_interval)

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._serving:
            self.shutdown()
        self.server_close()
        self.store.close()


def create_server(data_dir, port):
    store = Store(data_dir)
    try:
        return NotesServer(("127.0.0.1", port), store)
    except BaseException:
        store.close()
        raise
