# UI quality rules

Binding for every change to the page (`notes_vault/static/`) and to user-facing copy. Rules 1 and 2 were stated by the owner; rules 3 to 10 were proposed and approved by the owner on 2026-11-22. They keep the interface free of the usual marks of generated design. The record is entry 12 in [owner-decisions.md](owner-decisions.md).

1. No thick accent border on one side of a card, callout, alert, list item or quote (for example `border-left: 4px solid <accent>`). Use spacing, type weight, an icon or a full hairline border instead.
2. No soft tinted background with a thin border of the same hue as the default way to mark a status, tag, callout or card. One neutral surface and one clear signal (text, icon or a solid chip) is enough.
3. No gradient text and no purple-to-blue gradient as a default accent.
4. No blur or glass panels, and no drop shadow plus large radius on every card.
5. No emoji used as icons or bullets, and no sparkle marks.
6. No pill or badge on things that are not states. No all-caps, letter-spaced micro labels as section decoration.
7. No centred hero with a slogan in an application screen. Screens open on the user's task.
8. One accent colour, used for the primary action and the current selection. Status colours only for status.
9. Dense, aligned layouts on a consistent spacing scale. No card grid where a table or a list is the right form.
10. User-facing copy is plain and specific: no filler, no exclamation marks, and the same word for the same thing everywhere.

## How the rules are applied

- A UI ticket starts with the `ui-ux-pro-max` skill (`.claude/skills/ui-ux-pro-max/`): a design-system search for the product type with `python .claude/skills/ui-ux-pro-max/scripts/search.py`. The skill advises. These rules and the hard rules in `CLAUDE.md` win where they differ (no framework, no CDN, no external font, no inline style).
- A UI ticket ends with a check of every changed screen against the ten rules. The result goes into the pull request under Evidence.
- User-facing copy, documentation and pull request text go through the `unslop` skill (`.claude/skills/unslop/`) before the pull request is opened.
- Frontend Developer, Accessibility Auditor and Code Reviewer carry this file in their checklists. Enforcement is by the review gate (Code Reviewer on every ticket), not by a script. Rule 1 can be linted with `grep -nE "border-(left|right|top|bottom)" notes_vault/static/app.css`; rule 2 cannot be detected reliably from CSS.
- Breaches that already exist are collected in one ticket, "Bring the existing screens in line with docs/ui-quality.md". New work does not add to them.
