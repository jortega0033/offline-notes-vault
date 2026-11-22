# Releasing

Only the owner releases. An agent never tags, publishes or creates a GitHub release; the deny rules in `.claude/settings.json` and the review gate keep it that way.

## What a release is here

The application is a local tool with no package, installer or hosting. A release is a Git tag on `main` (for example `v0.2.0`) plus a GitHub release page that carries the changelog section. The version lives in one place, `__version__` in `notes_vault/__init__.py`, and is repeated in the health response and in `tests/test_cli.py` (`test_version`). The epic's last ticket (#9) sets `0.2.0`. No tag or release exists yet.

## Checks before tagging

1. The pull requests for the release are merged and CI is green on `main` (Linux and Windows, Python 3.12 and 3.13).
2. `python -m unittest` from a clean checkout of `main` ends with `OK`; keep the output tail for the release notes.
3. `docs/acceptance.md` (written by #9) records the manual browser checks for the release.
4. `CHANGELOG.md`: the Unreleased lines move under a new version heading with the date, and an empty Unreleased section stays at the top.
5. `__version__`, `test_version` and the health test agree with the heading.

## Tag and publish

1. On an up to date `main`: `git tag -a vX.Y.Z -m "vX.Y.Z"`, then `git push origin vX.Y.Z`.
2. Create the GitHub release from the tag, with the changelog section as its text.
3. There is nothing to upload: the source archive is the artifact.

## Rollback

A tag is not moved. If a release is wrong, fix forward with a new patch version and say so in the changelog.
