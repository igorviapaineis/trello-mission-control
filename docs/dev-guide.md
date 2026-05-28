# Developer guide

Working locally on the plugin.

## Clone and install

```bash
git clone https://github.com/igorviapaineis/trello-mission-control
cd trello-mission-control
openclaw plugins install $(pwd)
openclaw gateway restart
openclaw plugins list      # confirm trello-mission-control is loaded
```

Alternative: point a workspace at the checkout via `~/.openclaw/openclaw.json`:

```json5
{ skills: { load: { extraDirs: ["/abs/path/to/trello-mission-control"] } } }
```

That avoids re-installing on every change. Restart the gateway or run `/new` in an active session to refresh the skill snapshot.

## Layout

The repo is a hybrid skill + plugin:

- The skill is the `SKILL.md` plus `scripts/` and `references/` — loadable by OpenClaw on its own.
- The plugin layer (`openclaw.plugin.json`, `package.json`, `index.ts`) wraps the skill with hooks that the skill alone could not register.

You can develop the skill without touching the plugin layer. The hooks are convenient but not required for the CLI to work.

## Run tests locally

```bash
python3 -m py_compile scripts/*.py
python3 -m unittest discover -s tests -v
bash tests/smoke.sh
```

CI runs the same on Python 3.10, 3.11, 3.12. Match locally before pushing.

## Building `index.ts`

The plugin entry is written in TypeScript and intended to be type-checked locally if you have `tsc` installed:

```bash
npx tsc --noEmit index.ts
```

OpenClaw runtime can pick up the TypeScript directly via its plugin loader in dev. For a published bundle you would typically emit a `.js`:

```bash
npx tsc index.ts --target es2020 --module nodenext --moduleResolution nodenext
```

We do not commit the built `index.js` — it should be produced by the package build at publish time. (CI does not currently build it; that's tracked as out-of-scope for v3.0.1.)

## Packaging

```bash
npm pack
```

This produces `trello-mission-control-<version>.tgz` containing only the `files:` entries from `package.json` (the manifest, SKILL.md, scripts, references, the TS source).

## Publishing to ClawHub

See OpenClaw's [Building Plugins](https://docs.openclaw.ai/plugins/building-plugins) for the official publish flow. Briefly:

1. Bump `package.json` `version`.
2. Update `CHANGELOG.md`.
3. Tag, push, and create a GitHub release.
4. `npm pack` and submit to ClawHub through the registry's pipeline.

A user installing your release runs `openclaw plugins install git:github.com/<org>/<plugin>@<tag>` (or `clawhub:<org>/<plugin>` once the plugin has been published to the ClawHub registry).

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
