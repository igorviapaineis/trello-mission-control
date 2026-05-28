# Board template — bootstrap a fresh board from scratch

Trello Free does not let you publish a board template that other users can clone. The setup below takes ~5 minutes to do manually and is idempotent for the parts that touch the API.

## 1. Create the active board

In the Trello UI:

1. Create a workspace (or pick an existing one).
2. Create a board named `Mission Control` (or whatever you prefer).
3. Add these lists in order:
   - `inbox`
   - `executor` (one per executor agent; rename to taste, e.g. `backend-dev`, `qa`, `deploy`)
   - `done`
   - `_templates` (hidden list — keep template cards here)

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

## Going beyond 2 agents

Add entries to `config.agents` and rerun `setup_labels.py` — it creates the new `claim-<agent>` labels. Then add an `agents.list[]` entry in `~/.openclaw/openclaw.json` (see snippet). Each agent should authenticate with its own token to keep rate-limit headroom proportional.
