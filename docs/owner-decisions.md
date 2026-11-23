# Owner decisions

Decisions the owner made for this repository. Each entry carries its own date. Entry 14 also holds items recommended by the orchestrator and adopted under the owner's delegation of 2026-11-23; its source column says which. Changing any entry needs the owner. An agent that finds a decision blocking a ticket stops and says so.

| # | Decision | Date | Implemented in |
|---|---|---|---|
| 1 | The instructions, tooling and playbook live on the default branch (`main`), not on a preparation branch. | 2026-11-22 | `CLAUDE.md`, `.claude/` |
| 2 | Persona agents run automatically during ticket work and carry instructions tailored to this project. | 2026-11-22 | `.claude/agents/` (section "In this repository" in each role), `.claude/skills/implement-ticket/SKILL.md`, `CLAUDE.md` section "Agent roles" |
| 3 | Every open ticket is about app implementation. Tooling is installed, not ticketed. | 2026-11-22 | `.github/ISSUE_TEMPLATE/implementation-ticket.md`, `CLAUDE.md` section "Delivery workflow" |
| 4 | Agents may take a ticket up to a ready pull request. Only the owner merges and releases. | 2026-11-22 | `.claude/skills/next-ticket/SKILL.md`, `.claude/settings.json` (deny `gh pr merge`, `gh release create`), `docs/RELEASING.md`, `CLAUDE.md` |
| 5 | No scheduler. Ticket work starts only on the owner's go signal (`/next-ticket`), because the repository is used to train AI models. | 2026-11-22 | `.claude/skills/next-ticket/SKILL.md` (`disable-model-invocation: true`), `LOOP.md`, `loop-constraints.md` |
| 6 | A review gate hook blocks opening or readying a pull request until the gate roles have run after the last code edit. | 2026-11-22 | `.claude/hooks/role_gate.py`, `.claude/settings.json` (`hooks`), `.github/workflows/ci.yml` (self-test) |
| 7 | Loop Engineering stays at L1, report-only and unscheduled. | 2026-11-22 | `LOOP.md`, `loop-constraints.md` |
| 8 | Continuous integration runs on Linux and Windows; the default branch requires a pull request and green checks. | 2026-11-22 | `.github/workflows/ci.yml`; branch protection is set by the owner on GitHub |
| 9 | Permission rules: documented commands are allowed; force pushes, pushes to the default branch, merges, releases and reads of secrets are denied; edits to CI, agent configuration and Loop files ask first. | 2026-11-22 | `.claude/settings.json` (`permissions`) |
| 10 | Open decisions on tickets are settled with the ticket's stated default (list below). | 2026-11-22 | The issues named below; this file |
| 11 | Rust is verified in CI only. Not applicable: this repository has no Rust. | 2026-11-22 | none |
| 12 | The ten UI rules in `docs/ui-quality.md` are binding, and the `ui-ux-pro-max` and `unslop` skills are installed in the repository and used for UI work and for copy. | 2026-11-22 | `docs/ui-quality.md`, `.claude/skills/ui-ux-pro-max/`, `.claude/skills/unslop/`, `.claude/skills/implement-ticket/SKILL.md` |
| 13 | Visual system: Pipenzo Flow look tokens (docs/design-tokens.md). SDLC kit version: jortega0033/sdlc-kit v1.0.0. | 2026-11-23 | `notes_vault/static/tokens.css`, `notes_vault/static/app.css`, `docs/design-tokens.md` |
| 14 | Token rules: current selection (D1), focus ring (D2), themes (D3) and linking (D4); sources are listed in entry 14 below. | 2026-11-23 | `docs/design-tokens.md`, `docs/ui-quality.md` |

## Entry 14: token rules, 2026-11-23

Recorded in `docs/design-tokens.md` and `docs/ui-quality.md`. The source of each decision is given as stated.

| Item | Decision | Source |
|---|---|---|
| D1 | Current selection: the yellow accent is used for the primary action, the current-step marker and the current selection (UI rule 8). Decided by the owner on 2026-11-23. How (recommended by the orchestrator, adopted under the owner's delegation of the same day): a selection uses a solid --primary fill with --on-primary text (not only a yellow border, which has about 1.5:1 against white on light), plus a second sign that is not colour (weight, icon or text) and the existing aria attribute. Never a tint with a same-hue border and never a thick one-sided border. | Owner, 2026-11-23 (the rule); orchestrator recommendation adopted under the owner's delegation (the "How") |
| D2 | Focus ring: --focus is a focus indicator, exempt from the accent limit, including where it is yellow in dark. A ticket that says the focus style stays unchanged means the rule on main after the token pull request. | Recommended by the orchestrator, adopted under the owner's delegation of 2026-11-23 |
| D3 | Themes: contrast and no-colour-alone checks cover both the light and the dark block of tokens.css. | Recommended by the orchestrator, adopted under the owner's delegation of 2026-11-23 |
| D4 | Linking: a ticket that creates a page or its static allowlist links tokens.css before any other stylesheet and serves it (allowlist and its test). | Recommended by the orchestrator, adopted under the owner's delegation of 2026-11-23 |

## Entry 10: open decisions settled by a stated default

Each ticket below states the decision as its own choice, "to be confirmed by the owner in review". The stated choice is the default and is built until the owner says otherwise in that review. Where a ticket leaves part of a decision open, the conservative option is listed and marked "flag in issue".

| Issue | Decision | Default |
|---|---|---|
| #1 | Delete is a hard delete with a revision check, in its own ticket first in the order. | Hard delete in #7. |
| #1 | Search changes from literal substring to whole words, last word as prefix. | Whole words with a prefix on the last word (#4). |
| #1 | The Markdown subset has no Markdown links, images, tables or HTML; note links use `[[Title]]`. | As stated (#2, #3). |
| #1 | A link keeps its target once resolved; among equal titles the lowest id wins. | As stated (#3). |
| #1 | Revision snapshots (#8) and the draft journal (#5) are two tickets. | Two tickets. |
| #1 | A bundle carries current text and hashes of history, not history text; only import accepts more than 1 MiB (up to 20 MiB). | As stated (#6). |
| #1 | The Python floor stays 3.12; browser checks are manual and recorded; no browser automation or JavaScript test runner. | As stated. |
| #4 | Literal substring search goes away; punctuation cannot be searched. | Accept the loss; whole-word search. |
| #4 | The last word is a prefix from its first character, with its own timing criterion. | Prefix from the first character. |
| #6 | The bundle carries hashes of history, not history text. | Hashes. |
| #6 | A bundle is at most 20 MiB and export refuses above that; raising the cap or splitting the export is left to the owner. | Keep 20 MiB and refuse above (conservative option; flag in issue). |
| #6 | A fifth count, `updated`, separates "the other copy was ahead" from a real three-way merge. | Add `updated`. |
| #6 | Neighbouring lines changed by different sides merge cleanly. | Merge cleanly. |
| #9 | The ticket calls CI "a separate decision for the owner". | Decided by entry 8: CI is installed outside the epic, and #9 does not add it. |
