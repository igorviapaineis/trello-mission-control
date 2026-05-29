# Card spec — Trello Mission Control v3

A card is the single unit of work. The user never delegates by chat — only by card. Every card follows the structure below; helpers in `scripts/` enforce it.

## Anatomy

```
Card name        → 1 line summary of the task
List             → which agent picks it up (executor list)
Labels           → urgente / bloqueado / claim-<agent> / etc (see references/labels.md)
Due date         → optional; orchestrator may set if deadline-bound
Members          → optional human assignee (Trello UI, not used by agents)
Description      → structured markdown (Goal / Skills / Result / Changes / Metrics / Notes)
                   trailing <!--meta { ... } --> JSON block
Checklist(s)     → ordered subtasks; checked off as the executor progresses
Attachments      → diffs, logs, screenshots — long content lives here, not in comments
Comments         → brief status updates, all tagged with [ISO | @agent | tag] prefix
```

## Description template

The executor's `update_card_complete.py` script writes this layout. The orchestrator's card-creation flow should write at least Objetivo + meta block.

```markdown
## Goal
Short briefing — what the user asked for and what acceptance looks like.

## Skills
Chosen by the orchestrator via `discover_skills.py` (ClawHub search). One bullet per skill:
- `<slug>` — why it's needed; covers subtask N.

## Result
Filled by the executor at completion. What was actually done.

## Changes
- path/to/file.ts:42 — short description
- path/to/other.py:100 — short description

## Metrics
- Time: 25min
- Files changed: 3
- Tests: 12 pass, 0 fail

## Notes
Gotchas, decisions, things future you should know.

<!--meta
{
  "priority": "P1",
  "required_skills": ["nextjs", "vitest"],
  "parent_card": "abc123",
  "retries": 0,
  "estimated_min": 30,
  "created_by": "@orchestrator"
}
-->
```

### Meta keys (Trello Free has no real custom fields)

| Key | Type | Used by |
|---|---|---|
| `priority` | `P0`/`P1`/`P2`/`P3` string | orchestrator triage |
| `required_skills` | list of skill names | orchestrator picks via `discover_skills.py`; executor installs via `ensure_skills.py` |
| `parent_card` | card ID | trace back composite work |
| `retries` | int | executor increments on retry; orchestrator decides max |
| `estimated_min` | int | rough size; orchestrator uses for daily planning |
| `created_by` | `@<agent>` | provenance |

Use `trello_task.py meta-get/meta-set` to read/write. Both helpers preserve the human description above the block.

## Comment format

All agent-generated comments use the tag prefix:

```
[2026-05-28T14:33Z | @executor | claim] working
[2026-05-28T14:42Z | @executor | done] 3 files changed, 12/12 tests pass
[2026-05-28T14:55Z | @executor | blocked] missing skill nextjs — audit failed
[2026-05-28T15:10Z | @executor | handoff] passing to vision for code review
```

Tags: `claim` `done` `blocked` `handoff` `note`.

Comments are brief by rule. Long content goes into the description (`Result` / `Changes` / `Notes`) or attachments. The audit log (`activity --filter`) becomes useful precisely because comments are tagged and short.

## Checklist & subtasks

Default name: `Result`. The executor breaks the Goal into 3–7 ordered subtasks and adds them as checklist items (the orchestrator may seed them). It runs them **one at a time**, writing each subtask's output to a part file and ticking the item as it goes. Trello Free allows unlimited checklist items per card.

### Working dir & parts

Each subtask writes to `~/.openclaw/workspace-<agent>/work/<card_id>/parts/NN-<slug>.<ext>` — the `NN` numeric prefix sets assembly order. When all subtasks are done, `assemble_artifact.py` concatenates the parts in order into a single complete file (`_complete.<ext>`) and attaches it to the card. For binary or multi-file deliverables, attach directly with `attach` / `attach_dir.py` instead.

## Attachments

Trello Free caps attachments at 10 MB per file. For larger artifacts use `attach_dir.py`, which gzips a directory and uploads the archive.

Recommended artifacts:

| Artifact | When |
|---|---|
| `_complete.<ext>` | the deliverable assembled from subtask parts (`assemble_artifact.py`) |
| `diff.patch` | always when code changed |
| `logs/` (gzip) | failed/long runs |
| `screenshots/*.png` | UI work |
| `report.json` | machine-readable run metadata |

## Pipeline

If the work needs multiple agents (e.g. implement → review → deploy → QA), the card travels through the pipeline using `next --expect <current>`. The `--expect` flag prevents two agents from racing on advance: if another agent already moved the card, you get exit 7 (`STATE_DRIFT`) instead of a silent double-move.

The first stage of a multi-stage card gets the label `revisao` so the executor knows it must move with `next`, not `done`.
