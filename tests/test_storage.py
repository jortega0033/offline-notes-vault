import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from notes_vault import storage
from notes_vault.storage import Store


class StorageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.store = Store(self.dir)

    def test_migration_sets_version_and_is_idempotent(self):
        self.assertEqual(self.store.schema_version(), 1)
        n = self.store.create("a", "b")
        again = Store(self.dir)
        self.assertEqual(again.schema_version(), 1)
        self.assertEqual(again.get(n["id"])["title"], "a")

    def test_future_schema_rejected_and_untouched(self):
        path = self.dir / "future"
        path.mkdir()
        with sqlite3.connect(path / storage.DB_NAME) as c:
            c.execute("PRAGMA user_version=99")
        c.close()
        with self.assertRaises(storage.SchemaTooNew):
            Store(path)
        c = sqlite3.connect(path / storage.DB_NAME)
        self.addCleanup(c.close)
        self.assertEqual(c.execute("PRAGMA user_version").fetchone()[0], 99)
        self.assertEqual(c.execute("SELECT count(*) FROM sqlite_master").fetchone()[0], 0)

    def test_create_get_roundtrip_and_timestamp_format(self):
        n = self.store.create("Title", "Body")
        self.assertEqual(n["revision"], 1)
        self.assertRegex(n["created_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$")
        self.assertEqual(self.store.get(n["id"]), n)
        with self.assertRaises(storage.NotFound):
            self.store.get(999)

    def test_update_increments_and_stale_leaves_row_unchanged(self):
        n = self.store.create("t", "b")
        u = self.store.update(n["id"], "t2", "b2", 1)
        self.assertEqual((u["revision"], u["title"]), (2, "t2"))
        with self.assertRaises(storage.StaleRevision) as cm:
            self.store.update(n["id"], "x", "y", 1)
        self.assertEqual(cm.exception.current, u)
        self.assertEqual(self.store.get(n["id"]), u)
        with self.assertRaises(storage.NotFound):
            self.store.update(12345, "x", "y", 1)

    def test_concurrent_updates_single_winner(self):
        n = self.store.create("t", "b")
        results = []
        barrier = threading.Barrier(8)

        def worker(i):
            barrier.wait()
            try:
                self.store.update(n["id"], f"t{i}", "b", 1)
                results.append("ok")
            except storage.StaleRevision:
                results.append("stale")

        ts = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(sorted(results), ["ok"] + ["stale"] * 7)
        self.assertEqual(self.store.get(n["id"])["revision"], 2)

    def test_list_search_rules(self):
        self.store.create("Café", "plain")
        self.store.create("x", "100% sure_thing")
        self.store.create("Straße", "y")
        self.assertEqual([s["title"] for s in self.store.list("CAFÉ")[0]], ["Café"])
        self.assertEqual(self.store.list("%")[1], 1)
        self.assertEqual(self.store.list("_")[1], 1)
        self.assertEqual(self.store.list("0% s")[1], 1)
        self.assertEqual(self.store.list("zzz")[0], [])
        self.assertEqual(self.store.list("   ")[1], 3)

    def test_list_order_newest_first(self):
        a = self.store.create("a", "")
        b = self.store.create("b", "")
        self.store.update(a["id"], "a", "", 1)
        self.assertEqual([s["id"] for s in self.store.list()[0]], [a["id"], b["id"]])

    def test_snippet_collapses_whitespace_and_centres_on_match(self):
        body = "word\n\n  " * 50 + "NEEDLE here"
        s = storage.make_snippet(body, "needle".casefold())
        self.assertIn("NEEDLE", s)
        self.assertNotIn("  ", s)
        self.assertLessEqual(len(s), 120)
        self.assertEqual(storage.make_snippet("a\n\tb"), "a b")
        self.assertEqual(len(storage.make_snippet("x" * 500)), 120)

    def test_note_limit(self):
        with sqlite3.connect(self.store.path) as c:
            c.executemany(
                "INSERT INTO notes (title, body, revision, created_at, updated_at) VALUES ('t','',1,'x','x')",
                [()] * storage.MAX_NOTES)
        c.close()
        with self.assertRaises(storage.LimitReached):
            self.store.create("one more", "")
        with self.assertRaises(storage.LimitReached):
            self.store.create_fixture()
        self.assertEqual(self.store.list()[1], storage.MAX_NOTES)

    def test_check_constraints_roll_back(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.create("t" * 201, "")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.create("t", "b" * 100001)
        self.assertEqual(self.store.list()[1], 0)
        self.store.create("ok", "b" * 100000)

    def test_fixture_idempotent(self):
        first = self.store.create_fixture()
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["body"], storage.FIXTURE_BODY)
        self.assertEqual(self.store.create_fixture(), [])
        self.assertEqual(self.store.list("night platforms")[1], 1)


if __name__ == "__main__":
    unittest.main()
