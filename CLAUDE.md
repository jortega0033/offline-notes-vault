# CLAUDE.md

Working instructions for this repository. Read this file first, then the documents it links to. It does not repeat them.

## What this is

An offline notes workbench for one person. One Python package, standard library only, serves a JSON API and a static page on `127.0.0.1` and keeps the notes in one SQLite file. M1 (write, save, reopen, substring search, stale-revision handling, plain-text preview) is implemented. Markdown rendering, note links, delete, a full-text index, a draft journal, revision snapshots and export with merge are planned and tracked in the epic, issue #1.

## Sources of truth

| Topic | Document |
|---|---|
| Product scope, milestones, contracts, fixture, acceptance matrix | [docs/PRD.md](docs/PRD.md) |
| How the code is built, the traced save workflow, the rules the code keeps, differences between the PRD and the code | [docs/architecture.md](docs/architecture.md) |
| Launch, smoke steps, limits, baseline verification | [README.md](README.md) |
| Backlog | Epic issue #1 and its sub-issues on GitHub (listed in dependency order in the epic's table, which is authoritative; new tickets are added there). A big ticket is split into sub-issues of 1 to 4 hours, one pull request each; a ticket labelled `tracking` or with open sub-issues is a container and is never worked on itself. The epic gives the dependencies, the parallel tracks and the estimates. |
| Loop setup and its limits | [LOOP.md](LOOP.md), [loop-constraints.md](loop-constraints.md) |
| Project subagents, their origin and local changes | [.claude/agency-agents/README.md](.claude/agency-agents/README.md) |
| Ticket workflow and the step at which each agent role runs | [.claude/skills/implement-ticket/SKILL.md](.claude/skills/implement-ticket/SKILL.md), section "Agent roles" below |
| Delivery: driver, gate hook, permissions, CI, pull request template, labels, changelog | section "Delivery workflow" below |
| UI rules | [docs/ui-quality.md](docs/ui-quality.md) |
| Owner decisions, dated | [docs/owner-decisions.md](docs/owner-decisions.md) |

When the PRD and the code disagree, the code is the baseline and [docs/architecture.md](docs/architecture.md) records the difference. A ticket that changes a contract updates PRD section 5 or 6 in the same pull request.

## Setup

Python 3.12 or newer. Nothing to install: there is no package manifest, no virtual environment requirement, no build step and no lint step. On Windows the interpreter is `python`; on Linux it is `python3`.

## Commands

All of them were run during preparation on Windows 11 with Python 3.13.14, from the repository root (the server on port 18771 and a scratch data directory instead of the values shown).

Run the tests (49 tests, about 13 seconds):

```
python -m unittest
```

One test prints a `ZeroDivisionError` traceback on purpose: it checks that a server error does not reach the response. The run is good when the last line is `OK`.

A single test: `python -m unittest tests.test_storage.StorageTests.test_update_increments_and_stale_leaves_row_unchanged`.

Run the server (binds `127.0.0.1` only; `--data-dir` is required and is created if missing; stop with Ctrl+C):

```
python -m notes_vault --data-dir ./vault-data --port 8765
```

`--port 0` picks a free port and prints it. Without `--port` the default is 8765. The database files (`*.sqlite*`) are ignored by Git wherever they are. For experiments, use a scratch directory outside the repository and delete it afterwards.

Quick check that a running server answers:

```
curl -s http://127.0.0.1:8765/api/v1/health
```

Expected: `{"status": "ok", "version": "0.1.0", "schema_version": 1}`.

On Windows, `kill` from Git Bash can leave the Python process running. Stop a server you started in the background by process id (`taskkill //PID <pid> //F` or `Stop-Process -Id <pid>`), then confirm that nothing listens on the port.

## Hard rules

These come from PRD sections 3, 4 and 9. A change that breaks one needs the owner's approval first, not a pull request.

- Standard library only, in the application and in the tests. No pip or npm dependency, no build tooling, no CDN, font, image or script from another host.
- Loopback only. The server binds `127.0.0.1`. No CORS headers. No outgoing request from the server, the page or the tests.
- No accounts, sign-in, remote sync, hosting or model integration.
- Note text is data. It reaches the page through `textContent`, `value` or DOM nodes built with `createElement`, never through `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` or `eval`. No inline script or style: the CSP forbids it. `tests/test_static_assets.py` enforces part of this.
- Static files are served from the fixed allowlist in `notes_vault/server.py`. Request input is never joined into a file path.
- Tests use a temporary directory and port 0. No fixed port, no network, no dependence on wall-clock timing for a pass.

## Architecture boundaries

Details and line references are in [docs/architecture.md](docs/architecture.md). The short form:

