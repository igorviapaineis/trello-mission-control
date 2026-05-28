# Trello Mission Control v3

OpenClaw plugin for **multi-agent task orchestration via Trello**. The user talks to one orchestrator agent; the orchestrator creates Trello cards; executor agents pick them up from their list on heartbeat and execute. Communication between agents is exclusively through cards — never internal messages.

## Why

- **One source of truth.** Cards are the queue, the log, and the audit trail.
- **No racing.** A label-based `claim-<agent>` lock prevents two executors from grabbing the same card.
- **Free-tier friendly.** Everything fits in the Trello Free plan: nightly archive to a second board, one Butler rule, no custom fields (we use a JSON meta-block in the description).
- **Skill discovery.** Cards declare `required_skills`; executors install missing skills from ClawHub after a static audit.
- **Card hygiene.** On completion, the executor writes a structured description + ticked checklist + attachments. Comments stay short and tagged.

## Install

```bash
openclaw plugins install clawhub:igorviapaineis/trello-mission-control
openclaw gateway restart
```

Full setup steps (board creation, credentials, workspaces, config snippets, smoke test): see `references/install.md`.

## Architecture in 30 seconds

```
User --chat--> Orchestrator --create card--> Trello board <--heartbeat--> Executor(s)
```

Each agent has its own OpenClaw workspace at `~/.openclaw/workspace-<agent>/` containing the standard files (`AGENTS.md`, `SOUL.md`, `HEARTBEAT.md`, `MEMORY.md`, etc). Templates for both roles live in `references/agent-templates/`.

The plugin manifest (`openclaw.plugin.json`) wires three lifecycle hooks:

- `onGatewayStart` → `setup_labels.py` (ensure canonical labels exist).
- `onSessionStart` → print active claims for this agent.
- `onSessionStop` → `release_my_claims.py` (free anything left claimed).

## What's in the box

| Path | Purpose |
|---|---|
| `SKILL.md` | Protocol document loaded into every agent session |
| `openclaw.plugin.json` | Plugin manifest (hooks, config schema) |
| `index.ts` | Plugin entry — registers hooks |
| `scripts/trello_task.py` | Main CLI (one command per Trello operation + claim/release/meta/template) |
| `scripts/digest.py` | One-call board summary for the orchestrator |
| `scripts/archive_old.py` | Nightly free-tier hygiene |
| `scripts/wake_on_urgent.py` | Trigger executor heartbeat immediately on `urgente` |
| `scripts/setup_labels.py` | Idempotent canonical-label setup |
| `scripts/release_my_claims.py` | Hook payload for `onSessionStop` |
| `scripts/skill_audit.py` | Static scan of a clawhub skill before install |
| `scripts/ensure_skills.py` | Reads `required_skills` from a card; installs missing skills |
| `scripts/attach_dir.py` | gzip + attach a directory (10 MB Trello free cap) |
| `scripts/update_card_complete.py` | Card hygiene helper: structured desc, checklist, attachments, brief done comment |
| `references/*.md` | Documentation (card spec, labels, board template, install, audit checks, heartbeat budget) |
| `references/snippets/*` | Drop-in JSON blocks for `openclaw.json`, `exec-approvals.json`, Butler |
| `references/agent-templates/` | `AGENTS.md`/`SOUL.md`/`HEARTBEAT.md` templates per role |

## CLI

Every command respects `--dry`. Full reference in `SKILL.md`. Quick taste:

```bash
# board overview (1 nested call)
python3 scripts/trello_task.py board

# atomic claim (exit 5 if someone else has it)
python3 scripts/trello_task.py claim <card_id> executor

# pseudo custom fields (Trello free has no real ones)
python3 scripts/trello_task.py meta-set <card_id> priority P0
python3 scripts/trello_task.py meta-set <card_id> required_skills '["nextjs"]'

# completion helper: structured desc + checklist + attachments + brief done comment
python3 scripts/update_card_complete.py <card_id> \
  --resultado "..." --changes "file:line — ..." --attach /tmp/diff.patch \
  --comment "1-liner" --agent executor

# coordinator digest (1 call replaces board + pipeline-status + overdue + search)
python3 scripts/digest.py
```

## Free-tier limits

| Limit | How we stay below |
|---|---|
| 5000 open cards/board | `archive_old.py` nightly to a second board |
| 10 MB attachment | `attach_dir.py` gzips dirs; rejects oversized files |
| 250 Butler runs/month | Only 1 rule (`stale` after 7 days) — see `references/butler-stale-rule.md` |
| No custom fields | `<!--meta { ... } -->` JSON block in description |
| 100 req/10 s per token | One token per agent; CLI captures rate-limit headers; exit 6 on low budget |

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

## License

MIT
