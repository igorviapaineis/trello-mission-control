# Troubleshooting

## Install

### `openclaw plugins install clawhub:igorviapaineis/trello-mission-control` fails
Symptom: the install errors with `package not found in registry`, `unknown source`, or similar.

Cause: the plugin has not yet been published to the [ClawHub](https://docs.openclaw.ai/clawhub) registry. The `clawhub:` prefix only resolves names that the registry knows about.

Fix: install from the GitHub release tag instead:

```bash
openclaw plugins install git:github.com/igorviapaineis/trello-mission-control@v3.0.2
openclaw gateway restart
```

Pick the tag you want from https://github.com/igorviapaineis/trello-mission-control/releases.

### `openclaw plugins install git:...` fails with permission denied
Cause: SSH-style URL into a private repo or missing git credentials. The plugin's repo is public, so this should not happen. Verify the URL form is `git:github.com/<owner>/<repo>@<ref>` (not `git@github.com:...`) and that `git ls-remote https://github.com/igorviapaineis/trello-mission-control` works for you.

### Plugin installs but `openclaw plugins list` shows it disabled
Run `openclaw plugins enable trello-mission-control` then `openclaw gateway restart`.

## Exit codes

The CLI scripts use a defined set of exit codes. Every non-zero exit is one of these.

### `1` — Generic error
Unexpected. Check stderr for the actual message. Common causes: invalid arguments, file not found, malformed input.

### `2` — Auth / permission
The token or key was rejected (HTTP 401 or 403). Fix:
- Regenerate the token at https://trello.com/power-ups/admin (tokens can expire if you set an expiry at generation time).
- Confirm `TRELLO_API_KEY` and `TRELLO_TOKEN` are exported in the **same** shell that runs the script.
- Confirm the token has permission on the board (`read` and `write`).

### `3` — Rate limit exhausted
After 3 retries with backoff, Trello is still 429ing. Causes:
- Too many agents sharing a single token. Give each agent its own token (per-token limit is 100 req / 10 s).
- A burst from `pipeline-status` or `digest` on a huge board. Reduce frequency or split boards.
- A bug elsewhere causing rapid retries.

### `4` — Missing config
`trello_config.json` not found, or it's missing required keys. Fix:
```bash
python3 scripts/trello_task.py init    # writes a template
# fill board_id and archive_board_id
```
Or set `TRELLO_CONFIG=/abs/path/to/trello_config.json`.

### `5` — Already claimed
The card already has a `claim-<other-agent>` label. The agent that hit this should simply move on to the next card. **If you see this repeatedly on the same card after no agent is actively working it**, you have a claim leak — fix with:
```bash
python3 scripts/trello_task.py release-all <agent>
# or, to wipe any claim on a specific card:
python3 scripts/trello_task.py unlabel <card_id> claim-<agent>
```

### `6` — Low rate-limit budget
Less than 20 token requests remaining in the current 10-second window. Not fatal but a yellow flag. Fix:
- Increase heartbeat interval.
- Give each agent its own token.
- Audit if any script is calling the API in a loop unnecessarily.

### `7` — State drift
`next --expect <list>` or `prev --expect <list>` saw the card in a different list than expected. Another agent moved it concurrently. Fix:
- Refetch the card (`card <id>`) to see where it is now.
- If it's already at the target, do nothing.
- If something racy happened, check `activity <id>` for the move history.

### `8` — Skill audit failure
`skill_audit.py` refused a clawhub skill. The stderr message names the pattern that failed. Causes:
- The skill is genuinely dangerous — leave it.
- The skill has a false positive in the static scan — open an issue with the skill name and the failing pattern. See `references/skill-audit-checks.md` for what we check.
- The skill has a non-allowed shebang (`perl`, `ruby`) — that's a hard fail by design; ask the skill author for a Python or shell port.

## Operational problems

### A hook didn't fire
Symptom: starting an agent session, you don't see "You have N cards claimed", or ending it doesn't release claims.

Check:
```bash
openclaw plugins list                          # is trello-mission-control listed enabled?
openclaw plugins config trello-mission-control # is the config block present?
openclaw gateway restart                       # try a clean reload
```

If still failing, run the hook payload manually to isolate:
```bash
python3 scripts/release_my_claims.py <agent> --dry
```

### `setup_labels.py` created duplicates
Cause: a previous run created a label with the wrong color, then a config edit changed expectations. Delete the duplicates in the Trello UI, then re-run `python3 scripts/setup_labels.py`. The script reuses any label with the right name regardless of color.

### A card jumped back into `inbox` on its own
Cause: an agent's session was killed mid-task, and the `onSessionStop` hook ran `release_my_claims.py`. The card lost its `claim-<agent>` label and the next executor heartbeat picks it up. This is correct behaviour — the alternative is leaking claims forever.

If you want a card to *stay* claimed across a planned restart, comment with `--tag note "expect resume"` so the orchestrator's digest can flag it as long-running.

### `ensure_skills.py` blocks a card with "audit failed"
Read the blocking comment on the card. It names the skill and the audit reason. Options:
- Trust the user — install manually with `openclaw skills install <folder>` if you're sure.
- File an upstream issue with the skill author.
- Patch the skill locally and install from the patched copy.

### Rate-limit headers come back as `None`
Some Trello errors don't include the rate-limit headers in the response. Run `python3 scripts/trello_task.py rate-budget` for a fresh, deliberate query. If that returns `None`, your token is invalid (HTTP 401) and the error is being shadowed somewhere.

### Card description has the meta block but `meta-get` returns `NONE`
Causes:
- The meta block has invalid JSON. Trello accepts arbitrary text in `desc`, so you can see the block visually but the parser rejects it. Fix the JSON inside `<!--meta ... -->`.
- The meta block uses the wrong markers. They must be exactly `<!--meta` and `-->` with the JSON between them.

### `archive_old.py` says it would archive zero cards
Cause: no cards in the source list have `dateLastActivity` older than the threshold. Check with:
```bash
python3 scripts/trello_task.py search "" --label "" 2>/dev/null | head
```
or look at the source list in the UI — newly created cards have today's `dateLastActivity`.
