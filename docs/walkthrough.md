# Walkthrough — one card, end to end

Concrete example: the user asks the orchestrator to add a `/api/login` JWT endpoint to a Next.js project. We trace what each agent does, the exact commands they run, and what the card looks like at each step.

Assumptions: a working install per [quickstart](quickstart.md), two agents (`orchestrator` and `executor`), a board with lists `inbox`, `executor`, `done`, `_templates`.

## 1. User → Orchestrator

User opens a session with the `orchestrator` workspace (Telegram, Slack, Claude, web UI — whatever channel is configured) and sends:

> Implement `/api/login` with JWT in our Next.js app. Acceptance: returns 200 + token on valid creds, 401 otherwise. Tests required.

## 2. Orchestrator creates the card

The orchestrator picks the `executor` list, decides this is `P1` (not blocking, but soon), and needs the `nextjs` skill. It runs:

```bash
S=~/.openclaw/skills/trello-mission-control/scripts

python3 $S/trello_task.py create executor "Add /api/login with JWT" "urgente"
# CREATED:abc123|Add /api/login with JWT|https://trello.com/c/abc123

python3 $S/trello_task.py desc abc123 "$(cat <<'EOF'
## Goal
Add a POST `/api/login` endpoint in the Next.js app that validates email+password,
returns a signed JWT on success (200) and 401 on failure. Must include unit tests.

## Notes
Use the existing `lib/auth.ts` for password hashing. Sign with `JWT_SECRET` from env.
EOF
)"

python3 $S/trello_task.py meta-set abc123 priority P1
python3 $S/trello_task.py meta-set abc123 required_skills '["nextjs"]'
python3 $S/trello_task.py meta-set abc123 created_by '@orchestrator'

# Add a checklist that the executor will tick off as work progresses
CL=$(python3 $S/trello_task.py checklist abc123 create "Result" | cut -d'|' -f1 | cut -d: -f2)
python3 $S/trello_task.py checklist abc123 add $CL "Implement handler"
python3 $S/trello_task.py checklist abc123 add $CL "Validate input"
python3 $S/trello_task.py checklist abc123 add $CL "Sign and return JWT"
python3 $S/trello_task.py checklist abc123 add $CL "Unit tests"
python3 $S/trello_task.py checklist abc123 add $CL "Update API docs"

# Because we labelled urgente, wake the executor now
python3 $S/wake_on_urgent.py executor
# WAKE_REQUESTED:executor
```

Orchestrator replies to the user:

> Card `abc123` in `executor`. Urgent — executor woken now.

## 3. Executor heartbeat fires

Within seconds (the wake), the executor's `HEARTBEAT.md` runs. The relevant block:

```bash
python3 $S/trello_task.py get executor
# CARD:abc123|Add /api/login with JWT|labels=urgente|...
```

It picks the most urgent unclaimed card (this one) and claims it:

```bash
python3 $S/trello_task.py claim abc123 executor
# CLAIMED:abc123|executor

python3 $S/ensure_skills.py abc123
# (assume nextjs not installed yet)
# SKILL_INSTALLED:nextjs
```

If `ensure_skills.py` had returned exit 8, the card would now be labelled `bloqueado` with a tagged `blocked` comment and the executor would move on to the next card. Here we assume audit pass.

## 4. Executor does the work

This is the actual implementation, outside the scope of the plugin — the executor uses whatever skills it has (now including `nextjs`) plus its general agent capabilities. It writes the handler, tests pass, it captures the diff to `/tmp/diff.patch` and the test output to `/tmp/test.log`.

While working, it ticks off checklist items one by one:

```bash
python3 $S/trello_task.py checklist abc123 items $CL
# ITEM:item1|[ ] Implement handler
# ITEM:item2|[ ] Validate input
# ...
python3 $S/trello_task.py checklist abc123 check item1
# CHECKED:item1
```

## 5. Executor completes the card

```bash
python3 $S/update_card_complete.py abc123 \
  --result "Added pages/api/login.ts using jose for JWT signing. 12 unit tests added." \
  --changes "pages/api/login.ts:1-58 — new POST handler" \
  --changes "lib/auth.ts:42 — exported verifyPassword for reuse" \
  --changes "__tests__/api/login.test.ts:1-110 — 12 cases" \
  --metric "Time: 35min" \
  --metric "Files changed: 3" \
  --metric "Tests: 12 pass" \
  --notes "Used 'jose' lib (already in deps). JWT TTL hardcoded at 1h for now; consider making configurable later." \
  --check-step "Implement handler" \
  --check-step "Validate input" \
  --check-step "Sign and return JWT" \
  --check-step "Unit tests" \
  --check-step "Update API docs" \
  --attach /tmp/diff.patch \
  --attach /tmp/test.log \
  --comment "12 tests pass, JWT signed with JWT_SECRET" \
  --agent executor

python3 $S/trello_task.py done abc123
```

## 6. What the card looks like now

- **List**: `done`.
- **Labels**: `urgente` (still — not auto-removed).
- **Description**: 5 sections (Goal/Result/Changes/Metrics/Notes) plus the `<!--meta ... -->` block.
- **Checklist `Result`**: 5/5 checked.
- **Attachments**: `diff.patch`, `test.log`.
- **Comments**:
  - `[2026-05-28T14:22Z | @executor | claim] working`
  - `[2026-05-28T14:55Z | @executor | done] 12 tests pass, JWT signed with JWT_SECRET`

## 7. Tomorrow: orchestrator digest

The next time the user opens an orchestrator session (or the orchestrator's 30-min heartbeat fires), `digest.py` reports the board state:

```
DIGEST:
  pipeline:
    inbox: 0
    executor: 0
    done: 1
  overdue: 0
  urgent: 0
  stale_7d: 0
  claimed: 0
```

In 30 days, `archive_old.py` (which runs nightly) will move card `abc123` to the archive board's `archived-2026-06` list, keeping the active board lean.

## 8. If something had gone wrong

- **Executor session died mid-task**: `onSessionStop` runs `release_my_claims.py executor`. Card loses `claim-executor`, returns to the queue. Next heartbeat (this or another executor) picks it up. Comments left so far stay in place.
- **`nextjs` skill audit failed**: ensure_skills posts `[ISO | @executor | blocked] missing skills for card: 1 failed - nextjs: <reason>` and labels the card `bloqueado`. Orchestrator's next digest reports the block.
- **Tests didn't pass**: executor calls `comment --tag blocked "tests failing: ..."`, labels `bloqueado`, leaves the card. Orchestrator sees it on the next digest and can decide to push back or escalate to a human.
- **Two executors raced**: the second to call `claim` gets exit 5 (`ALREADY_CLAIMED`) and moves to the next card. No double-work.

This loop, multiplied across N executors, is the entire system.
