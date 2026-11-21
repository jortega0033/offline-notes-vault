# Offline Notes Vault — PRD and technical spec

Status legend: **[Implemented M1]** = implemented in M1 (see [baseline verification](../README.md#baseline-verification)). **[Planned]** = future work, not implemented.

## 1. Intended user and workflow

One person collecting technical notes (field observations, commands, configuration details) on a single machine with no network. They need to (a) write a note quickly, (b) find a detail from weeks ago by a remembered word, and (c) never lose typed text, including when a second browser tab saved a newer version first.

Workflow: start the local server → open `http://127.0.0.1:<port>/` → New note → type title and text → Save → later type a word in Search notes → pick the note by title → edit → Save. Notes live in a SQLite file in the chosen data directory and survive restarts.

## 2. Milestones

| Milestone | Content | Status |
|---|---|---|
| M1 | Note list, title + Markdown-source body stored as plain text, case-insensitive substring filter, save/reopen in SQLite, safe text rendering, stale-conflict handling, opt-in sample note, plain-text preview | **[Implemented M1]** |
| P1 | Bounded safe Markdown renderer | [Planned] |
| P2 | Stable note links and backlinks | [Planned] |
| P3 | Versioned full-text index, delete | [Planned] |
| P4 | Draft journal and revision snapshots | [Planned] |
| P5 | Offline copies with three-way merge | [Planned] |

## 3. Scope boundaries

In scope: single-person, single-machine, browser UI on loopback, Python 3.12 standard library, SQLite, static HTML/CSS/native JS.

Out of scope (all milestones): accounts or sign-in, remote sync or hosting, paid services, model integrations, external media or fonts, spatial canvas, real-time multi-user collaboration, build tooling. M1 additionally excludes Markdown rendering, note deletion, links, full-text index, draft journal and merge.

Any package, tool or reference needed by later work must be plannable offline and approved before it is added.

## 4. System stack

- Server: `python -m notes_vault --data-dir <path> --port <port>` (`python3` on Linux); `http.server.ThreadingHTTPServer`, bound to `127.0.0.1`, handler socket timeout 10 s, daemon request threads, explicit `close()`.
- Storage: `sqlite3`, file `<data-dir>/notes.sqlite3`, WAL, `busy_timeout` 5000 ms, schema version in `PRAGMA user_version`, ordered migrations in one transaction.
- UI: `notes_vault/static/{index.html,app.css,app.js}`, served from a fixed allowlist.
- Tests: `unittest` under `tests/`, discovered with `python -m unittest` (disposable temp directories, port 0).

## 5. Contracts

This section is the contract for the implementation and its tests.

### 5.1 Schema (version 1)

`notes(id INTEGER PK AUTOINCREMENT, title TEXT NOT NULL CHECK length 1..200, body TEXT NOT NULL CHECK length ≤ 100000, revision INTEGER NOT NULL ≥ 1, created_at TEXT, updated_at TEXT)` plus index on `(updated_at DESC, id DESC)`. Timestamps are UTC ISO-8601 with microseconds.

### 5.2 HTTP API (JSON)

| Request | Success | Errors |
|---|---|---|
| `GET /api/v1/health` | 200 `{status, version, schema_version}` | – |
| `GET /api/v1/notes?q=` | 200 `{notes:[{id,title,revision,updated_at,snippet}], total}` | 400 q > 200 chars |
| `GET /api/v1/notes/{id}` | 200 note | 404 |
| `POST /api/v1/notes` `{title, body}` | 201 note, revision 1 | 400, 403, 409 `limit_reached`, 411, 413, 415 |
| `PUT /api/v1/notes/{id}` `{title, body, base_revision}` | 200 note, revision + 1 | 400, 403, 404, 409 `stale_revision` (+ `current`), 411, 413, 415 |
| `POST /api/v1/fixtures` | 201 `{created:[…]}`, or 200 `{created:[]}` if already present | 400, 403, 411, 413, 415 |

Error envelope: `{"error":{"code","message"}}`; stale conflicts add `"current"` (the stored note). Other statuses: 404 `not_found`, 405 `method_not_allowed`, 500 `internal_error` (no internals leaked).

### 5.3 Search algorithm (M1)

`q` is stripped; empty = all notes. Otherwise `q.casefold()` is a literal substring of `title.casefold()` or `body.casefold()` (no wildcards, regex or LIKE semantics). Order: `updated_at DESC, id DESC`. Snippet: ≤ 120 chars, whitespace collapsed, centred on the first body match when present. Limits: 5000 notes, so the scan is bounded.

### 5.4 UI contract

Accessible names: search field **Search notes**, button **New note**, fields **Note title** and **Note text**, button **Save**, button **Load sample note** (explicit opt-in). The list is a `nav` named "Notes" with one button per note whose name is the exact title. Regions: `#status` (polite live), `#conflict` (alert). Preview pane mirrors the editor text as plain text (`textContent`).

Stale conflict (409): the editor text is never replaced. The conflict panel offers **Load latest into editor** (own text first copied to a read-only "Your unsaved text" box) and **Save mine as a new revision** (explicit re-PUT against the revision reported by the server).

### 5.5 Versioning

API prefix `/api/v1`; breaking changes bump to `/api/v2`. Schema changes add a migration and increment `user_version`; a database newer than the code is refused. Package version `0.1.0`.

## 6. Deterministic fixtures

Sample note, created only by **Load sample note** / `POST /api/v1/fixtures`:

Title `Station field notes`; body:

```
# Station field notes

Night platforms are quiet after 23:00; the east stairwell light flickers.
Door sensor 4 reset twice. Check the relay cabinet on the next visit.
```

| Input | Expected |
|---|---|
| `GET /api/v1/notes?q=night platforms` (any case) | total 1, title `Station field notes` |
| `q=RELAY` | total 1 |
| `q=zzz-none` | `{"notes":[],"total":0}`; UI shows “No notes match …” |
| Empty database | UI shows empty-state with **Load sample note** |
| `PUT` with `base_revision` 1 when stored revision is 2 | 409 `stale_revision`, `current.revision` = 2, stored row unchanged |
| `q=%` | only notes literally containing `%` |
| `q=É` against a note containing `é` | match |

## 7. Responsiveness and accessibility

Two panes (list/search and editor/preview) at ≥ 760 px; stacked below. No horizontal body scroll at 800×600 or 360×640. System font stack, text contrast ≥ 4.5:1, `:focus-visible` outline ≥ 2 px, labels associated via `for`, controls ≥ 40 px tall, status messages in live regions, keyboard-only operation including Ctrl/Cmd+S.

## 8. Errors, retry, restart, concurrency

- Network or server failure: status message, editor text kept, Save re-enabled for retry.
- Validation failure: field-named message; no text cleared.
- Restart: all state is in SQLite; the list is reloaded on page load. Unsaved editor text is not persisted until P4 (a `beforeunload` guard warns while dirty).
- Concurrency: every update is `UPDATE … WHERE id=? AND revision=?` inside a transaction; with N concurrent writers using the same base revision exactly one succeeds and the others receive 409 with the current note. Connections are per operation; busy timeout 5 s.
- Timeouts: 10 s socket timeout per connection; 1 MiB request cap (100,000 characters of any script fit).

## 9. Security and validation

Bind `127.0.0.1` only. Mutations (and all requests) with a `Host` other than `127.0.0.1:<port>`/`localhost:<port>` → 403; a mutation carrying a foreign `Origin` → 403. No CORS headers are emitted. Static files come from an exact-path allowlist (no path joining from requests). CSP forbids inline script/style and external sources; user text is inserted with `textContent`/`value` only. JSON shape validated with unknown keys rejected; NUL rejected; `Content-Type` enforced; body size checked before reading. SQLite CHECK constraints back application validation. Generic 500 responses.

## 10. Acceptance matrix (M1)

| # | Criterion | Measure | How checked |
|---|---|---|---|
| A1 | Launch and health | `GET /api/v1/health` 200 with `status: ok`; `/` serves HTML | unittest + smoke |
| A2 | Save/reopen | note readable after server restart on same dir | unittest |
| A3 | Substring filter | rows in §6 | unittest |
| A4 | Stale conflict | 409 + `current`, DB unchanged; UI keeps text | unittest + manual |
| A5 | Concurrency | 8 threads same base revision → 1×200, 7×409 | unittest |
| A6 | Caps and shapes | 413/415/400 per §5.2 | unittest |
| A7 | Host/Origin/CORS | foreign → 403, no ACAO header | unittest |
| A8 | Static allowlist | traversal paths → 404 | unittest |
| A9 | Safe rendering | no inline script/handlers/external URLs in static files; `textContent` use | unittest (static scan) + review |
| A10 | Layout | no horizontal overflow at 800×600 | manual |
| A11 | Bad data dir | file path/empty → exit code 2 | unittest |

## 11. Sample demo (manual smoke)

1. Start the server with a new empty directory.
2. Open the URL; see the empty-state message.
3. Press **Load sample note**; the list shows `Station field notes`.
4. Type `night platforms` in **Search notes**; one item remains. Type `zzz-none`; the no-match message appears. Clear it.
5. Select **Station field notes** by title; edit **Note text**; **Save** → "Saved revision 2".
6. **New note** → title `Wiring`, text `Panel B` → **Save**.
7. Open a second tab on the same note, save there, then Save in the first tab: conflict panel appears, text preserved.
8. Stop and restart the server with the same directory; both notes are listed.

## 12. Test plan

Automated (`python -m unittest` from the repository root): storage migrations, constraints, persistence; API routes, validation, status codes, concurrency; CLI/data-dir errors; static asset scan. Manual: §11 plus 800×600 and 360×640 resize, keyboard-only pass, screen reader label check.

## 13. Future work (one epic, five issues)

Epic: **Writing and retrieval for a single-person offline vault.** User stories: as a note collector I want to read my notes with structure, jump between related notes, find any word fast, trust that typed text survives crashes and conflicts, and move my vault between two offline machines safely. Each ticket below becomes one tracked issue; acceptance criteria are summarised here and detailed in the issue text:

| Key | Outcome | Depends on | Key acceptance |
|---|---|---|---|
| P1 | Bounded safe Markdown renderer (headings, lists, quotes, fenced code, inert raw HTML), ordered fixtures | M1 | Raw `<script>` appears as text; 100001-char body not rendered |
| P2 | `[[Title]]` links by stable id, backlinks, clear dangling state | P1 | Rename keeps backlinks; dangling link resolves on creation |
| P3 | Deterministic versioned full-text index, Unicode, updates/deletes, rebuild | M1 | Stale-index rebuild yields identical dumps |
| P4 | Draft journal, 409 text saved as draft, revision snapshots (last 50) | P3 | Draft survives restart byte-identical |
| P5 | Export bundle and idempotent three-way merge import | P4 | Independent lines merge; same-line conflicts kept as draft |

## 14. Open choices

- Delete semantics (hard delete vs. trash) arrive with P3; hard delete with revision check is the current plan.
- Whether the Markdown renderer lives in JS only with Python fixtures as the reference (P1 plans a mirrored Python reference).
- Bundle format for P5 (JSON now; a SQLite-file copy is rejected because merging needs per-note history).
- Default port is 8765; whether to pick a free port automatically is open.
