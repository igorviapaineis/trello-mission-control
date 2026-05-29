# Board template — bootstrap a fresh board from scratch

Trello Free does not let you publish a board template that other users can clone. There are two paths:

- **§0 Auto-bootstrap (recommended)** — one Python script creates everything in ~10 seconds.
- **§1–§6 Manual** — UI-driven walkthrough; useful if you want full visual control or are extending an existing board.

## 0. Auto-bootstrap (recommended)

```bash
export TRELLO_API_KEY='...'
export TRELLO_TOKEN='...'   # from https://trello.com/power-ups/admin (read+write by default)

# Pick ONE of the three ways to name the per-agent lists:

# a) Auto-detect — reads ~/.openclaw/openclaw.json agents.list[], skips `orchestrator`.
python3 scripts/bootstrap_board.py --auto-detect --with-labels

# b) Explicit list (the installing agent should ASK the user first; do not hardcode).
python3 scripts/bootstrap_board.py --agents jarvis,vision,friday,sia --with-labels

# c) Default single `executor` list (minimum viable).
python3 scripts/bootstrap_board.py --with-labels
```

This calls Trello's REST API to:

1. `POST /1/boards/` — create the active board (`Mission Control`).
2. `POST /1/lists/` × N — create `inbox`, one list per agent, `_templates` (no `done` list — status is a label).
3. `POST /1/boards/` — create the archive board (`Mission Control — Archive`).
4. Write every ID into `trello_config.json` (merges with any existing fields — does not clobber).
5. `--with-labels`: invoke `setup_labels.py` to create the 6 global + per-agent `claim-*` labels.

When it finishes you see:

```
BOARD_READY:active=https://trello.com/b/<id>|archive=https://trello.com/b/<id>
```

Open the URLs to confirm. Skip directly to step 6 of the SKILL.md Quickstart (workspace templates).

Flags:

| Flag | Default | Purpose |
|---|---|---|
| `--name` | `Mission Control` | Active board name |
| `--archive-name` | `<name> — Archive` | Archive board name |
| `--agents` | `executor` | Comma-separated agent slugs → one list each. Takes precedence over `--auto-detect`. |
| `--auto-detect` | off | Read `~/.openclaw/openclaw.json` `agents.list[]` and use every id except `orchestrator`. Falls back to `executor` if the file is missing or has no agents. |
| `--openclaw-config` | `~/.openclaw/openclaw.json` | Override path for `--auto-detect` (useful in tests). |
| `--workspace-id` | personal | Trello workspace/org ID (find at trello.com/w/<workspace>) |
| `--config` | `./trello_config.json` | Path to write the merged config |
| `--with-labels` | off | Run `setup_labels.py` after bootstrap |
| `--dry` | off | Print the plan; touch nothing |

Re-running is safe for the config merge but Trello has no native idempotency for board create — you will get a *second* board with the same name. Delete the old one in the UI before re-running.

The remaining sections (§1–§6) describe the same setup by hand if you prefer the UI route.

## 1. Create the active board

In the Trello UI:

1. Create a workspace (or pick an existing one).
2. Create a board named `Mission Control` (or whatever you prefer).
3. Add these lists in order:
   - `inbox` (optional triage drop zone)
   - `executor` (one column per agent; rename to taste, e.g. `backend-dev`, `qa`, `deploy`) — the agent owns this column; its cards never leave it
   - `_templates` (hidden list — keep template cards here)

   **No `done` list.** Status is a label, not a list: `claim-<agent>` = doing, `done` (+ native `dueComplete`) = finished. `archive_old.py` sweeps `done`-labelled cards off the board on a timer. (Pipeline mode is optional — add a `pipeline` array to `trello_config.json` only if a card must traverse several agents.)

## 2. Create the archive board

In the same workspace:

1. Create a board named `Mission Control — Archive`.
2. Leave it empty; `archive_old.py` will create month-keyed lists (e.g. `archived-2026-05`) as needed.

## 3. Find the board and list IDs

Easiest way: open the board in the browser and append `.json` to the URL. The first `id` field is the board ID; under `lists[]` you get the list IDs.

Or, via the CLI (after credentials are exported):

```bash
export TRELLO_API_KEY='...'
export TRELLO_TOKEN='...'
python3 scripts/trello_task.py init                       # writes template trello_config.json
# fill board_id / archive_board_id in the file
python3 scripts/trello_task.py board                      # lists with their IDs
# fill lists.* with the right IDs
```

## 4. Create canonical labels

```bash
python3 scripts/setup_labels.py
```

This creates any missing canonical labels and writes their IDs back into `trello_config.json`. It is safe to re-run.

If you used a non-default agent set, edit `config.agents` first — `setup_labels.py` derives one `claim-<agent>` label per agent.

## 5. Seed template cards (optional)

In the UI, create a few cards in `_templates`:

- `tpl-bug` — checklist: Reproduce / Locate / Fix / Test / Document
- `tpl-feature` — checklist: Spec / Build / Test / Deploy / Document
- `tpl-pipeline` — checklist: Stage 1 / Stage 2 / Stage 3
- `tpl-qa` — checklist: Smoke / Regression / Sign-off
- `tpl-deploy` — checklist: Branch / Build / Promote / Verify

