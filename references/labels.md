# Canonical labels (v3)

`setup_labels.py` ensures these exist on the configured board. It is idempotent — safe to run on every gateway start (plugin hook does so). When new agent IDs are added to `config.agents`, the script creates their `claim-<agent>` labels automatically.

| Label | Color | When applied | Removed by |
|---|---|---|---|
| `urgente` | red | orchestrator at card creation when user signals urgency; triggers `wake_on_urgent.py` | manual / when done |
| `bloqueado` | orange | executor when a dependency is missing or skill audit fails | when unblocked |
| `revisao` | yellow | pipeline projects that must traverse multiple stages | when done |
| `pediu` | purple | direct user request (vs internal task spawn) | when done |
| `claim-<agent>` | sky | `claim` command — one per agent | `release` / hook `onSessionStop` |
| `stale` | lime | Butler rule, 7 days of no activity | when activity resumes (manual or via update) |
| `qa-failed` | pink | QA executor rejects a card after review | when re-submitted |

## Color note

Trello's color palette is constrained. We picked colors that read distinctly against each other on the default board background. If your colorblindness profile makes red/orange or sky/lime hard to tell apart, change the colors directly in `setup_labels.py` — the rest of the system uses label **names**, not colors.

## Why these specific labels and not others

- **One label per concept, no overlap.** Avoid having both `priority-high` and `urgente`; pick one.
- **Lock state is a label, not a list.** That keeps the pipeline lists clean (only state-of-work, not state-of-claim).
- **`stale` is informational, not actionable.** It tells the orchestrator to nudge `@igor` (or whoever the user is) on the next digest — it does not block work.
- **`claim-<agent>` per agent.** Avoids a single shared "in progress" label that would not tell us *who* is working.

## Adding more

Need a new label? Add a `(name, color)` tuple to `CANONICAL_LABELS` in `scripts/setup_labels.py` and re-run the script. The plugin hook will pick it up on the next gateway start automatically.
