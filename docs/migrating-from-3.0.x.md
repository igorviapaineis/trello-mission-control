# Migrating from 3.0.0–3.0.2

Versions 3.0.0–3.0.2 tried to ship as an OpenClaw **plugin** but the manifest was incomplete (`openclaw.extensions` missing, `index.ts` importing a non-existent SDK), so `openclaw plugins install` always failed with:

```
package.json missing openclaw.extensions
```

v3.0.3 drops the plugin layer and ships as an OpenClaw **skill** instead. Install works end-to-end.

## If you already attempted install

```bash
# Clean up any half-installed plugin entry (no-op if it never attached).
openclaw plugins uninstall trello-mission-control 2>/dev/null || true

# Install as a skill.
openclaw skills install git:github.com/igorviapaineis/trello-mission-control@v3.0.3

# One-shot: create canonical labels (was the former onGatewayStart plugin hook).
python3 ~/.openclaw/skills/trello-mission-control/scripts/setup_labels.py
```

## Workspace changes

Each executor agent's `HEARTBEAT.md` must now start with a self-release of any leftover claim — this replaces the former `onSessionStop` plugin hook:

```bash
python3 ~/.openclaw/skills/trello-mission-control/scripts/release_my_claims.py <MY_AGENT_ID>
```

The shipped `references/agent-templates/executor/HEARTBEAT.md.template` already has this. Copy it again into your workspace if you started from an older template:

```bash
cp ~/.openclaw/skills/trello-mission-control/references/agent-templates/executor/HEARTBEAT.md.template \
   ~/.openclaw/workspace-<agent>/HEARTBEAT.md
# edit, fill in <MY_LIST> and <MY_AGENT_ID>
```

## Optional but recommended: daily stale-claim janitor

Sessions that crash between the last claim and the next heartbeat leave a stuck `claim-*` label. Schedule a daily sweep that releases any `claim-*` whose card has had no activity for 30 minutes:

```bash
# via OpenClaw cron
openclaw cron add stale-claims --schedule "0 4 * * *" \
  --command "python3 ~/.openclaw/skills/trello-mission-control/scripts/cron_stale_claims.py"

# or system crontab
0 4 * * * python3 ~/.openclaw/skills/trello-mission-control/scripts/cron_stale_claims.py
```

## OpenClaw config changes

The `plugins.entries.trello-mission-control` block in `~/.openclaw/openclaw.json` is no longer used (the skill reads its config from `$TRELLO_CONFIG` or `./trello_config.json`). You can remove that block. The `agents.list` block and `plugins.entries.tokenjuice` remain unchanged.

The updated snippet to merge:

```bash
~/.openclaw/skills/trello-mission-control/references/snippets/openclaw-config.snippet.json5
```

## No data migration

No card format change. Cards created against 3.0.0–3.0.2 (none, in practice, since install failed) and all cards created against earlier versions continue to work identically.

## What's next

- v3.1.0+ will offer a real OpenClaw plugin with a valid manifest, compiled `dist/index.js`, and hooks mapped to the real `api.on(...)` / `api.registerHook(...)` API. The skill-only form will keep working.

---

# Migrating to 3.2.0 — status by label (no `done` list)

v3.2.0 changes how completion is recorded. Instead of moving a finished card to a `done` list, the executor adds a `done` label (+ the native `dueComplete` check) and the card **stays in its owner's column**. This removes the `done`-list pile-up and the cross-list pickup bug.

Existing boards keep working; do this to adopt the new model:

1. **Create the `done` label** (idempotent — adds the new green `done` label to the canonical set):
   ```bash
   python3 ~/.openclaw/skills/trello-mission-control/scripts/setup_labels.py
   ```

2. **(Optional) Label the cards already sitting in your old `done` list** so the archive sweep can collect them, then delete/hide the `done` list:
   ```bash
   # for each card id in the old done list:
   python3 ~/.openclaw/skills/trello-mission-control/scripts/trello_task.py done <card_id>
   ```

3. **Schedule the archive sweep** (moves `done`-labelled cards with no activity for N days off the board):
   ```bash
   openclaw cron add archive-done --schedule "0 4 * * *" \
     --command "python3 ~/.openclaw/skills/trello-mission-control/scripts/archive_old.py --days 14"
   ```

4. **Refresh the agent templates** from `references/agent-templates/`. Executors now finish with `done <card_id> <agent>` (no move) and read actionable work with `get <list> --for-agent <agent>` (hides done + others' claimed cards).

Pipeline users: keep your `pipeline` array in `trello_config.json`. `next`/`prev` still hand off between columns; only the terminal step changes from "move to `done` list" to `done` (label).
