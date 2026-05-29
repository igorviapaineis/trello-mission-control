# Architecture

> **v3.2.0 status model (default).** A card belongs to one agent and stays in that agent's column for its whole life. Status is a label, never a list move: `claim-<agent>` = doing, `done` (+ native `dueComplete`) = finished. There is no `done` list — `archive_old.py` sweeps `done`-labelled cards to the archive board on a timer. Multi-stage cards can opt into **pipeline mode** (handoff between columns via `next`/`prev`), where the move-based diagrams below still apply; in single-owner mode the only "move" is the archive sweep.

The plugin is structured in four cooperating layers. The diagrams render directly on GitHub.

## Component view

```mermaid
flowchart LR
    U[User]
    O[Orchestrator agent]
    E1[Executor 1]
    E2[Executor 2..N]
    T[(Trello board)]
    A[(Archive board)]
    C[ClawHub]

    U -->|chat| O
    O -->|create card| T
    O -->|digest 30min| T
    O -->|wake-on-urgent| E1
    O -->|wake-on-urgent| E2
    T -->|heartbeat 30min: get my list| E1
    T -->|heartbeat 30min: get my list| E2
    E1 -->|claim / release / handoff| T
    E2 -->|claim / release / handoff| T
    E1 -->|ensure_skills download| C
    E2 -->|ensure_skills download| C
    T -->|archive_old nightly cron| A
```

## Sequence: one card, end to end

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant O as Orchestrator
    participant T as Trello
    participant E as Executor
    participant C as ClawHub

    User->>O: "Implement /api/login with JWT"
    O->>T: create card in `executor` list (desc, meta, checklist, label urgente)
    O->>E: openclaw heartbeat wake executor --now
    E->>T: GET /lists/executor/cards
    T-->>E: cards (the new one)
    E->>T: claim cardId executor (POST label claim-executor)
    E->>T: meta-get cardId required_skills
    T-->>E: ["nextjs"]
    E->>C: clawhub search nextjs --json
    C-->>E: slug
    E->>C: clawhub inspect <slug> --json
    C-->>E: metadata (repository URL)
    E->>E: git clone --depth 1 <repo> /tmp/nextjs
    E->>E: skill_audit /tmp/nextjs (exit 0)
    E->>E: openclaw skills install /tmp/nextjs
    Note right of E: do the work
    E->>T: update_card_complete (desc, checklist, attachments)
    E->>T: comment --tag done "..."
    E->>T: done cardId (idList → done, dueComplete=true)
```

## Sequence: multi-agent pipeline (JARVIS → VISION → Friday → Sia)

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant O as Orchestrator
    participant T as Trello
    participant J as JARVIS
    participant V as VISION
    participant F as Friday
    participant S as Sia

    User->>O: "Build /api/login with JWT"
    O->>T: create card in `inbox` (desc, meta, checklist, revisao)

    Note over J,T: JARVIS heartbeat (research stage)
    J->>T: get jarvis
    T-->>J: card list
    J->>T: claim cardId jarvis
    J->>T: research, comment --tag note
    J->>T: next cardId --expect jarvis  → VISION

    Note over V,T: VISION heartbeat (design stage)
    V->>T: get vision; claim; design output; comment done
    V->>T: next cardId --expect vision  → Friday

    Note over F,T: Friday heartbeat (build stage)
    F->>T: get friday; claim; implement
    F->>T: update_card_complete (desc, attach, done comment)
    F->>T: next cardId --expect friday  → Sia

    Note over S,T: Sia heartbeat (review stage)
    S->>T: get sia; claim; QA
    alt accept
        S->>T: done cardId (idList → done, dueComplete=true)
    else reject
        S->>T: label qa-failed
        S->>T: prev cardId --expect sia  → Friday (rework)
    end
```

The single-executor diagram (above) shows the protocol primitives; this one shows the same primitives chained across stages.

## Layers

```
L2 — Per-agent workspace (~/.openclaw/workspace-<agent>/)
     Standard OpenClaw files: AGENTS.md, SOUL.md, USER.md, IDENTITY.md,
     TOOLS.md, HEARTBEAT.md, MEMORY.md, memory/YYYY-MM-DD.md.

L1 — Skill (~/.openclaw/skills/trello-mission-control/)
     SKILL.md with YAML frontmatter.
     scripts/ holds the Python CLI.
     references/ holds the docs, snippets, agent templates.

L0 — Global config
     ~/.openclaw/openclaw.json     — agents.list with skills+tools allow.
     ~/.openclaw/exec-approvals.json — per-agent allowlist patterns.
```

## Why these specific choices

- **Skill, not plugin**: an OpenClaw plugin can register typed runtime hooks but requires a built JS entry, a valid `openclaw.extensions` manifest, and a pinned plugin-API version. None of that is worth the cost for the three lifecycle moments this project cares about. We replace those moments with `setup_labels.py` (post-install), an inline `release_my_claims.py` at the top of every executor heartbeat, and a daily `cron_stale_claims.py` janitor. Trade-off: a session that crashes between the last claim and the next heartbeat leaves its claim stuck until the cron runs; in practice that's a few hours at most.
- **Label-based claim**: the Trello API has no compare-and-swap. A label is visible in the UI, simple to query, and the race window (read labels → POST label) is ~200ms — small enough that two agents almost never race on the same card.
- **One nested `/boards/{id}/cards` call**: replaces `pipeline-status` and `digest`'s previous N+1. Saves rate-limit budget and reduces orchestrator latency.
- **JSON meta block in `desc`**: Trello Free has no custom fields. Putting structured metadata in a comment-style block keeps the description readable and parseable.
- **Static skill audit**: a sandbox would be more thorough but adds dependencies and complexity. A static scan catches the obvious dangerous patterns and is good enough as a first filter; the user is the final arbiter.
- **Tokenjuice on by default**: every CLI call returns a few-line summary, but `pipeline-status` or `digest` on a busy board can produce a lot. Tokenjuice compacts it without changing exit codes or stderr.
- **Per-token rate budget**: each agent should authenticate with its own token so the per-token 100 req / 10 s limit applies independently. Sharing a token is the most common rate-limit footgun.

## Where things live in this repo

```
trello-mission-control/
├── package.json            # npm metadata + version (no plugin manifest)
├── SKILL.md                # protocol document loaded into every agent session
├── scripts/                # CLI (Python 3 stdlib only)
│   ├── trello_task.py      # main CLI
│   ├── digest.py           # 1-call orchestrator summary
│   ├── archive_old.py      # nightly archive cron payload
│   ├── wake_on_urgent.py   # openclaw heartbeat wake wrapper
│   ├── setup_labels.py     # idempotent label setup (one-shot, post-install)
│   ├── release_my_claims.py# called at the top of every executor HEARTBEAT tick
│   ├── cron_stale_claims.py# daily janitor for stale claim-* labels
│   ├── skill_audit.py      # static scan for clawhub skills
│   ├── ensure_skills.py    # reads required_skills, installs missing
│   ├── attach_dir.py       # gzip a dir, attach (10 MB cap)
│   └── update_card_complete.py  # card hygiene helper
├── references/             # human-readable design + snippets + templates
├── tests/                  # unittest suite + smoke.sh
└── docs/                   # docs entry points (quickstart, troubleshooting, this)
```
