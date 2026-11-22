# Architecture and PRD reconciliation

This file records how the code is built, one workflow traced from the page to the database, the rules the code keeps, and where the code and [PRD.md](PRD.md) differ. It was written during backlog preparation on 2026-11-22 against commit `42ad536`. Line numbers refer to that commit.

Every statement carries one of three marks:

- **Run**: observed by running the code in this preparation (Windows 11, Python 3.13.14, SQLite 3.50.4).
- **Read**: taken from the source, not executed.
- **Not verified**: claimed elsewhere, not reproduced here.

## 1. Shape

One Python package, standard library only, in three layers, plus a static page. There is no build step, no package manifest and no third-party code.

| Layer | File | Job | Must not |
|---|---|---|---|
| Command line | `notes_vault/__main__.py`, `notes_vault/config.py` | Parse `--data-dir` and `--port`, create the data directory, map start-up failures to exit code 2 | Serve requests or run SQL |
| HTTP | `notes_vault/server.py` | Sockets, request line, Host and Origin guard call, body length and media type checks, static allowlist, security headers, JSON encoding, generic 500 | Run SQL or know note rules |
| API | `notes_vault/api.py` | Route table, JSON shape validation, mapping of storage errors to status codes. It receives a `read_json` callable and never touches a socket | Open files or sockets |
| Storage | `notes_vault/storage.py` | The only module that uses `sqlite3`: migrations, limits, compare-and-set update, search scan, sample note | Know about HTTP |
| Page | `notes_vault/static/index.html`, `app.css`, `app.js` | One page, native JavaScript in one function scope, talks to `/api/v1` only | Hold durable state |
| Tests | `tests/` | `unittest`: `test_storage.py` drives `Store`, `test_api.py` drives a real server on port 0 over `http.client`, `test_cli.py` drives `main()` and argument parsing, `test_static_assets.py` scans the three static files as text | Use the network or a fixed port |

Start-up (**Run**): `python -m notes_vault --data-dir <dir> --port <port>` calls `main()` (`__main__.py:10`), which calls `parse_args` (`config.py:52`) and `validate_data_dir` (`config.py:32`), then `create_server` (`server.py:176`). That builds a `Store` (running migrations) and a `NotesServer` bound to `127.0.0.1` (`server.py:179`). The process prints `Offline Notes Vault listening on http://127.0.0.1:<port>/` (`__main__.py:20`). A storage, SQLite or socket error at start prints `error: cannot start: ...` and returns 2 (`__main__.py:16-18`).

## 2. Traced workflow: save an edit, meet a newer revision, resolve it

1. **Page.** Save or Ctrl/Cmd+S calls `save()` (`app.js:263`). It trims the title, refuses an empty title or a body over 100,000 code points, and sends `PUT /api/v1/notes/{id}` with `title`, `body` and `base_revision` (`app.js:286-290`). **Run** (browser).
2. **HTTP.** `Handler._handle` (`server.py:109`) splits the request target, calls `api.check_origin` (`server.py:116`, `api.py:32`), answers static paths from the allowlist (`server.py:122`), and passes API paths to `api.handle` (`server.py:126`) with `self._read_json`. `_read_json` (`server.py:73-91`) requires `Content-Length`, rejects more than 1 MiB before reading, and requires `application/json`. **Run** (411, 413 and 415 are covered by passing tests; 415 also over HTTP).
3. **API.** `route()` (`api.py:44-55`) matches `/api/v1/notes/<1 to 18 digits>`. `validate_note` (`api.py:84-102`) rejects unknown and missing keys, non-strings, NUL, lone surrogates, a title outside 1 to 200 characters after trimming, a body over 100,000 characters, and a `base_revision` that is not an integer from 1 to 2^63-1. `_text` (`api.py:58-67`) turns CRLF into LF in the body. **Run** (a body sent with `\r\n` came back with `\n`).
4. **Storage.** `Store.update` (`storage.py:165-175`) opens `BEGIN IMMEDIATE` (`storage.py:108-118`) and runs `UPDATE notes SET ..., revision=revision+1 WHERE id=? AND revision=?`. No row for the id raises `NotFound`. A row but zero rows changed raises `StaleRevision` carrying the stored note. `updated_at` comes from `_next_ts` (`storage.py:64-72`), which is always later than every stored `updated_at`. **Run**.
5. **Error mapping.** `api.handle` (`api.py:105-122`) turns `StaleRevision` into 409 `stale_revision` with the stored note under `current`. **Run**: the first PUT with `base_revision` 1 returned 200 and revision 2; the same request again returned 409 with `current.revision` 2 and the stored body unchanged.
6. **Page again.** On 200 the status line reads "Saved revision N" and the list reloads (`app.js:292-310`). On 409 `showConflict` (`app.js:252-261`) shows the conflict panel and leaves the editor alone. "Load latest into editor" copies the person's text into a read-only box first (`app.js:325-339`). "Save mine as a new revision" sends the PUT again with the revision the server reported (`app.js:341-345`). **Run** (browser) for the 409, the kept text and "Save mine as a new revision"; **Read** for "Load latest into editor".
7. **Durability.** The row is in `<data-dir>/notes.sqlite3`. **Run**: after stopping the process and starting it again on the same directory, the list and the edited note were returned unchanged.

