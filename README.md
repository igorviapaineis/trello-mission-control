# Trello Mission Control v2

CLI for managing cross-agent task delegation via Trello boards.

## Features

- **Config-driven** — board lists, labels, and pipeline defined in `trello_config.json`
- **Pipeline workflow** — `next`/`prev` moves cards through defined stages
- **Name resolution** — use list/label names instead of raw IDs everywhere
- **Dry run** — `--dry` flag simulates without executing
- **Error handling** — retry with backoff on rate limits, clear auth errors
- **Zero dependencies** — pure Python stdlib (urllib only)

## Install

```bash
# 1. Set credentials
export TRELLO_API_KEY="your-api-key"
export TRELLO_TOKEN="your-token"

# 2. Generate config
python3 scripts/trello_task.py init

# 3. Edit trello_config.json with your board data
#    See references/example-config.json for a full example
```

## Quick Start

```bash
# Board overview
python3 scripts/trello_task.py board

# Pipeline status
python3 scripts/trello_task.py pipeline-status

# Create task
python3 scripts/trello_task.py create jarvis "Fix bug" "urgente"

# Advance pipeline
python3 scripts/trello_task.py next <card_id>

# Dry run
python3 scripts/trello_task.py --dry move <card_id> vision
```

## Config

```json
{
  "board_id": "YOUR_BOARD_ID",
  "lists": { "inbox": "ID", "done": "ID" },
  "labels": { "urgent": "ID" },
  "pipeline": ["inbox", "done"]
}
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Generic error |
| 2 | Auth/permission error |
| 3 | Rate limit exhausted |
| 4 | Missing config |
