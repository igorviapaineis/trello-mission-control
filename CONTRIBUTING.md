# Contributing

Thanks for your interest in improving Trello Mission Control. This document tells you how to work locally, what shape contributions take, and what the bar is for getting a PR merged.

## Ground rules

- **English only.** Documentation, commits, comments, identifiers — all English. The plugin is distributed publicly via ClawHub.
- **Zero added dependencies** without prior discussion. The plugin must run in any OpenClaw environment, so the scripts use only the Python 3 stdlib.
- **Tests must pass.** CI is the gate.
- **No PT-BR snippets in code, docs, or templates.** The previous version had some; v3.0.1 cleaned them up. Don't reintroduce.

## Setting up locally

```bash
git clone https://github.com/igorviapaineis/trello-mission-control
cd trello-mission-control
openclaw skills install $(pwd)
```

You can also point a workspace at the local checkout via `~/.openclaw/openclaw.json`:

```json5
{ skills: { load: { extraDirs: ["/abs/path/to/trello-mission-control"] } } }
```

## Running the test suite

```bash
python3 -m py_compile scripts/*.py     # syntax
python3 -m unittest discover -s tests  # unit tests
bash tests/smoke.sh                    # CLI dry-run smoke
```

Everything must pass before opening a PR. CI runs the same on Python 3.10, 3.11, 3.12.

## Commit style

Conventional Commits, English, ≤ 72-char subject. Examples:

- `feat(claim): add release-all <agent>`
- `fix(archive): handle missing dateLastActivity`
- `docs(troubleshooting): add 401 entry`
- `test(skill_audit): cover non-TLS URL case`
- `chore(release): v3.0.1`

Subject is imperative ("add", not "added"). Body explains the *why* if the *what* is not obvious from the diff.

## Pull requests

Use the PR template; it includes a checklist. At minimum:

- CI is green.
- `CHANGELOG.md` has an entry under `[Unreleased]` (or the upcoming version).
- New behaviour is covered by a test in `tests/`.
- No new dependencies.
- Docs updated if the public surface changed (commands, flags, hooks, config schema).

## Security-sensitive contributions

If your change touches `scripts/skill_audit.py`, `scripts/ensure_skills.py`, or the static-scan patterns:

1. Read `references/skill-audit-checks.md`.
2. Add a fixture in `tests/test_skill_audit.py` covering the new check.
3. Don't relax existing checks without an explicit justification in the PR description.

If you found a way to bypass the audit, **do not open a public issue.** See `SECURITY.md` for the disclosure flow.

## Releasing (maintainers)

1. Bump `package.json` version.
2. Update `CHANGELOG.md` moving items from `[Unreleased]` to the new version.
3. Commit: `chore(release): vX.Y.Z`.
4. Tag: `git tag -a vX.Y.Z -m "..."`.
5. Push: `git push origin master && git push origin vX.Y.Z`.
6. `gh release create vX.Y.Z` with notes from CHANGELOG.
7. Publish to ClawHub when the publishing pipeline is set up.