## 3. Data ownership

- `Store` owns one file, `<data-dir>/notes.sqlite3`. It holds no connection between calls: each operation opens one, uses it and closes it (`storage.py:97-118`). Each connection sets `busy_timeout` 5000 ms and `foreign_keys=ON`. **Run** (`foreign_keys` reads 1 on a `Store` connection).
- The journal mode is WAL, set once in `_migrate` after the version check (`storage.py:120-127`). `-wal` and `-shm` files exist while the database is in use.
- The schema is the ordered list `MIGRATIONS` (`storage.py:21-33`). Entry `i` upgrades version `i` to `i+1`, the version is `PRAGMA user_version`, and all pending entries run in one transaction (`storage.py:128-136`). A database with a higher version is refused before anything is written (`SchemaTooNew`). Schema version 1 has one table, `notes`, and one index on `(updated_at DESC, id DESC)`.
- Note ids come from `AUTOINCREMENT`, so an id is never reused.
- The page keeps the open note's id, revision and last saved text in memory (`app.js:31-41`) and the id in the URL fragment `#note-<id>`. Nothing is stored in the browser. Unsaved text is lost on a crash; a `beforeunload` prompt is the only guard (`app.js:408-413`).

## 4. Rules the code keeps

| Rule | Where | Mark |
|---|---|---|
| An update succeeds only if `base_revision` equals the stored revision; of N writers with the same base exactly one wins | `storage.py:165-175`; tests `test_concurrent_puts_one_winner`, `test_concurrent_updates_single_winner` (8 threads) | Run |
| At most 5,000 notes | `storage.py:146-147` | Run (test) |
| Title 1 to 200 characters, body at most 100,000, enforced in the API and again by `CHECK` constraints | `api.py:91-96`, `storage.py:23-30` | Run (tests) |
| The API trims titles; `Store.create` does not | `api.py:67`, `storage.py:154` | Run |
| Search is a literal, case-folded substring test in Python over every note; `%` and `_` are not wildcards; order is `updated_at DESC, id DESC` | `storage.py:177-189` | Run |
| Every request needs `Host` equal to `127.0.0.1:<port>` or `localhost:<port>`; POST and PUT also reject a foreign `Origin`; no CORS header is ever sent | `api.py:28-41`, `server.py:116` | Run |
| Static files come from four exact paths; nothing from the request is joined into a file path | `server.py:17-22`, `138-146` | Run |
| Every response has `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`; HTML also has a CSP with `default-src 'none'` and no inline script or style | `server.py:23-24`, `40-55` | Run |
| Note text reaches the page through `textContent` and `value` only | `app.js:105`, `110`, `158`; static scan in `tests/test_static_assets.py:36-38` | Run |
| An error after an unread body does not corrupt a keep-alive connection | `server.py:96-107` | Run (test) |
| A 500 never contains a traceback | `server.py:133-136` | Run (test) |
| The server binds `127.0.0.1` only | `server.py:179` | Run |

## 5. PRD against the code

