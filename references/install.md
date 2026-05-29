# Install — Trello Mission Control v3

## 1. Install the skill

From a tagged GitHub release (recommended for end users):

```bash
openclaw skills install git:github.com/igorviapaineis/trello-mission-control@v3.2.0
openclaw skills list                  # should include trello-mission-control
```

> The skill will move to `openclaw skills install clawhub:igorviapaineis/trello-mission-control` once it is published to the [ClawHub](https://docs.openclaw.ai/clawhub) registry. Until then, install from git.

Local development checkout:

```bash
git clone https://github.com/igorviapaineis/trello-mission-control ~/.openclaw/skills/trello-mission-control
# the skill is now resolvable from this path on the next session (no plugin install needed)
```

## 2. Set credentials

Generate an API key + token from the Trello developer page (https://trello.com/power-ups/admin). Export them in the environment of each agent that needs to call the API:

```bash
export TRELLO_API_KEY='...'
export TRELLO_TOKEN='...'
```

Best practice: one token per agent, never share. The per-token rate limit is `100 requests / 10 s` and that is the headroom that matters most.

## 3. Create the board

**The active board must exist before you run any other step** — `setup_labels.py` writes to it, and `doctor.py` checks against it. The complete board prep walkthrough is in [`board-template.md`](board-template.md) — it covers list creation, finding board/list IDs via the `.json` URL trick, archive board setup, and seeding template cards. Five-minute summary:

- Active board with lists `inbox`, `<executor list>`, `done`, `_templates`.
- Archive board (empty — `archive_old.py` populates).
- Run `python3 scripts/setup_labels.py` to create the canonical 8-label set.

## 3a. Verify your setup so far

```bash
python3 scripts/doctor.py
```

10 numbered checks run. Exit 0 means the install is healthy through step 3. Exit 9 prints which check failed and why; see `docs/troubleshooting.md` for fixes.

## 4. Wire up OpenClaw config

Merge the snippets in `references/snippets/` into your OpenClaw config:

```bash
# ~/.openclaw/openclaw.json — merge with the openclaw-config snippet
# ~/.openclaw/exec-approvals.json — merge with the exec-approvals snippet
```

The snippets pre-approve the CLI scripts for both `orchestrator` and `executor` agents so no approval prompts interrupt the heartbeat.

Tokenjuice is bundled with OpenClaw — the snippet enables it to compact `exec` output and save tokens.

## 5. Create workspaces

For each agent (at minimum: `orchestrator` and `executor`):

```bash
mkdir -p ~/.openclaw/workspace-orchestrator
cp references/agent-templates/orchestrator/* ~/.openclaw/workspace-orchestrator/
cp references/agent-templates/shared/MEMORY.md.template ~/.openclaw/workspace-orchestrator/MEMORY.md

mkdir -p ~/.openclaw/workspace-executor
cp references/agent-templates/executor/* ~/.openclaw/workspace-executor/
cp references/agent-templates/shared/MEMORY.md.template ~/.openclaw/workspace-executor/MEMORY.md
```

Edit the copied files: rename `.template` suffix, fill in agent ID, user name, list name, etc.

## 6. Add more executors

Repeat step 5 for each new executor with a distinct agent ID. Then:

```bash
python3 scripts/setup_labels.py     # creates claim-<new_agent> labels
```

Add the agent's entry to `~/.openclaw/openclaw.json` under `agents.list`.

## 7. Smoke test

```bash
python3 scripts/trello_task.py rate-budget
python3 scripts/digest.py
```

Open the orchestrator workspace (`openclaw chat orchestrator` or your usual channel) and send a test message — orchestrator should create a card in the executor list. The executor picks it up on the next heartbeat (within 30 min, or seconds if you label `urgente`).

## Post-install lifecycle wiring

This is a skill, not a plugin, so it does not register lifecycle hooks. Three small pieces of glue replace what the former plugin hooks did:

1. **One-shot, post-install**: ensure canonical labels exist on the board.

   ```bash
   python3 ~/.openclaw/skills/trello-mission-control/scripts/setup_labels.py
   ```

2. **Start of every executor heartbeat**: release any claim that the previous tick left behind.

   The shipped `references/agent-templates/executor/HEARTBEAT.md.template` already runs:

   ```bash
   python3 ~/.openclaw/skills/trello-mission-control/scripts/release_my_claims.py <MY_AGENT_ID>
   ```

   as its first step. Keep that line in your `~/.openclaw/workspace-<agent>/HEARTBEAT.md`.

3. **Daily safety net**: a cron job that releases `claim-*` labels with no activity for 30 minutes. Covers crashes that skip the heartbeat cleanup.

   Via OpenClaw cron ([docs](https://docs.openclaw.ai/automation/cron-jobs)):

   ```bash
   openclaw cron add stale-claims --schedule "0 4 * * *" \
     --command "python3 ~/.openclaw/skills/trello-mission-control/scripts/cron_stale_claims.py"
   ```

   Or system crontab:

   ```cron
   0 4 * * * python3 ~/.openclaw/skills/trello-mission-control/scripts/cron_stale_claims.py
   ```

## Update flow

```bash
openclaw skills install git:github.com/igorviapaineis/trello-mission-control@<new-tag>
```

Or in each running session: `/new` recreates the skill snapshot.
