"""SQLite storage. One short-lived connection per operation."""

import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_NAME = "notes.sqlite3"
MAX_NOTES = 5000
MAX_TITLE = 200
MAX_BODY = 100000
SNIPPET_LEN = 120
FIXTURE_TITLE = "Station field notes"
FIXTURE_BODY = (
    "# Station field notes\n\n"
    "Night platforms are quiet after 23:00; the east stairwell light flickers.\n"
    "Door sensor 4 reset twice. Check the relay cabinet on the next visit.\n"
)

# Ordered migrations; index i upgrades schema version i to i+1.
MIGRATIONS = [
    [
        """CREATE TABLE notes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
          body TEXT NOT NULL CHECK (length(body) <= 100000),
          revision INTEGER NOT NULL CHECK (revision >= 1),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )""",
        "CREATE INDEX notes_updated ON notes(updated_at DESC, id DESC)",
    ],
]
SCHEMA_VERSION = len(MIGRATIONS)
_COLS = "id, title, body, revision, created_at, updated_at"


class StorageError(Exception):
    pass


class SchemaTooNew(StorageError):
    pass


class NotFound(StorageError):
    pass


class LimitReached(StorageError):
    pass


class StaleRevision(StorageError):
    def __init__(self, current):
        super().__init__("stale revision")
        self.current = current


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _next_ts(conn):
    """Timestamp strictly after every stored updated_at, so list order is stable
    even when the system clock has coarse resolution."""
    ts = now_iso()
    last = conn.execute("SELECT MAX(updated_at) FROM notes").fetchone()[0]
    if last and ts <= last:
        dt = datetime.strptime(last, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        ts = (dt + timedelta(microseconds=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return ts


def _note(row):
    return dict(zip(("id", "title", "body", "revision", "created_at", "updated_at"), row))


def make_snippet(body, q=""):
    text = " ".join(body.split())
    start = 0
    qf = q.casefold()
    if qf:
        # Map positions in the casefolded text back to the original text.
        origin = [i for i, ch in enumerate(text) for _ in ch.casefold()]
        idx = text.casefold().find(qf)
        if idx >= 0:
            start = max(0, origin[idx] - 40)
    return text[start:start + SNIPPET_LEN]


class Store:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / DB_NAME
        self._migrate()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
        except BaseException:
            conn.close()
            raise
        return conn

    @contextmanager
    def _tx(self):
        """Connection inside a write transaction; rolled back on any error."""
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.execute("COMMIT")
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise

    def _migrate(self):
        # Check the version before touching the file's journal mode.
        with closing(self._connect()) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise SchemaTooNew(
                    f"database schema version {version} is newer than supported version {SCHEMA_VERSION}")
            conn.execute("PRAGMA journal_mode=WAL")
        with self._tx() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise SchemaTooNew(
                    f"database schema version {version} is newer than supported version {SCHEMA_VERSION}")
            for v in range(version, SCHEMA_VERSION):
                for stmt in MIGRATIONS[v]:
                    conn.execute(stmt)
                conn.execute(f"PRAGMA user_version={v + 1}")

    def schema_version(self):
        with closing(self._connect()) as conn:
            return conn.execute("PRAGMA user_version").fetchone()[0]

    def close(self):
        """No persistent connections are held; kept for lifecycle symmetry."""

    def _insert(self, conn, title, body):
        if conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] >= MAX_NOTES:
            raise LimitReached("note limit reached")
        ts = _next_ts(conn)
        cur = conn.execute(
            "INSERT INTO notes (title, body, revision, created_at, updated_at) VALUES (?,?,1,?,?)",
            (title, body, ts, ts))
        return _note(conn.execute(f"SELECT {_COLS} FROM notes WHERE id=?", (cur.lastrowid,)).fetchone())

    def create(self, title, body):
        with self._tx() as conn:
            return self._insert(conn, title, body)

    def get(self, note_id):
        with closing(self._connect()) as conn:
            row = conn.execute(f"SELECT {_COLS} FROM notes WHERE id=?", (note_id,)).fetchone()
        if row is None:
            raise NotFound("note not found")
        return _note(row)

    def update(self, note_id, title, body, base_revision):
        with self._tx() as conn:
            cur = conn.execute(
                "UPDATE notes SET title=?, body=?, revision=revision+1, updated_at=? WHERE id=? AND revision=?",
                (title, body, _next_ts(conn), note_id, base_revision))
            row = conn.execute(f"SELECT {_COLS} FROM notes WHERE id=?", (note_id,)).fetchone()
            if row is None:
                raise NotFound("note not found")
            if cur.rowcount == 0:
                raise StaleRevision(_note(row))
            return _note(row)

    def list(self, q=""):
        """Return (summaries, total) ordered by updated_at DESC, id DESC."""
        qf = q.strip().casefold()
        out = []
        with closing(self._connect()) as conn:
            cur = conn.execute(f"SELECT {_COLS} FROM notes ORDER BY updated_at DESC, id DESC")
            for row in cur:
                n = _note(row)
                if qf and qf not in n["title"].casefold() and qf not in n["body"].casefold():
                    continue
                out.append({"id": n["id"], "title": n["title"], "revision": n["revision"],
                            "updated_at": n["updated_at"], "snippet": make_snippet(n["body"], qf)})
        return out, len(out)

    def create_fixture(self):
        """Create the sample note once; returns the created notes (empty if present)."""
        with self._tx() as conn:
            if conn.execute("SELECT 1 FROM notes WHERE title=?", (FIXTURE_TITLE,)).fetchone():
                return []
            return [self._insert(conn, FIXTURE_TITLE, FIXTURE_BODY)]
