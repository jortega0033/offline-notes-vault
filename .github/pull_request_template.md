## Ticket

Closes #

## What changed

<!-- What the change does and why, in plain sentences. -->

## Evidence

<!-- Each command and its result. Paste real output; see CLAUDE.md, "Evidence before a ticket is called done". -->

| Command or manual step | Result |
|---|---|
| `python -m unittest` | |

## Agent roles run

<!-- Role, what it was asked, verdict. Code Reviewer and Reality Checker run on every ticket. -->

| Role | Asked to | Verdict |
|---|---|---|
| Code Reviewer | | |
| Reality Checker | | |

## Risks and rollback

<!-- What could go wrong, and how to undo this change. -->

## Checklist

- [ ] CI is green on this pull request.
- [ ] Both gates (Code Reviewer, Reality Checker) passed on the current diff.
- [ ] `CHANGELOG.md` has a line under Unreleased.
- [ ] A UI change was checked against `docs/ui-quality.md`; copy and text went through the `unslop` skill.
- [ ] No dependency, external request or non-loopback listener was added.