| PRD item | Status | Evidence |
|---|---|---|
| M1 launch and health (A1) | Implemented | Run: health 200 `{"status": "ok", "version": "0.1.0", "schema_version": 1}`; `/` 200 `text/html` with CSP |
| Save and reopen after restart (A2) | Implemented | Run: over HTTP and in `test_persistence_across_restart` |
| Substring filter and the fixture rows of section 6 (A3) | Implemented | Run: `NIGHT platforms` 1, `RELAY` 1, `zzz-none` 0, `%` only the note containing `%`, `CAFÉ` matches `café` |
| Stale conflict, API and page (A4) | Implemented | Run: API over HTTP; page in a browser (see finding D3) |
| Concurrency (A5), caps and shapes (A6), Host and Origin (A7), static allowlist (A8), static scan (A9), bad data directory (A11) | Implemented | Run: `python -m unittest`, 49 tests, OK; 403, 404, 405, 415, 400 also over HTTP |
| Layout at 800x600 and 360x640 (section 7, A10) | Implemented | Run: no horizontal overflow at either size in a Chromium 156 engine; smallest button 40 px |
| Keyboard-only use, screen reader labels, contrast (section 7) | Needs verification | Labels and landmarks are present (Run: accessibility tree; `test_labels_and_landmarks`). Tab order, a screen reader and contrast were not checked |
| Opt-in sample note | Implemented | Run: page button and `POST /api/v1/fixtures` (201, then 200 with an empty list) |
| P1 Markdown renderer | Planned (issue #2) | The preview is a `pre` filled with `textContent` |
| P2 note links and backlinks | Planned (issue #3) | No link table, no `[[` handling |
| P3 full-text index | Planned (issue #4) | Search is the scan in `storage.py:177-189` |
| Delete (PRD files it under P3) | Planned (the epic, issue #1, lists the ticket) | `DELETE` answers 405 (`api.py:44-55`) |
| P4 draft journal and revision snapshots | Planned (issue #5 and the epic) | Only the current revision of a note is stored |
| P5 export and three-way merge | Planned (issue #6) | Nothing present |
| Python 3.12 on Ubuntu 24.04 WSL; Chrome 157 with external requests blocked (README baseline) | Not verified | Not repeated here. This preparation ran Python 3.13.14 on Windows only |

## 6. Findings: drift, gaps and facts a later ticket depends on

| # | Finding | Mark | Consequence |
|---|---|---|---|
| D1 | The Origin check applies to POST and PUT only (`server.py:116`), and the `Allow` header for OPTIONS is the fixed text `GET, HEAD, POST, PUT` (`server.py:120-121`). PRD section 9 says "a mutation carrying a foreign Origin" is refused. | Read | Correct today, because no other mutating method has a route. The ticket that adds `DELETE` must extend both, with a test. |
| D2 | A query string with more than 50 fields makes `parse_qs` raise `ValueError` (`api.py:129`), which nothing maps, so the server answers 500 instead of 400. | Run (in process) | Small defect in input handling. Fixed in the delete ticket, which adds one query-string helper for every route. |
| D3 | While the conflict panel is shown, typing in the title or text hides it (`app.js:391-399`). The next Save sends the old `base_revision`, gets 409 again and the panel returns. No text is lost. PRD section 5.4 does not describe this. | Run (browser) | Works, but the person needs two saves to reach "Save mine as a new revision" after touching the text. The draft journal ticket changes this flow and must state the new behaviour. |
| D4 | PRD sections 3 and 4 say Python 3.12. Nothing in the code checks the version. | Run on 3.13.14 only | Treat the floor as 3.12. A ticket that uses a newer language or library feature breaks the documented floor. |
| D5 | PRD sections 5.3 and 6 define search as a literal substring match, with fixture rows for `q=%` and `É`. Issue #4 replaces the scan with a token index, under which a query of punctuation only has no tokens and a partial word does not match. | Read | The search ticket must state the new rules, change PRD sections 5.3 and 6 and rewrite `test_search` and `test_list_search_rules` in the same pull request. |
| D6 | The list reads the full body of every note on every call, with or without a query, to filter and to cut the snippet (`storage.py:182-188`). The page calls it after every save and 150 ms after each keystroke in the search field. | Read | Bounded by the caps (5,000 notes of 100,000 characters) but grows with total text. The search ticket removes the scan. |
| D7 | A migration is a list of SQL strings (`storage.py:21-33`, `133-136`). There is no way to run Python during a migration, and tests assert the literal schema version 1 (`tests/test_api.py:63`, `tests/test_storage.py:19`, `22`). Three tests also hard-code a "future" version: 7 (`tests/test_api.py:286`), 42 (`tests/test_cli.py:94`) and 99 (`tests/test_storage.py:29`, `35`). | Read | Planned tables that must be filled from existing notes (links, index, snapshots) need a migration step that can call Python. The first ticket of the batch adds that once, for all of them. The planned batch adds five migrations and takes the schema version to 6, one below the literal 7, so the same ticket changes the three tests to `storage.SCHEMA_VERSION + 1`. |
| D8 | The 1 MiB body cap is one constant for every route (`api.py:10`, `server.py:80`). Issue #6 accepts bundles up to 20 MiB. | Read | The import route needs its own cap; every other route keeps 1 MiB. |
| D9 | Titles are not unique. The sample note is skipped when any note has its title (`storage.py:194`). | Run (in process) | Link resolution by title (issue #3) needs a rule for duplicates. |
| D10 | `tests/test_static_assets.py` reads exactly three files (lines 16-18) and asserts that the page contains the words "Plain text preview" (line 71). A new static file must also be added to the allowlist (`server.py:17-22`). The checks are already split by file type: external addresses in all three files (line 20), inline script, style and handler attributes in the HTML only (line 27), unsafe sinks in the script only (line 36). | Read | The renderer ticket changes that assertion and extends the scan to every file under `static/`, keeping the split by file type: the HTML checks do not apply to a JSON data file, which must be able to hold `<script>` as fixture text. |
| D11 | The fragment `#note-<id>` is written when a note opens and read once at page load (`app.js:203-205`, `419-422`). There is no `hashchange` handler. | Read | A link between notes cannot rely on changing the fragment; it must call the same open routine, including the unsaved-changes prompt. |
| D12 | PRD section 5.2 does not mention `HEAD` on the GET routes, the 400 for a repeated `q`, the `Location` header on 201, or the names of the error codes. | Read | The code is the reference. The release check ticket brings section 5.2 up to date. |
| D13 | PRD section 13 lists five future tickets. The prepared batch has more, because delete, revision snapshots and a release check became tickets of their own. | Read | The epic (issue #1) is the list of record. The release check ticket updates section 13. |
| D14 | `allow_reuse_address` is off (`server.py:153`). | Run on Windows: an immediate restart on the same port worked | On Linux a restart on a fixed port can fail for a short time. Scripts and tests should use port 0. |
| D15 | A local `.prep/` directory may exist in a checkout. Git ignores it. | Read | It is not a source of truth. |

## 7. Where planned work connects

| Planned capability | Connects at |
|---|---|
| Any new route | `route()` in `api.py` (one regular expression for `/api/v1/notes/{id}` today, no sub-resources), `_dispatch`, the mutating-method test in `server.py:116`, PRD section 5.2 |
| Any new table | A new entry at the end of `MIGRATIONS`; never edit an existing entry. Version numbers follow merge order: a branch that merges second renumbers its entry |
| Any write that touches two tables | One `Store._tx()` block, so the note row and the derived rows commit or roll back together |
| Rows derived from a note (links, index, snapshots) | Planned, not present: today the `notes` row is written in two places, `_insert` (`storage.py:145-152`) and `update` (`storage.py:165-175`). The first ticket of the batch (the epic lists it) moves both into one internal write routine with a list of derived-row steps; later tickets append a step there and never write the `notes` row by a second path |
| Any new static file | `STATIC` in `server.py`, a `script` or `link` element in `index.html` (the CSP allows same-origin files only), the static scan test |
| Rendered note text | DOM nodes built with `createElement` and `textContent`. The static scan forbids `innerHTML` and similar sinks, and any `http:` or `https:` text in a static file |
| Health payload | `test_health` compares the whole object (`tests/test_api.py:63`); a new field or schema version changes that test |

## 8. Not verified in this preparation

- Linux, WSL and Python 3.12.
- Chrome and Firefox as separate products, a second real tab, "Load latest into editor", the unsaved-changes prompts, keyboard-only tab order, a screen reader and contrast.
- Behaviour at the caps: 5,000 notes and 100,000-character bodies were not loaded.