- `notes_vault/__main__.py`, `notes_vault/config.py`: command line only. Arguments, the data directory check, exit code 2 on a start-up failure.
- `notes_vault/server.py`: HTTP only. Request guards (Host, Origin, body length cap, media type), static allowlist, security headers, JSON encoding, the generic 500. It never runs SQL.
- `notes_vault/api.py`: routes, JSON shape validation, mapping of storage errors to status codes. It gets a `read_json` callable and never touches a socket or a file.
- `notes_vault/storage.py`: the only module that imports `sqlite3`. Migrations by `PRAGMA user_version`, one connection per operation, every write inside one `BEGIN IMMEDIATE` transaction. It never touches HTTP objects.
- `notes_vault/static/`: one page, native JavaScript, no framework. It talks to the server through `/api/v1` only and stores nothing in the browser.
- `tests/`: `unittest`. `test_storage.py` drives `Store`, `test_api.py` drives a real server on port 0 over `http.client`, `test_cli.py` drives `main()`, `test_static_assets.py` scans the static files as text.

Keep new code on the correct side of these lines. A new module is fine when a file would otherwise take on a second job (for example a Markdown parser, a tokenizer or a merge routine).

Rules that every change must keep:

- A save succeeds only when `base_revision` equals the stored revision. A stale save changes nothing and answers 409 with the stored note. Any new write to a note (restore, import, delete) uses the same check inside the same transaction as its derived rows.
- Existing databases open under new code. A schema change is a new entry at the end of `MIGRATIONS`, never an edit of an old one, with a test that opens a database made by the previous version. A database newer than the code is refused untouched.
- Every route checks `Host`. Every mutating route also checks `Origin`. Error responses use the envelope `{"error": {"code", "message"}}` and never contain a traceback.
- Limits stay enforced on both sides: title 1 to 200 characters, body at most 100,000, 5,000 notes, 1 MiB per request unless a route documents its own cap.
- Typed text is never discarded without the person choosing it.

## Git workflow

