# Heartbeat budget — rate-limit math

Trello REST API limits (per the [official docs](https://developer.atlassian.com/cloud/trello/guides/rest-api/rate-limits/)):

- **300 requests / 10 s** per API key
- **100 requests / 10 s** per token
- Endpoint-specific limits: `/1/members`, `/1/membersSearch`, `/1/search` use stricter quotas — only the `digest` and the optional `search` command touch `/1/search` (and only when the orchestrator explicitly wants to search by free text).

## Baseline (2-agent minimum setup)

| Agent | Interval | Calls per tick | Calls / 10 s |
|---|---|---|---|
| orchestrator | 30 min | 1 (`digest`) | ~0.0056 |
| executor | 30 min | 2 (`get`, then `claim`/`comment`/`done` per card) | ~0.011 |

Total worst-case (assuming each tick processes 5 cards): ~10 calls / 10 s.

Headroom against the 100 / 10 s token limit: > 90 %.

## N executors

Per additional executor, add ~2 calls / 10 s in the worst case. The free tier comfortably supports more than a dozen executors before getting near the token limit.

Each agent should authenticate with its **own token**. Sharing a single token across agents drops effective headroom proportionally — the per-token limit is what bites first.

## Stagger

The `--wake now` mechanism plus the natural 30-min OpenClaw default already stagger most ticks. No explicit cron offset is required for the 2-agent baseline.

If many executors run on the same machine and you observe 429s, configure their heartbeats with offset (OpenClaw cron automatically applies up to 5 min stagger for top-of-hour expressions — see [Cron jobs](https://docs.openclaw.ai/automation/cron-jobs)).

## Observability

Every CLI call captures `x-rate-limit-api-token-remaining` and `x-rate-limit-api-key-remaining`. Run with `--verbose` to see them after each call. The standalone `rate-budget` command exits with code 6 (`LOW_BUDGET`) if less than 20 token requests remain.
