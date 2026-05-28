---
name: trello-mission-control
description: "Multi-agent task orchestration via Trello — claim, pipeline, archive, digest, skill discovery, card hygiene. Use whenever the user mentions Trello-based agent coordination, multi-agent task delegation via cards, claim/release locking, board hygiene and archiving, or wants to set up orchestrator + executor agents that pass work through Trello — e.g. 'cria board pra meus agentes', 'orquestra X via Trello', 'meu agente precisa pegar cards do Trello', 'configura multi-agent via Trello', 'crie orchestrator pra Trello'."
metadata:
  openclaw:
    emoji: "📋"
    homepage: https://github.com/igorviapaineis/trello-mission-control
    license: MIT
    requires:
      bins: [python3, git, openclaw]
      env: [TRELLO_API_KEY, TRELLO_TOKEN]
---

# Trello Mission Control

Multi-agent task coordination via Trello. The user talks only to an **orchestrator** agent; the orchestrator creates cards; **executor** agents pick them up from their list on heartbeat and execute. Communication between agents is **only** through cards — never through `agent_send` or sub-agent sessions.

## Prerequisites

Before installing this skill make sure you have:

- Python ≥ 3.10 (`python3 --version`)
- `openclaw` CLI on `PATH` (`openclaw --version`)
- `git`
- A Trello account with:
  - **An API key and token** — generate at <https://trello.com/power-ups/admin>:
    1. Click **"New"** → name your Power-Up (any name), pick a workspace and visibility.
    2. Once created, copy the **API Key** from the top of the page.
    3. Below the key, click **"Token"** → authorize → copy the long token string.
    The token does not expire by default; append `&expiration=30days` to the URL if you want rotation.
  - **Two boards already created** with the layout described in [`references/board-template.md`](references/board-template.md) (~5 min setup):
    - Active board (e.g. `Mission Control`) with lists `inbox`, `executor`, `done`, `_templates`.
    - Archive board (e.g. `Mission Control — Archive`), empty — `archive_old.py` populates it.
- One OpenClaw workspace per agent (default: `orchestrator` and `executor`).

If any of the above is missing, `scripts/doctor.py` (step 5 of the Quickstart) will tell you which.

> **First time?** Follow [`references/board-template.md`](references/board-template.md) step-by-step before the Quickstart. It walks through board creation, list creation, finding IDs (`board.json` trick), and seeding template cards. The Quickstart below assumes those steps are done.

## Quickstart

```bash
# 0. First time? Auto-bootstrap the Trello side (~10 sec, requires creds from step 2 first):
#      python3 scripts/bootstrap_board.py --agents jarvis,vision,friday,sia --with-labels
#    This creates the active board + lists + archive board + canonical labels and writes trello_config.json.
#    Prefer to set everything up manually? Follow references/board-template.md §1 onwards.

# 1. Install the skill (git source until published to ClawHub)
openclaw skills install git:github.com/igorviapaineis/trello-mission-control@v3.1.0

# 2. Export Trello credentials (every script reads them from the environment)
export TRELLO_API_KEY='...'
export TRELLO_TOKEN='...'
# persist in ~/.zshrc or ~/.bashrc so they survive new shells

# 3. Generate the config template (or skip — `bootstrap_board.py` in step 0 already wrote it)
cd ~/.openclaw/skills/trello-mission-control
[ -f trello_config.json ] || python3 scripts/trello_task.py init
# If you did NOT run bootstrap_board, edit trello_config.json manually:
#   board_id, archive_board_id, templates_list_id, lists.* — see references/board-template.md
# Bootstrap users can skip the edit; everything is already populated.

# 4. Create the canonical labels on the active board (idempotent)
python3 scripts/setup_labels.py

# 5. Verify the install end-to-end
python3 scripts/doctor.py
#   exits 0 if all 10 checks pass; exit 9 (DOCTOR_FAIL) with details otherwise

# 6. Copy agent templates into per-agent workspaces
mkdir -p ~/.openclaw/workspace-{orchestrator,executor}
cp -r references/agent-templates/orchestrator/. ~/.openclaw/workspace-orchestrator/
cp -r references/agent-templates/executor/.     ~/.openclaw/workspace-executor/
cp references/agent-templates/shared/MEMORY.md.template \
   ~/.openclaw/workspace-orchestrator/MEMORY.md
cp references/agent-templates/shared/MEMORY.md.template \
   ~/.openclaw/workspace-executor/MEMORY.md
# rename each *.template → drop the suffix; fill <MY_AGENT_ID> and <MY_LIST>

# 7. Merge config snippets into the global OpenClaw config
#    references/snippets/openclaw-config.snippet.json5 → ~/.openclaw/openclaw.json
#    references/snippets/exec-approvals.snippet.json   → ~/.openclaw/exec-approvals.json

# 8. Activate the heartbeat (the snippet sets `heartbeat.every: "30m"` already)
openclaw gateway restart

# 9. Send your first card from a chat with the orchestrator
openclaw chat orchestrator      # or whichever channel you wired
# Say: "Create a test card titled 'Hello Trello' in the executor list"
# Expect: a CREATED:<id> line in the reply and the card visible in Trello within seconds
```

