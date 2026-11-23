import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from notes_vault import api, storage
from notes_vault.server import create_server

JSON = {"Content-Type": "application/json"}


class ApiBase(unittest.TestCase):
    def start(self, data_dir=None):
        if data_dir is None:
            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            data_dir = tmp.name
        server = create_server(data_dir, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.close)
        self.port = server.server_address[1]
        self.request("GET", "/api/v1/health")  # ensure the loop is running
        return server

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.server = self.start(self.tmp.name)

    def request(self, method, path, body=None, headers=None, raw=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            hdrs = dict(headers or {})
            data = raw
            if body is not None:
                data = json.dumps(body).encode("utf-8")
                hdrs.setdefault("Content-Type", "application/json")
            conn.request(method, path, body=data, headers=hdrs)
            resp = conn.getresponse()
            payload = resp.read()
            return resp, payload
        finally:
            conn.close()

    def call(self, method, path, body=None, headers=None):
        resp, payload = self.request(method, path, body, headers)
        return resp.status, json.loads(payload), resp

    def make(self, title="T", body="B"):
        status, note, _ = self.call("POST", "/api/v1/notes", {"title": title, "body": body})
        self.assertEqual(status, 201)
        return note


class NotesApiTests(ApiBase):
    def test_health(self):
        status, data, resp = self.call("GET", "/api/v1/health")
        self.assertEqual((status, data), (200, {"status": "ok", "version": "0.1.0", "schema_version": 1}))
        self.assertEqual(resp.getheader("Cache-Control"), "no-store")
        self.assertEqual(resp.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.getheader("Referrer-Policy"), "no-referrer")
        self.assertIsNone(resp.getheader("Access-Control-Allow-Origin"))

    def test_create_list_get(self):
        status, note, resp = self.call("POST", "/api/v1/notes", {"title": "  Hello  ", "body": "a\r\nb"})
        self.assertEqual(status, 201)
        self.assertEqual(resp.getheader("Location"), f"/api/v1/notes/{note['id']}")
        self.assertEqual((note["title"], note["body"], note["revision"]), ("Hello", "a\nb", 1))
        self.assertEqual(self.call("GET", f"/api/v1/notes/{note['id']}")[1], note)
        _, listing, _ = self.call("GET", "/api/v1/notes")
        self.assertEqual(listing["total"], 1)
        self.assertEqual(set(listing["notes"][0]), {"id", "title", "revision", "updated_at", "snippet"})
        self.assertEqual(listing["notes"][0]["snippet"], "a b")

    def test_search(self):
        self.make("Émile", "plain")
        self.make("x", "50% off, a_b")
        self.make("Straße", "y")
        q = lambda s: self.call("GET", "/api/v1/notes?q=" + s)[1]
        self.assertEqual(q("%C3%A9mile")["total"], 1)
        self.assertEqual(q("%C3%89MILE")["total"], 1)
        self.assertEqual(q("%25")["total"], 1)
        self.assertEqual(q("_")["total"], 1)
        self.assertEqual(q("zzz-none"), {"notes": [], "total": 0})
        self.assertEqual(q("%20%20")["total"], 3)
        self.assertEqual(self.call("GET", "/api/v1/notes?q=" + "a" * 201)[0], 400)

    def test_validation_errors(self):
        bad = [
            {"title": "t"}, {"title": "t", "body": "b", "extra": 1}, {"title": "  ", "body": ""},
            {"title": "t" * 201, "body": ""}, {"title": "t", "body": "b" * 100001},
            {"title": 5, "body": ""}, {"title": "a\u0000b", "body": ""}, {"title": "t", "body": "\u0000"},
            {"title": "\ud800", "body": ""}, [], "text",
        ]
        for payload in bad:
            with self.subTest(payload=str(payload)[:40]):
                status, data, _ = self.call("POST", "/api/v1/notes", payload)
                self.assertEqual(status, 400)
                self.assertEqual(data["error"]["code"], "validation_failed")
        resp, payload = self.request("POST", "/api/v1/notes", headers=JSON, raw=b"{nope")
        self.assertEqual((resp.status, json.loads(payload)["error"]["code"]), (400, "invalid_json"))
        resp, payload = self.request("POST", "/api/v1/notes", headers=JSON, raw=b'{"title":NaN,"body":""}')
        self.assertEqual(resp.status, 400)
        resp, _ = self.request("POST", "/api/v1/notes", headers=JSON, raw=b"\xff\xfe")
        self.assertEqual(resp.status, 400)
        self.assertEqual(self.call("GET", "/api/v1/notes")[1]["total"], 0)

    def test_put_validation(self):
        n = self.make()
        for rev in (0, -1, True, "1", 1.5, None, 2**70):
            with self.subTest(rev=rev):
                status, _, _ = self.call("PUT", f"/api/v1/notes/{n['id']}",
                                         {"title": "t", "body": "", "base_revision": rev})
                self.assertEqual(status, 400)
        status, _, _ = self.call("PUT", f"/api/v1/notes/{n['id']}", {"title": "t", "body": ""})
        self.assertEqual(status, 400)
        self.assertEqual(self.call("GET", f"/api/v1/notes/{n['id']}")[1]["revision"], 1)

    def test_update_and_stale_conflict(self):
        n = self.make("t", "one")
        status, upd, _ = self.call("PUT", f"/api/v1/notes/{n['id']}",
                                   {"title": "t", "body": "two", "base_revision": 1})
        self.assertEqual((status, upd["revision"], upd["body"]), (200, 2, "two"))
        status, data, _ = self.call("PUT", f"/api/v1/notes/{n['id']}",
                                    {"title": "t", "body": "mine", "base_revision": 1})
        self.assertEqual(status, 409)
        self.assertEqual(data["error"]["code"], "stale_revision")
        self.assertEqual(data["current"], upd)
        self.assertEqual(self.call("GET", f"/api/v1/notes/{n['id']}")[1], upd)
        status, data, _ = self.call("PUT", "/api/v1/notes/9999", {"title": "t", "body": "", "base_revision": 1})
        self.assertEqual((status, data["error"]["code"]), (404, "not_found"))

    def test_concurrent_puts_one_winner(self):
        n = self.make()
        out, barrier = [], threading.Barrier(8)

        def worker(i):
            barrier.wait()
            out.append(self.call("PUT", f"/api/v1/notes/{n['id']}",
                                 {"title": f"w{i}", "body": "", "base_revision": 1})[0])

        ts = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(sorted(out), [200] + [409] * 7)
        self.assertEqual(self.call("GET", f"/api/v1/notes/{n['id']}")[1]["revision"], 2)

    def test_fixture_idempotent_and_searchable(self):
        status, data, _ = self.call("POST", "/api/v1/fixtures", {})
        self.assertEqual(status, 201)
        self.assertEqual(data["created"][0]["title"], "Station field notes")
        resp, payload = self.request("POST", "/api/v1/fixtures", raw=b"", headers={"Content-Length": "0"})
        self.assertEqual((resp.status, json.loads(payload)), (200, {"created": []}))
        self.assertEqual(self.call("GET", "/api/v1/notes?q=NIGHT%20platforms")[1]["total"], 1)
        self.assertEqual(self.call("GET", "/api/v1/notes")[1]["total"], 1)
        self.assertEqual(self.call("POST", "/api/v1/fixtures", {"x": 1})[0], 400)

    def test_persistence_across_restart(self):
        n = self.make("keep", "me")
        self.server.close()
        server2 = self.start(self.tmp.name)
        self.assertEqual(self.call("GET", f"/api/v1/notes/{n['id']}")[1], n)
        self.assertNotEqual(server2, self.server)


class HttpBoundaryTests(ApiBase):
    def test_size_cap_413_and_exact_limit(self):
        # Declare an oversize body but send none: the server must answer from the header alone.
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        self.addCleanup(conn.close)
        conn.putrequest("POST", "/api/v1/notes")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(api.MAX_REQUEST_BYTES + 1))
        conn.endheaders()
        resp = conn.getresponse()
        self.assertEqual((resp.status, json.loads(resp.read())["error"]["code"]), (413, "payload_too_large"))
        self.assertEqual(self.call("GET", "/api/v1/notes")[1]["total"], 0)
        status, _, _ = self.call("POST", "/api/v1/notes", {"title": "ok", "body": "x"})
        self.assertEqual(status, 201)

    def test_missing_length_411(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        self.addCleanup(conn.close)
        conn.putrequest("POST", "/api/v1/notes")
        conn.putheader("Content-Type", "application/json")
        conn.endheaders()
        resp = conn.getresponse()
        self.assertEqual((resp.status, json.loads(resp.read())["error"]["code"]), (411, "length_required"))

    def test_content_type_415(self):
        for ct in ("text/plain", "application/x-www-form-urlencoded", "application/jsonx"):
            resp, payload = self.request("POST", "/api/v1/notes", raw=b"{}", headers={"Content-Type": ct})
            self.assertEqual((resp.status, json.loads(payload)["error"]["code"]), (415, "unsupported_media_type"))
        resp, _ = self.request("POST", "/api/v1/notes", raw=b"{}")
        self.assertEqual(resp.status, 415)
        ct = "application/json; charset=utf-8"
        resp, _ = self.request("POST", "/api/v1/notes", raw=b'{"title":"t","body":""}', headers={"Content-Type": ct})
        self.assertEqual(resp.status, 201)

    def test_foreign_host_and_origin_403(self):
        body = {"title": "t", "body": ""}
        for headers in ({"Host": "evil.example"}, {"Host": "127.0.0.1"}, {"Origin": "http://evil.example"},
                        {"Origin": "null"}, {"Origin": f"http://127.0.0.1:{self.port + 1}"}):
            with self.subTest(headers=headers):
                status, data, _ = self.call("POST", "/api/v1/notes", body, headers)
                self.assertEqual((status, data["error"]["code"]), (403, "forbidden_origin"))
        self.assertEqual(self.call("GET", "/api/v1/health", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("GET", "/", headers={"Host": "evil.example"})[0].status, 403)
        self.assertEqual(self.call("GET", "/api/v1/notes")[1]["total"], 0)
        for ok in (f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"):
            self.assertEqual(self.call("POST", "/api/v1/notes", body, {"Origin": ok})[0], 201)
        self.assertEqual(self.call("GET", "/api/v1/health", headers={"Host": f"localhost:{self.port}"})[0], 200)

    def test_routing_errors(self):
        for method, path in (("GET", "/api/v1/nope"), ("GET", "/api/v1/notes/abc"), ("GET", "/api/v1/notes/1/"),
                             ("GET", "/api/v1/notes/" + "1" * 19), ("GET", "/api/v1/notes/%31"),
                             ("GET", "/nope"), ("GET", "//static/app.css")):
            with self.subTest(path=path):
                status, data, _ = self.call(method, path)
                self.assertEqual((status, data["error"]["code"]), (404, "not_found"))
        status, data, resp = self.call("DELETE", "/api/v1/notes/1")
        self.assertEqual((status, data["error"]["code"]), (405, "method_not_allowed"))
        self.assertIn("GET", resp.getheader("Allow"))
        status, _, resp = self.call("POST", "/api/v1/health", {})
        self.assertEqual(status, 405)
        self.assertEqual(self.call("OPTIONS", "/api/v1/notes")[0], 405)
        self.assertIsNone(self.request("OPTIONS", "/api/v1/notes")[0].getheader("Access-Control-Allow-Origin"))

    def test_static_allowlist(self):
        static = Path(storage.__file__).parent / "static"
        for path, name, ctype in (("/", "index.html", "text/html"), ("/index.html", "index.html", "text/html"),
                                  ("/static/tokens.css", "tokens.css", "text/css"),
                                  ("/static/app.css", "app.css", "text/css"),
                                  ("/static/app.js", "app.js", "text/javascript")):
            if not (static / name).is_file():
                self.skipTest("static assets not present yet")
            with self.subTest(path=path):
                resp, payload = self.request("GET", path + "?v=1")
                self.assertEqual(resp.status, 200)
                self.assertTrue(resp.getheader("Content-Type").startswith(ctype))
                self.assertEqual(payload, (static / name).read_bytes())
                self.assertEqual(resp.getheader("Cache-Control"), "no-store")
                self.assertEqual(bool(resp.getheader("Content-Security-Policy")), ctype == "text/html")
                head, body = self.request("HEAD", path)
                self.assertEqual((head.status, body), (200, b""))
        csp = self.request("GET", "/")[0].getheader("Content-Security-Policy")
        self.assertIn("default-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)

    def test_static_traversal_and_other_files_404(self):
        for path in ("/static/", "/static/../storage.py", "/static/%2e%2e/storage.py", "/static/..%2fapi.py",
                     "/static/app.css/", "/static/index.html", "/../notes_vault/server.py", "/__init__.py",
                     "/static\\app.css", "/static/app.js%00", "/notes.sqlite3"):
            with self.subTest(path=path):
                resp, payload = self.request("GET", path)
                self.assertEqual(resp.status, 404)
                self.assertEqual(json.loads(payload)["error"]["code"], "not_found")
        self.assertEqual(self.request("POST", "/static/app.js", raw=b"{}", headers=JSON)[0].status, 405)

    def test_error_after_unread_body_keeps_server_usable(self):
        resp, _ = self.request("POST", "/api/v1/notes/1", raw=b"x" * 1000, headers=JSON)
        self.assertEqual(resp.status, 405)
        self.assertEqual(self.call("GET", "/api/v1/health")[0], 200)

    def test_internal_error_hides_details(self):
        self.server.store.list = lambda q="": 1 / 0
        resp, payload = self.request("GET", "/api/v1/notes")
        self.assertEqual(resp.status, 500)
        self.assertEqual(json.loads(payload)["error"]["code"], "internal_error")
        self.assertNotIn(b"ZeroDivision", payload)
        self.assertNotIn(b"Traceback", payload)


class StartupTests(ApiBase):
    def setUp(self):
        pass

    def test_future_schema_refuses_to_start(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        c = sqlite3.connect(Path(tmp.name) / storage.DB_NAME)
        c.execute("PRAGMA user_version=7")
        c.close()
        with self.assertRaises(storage.SchemaTooNew):
            create_server(tmp.name, 0)

    def test_bind_failure_does_not_leak_store(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        first = self.start(self.tmp.name)
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(OSError):
                create_server(other, first.server_address[1])

    def test_close_without_serving_and_twice(self):
        with tempfile.TemporaryDirectory() as d:
            server = create_server(d, 0)
            server.close()
            server.close()


if __name__ == "__main__":
    unittest.main()
