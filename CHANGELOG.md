# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.6] — 2026-05-28

### Changed
- `docs/troubleshooting.md` "Doctor checks" section: each `CHECK N` entry now has a four-block layout — **Symptom** (literal `doctor.py` output), **Cause**, **Fix** (copy-pasteable shell), **Verify** (re-run command + expected output). Added a "healthy doctor output" preview at the top of the section so users know what success looks like.
- `references/board-template.md` adds Section 7 "Real-world example: pipeline of named agents" with a concrete JARVIS/VISION/Friday/Sia layout, ASCII art board, full `trello_config.json`, derived `claim-*` labels, `openclaw.json` agents block, pipeline flow narrative, and a "one token per agent" note. The previous "Going beyond 2 agents" renumbers to Section 8 ("Going beyond 4 agents").
- `docs/architecture.md` adds a second Mermaid sequence diagram for the multi-agent pipeline (JARVIS → VISION → Friday → Sia, with QA reject branch). The single-executor flow remains the primary intro.
- README, `docs/quickstart.md`, `references/install.md` bump `@v3.0.5` → `@v3.0.6`.
- `package.json` bumped to 3.0.6.

### Notes
- No script changes. No test changes. No behavior change.
- Triggered by a second self-review pass via `openclaw-skill-creator` flagging that troubleshooting was diagnostic-only (no "Verify" step) and that `board-template.md` only documented the minimum two-list layout.

## [3.0.5] — 2026-05-28

### Changed
- `SKILL.md` description rewritten as a pushy trigger phrase that names concrete contexts and lists example user prompts (per `~/.claude/skills/openclaw-skill-creator/references/triggering-tips.md`). The previous 113-character description under-triggered on natural prompts like "cria board pra meus agentes" or "orquestra via trello". Net: description grew from 113 to 521 characters, body still ≤ 500 lines.
- `SKILL.md` frontmatter adds `metadata.openclaw.homepage` and `metadata.openclaw.license`. Inert at runtime; useful for discoverability and license metadata.
- `SKILL.md` Prerequisites now spells out how to generate the Trello API key + token step by step (instead of just linking the dev page) and links `references/board-template.md` explicitly as the place to start when prepping the Trello side from scratch.
- `SKILL.md` Quickstart now opens with a Step 0 "prep checklist" pointing new users at `references/board-template.md` before any CLI runs. Steps 1–9 unchanged.
- `SKILL.md` "Card hygiene on completion" section trimmed to a one-line pointer at `references/card-spec.md`. The card-spec was already canonical; the duplicate content in SKILL.md was drift-prone. Body 335 → 324 lines.
- `docs/quickstart.md` opens with the same Step 0 prep checklist.
- `references/install.md` Section 3 now highlights `references/board-template.md` as the primary walkthrough instead of a brief mention.
- README, docs/quickstart.md, references/install.md install version `@v3.0.4` → `@v3.0.5`.
- `package.json` bumped to 3.0.5.

### Notes
- No script changes. No test changes. No behavior change.
- A self-review pass on the skill metadata using the `openclaw-skill-creator` skill (the one installed in Claude Code).

## [3.0.4] — 2026-05-28

### Added
- `scripts/doctor.py` — end-to-end setup verification with 10 numbered checks (`python_version`, `openclaw_cli`, `git_cli`, `env_credentials`, `config_present`, `trello_auth`, `board_reachable`, `canonical_labels`, `workspace_dirs`, `heartbeat_config`). Exit 0 on full pass; exit 9 (`DOCTOR_FAIL`) on any failure. `--verbose` and `--dry` modes.
- `tests/test_doctor.py` — pure-helper coverage for the JSON5 parser, agent lookup, missing-label diff, and heartbeat detection.
- `tests/smoke.sh` adds a dry-run entry for `doctor.py`.
- New exit code `9` `DOCTOR_FAIL` (documented in `SKILL.md` and `README.md`).

### Changed
- `SKILL.md` opens with **Prerequisites** and a 9-step numbered **Quickstart** (install → env vars → init+edit config → `setup_labels.py` → `doctor.py` → workspace templates → snippets → activate heartbeat → first card) **before** the existing Rules / CLI reference. The frontmatter now declares `git` and `openclaw` in addition to `python3` under `metadata.openclaw.requires.bins`, adds an `emoji`, and quotes the `description` per the OpenClaw skill convention.
- `docs/quickstart.md` aligned with the new SKILL.md Quickstart and adds the `doctor.py` verification step.
- `references/install.md`: a new section warns that the active board must exist before any script runs, and adds `doctor.py` as the verification step.
- `docs/troubleshooting.md`: a new **Doctor checks** section maps each of the 10 checks to its cause and a copy-pasteable fix.
- `README.md` Quickstart adds `doctor.py`; the "What's in the box" table lists it; the exit-codes table adds `9`.
- `scripts/trello_task.py` exports `EXIT_DOCTOR_FAIL = 9`.
- `package.json` bumped to `3.0.4`.

