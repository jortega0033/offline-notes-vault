# Offline Notes Vault

A small offline notes workbench for one person: write technical notes in a browser, find earlier details by a remembered word, and keep text safe when two tabs edit the same note. Everything runs on your machine: Python 3.12 standard library, SQLite, and static HTML/CSS/JS served on `127.0.0.1`. No network, accounts, build step or external assets.

M1 implements saving, reopening, and filtering plain-text notes. See the baseline verification below. Full spec: [docs/PRD.md](docs/PRD.md).

## Launch

Linux:

```
python3 -m notes_vault --data-dir ./vault-data --port 8765
```

Windows:

```
python -m notes_vault --data-dir .\vault-data --port 8765
```

Then open `http://127.0.0.1:8765/`. `--data-dir` is required; `--port` defaults to 8765. `--data-dir` is created if missing; a path that is a file or is not writable exits with code 2. Stop with Ctrl-C.

## M1 smoke steps

1. Start with a new empty data directory and open the page: the empty state is shown.
2. Press **Load sample note** to add `Station field notes` (opt-in, never automatic).
3. Type `night platforms` into **Search notes**: one match. Type `zzz-none`: a no-match message. Clear the field.
4. Select **Station field notes** by title, change **Note text**, press **Save** (or Ctrl/Cmd+S).
5. **New note**, enter **Note title** and **Note text**, **Save**.
6. Open the same note in a second tab and save there, then save in the first tab: a conflict panel appears and your text stays in the editor.
7. Restart the server with the same `--data-dir`: the notes are still listed.

## What M1 does and does not do

- Title and body are stored as plain text (Markdown source); the preview pane mirrors the text as plain text. No Markdown rendering yet.
- Search is a case-insensitive literal substring match over title and body.
- No delete, links, full-text index, draft journal or merge yet.

## Limits

Title 1–200 characters; body up to 100,000 characters; request up to 1 MiB; up to 5,000 notes; search query up to 200 characters; 10 s socket timeout. Mutations from a foreign `Host` or `Origin` are rejected, no CORS headers are sent, and the server binds `127.0.0.1` only.

## Local persistence

Data is in `<data-dir>/notes.sqlite3` (WAL mode; `-wal`/`-shm` side files appear while running). The schema version is stored in `PRAGMA user_version`; a database from a newer version is refused. Back up by copying the directory while the server is stopped.

## Tests

From the repository root:

```
python -m unittest        # Windows
python3 -m unittest       # Linux
```

Tests use temporary directories and OS-assigned ports.

## Planned work (high level)

Markdown rendering, note links and backlinks, a versioned full-text index with delete, a draft journal with revision snapshots, and export/merge between offline copies. Details and acceptance criteria are in [docs/PRD.md](docs/PRD.md).

## Baseline verification

- Windows with Python 3.13.14 and Ubuntu 24.04 WSL with Python 3.12.3 each passed 49 unit and API tests. WSL unit tests used temporary storage on tmpfs.
- Chrome 157 verified the main workflow with external requests blocked. A note saved, appeared in search, and reopened with its exact body after a server restart.
