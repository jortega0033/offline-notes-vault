"""JSON API: routing, validation and error mapping. Independent of the socket layer."""

import json
import re
from urllib.parse import parse_qs

from . import __version__
from . import storage

MAX_REQUEST_BYTES = 1048576
MAX_QUERY = 200
MAX_REVISION = 2**63 - 1
_ID_RE = re.compile(r"/api/v1/notes/([0-9]{1,18})")
_NOTE_KEYS = {"title", "body"}
_PUT_KEYS = {"title", "body", "base_revision"}


class ApiError(Exception):
    def __init__(self, status, code, message, extra=None, headers=None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.extra, self.headers = extra or {}, headers or {}

    def payload(self):
        return {"error": {"code": self.code, "message": self.message}, **self.extra}


def allowed_hosts(port):
    return {f"127.0.0.1:{port}", f"localhost:{port}"}


def check_origin(headers, port, mutating):
    """DNS-rebinding and cross-origin guard; raises ApiError 403."""
    hosts = allowed_hosts(port)
    host = (headers.get("Host") or "").strip().lower()
    if host not in hosts:
        raise ApiError(403, "forbidden_origin", "Host not allowed")
    if mutating:
        origin = headers.get("Origin")
        if origin is not None and origin.strip().lower() not in {f"http://{h}" for h in hosts}:
            raise ApiError(403, "forbidden_origin", "Origin not allowed")


def route(path):
    """Return (handler_name, allowed_methods, args) or None."""
    if path == "/api/v1/health":
        return "health", ("GET", "HEAD"), ()
    if path == "/api/v1/notes":
        return "notes", ("GET", "HEAD", "POST"), ()
    if path == "/api/v1/fixtures":
        return "fixtures", ("POST",), ()
    m = _ID_RE.fullmatch(path)
    if m:
        return "note", ("GET", "HEAD", "PUT"), (int(m.group(1)),)
    return None


def _text(value, field, limit, strip):
    if not isinstance(value, str):
        raise ApiError(400, "validation_failed", f"{field} must be a string")
    if "\x00" in value:
        raise ApiError(400, "validation_failed", f"{field} must not contain NUL characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ApiError(400, "validation_failed", f"{field} contains invalid Unicode") from None
    return value.strip() if strip else value.replace("\r\n", "\n")


def parse_json_object(raw):
    try:
        data = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        raise ApiError(400, "invalid_json", "Request body is not valid JSON") from None
    if not isinstance(data, dict):
        raise ApiError(400, "validation_failed", "Request body must be a JSON object")
    return data


def _reject_constant(name):
    raise ValueError(name)


def validate_note(data, keys):
    unknown = set(data) - keys
    if unknown:
        raise ApiError(400, "validation_failed", f"unknown field: {sorted(unknown)[0]}")
    missing = keys - set(data)
    if missing:
        raise ApiError(400, "validation_failed", f"missing field: {sorted(missing)[0]}")
    title = _text(data["title"], "title", storage.MAX_TITLE, True)
    if not 1 <= len(title) <= storage.MAX_TITLE:
        raise ApiError(400, "validation_failed", f"title must be 1..{storage.MAX_TITLE} characters")
    body = _text(data["body"], "body", storage.MAX_BODY, False)
    if len(body) > storage.MAX_BODY:
        raise ApiError(400, "validation_failed", f"body must be at most {storage.MAX_BODY} characters")
    rev = None
    if "base_revision" in keys:
        rev = data["base_revision"]
        if isinstance(rev, bool) or not isinstance(rev, int) or not 1 <= rev <= MAX_REVISION:
            raise ApiError(400, "validation_failed", "base_revision must be an integer >= 1")
    return title, body, rev


def handle(store, method, path, query, read_json):
    """Return (status, payload, extra_headers). `read_json()` yields the parsed
    body object and is only called for routes that need one."""
    r = route(path)
    if r is None:
        raise ApiError(404, "not_found", "Not found")
    name, allowed, args = r
    if method not in allowed:
        raise ApiError(405, "method_not_allowed", "Method not allowed", headers={"Allow": ", ".join(allowed)})
    try:
        return _dispatch(store, name, method, query, args, read_json)
    except storage.NotFound:
        raise ApiError(404, "not_found", "Note not found") from None
    except storage.LimitReached:
        raise ApiError(409, "limit_reached", f"Note limit of {storage.MAX_NOTES} reached") from None
    except storage.StaleRevision as exc:
        raise ApiError(409, "stale_revision", "Note changed since base_revision",
                       extra={"current": exc.current}) from None


def _dispatch(store, name, method, query, args, read_json):
    if name == "health":
        return 200, {"status": "ok", "version": __version__, "schema_version": store.schema_version()}, {}
    if name == "notes" and method != "POST":
        params = parse_qs(query, keep_blank_values=True, max_num_fields=50)
        qs = params.get("q", [""])
        if len(qs) != 1 or len(qs[0]) > MAX_QUERY:
            raise ApiError(400, "validation_failed", f"q must be a single value of at most {MAX_QUERY} characters")
        notes, total = store.list(qs[0])
        return 200, {"notes": notes, "total": total}, {}
    if name == "notes":
        title, body, _ = validate_note(read_json(), _NOTE_KEYS)
        note = store.create(title, body)
        return 201, note, {"Location": f"/api/v1/notes/{note['id']}"}
    if name == "note" and method != "PUT":
        return 200, store.get(args[0]), {}
    if name == "note":
        title, body, rev = validate_note(read_json(), _PUT_KEYS)
        return 200, store.update(args[0], title, body, rev), {}
    # fixtures
    data = read_json(allow_empty=True)
    if data:
        raise ApiError(400, "validation_failed", "fixtures takes an empty body or {}")
    created = store.create_fixture()
    summaries = [{"id": n["id"], "title": n["title"], "revision": n["revision"],
                  "updated_at": n["updated_at"], "snippet": storage.make_snippet(n["body"])} for n in created]
    return (201 if created else 200), {"created": summaries}, {}
