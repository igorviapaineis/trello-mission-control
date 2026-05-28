# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.1] — 2026-05-28

### Added
- `LICENSE` (MIT).
- `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` at repo root.
- `.github/workflows/ci.yml` running syntax + JSON validation + unittest + smoke on Python 3.10/3.11/3.12. *(Note: the workflow file ships in this commit but the initial v3.0.1 push omitted it because the publishing token lacked the GitHub `workflow` scope. Maintainers should add it manually via `git push` after `gh auth refresh -s workflow`, or paste it into the GitHub UI.)*
- `.github/ISSUE_TEMPLATE/` (bug, feature) and `.github/PULL_REQUEST_TEMPLATE.md`.
- `tests/` test suite using stdlib `unittest`: meta-block round-trip, tag-prefix shape, format_card edge cases, resolve_list/resolve_label, skill_audit fixtures (1 pass + 8 fail scenarios), archive month-list derivation. Plus `tests/smoke.sh` running 15+ CLI dry-runs.
- `docs/quickstart.md` — 5-minute install path.
- `docs/troubleshooting.md` — every exit code (1–8) and the most common operational issues mapped to causes and fixes.
- `docs/architecture.md` — Mermaid diagrams (component and sequence).
- `docs/dev-guide.md` — local install, build, packaging.
- `docs/walkthrough.md` — concrete end-to-end example of a card travelling through the system.
- README now opens with a `## Quickstart` block linking into `docs/`.

### Changed
- All English-only across SKILL.md, references, and templates. Card description section headers migrated from Portuguese (`Objetivo / Resultado / Mudanças / Métricas / Notas`) to English (`Goal / Result / Changes / Metrics / Notes`).
- `scripts/update_card_complete.py::parse_existing` now accepts both the legacy Portuguese headers and the new English ones (backward compatible) and always emits English on render.
- `package.json` version bumped to `3.0.1`.
- `.gitignore` adds `*.pyc`, `__pycache__/`, `.venv/`, `tests/.tmp_*/`, `*.egg-info/`.

### Notes
- Label names (`urgente`, `bloqueado`, `revisao`, `pediu`, `qa-failed`) are intentionally kept as-is — they are identifiers in user configs and renaming them would break installs without offering meaningful value.
- No code behavior changes other than `parse_existing` accepting the legacy Portuguese headers.

## [3.0.0] — 2026-05-28

### Added
- Conversion from skill-only layout to an OpenClaw **plugin** with `openclaw.plugin.json` manifest and `index.ts` registering `onGatewayStart`, `onSessionStart`, `onSessionStop` hooks.
- Generic `orchestrator` + `executor` 2-agent baseline, extensible to N executors.
- Atomic claim/release via `claim-<agent>` label (exit code 5 = `ALREADY_CLAIMED`).
- `scripts/digest.py` — single-call orchestrator summary.
- `scripts/archive_old.py` — nightly archive to a second board (Trello Free hygiene).
- `scripts/wake_on_urgent.py` — `openclaw heartbeat wake <agent> --now`.
- `scripts/setup_labels.py` — idempotent canonical-label creation.
- `scripts/release_my_claims.py` — payload for the `onSessionStop` hook.
- `scripts/skill_audit.py` — static scan that refuses common dangerous patterns in clawhub skills (exit 8 on failure).
- `scripts/ensure_skills.py` — reads `required_skills` from a card's meta block and installs missing skills from ClawHub after audit; blocks the card with an explanatory comment on audit failure.
- `scripts/attach_dir.py` — gzip a directory and attach within the Trello Free 10 MB cap.
- `scripts/update_card_complete.py` — card hygiene helper: structured description, ticked checklist, attachments, brief tagged `done` comment.
- New `trello_task.py` commands: `claim`, `release`, `claimed-by`, `release-all`, `meta-get`, `meta-set`, `template`, `rate-budget`.
- New flags: `--tag`, `--filter`, `--since`, `--expect`, `--verbose`.
- New exit codes: 5 `ALREADY_CLAIMED`, 6 `LOW_BUDGET`, 7 `STATE_DRIFT`, 8 `SKILL_AUDIT`.
- Per-call rate-limit header capture and observability (`rate-budget` command).
- `references/` documentation: `card-spec.md`, `labels.md`, `board-template.md`, `butler-stale-rule.md`, `heartbeat-budget.md`, `skill-audit-checks.md`, `install.md`.
- `references/snippets/` — drop-in JSON for `openclaw.json`, `exec-approvals.json`, Butler.
- `references/agent-templates/` — `AGENTS.md`, `SOUL.md`, `HEARTBEAT.md` templates per role and a shared `MEMORY.md`.
- YAML frontmatter on `SKILL.md` (required by OpenClaw skill spec).

### Changed
- `SKILL.md` rewritten around the canonical workflow with claim/release, provenance tagging, card-hygiene spec, and skill discovery.
- `scripts/trello_task.py` rewrites `pipeline-status` and `board` to use one nested `/boards/{id}/cards` call instead of N per-list calls.
- `done` now also sets `dueComplete=true`.
- `example-config.json` reshaped around the new `archive_board_id`, `templates_list_id`, and `agents` block.
