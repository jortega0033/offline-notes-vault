# AGENTS.md

The full repository instructions are in [CLAUDE.md](CLAUDE.md). This file repeats only what an agent needs before it reads that.

## Test commands

```
python -m unittest
```

(`python3` on Linux.) Run it from the repository root. Python 3.12 or newer, standard library only. There is no lint step, no build step and no package manifest. Do not add pip or npm dependencies.

## Run

```
python -m notes_vault --data-dir ./vault-data --port 8765
```

The server binds `127.0.0.1` only. `--data-dir` is required. Stop it with Ctrl+C.

## Ticket work

To implement a GitHub issue, follow the steps in [.claude/skills/implement-ticket/SKILL.md](.claude/skills/implement-ticket/SKILL.md) and the section "Agent roles" in [CLAUDE.md](CLAUDE.md). The role files in `.claude/agents/` each start with a section "In this repository" that holds the project rules for that role. An agent that cannot delegate to those roles does the before-coding, while-coding and specialist steps itself and says so in the pull request. The review gate and the acceptance gate still apply to every ticket, but the agent that wrote the change cannot pass them: do not push or open the pull request. Stop, report in the issue comment (or the session output) that the gates could not run, and leave the run for the owner. The order is: local checks, both gates, draft pull request, CI, then ready only on green CI. A pull request is opened or marked ready only after both gates passed on the current diff.

## Loop conventions

- The loop runs at L1: report-only, started by hand. It proposes; it does not label, comment, close, edit source, push or merge.
- No scheduler and no loop workflow is installed. Do not add one without the owner's approval. The only workflow is the test CI in `.github/workflows/ci.yml`.
- See [LOOP.md](LOOP.md) for the manual command and the human gates.
