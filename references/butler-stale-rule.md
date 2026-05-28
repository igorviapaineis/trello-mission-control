# Butler rule — auto-label `stale` after 7 days of inactivity

Trello Free includes 250 Butler automation runs per month. We use only **one** rule, since the rest of the maintenance work (`archive_old.py`, `setup_labels.py`, claim release) runs on cron or hooks and does not consume Butler quota.

## Estimated cost

- Active board size: ~100–300 cards.
- Cards that go 7 days without activity: typically < 5 per week → ~20 runs/month.
- Even in extreme cases (large or noisy boards) the rule should stay below ~80 runs/month.
- 250 quota leaves a safety margin of ~170 runs for future rules.

## Rule

Trigger:
> every day at 4:00 am on board `<board>` for each card with no activity in the last 7 days that does not have the label `stale`...

Actions:
- add label `stale`
- post a comment `[<ISO time> | @butler | note] stale: 7d no activity`

## Importable JSON (Butler → Imports)

Copy the block below and paste into Butler → Imports. The snippet uses placeholder board/label IDs — replace them via `python3 scripts/setup_labels.py` first to ensure the `stale` label exists, then look up the IDs in `trello_config.json`.

```json
{
  "version": 1,
  "rules": [
    {
      "name": "auto-label stale 7d",
      "type": "calendar",
      "schedule": "daily",
      "time": "04:00",
      "boardId": "REPLACE_WITH_BOARD_ID",
      "filter": {
        "lastActivityDays": 7,
        "notHasLabel": "stale"
      },
      "actions": [
        { "type": "addLabel", "labelId": "REPLACE_WITH_STALE_LABEL_ID" },
        {
          "type": "addComment",
          "text": "[{date.iso} | @butler | note] stale: 7d no activity"
        }
      ]
    }
  ]
}
```

## Why no other Butler rules

Everything else CLI-can-do, we prefer CLI:

| Need | Where it lives |
|---|---|
| Mark dueComplete when moving to Done | `trello_task.py done` already passes `dueComplete=true` |
| Archive cards older than 30 days in Done | `archive_old.py` (cron daily) |
| Release claims when session stops | `release_my_claims.py` (plugin hook) |
| Ensure canonical labels | `setup_labels.py` (plugin onGatewayStart) |
| Notify on urgent stuck cards | orchestrator `digest` reports `overdue` and `stale` |

This keeps the 250 Butler runs/month free for future rules or one-off automations.