Full step-by-step with screenshots: [docs/walkthrough.md](docs/walkthrough.md). Detailed install: [references/install.md](references/install.md). Diagnose problems: `python3 scripts/doctor.py --verbose` or [docs/troubleshooting.md](docs/troubleshooting.md).

## Canonical workflow

```
User --chat--> Orchestrator
                  |
                  | creates card with:
                  |   - target list (executor list)
                  |   - structured description (objective, context, acceptance)
                  |   - meta { priority, required_skills, parent_card }
                  |   - urgente label (if urgent → triggers wake)
                  |   - checklist with execution steps
                  v
              Trello board
                  |
                  | executor heartbeat (default 30min) or wake-on-urgent
                  v
              Executor
                  |
                  +-- /claim <id>
                  +-- ensure required_skills (clawhub install if missing → audit → install)
                  +-- work
                  +-- update checklist per step
                  +-- attach diffs, logs, screenshots
                  +-- update description (Objective / Result / Changes / Metrics / Notes)
                  +-- brief done comment with tag
                  +-- /handoff or /done
```

## Rules

### Delegation only via Trello
- All task delegation between agents goes through cards.
- Never `sessions_send`, `sessions_spawn` or internal messages to delegate tasks.
- Internal channel between agents is only for chat / coordination (questions, alignment).
- Handoff = move card + comment what was done.

### Claim / release (atomic-ish lock)
- Before working on a card, call `claim <card_id> <agent>`. Exit 5 = `ALREADY_CLAIMED` → skip card.
- After work (or aborting), call `release <card_id> <agent>` or move to `done`/next pipeline stage.
- On session stop, the plugin hook `onSessionStop` calls `release_my_claims.py <agent>` to free anything that was claimed.

### Provenance — tag every comment generated by an agent
Comments generated by the CLI must use `--tag <claim|done|blocked|handoff|note>` which prepends:

```
[YYYY-MM-DDTHH:MMZ | @<agent> | <tag>] <message>
```

Allows machine-readable activity audit via `activity --filter claim,done`.

### Card hygiene on completion — use Trello Free to its max
On finishing a card, the executor must update it with the maximum useful structure. Comments stay brief — never put long content in comments.

The canonical card layout (5 description sections, checklist, attachments, brief done comment) lives in [`references/card-spec.md`](references/card-spec.md). The helper `update_card_complete.py` writes all of it in one call:

```bash
python3 {baseDir}/scripts/update_card_complete.py <id> --result "..." --changes "..." --attach /tmp/diff.patch --agent <me>
```

### Pipeline
- Use `next <card_id> --expect <current_list>` to advance. The `--expect` guards against state drift (another agent moved the card). Exit 7 = `STATE_DRIFT`.
- Never skip pipeline stages.
- Bugs found in review → label `bloqueado` + `prev`.

### Multiple cards in the same list
- Priority: label `urgente` first, then oldest.
- Process one at a time. Comment + advance/release before grabbing the next.

### Skill discovery (read `required_skills` from card meta)
1. `meta-get <card_id> required_skills` returns a JSON list.
2. `openclaw skills list` shows installed.
3. For each missing: `clawhub search <name>` → `clawhub inspect <slug>` (resolves the slug to repository metadata, including the git URL) → `git clone --depth 1 <repo_url> /tmp/<slug>` → `python3 {baseDir}/scripts/skill_audit.py /tmp/<slug>`.
4. Audit pass → `openclaw skills install /tmp/<slug>` + `/new`.
5. Audit fail → comment with `--tag blocked` + add label `bloqueado` + exit.

### Wake on urgent
When the orchestrator creates a card with label `urgente`, it also runs:
```bash
python3 {baseDir}/scripts/wake_on_urgent.py <executor-agent-id>
```
which calls `openclaw heartbeat wake <agent> --now` so the executor wakes within seconds instead of waiting 30 min.

## CLI reference

The CLI is `{baseDir}/scripts/trello_task.py`. All commands respect `--dry`.

### Setup
```bash
python3 {baseDir}/scripts/trello_task.py init                    # generate trello_config.json template
python3 {baseDir}/scripts/setup_labels.py                        # idempotent: ensure 11 canonical labels exist
```

### Board overview
```bash
python3 {baseDir}/scripts/trello_task.py board                   # list + card counts (1 nested call)
python3 {baseDir}/scripts/trello_task.py members
python3 {baseDir}/scripts/digest.py                              # 1 call: pipeline + overdue + urgent + stale + claimed
python3 {baseDir}/scripts/trello_task.py rate-budget             # remaining API quota
```