### Notes
- No behaviour change to any existing script. `doctor.py` is purely read-only diagnostic.

## [3.0.3] — 2026-05-28

### Removed
- `openclaw.plugin.json` and `index.ts` — the project no longer ships as an OpenClaw plugin. It is a skill, installed via `openclaw skills install git:...`. The previous plugin layer never installed successfully because the manifest was missing the required `openclaw.extensions` field and `index.ts` imported a non-existent SDK package.
- The `openclaw.*` block, `main` field, and `type` field in `package.json` (npm metadata remains for `npm pack` distribution).
- `plugins.entries.trello-mission-control` from `references/snippets/openclaw-config.snippet.json5`.
- Building / packaging sections in `docs/dev-guide.md` that referenced `index.ts` and the plugin SDK.

### Changed
- Install command in README, quickstart, install.md, dev-guide, troubleshooting, walkthrough, and CONTRIBUTING changed from `openclaw plugins install` to `openclaw skills install`. `openclaw gateway restart` is no longer required for first install.
- `references/agent-templates/executor/HEARTBEAT.md.template` now runs `release_my_claims.py <agent>` at the start of every tick as a replacement for the former `onSessionStop` lifecycle hook.
- `references/install.md` documents the new post-install lifecycle wiring (one-shot `setup_labels.py`, inline release at heartbeat start, daily `cron_stale_claims.py`).
- `docs/architecture.md` drops the L2 plugin layer; "Why these specific choices" explains the trade-off versus a real plugin.
- `docs/troubleshooting.md` adds an entry for the exact error `package.json missing openclaw.extensions` and updates the operational guidance away from `openclaw plugins list` / `openclaw gateway restart`.
- `SKILL.md` frontmatter no longer references the (now-removed) plugin config path.
- `.github/workflows/ci.yml` drops `openclaw.plugin.json` from JSON validation.

### Added
- `scripts/cron_stale_claims.py` — daily janitor that releases `claim-*` labels whose card has no activity for 30 minutes (configurable via `--minutes`). Replaces the missing `onSessionStop` hook for sessions that crash without running the HEARTBEAT cleanup.
- `tests/test_cron_stale_claims.py` — pure helper coverage for the stale-window filter and ISO parsing.
- `tests/smoke.sh` adds a dry-run case for `cron_stale_claims.py`.
- `docs/migrating-from-3.0.x.md` — concrete migration steps for anyone who attempted 3.0.0–3.0.2.

### Notes
- A real OpenClaw plugin (with correct `openclaw.extensions` manifest, compiled `dist/index.js`, and hooks mapped to the real `api.on(...)` / `api.registerHook(...)` surface) is on the roadmap for a future minor release. The skill-only form is functionally complete for the canonical workflow.
- Label names (`urgente`, `bloqueado`, `revisao`, `pediu`, `qa-failed`) and the structured card layout are unchanged from 3.0.1/3.0.2.

## [3.0.2] — 2026-05-28

### Fixed
- Install commands in README, `docs/quickstart.md`, `docs/dev-guide.md`, and `references/install.md` now use `git:github.com/igorviapaineis/trello-mission-control@v3.0.2` instead of `clawhub:igorviapaineis/trello-mission-control`. The plugin has not yet been published to the [ClawHub registry](https://docs.openclaw.ai/clawhub), so the previous `clawhub:` form failed at install time for end users.
- `scripts/ensure_skills.py` no longer relies on the non-existent `clawhub download <slug> --no-install` flag. New flow: `clawhub search` → `clawhub inspect <slug>` (returns metadata including the git repository URL) → `git clone --depth 1` to a temporary directory → `scripts/skill_audit.py` → `openclaw skills install`. Documented in `SKILL.md` and the architecture sequence diagram.
- `scripts/skill_audit.py` docstring updated to reflect the new flow.

### Added
- `docs/troubleshooting.md`: new **Install** section covering the `clawhub:` install failure, `git:` install permission errors, and disabled-after-install diagnostics.
- `tests/test_ensure_skills_inspect.py` — unit coverage for `repo_url_from_metadata`, plus dry-run safety of `search_clawhub` and `inspect_clawhub`.
- `tests/smoke.sh` now exercises `ensure_skills.py --dry`.

### Notes
- A future release will switch the recommended install back to `clawhub:` once the plugin has been published to the ClawHub registry.

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