- `main` is the default branch. A pull request is required and the CI checks must be green (branch protection is the owner's setting on GitHub). Checks are also run locally and reported with their output.
- One branch per issue. Branches are named `<issue-number>-<short-slug>`. Small commits with imperative subjects and a type prefix, as in the existing history (`feat:`, and by extension `fix:`, `docs:`, `test:`, `chore:`).
- Order for every ticket: local checks, Code Reviewer, Reality Checker, then a draft pull request that names the issue (`Part of #1`, `Closes #n`), then CI on that draft, then `gh pr ready` only when CI is green. Code Reviewer and Reality Checker have no shell, so the diff and the local evidence are written to `.claude/state/review/` in the ticket worktree before they are called. The last open sub-issue of a parent also says `Closes #<parent>`. Acceptance steps that need a person are done as far as an agent can and the rest is listed under "Owner checks" in the pull request. Do not push or open a pull request unless the owner asked in the current session; a `/next-ticket` run counts as that request. Do not merge your own pull request and do not push to `main`.
- Never commit a data directory, a SQLite file, `.env*`, or `.prep/`.
- Do not change `.claude/agents/`, `.claude/skills/`, `.claude/hooks/`, `.claude/settings.json`, `LOOP.md`, `loop-constraints.md` or `loop-budget.md` as part of a feature ticket.

## Evidence before a ticket is called done

Items 1 to 6 and 8 are recorded locally before the draft pull request is opened, and both gates judge them. Item 7 comes after the draft is open: CI cannot be judged by a gate that ran before it. Paste real output into the pull request description; do not summarise a run you did not make.

1. The output tail of `python -m unittest` from a clean checkout, with the Python version and the operating system. State the test count before and after the change.
2. For each acceptance criterion of the issue: the name of the test that proves it, or the exact manual step and what was observed.
3. For a schema change: the test that opens a database created by the previous schema version, and the new `user_version`.
4. For a new or changed route: one request and response pair per success and per error code, taken from a server started with `--port 0` on a scratch data directory, and the PRD section 5.2 diff.
5. For a change under `notes_vault/static/`: a browser run on `http://127.0.0.1:<port>/` with the browser name and version, the viewport sizes checked (800x600 and 360x640), keyboard-only operation of the changed controls, and the console and network log free of errors and of external requests. No headless browser is approved for this repository, so an agent cannot produce the browser run itself. The agent records what it can (the server started, the served page and assets fetched, `python -m unittest`), lists the browser steps it could not do under "Owner checks" in the pull request, and the owner does them. Reality Checker accepts the open browser record only where the ticket marks the step as manual; for the gate, the recorded commands and the "Owner checks" list replace the browser record.
6. `git status` showing no stray files, and confirmation that no dependency, external URL or non-loopback listener was added.
7. A line for the ticket under Unreleased in `CHANGELOG.md`, and, after the draft pull request is open, CI green on it (`gh pr checks`). The driver checks CI before `gh pr ready`; Reality Checker is not asked to confirm it.
8. Anything not verified, said plainly.

## Agent roles

Project subagents are in `.claude/agents/`: ten Agency Agents roles and `loop-verifier`, which belongs to the Loop setup. Each Agency Agents role file starts with a section "In this repository", written for this project: the stack and hard rules that bind the role, the files it owns or reviews, its commands or the output it must be given, a checklist of this project's rules, the parts of the generic text that do not apply, and what it hands back. That section and this file override the generic text below it. Sources, licence, local changes and the name collision with a user-level install are in [.claude/agency-agents/README.md](.claude/agency-agents/README.md).

When asked to implement, continue or finish a GitHub issue, follow the playbook [`.claude/skills/implement-ticket/SKILL.md`](.claude/skills/implement-ticket/SKILL.md). Claude Code loads it on its own for ticket work; `/implement-ticket <issue number>` starts it by hand. Delegate to the roles without waiting to be asked: each role's `description` ends with a "Use proactively ..." sentence, which is what makes Claude Code delegate. The playbook gives the exact trigger of each role.

| When | Roles | Access |
|---|---|---|
| Before coding | Codebase Onboarding Engineer (unfamiliar area), Software Architect (module boundary, data model, schema, API or dependency) | `Read, Grep, Glob` |
| While coding | Backend Architect (`notes_vault/*.py`), Frontend Developer (`notes_vault/static/`) | can edit |
| While coding | Database Optimizer (SQL, schema, indexes, query paths) | `Read, Grep, Glob` |
| After coding, when the trigger matches | Application Security Engineer (untrusted input, Host and Origin checks, import), Accessibility Auditor (page, keyboard, focus, markup) | `Read, Grep, Glob` |
| After coding, when the trigger matches | API Tester (new or changed route, status code or contract; writes tests in `tests/`) | can edit |
| Gate on every ticket | Code Reviewer on the full diff, until no material finding is left | `Read, Grep, Glob` |
| Acceptance gate on every ticket, after Code Reviewer | Reality Checker on each acceptance criterion and the recorded local evidence, and that CI is configured to run the checks (no CI result is needed) | `Read, Grep, Glob` |

- The two gates run on every ticket, whatever its size. A ticket is not called done before both have passed.
- Roles limited to `Read, Grep, Glob` cannot run commands. Give them the diff, the acceptance criteria and the recorded command output.
- The session or role that wrote a change does not count as its reviewer.
- If a role is missing or cannot be delegated to, the session does the before-coding, while-coding and specialist steps itself and says so. It cannot pass the two gates on its own change: do not push or open the pull request. Stop, report in the issue comment (or the session output) that the gates could not run, and leave the run for the owner. A pull request is opened or marked ready only after both gates passed on the current diff. This overrides the playbook's sentence "do that step yourself" for the two gates.
- In the pull request description, list under "Agent roles run" each role that ran, what it was asked and its verdict, and any step done without a role.

## Delivery workflow

How a ticket gets from the backlog to a ready pull request. Each piece is described in its own file; this section only links them.

- **Start and playbook.** The owner starts one leaf ticket with `/next-ticket` ([.claude/skills/next-ticket/SKILL.md](.claude/skills/next-ticket/SKILL.md)); the steps are in [.claude/skills/implement-ticket/SKILL.md](.claude/skills/implement-ticket/SKILL.md). There is no scheduler. After the draft pull request is pushed the driver ends its turn with "Draft pull request #N is waiting for CI" and reads `gh pr checks` once when woken; it does not poll.
- **Review gate hook.** [.claude/hooks/role_gate.py](.claude/hooks/role_gate.py), wired in [.claude/settings.json](.claude/settings.json), blocks `gh pr create` and `gh pr ready` until Code Reviewer and Reality Checker ran after the last code edit, so the draft pull request opens only after local checks and both gates, and `gh pr ready` follows green CI. `ROLE_GATE=off` in the environment Claude Code is started from switches it off for that session; only the owner does that.
- **Permissions.** The `permissions` block of [.claude/settings.json](.claude/settings.json): documented commands are allowed, merges, releases, force pushes, pushes to `main` and reads of `.env` are denied, edits to CI, agent configuration and Loop files ask first, in the repository root and in ticket worktrees alike (`Edit` and `Write` on `**/.claude/{agents,skills,hooks,agency-agents}/**` and `**/.claude/settings.json`). Edits through a shell command are not covered, so a ticket never changes agent configuration.
- **CI.** [.github/workflows/ci.yml](.github/workflows/ci.yml) runs the test command and the hook self-test on Linux and Windows. All jobs run on the draft pull request and must be green before it is marked ready.
- **Pull request.** [.github/pull_request_template.md](.github/pull_request_template.md). Labels on tickets: `status:ready`, `status:blocked`, `status:in-progress`, `needs-decision`.
- **Changelog.** Every ticket pull request adds one line under Unreleased in [CHANGELOG.md](CHANGELOG.md).
- **UI and copy.** [docs/ui-quality.md](docs/ui-quality.md); the `ui-ux-pro-max` and `unslop` skills under `.claude/skills/`.
- **Merge and release.** Only the owner merges and releases ([docs/RELEASING.md](docs/RELEASING.md)). Security reports: [SECURITY.md](SECURITY.md). Decisions behind all of this: [docs/owner-decisions.md](docs/owner-decisions.md).

## Loop

Issue triage runs at L1: report-only, started by hand, no scheduler, no GitHub writes. See [LOOP.md](LOOP.md).
