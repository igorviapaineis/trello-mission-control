# Quickstart

Get a working 2-agent setup in 5 minutes.

```bash
# 0. First time? Auto-bootstrap the Trello side (~10 sec, requires creds from step 2 first).
#    Choose one of:
#      python3 scripts/bootstrap_board.py --auto-detect --with-labels         # read agents from ~/.openclaw/openclaw.json
#      python3 scripts/bootstrap_board.py --agents <list> --with-labels       # explicit (interview the user first)
#      python3 scripts/bootstrap_board.py --with-labels                       # single executor (default)
#    Creates the active board + lists + archive board + canonical labels and writes trello_config.json.
#    Prefer manual setup? See references/board-template.md §1 onwards.

# 1. Install the skill (git source; will move to `clawhub:igorviapaineis/trello-mission-control` once published)
openclaw skills install git:github.com/igorviapaineis/trello-mission-control@v3.1.2

# 2. Set Trello credentials
export TRELLO_API_KEY='...'      # https://trello.com/power-ups/admin
export TRELLO_TOKEN='...'

# 3. Create boards in Trello UI:
#    - "Mission Control"          (active board)
#      lists: inbox, executor, done, _templates
#    - "Mission Control — Archive" (empty; nightly archive target)

# 4. Generate and edit the config
cd ~/.openclaw/skills/trello-mission-control
python3 scripts/trello_task.py init
# fill board_id, archive_board_id, templates_list_id, lists.* in the file

# 5. Create canonical labels (idempotent — board must already exist)
python3 scripts/setup_labels.py

# 5a. Verify setup end-to-end
python3 scripts/doctor.py
# exits 0 if everything is wired up; non-zero with explanation otherwise

# 6. Create workspaces for both agents
mkdir -p ~/.openclaw/workspace-{orchestrator,executor}
cp references/agent-templates/orchestrator/*.template ~/.openclaw/workspace-orchestrator/
cp references/agent-templates/executor/*.template     ~/.openclaw/workspace-executor/
cp references/agent-templates/shared/MEMORY.md.template ~/.openclaw/workspace-orchestrator/MEMORY.md
cp references/agent-templates/shared/MEMORY.md.template ~/.openclaw/workspace-executor/MEMORY.md
# rename .template -> drop suffix; fill in IDs

# 7. Merge the OpenClaw and exec-approvals snippets
#    references/snippets/openclaw-config.snippet.json5 → ~/.openclaw/openclaw.json
#    references/snippets/exec-approvals.snippet.json   → ~/.openclaw/exec-approvals.json

# 8. Smoke test
python3 scripts/digest.py
python3 scripts/trello_task.py rate-budget
```

Now open a session with the orchestrator and send a test message. Full reference: [references/install.md](../references/install.md). Architecture: [docs/architecture.md](architecture.md). Worked example: [docs/walkthrough.md](walkthrough.md).
