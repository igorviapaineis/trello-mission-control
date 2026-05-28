# Developer guide

Working locally on the plugin.

## Clone and install

```bash
git clone https://github.com/igorviapaineis/trello-mission-control
cd trello-mission-control
openclaw skills install $(pwd)
openclaw skills list       # confirm trello-mission-control is loaded
```

Alternative: point a workspace at the checkout via `~/.openclaw/openclaw.json`:

```json5
{ skills: { load: { extraDirs: ["/abs/path/to/trello-mission-control"] } } }
```

That avoids re-installing on every change. Restart the gateway or run `/new` in an active session to refresh the skill snapshot.

## Layout

The repo ships as an OpenClaw **skill** — `SKILL.md` plus `scripts/` and `references/`.

Lifecycle work that a plugin would normally register as hooks is handled inline by the skill:

- `setup_labels.py` runs once after install (documented in `references/install.md`).
- `release_my_claims.py` runs as the first command in every executor's `HEARTBEAT.md`.
- `cron_stale_claims.py` runs as a daily cron job to release `claim-*` labels with no activity for 30 minutes.

There is no plugin manifest, no TypeScript entry, no build step.

## Run tests locally

```bash
python3 -m py_compile scripts/*.py
python3 -m unittest discover -s tests -v
bash tests/smoke.sh
```

CI runs the same on Python 3.10, 3.11, 3.12. Match locally before pushing.

## Packaging

```bash
npm pack
```

Produces `trello-mission-control-<version>.tgz` containing the entries listed under `files:` in `package.json` (SKILL.md, scripts, references, docs, tests, CHANGELOG, LICENSE, README, CONTRIBUTING, SECURITY).

## Publishing to ClawHub

The skill is not yet on the ClawHub registry. When it is, end users will install with:

```bash
openclaw skills install clawhub:igorviapaineis/trello-mission-control
```

Publish flow (when the registry pipeline is set up):

1. Bump `package.json` `version`.
2. Update `CHANGELOG.md`.
3. Tag, push, and create a GitHub release.
4. Submit to ClawHub via [`clawhub skill publish`](https://docs.openclaw.ai/clawhub).

Until then, users install from the GitHub release tag:

```bash
openclaw skills install git:github.com/igorviapaineis/trello-mission-control@<tag>
```

## Adding a new CLI command

1. Add the implementation as a `cmd_*` function in `scripts/trello_task.py`.
2. Wire it into the `main()` dispatch.
3. Add a usage line to the module docstring at the top.
4. Add an entry to `SKILL.md` under "CLI reference".
5. Add a dry-run case to `tests/smoke.sh`.
6. Add a focused unit test if the command has parsing/formatting logic.
7. Update `CHANGELOG.md`.

## Adding a new helper script

1. Create `scripts/<name>.py` importing the helpers it needs from `trello_task` via `sys.path.insert`.
2. Honour `--dry`.
3. Map errors to the existing exit codes in `trello_task.EXIT_*`.
4. Add a smoke case in `tests/smoke.sh`.
5. Update `SKILL.md` and `CHANGELOG.md`.

## Style

- Python 3 stdlib only. No new dependencies without prior discussion.
- ≤120 column lines.
- Type hints optional but encouraged in helpers.
- Avoid emojis in code/output (Trello renders fine but our log scraping doesn't).
- Comments only when the *why* is non-obvious. Identifiers should be self-describing.

## Where to ask

- Bugs and feature ideas: open a GitHub issue using the templates.
- Security: `SECURITY.md`.
- General: `CONTRIBUTING.md`.