### Cards
```bash
python3 {baseDir}/scripts/trello_task.py get <list>
python3 {baseDir}/scripts/trello_task.py card <id>
python3 {baseDir}/scripts/trello_task.py create <list> "<name>" "labels,csv" [due] [member]
python3 {baseDir}/scripts/trello_task.py template <tpl_card_id> <list> "<new name>"
python3 {baseDir}/scripts/trello_task.py archive <id>
python3 {baseDir}/scripts/trello_task.py done <id>
python3 {baseDir}/scripts/trello_task.py move <id> <target_list>
python3 {baseDir}/scripts/trello_task.py next <id> --expect <current>
python3 {baseDir}/scripts/trello_task.py prev <id> --expect <current>
```

### Claim / release
```bash
python3 {baseDir}/scripts/trello_task.py claim <id> <agent>      # exit 5 if already claimed
python3 {baseDir}/scripts/trello_task.py release <id> <agent>
python3 {baseDir}/scripts/trello_task.py claimed-by <id>
python3 {baseDir}/scripts/trello_task.py release-all <agent>     # used by /stop hook
```

### Comments / activity
```bash
python3 {baseDir}/scripts/trello_task.py comment <id> --tag claim "starting"
python3 {baseDir}/scripts/trello_task.py comment <id> --tag done "fixed auth.ts:42"
python3 {baseDir}/scripts/trello_task.py activity <id> --filter claim,done --since 2026-05-28T00:00Z
```

### Description / labels / due / assign
```bash
python3 {baseDir}/scripts/trello_task.py desc <id> "<markdown>"
python3 {baseDir}/scripts/trello_task.py label <id> urgente
python3 {baseDir}/scripts/trello_task.py unlabel <id> urgente
python3 {baseDir}/scripts/trello_task.py due <id> 2026-06-01
python3 {baseDir}/scripts/trello_task.py assign <id> <member_id>
```

### Pseudo custom fields (Free has no real custom fields)
Stored in the description as `<!--meta { ... } -->`. The CLI preserves the human description above the block.

```bash
python3 {baseDir}/scripts/trello_task.py meta-set <id> priority P0
python3 {baseDir}/scripts/trello_task.py meta-set <id> required_skills '["nextjs","vitest"]'
python3 {baseDir}/scripts/trello_task.py meta-get <id> priority
```

### Checklists
```bash
python3 {baseDir}/scripts/trello_task.py checklist <id> create "Result"
python3 {baseDir}/scripts/trello_task.py checklist <id> add <cl_id> "Build"
python3 {baseDir}/scripts/trello_task.py checklist <id> items <cl_id>
python3 {baseDir}/scripts/trello_task.py checklist <id> check <item_id>
```

### Attachments
```bash
python3 {baseDir}/scripts/trello_task.py attach <id> /path/to/diff.patch
python3 {baseDir}/scripts/attach_dir.py <id> /path/to/logs        # gzips dir, attaches single archive
```

### Search and reports
```bash
python3 {baseDir}/scripts/trello_task.py search "auth" --label urgente
python3 {baseDir}/scripts/trello_task.py overdue --list executor
```

### Skill discovery / audit
```bash
python3 {baseDir}/scripts/ensure_skills.py <card_id>              # reads required_skills meta, installs missing
python3 {baseDir}/scripts/skill_audit.py <skill_folder>           # static scan; exit 8 on failure
```

### Maintenance
```bash
python3 {baseDir}/scripts/archive_old.py --days 30 --from done    # cron daily; move to archive board
python3 {baseDir}/scripts/release_my_claims.py <agent>            # called by onSessionStop hook
```

### Wake on urgent (orchestrator only)
```bash
python3 {baseDir}/scripts/wake_on_urgent.py <executor-agent-id>
```

## Heartbeat templates

See `{baseDir}/references/agent-templates/`:
- `orchestrator/HEARTBEAT.md.template` — runs `digest`, alerts on overdue/stale.
- `executor/HEARTBEAT.md.template` — `get`, `claim`, `ensure_skills`, work, `update_card_complete`, `handoff` or `done`.

Both stay below the OpenClaw recommended 50 lines.

## Labels (canonical set)

| Label | Color | Purpose |
|---|---|---|
| `urgente` | red | max priority; triggers wake-on-urgent |
| `bloqueado` | orange | waiting on dependency |
| `revisao` | yellow | pipeline project flag |
| `pediu` | purple | direct user request |
| `claim-<agent>` | sky | lock (one per agent) |
| `stale` | gray | auto-applied by Butler after 7d no activity |
| `qa-failed` | pink | QA rejected |

`setup_labels.py` is idempotent — also runs on `onGatewayStart` hook.

## Free tier hygiene

- Boards on Trello Free are capped at 5000 open cards.
- `archive_old.py` runs nightly and moves Done cards older than 30 days to the **archive board** (configured as `archive_board_id`).
- Single Butler rule, within the 250 runs/month quota: label `stale` if no activity in 7 days. See `{baseDir}/references/butler-stale-rule.md`.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | OK |
| 1 | Generic error |
| 2 | Auth/permission |
| 3 | Rate limit exhausted |
| 4 | Missing config |
| 5 | Already claimed |
| 6 | Low rate-limit budget |
| 7 | State drift (pipeline `--expect` mismatch) |
| 8 | Skill audit failure |
| 9 | Doctor check failure (`scripts/doctor.py`) |
