# Design tokens

The page uses the Pipenzo "Flow look" tokens: a black page, Flow-style alpha layers, one accent (Pipenzo yellow `#FECE02`) and red only for danger. Where this page and the header comment of `tokens.css` differ, this page takes precedence (see "Rules").

## Source and resync

`notes_vault/static/tokens.css` is a byte-for-byte copy of `extension/sidepanel/tokens.css` in jortega0033/clip-to-reel-studio at commit `a13378ce73e5b27213c9a200fc960ec93afef054` (2026-11-21). The file is never edited here. To resync, copy the file over the old one; nothing else changes. The page links it before `app.css`, and `notes_vault/server.py` serves it from the fixed allowlist.

## Token names by role

- Surfaces: `--bg` (page), `--bg-raised` (inputs), `--surface` (cards, list rows), `--bg-sunken` (wells, disabled fill).
- Text: `--fg`, `--muted`, `--faint` (captions only), `--on-ink`, `--on-ink-muted`, `--on-primary`.
- Lines: `--border`, `--hairline`, `--control-border`, `--input-border`, `--ink-border`.
- Dark block: `--ink` (the top bar).
- Accent: `--primary`, `--primary-press`, `--primary-edge`, `--on-primary`.
- Status: `--danger`, `--danger-bg`, `--ok`, `--ok-bg`, `--warn-fg`, `--warn-bg`, `--success`, `--info`, `--focus`.
- Alpha layers: `--state-hover`, `--state-selected`, `--btn-secondary`, `--scrim`, `--glass*`. Text never sits on a bare alpha layer.
- Shape, type, motion: `--space-*`, `--radius-*`, `--font`, `--mono`, `--dur-*`, `--ease-*`, `--shadow-*`.

## Rules

- New UI uses these tokens. No new colour literals in CSS or JavaScript.
- Yellow is for the primary action, the current-step marker and the current selection (UI rule 8). Red is for danger only. Apart from the focus ring (see "Focus ring"), yellow is not used for anything else.
- The header comment of `tokens.css` gives a different list: it does not name the current selection, and it also names the "your turn" chip and two dots of the source product, which are not used here. This document takes precedence. The comment is not edited, because the copy must stay identical to the source file.
- JavaScript that needs a colour reads it with `getComputedStyle(document.documentElement).getPropertyValue('--token')`.

## Light and dark

Dark is the primary design. The light block in `:root` is the matching light theme. The operating system colour scheme (`prefers-color-scheme`) chooses between them; there is no switch in the page.

## Current selection

Decided by the owner on 2026-11-23: the yellow accent marks the current selection. How it is drawn (recommended by the orchestrator, adopted under the owner's delegation of the same day):

- A selected item uses a solid `--primary` fill with `--on-primary` text. A yellow border alone is not enough: it has about 1.5:1 contrast against white in the light theme.
- A second sign that is not colour: weight, an icon or text. The existing aria attribute (for example `aria-current` or `aria-selected`) stays.
- Never a tint with a border of the same hue, and never a thick border on one side (UI rules 1 and 2).
- `--state-selected` (an alpha layer) is not the selection marker on its own.

The page does not follow this rule yet: the selected note in the list (`aria-current="true"`) still has a neutral border with a 6px left edge and a neutral fill. It is to be changed in ticket work; this change does not restyle it.

## Focus ring

`--focus` is a focus indicator and is exempt from the accent limit, including where it is yellow in the dark theme. A ticket that says the focus style stays unchanged means the rule on `main` after the token pull request (#55).

## Themes and checks

Contrast checks and no-colour-alone checks cover both the light block and the dark block of `tokens.css`, not one of them.

## Pages and the static allowlist

A ticket that creates a page, or its static allowlist, links `tokens.css` before any other stylesheet and serves it: the allowlist in `notes_vault/server.py` and its test both include it.

## Sources

Entry 14 in `owner-decisions.md` records the sources. The current selection rule is the owner's decision; focus ring, themes and linking were recommended by the orchestrator and adopted under the owner's delegation of 2026-11-23.
