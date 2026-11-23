# Design tokens

The page uses the Pipenzo "Flow look" tokens: a black page, Flow-style alpha layers, one accent (Pipenzo yellow `#FECE02`) and red only for danger.

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
- Yellow is for the primary action and the current-step marker only. Red is for danger only.
- JavaScript that needs a colour reads it with `getComputedStyle(document.documentElement).getPropertyValue('--token')`.

## Light and dark

Dark is the primary design. The light block in `:root` is the matching light theme. The operating system colour scheme (`prefers-color-scheme`) chooses between them; there is no switch in the page.