Set `templates_list_id` in `trello_config.json` to the `_templates` list ID.

The orchestrator then uses:

```bash
python3 scripts/trello_task.py template <template_card_id> executor "Fix login bug"
```

to clone a template into the executor list. Trello Free supports `idCardSource` with `keepFromSource=checklists,labels,due,attachments`.

## 6. Wire up the OpenClaw config

See `references/snippets/openclaw-config.snippet.json5` for the block to paste into `~/.openclaw/openclaw.json` and `references/snippets/exec-approvals.snippet.json` for the approval pre-allowlist.

## 7. Smoke test

```bash
python3 scripts/trello_task.py rate-budget
python3 scripts/digest.py
```

If both run without errors, the board is wired correctly.

## 7. Real-world example: optional pipeline of named agents

> **This section shows the optional pipeline mode** — one card flowing through several named agents in sequence (JARVIS → VISION → Friday → Sia), each stage a column, plus a terminal `done` column. Use it only when a single card genuinely needs multiple agents. The **default** model is single-owner (one agent per card, no move, `done` label) — see Section 1. In pipeline mode the final stage still finishes with the `done` label; the `done` column below is illustrative of the older list-based flow.

The single `executor` layout is the minimum that exercises the protocol. Some setups fan out to multiple named agents — each owning one stage of the pipeline.

Concrete example with four agents named **JARVIS** (research), **VISION** (design), **Friday** (build), and **Sia** (review):

### Board layout

```
┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬─────────────┐
│  inbox   │  JARVIS  │  VISION  │  Friday  │   Sia    │   done   │ _templates  │
├──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼─────────────┤
│ #312 raw │ #309     │ #305 wip │ #299     │ #287     │ #281     │ tpl-bug     │
│ #311 raw │ urgente  │ claim-V  │ claim-F  │ revisao  │ done     │ tpl-feat    │
│ #310 raw │ claim-J  │          │          │ claim-S  │ done     │ tpl-deploy  │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────┴─────────────┘
   user      research    design     build      review    archive    pre-built
   drops     grabs       handoff    handoff    QA pass   target     work cards
   here      from        from J     from V     from F    of done
            inbox
```

### `trello_config.json`

```json
{
  "board_id": "abc1234567890abcdef",
  "archive_board_id": "987zyx6543210fedcba",
  "templates_list_id": "list_templates_id",
  "lists": {
    "inbox":   "list_inbox_id",
    "jarvis":  "list_jarvis_id",
    "vision":  "list_vision_id",
    "friday":  "list_friday_id",
    "sia":     "list_sia_id",
    "done":    "list_done_id"
  },
  "agents": {
    "jarvis": { "role": "executor", "list_id": "list_jarvis_id" },
    "vision": { "role": "executor", "list_id": "list_vision_id" },
    "friday": { "role": "executor", "list_id": "list_friday_id" },
    "sia":    { "role": "executor", "list_id": "list_sia_id" }
  }
}
```

### Labels created by `setup_labels.py`

For each agent in `config.agents`, `setup_labels.py` derives one `claim-<agent>` label automatically:

- `claim-jarvis`, `claim-vision`, `claim-friday`, `claim-sia`

Plus the global ones: `urgente`, `bloqueado`, `revisao`, `pediu`, `stale`, `qa-failed`.

### `~/.openclaw/openclaw.json` `agents.list[]`

```json5
{
  agents: {
    list: [
      { id: "orchestrator", skills: ["trello-mission-control"], heartbeat: { every: "30m" } },
      { id: "jarvis",       skills: ["trello-mission-control"], heartbeat: { every: "30m" } },
      { id: "vision",       skills: ["trello-mission-control"], heartbeat: { every: "30m" } },
      { id: "friday",       skills: ["trello-mission-control"], heartbeat: { every: "30m" } },
      { id: "sia",          skills: ["trello-mission-control"], heartbeat: { every: "30m" } },
    ],
  },
}
```

Each agent's workspace `HEARTBEAT.md` reads its own list (`<MY_LIST>` placeholder filled with the matching list name).

### Pipeline flow

The orchestrator drops cards in `inbox`. JARVIS heartbeat picks them up (`get jarvis`), `claim jarvis`, does research, then `next --expect jarvis` advances to VISION. VISION repeats the cycle. The card walks `inbox → jarvis → vision → friday → sia → done`. Sia is the final QA gate before `done`.

If a stage rejects (label `qa-failed`), the card moves back one step with `prev`. The `claim-<agent>` label is automatic; another agent's heartbeat skips cards already claimed.

### Why each agent gets its own token

Trello rate-limits **per token** at 100 req/10 s. Five agents sharing one token would race against the same budget. Issue one token per agent (re-login as the same Trello user multiple times in incognito tabs works for personal use; for team setups, use multiple Trello users).

## 8. Going beyond 4 agents

Add entries to `config.agents` and rerun `setup_labels.py` — it creates the new `claim-<agent>` labels. Then add an `agents.list[]` entry in `~/.openclaw/openclaw.json` (see snippet). Each agent should authenticate with its own token to keep rate-limit headroom proportional.
