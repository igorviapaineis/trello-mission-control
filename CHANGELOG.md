# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.2.0] — 2026-05-29

### Changed (behaviour)
- **Status is now a label, not a list move.** Default model is single-owner: a card is created in its owner agent's column and stays there for its whole life. `claim-<agent>` = doing/em-andamento; the new `done` label (+ native `dueComplete`) = finished. This removes the `done`-list pile-up and the cross-list pickup bug class. Pipeline (multi-stage handoff via `next`/`prev`) is kept as a first-class **optional** mode for cards that genuinely need it.
- `trello_task.py done <id> [agent]` no longer moves the card to a `done` list. It adds the `done` label, sets `dueComplete=true`, and releases the agent's claim — the card does not move. `[agent]` defaults to `$OPENCLAW_AGENT_ID`.
- `trello_task.py get <list> --for-agent <me>` now also hides cards carrying the `done` label (actionable view), in addition to cards claimed by other agents.
- `scripts/archive_old.py` default mode now scans the whole board and archives every `done`-labelled card with no activity for N days (default `--days 14`). This timer is what keeps each column compact now that finished cards stay put. The old `--from <list>` whole-list archive is kept as a legacy override.
- `scripts/bootstrap_board.py` no longer creates a `done` list: fresh boards are `inbox` + one column per agent + `_templates`.
- `scripts/setup_labels.py` adds `done` (green) to the canonical label set.
- `scripts/digest.py` reports a `done` count per column and overall.
- `_pipeline_step` / `cmd_pipeline_status` short-circuit on `--dry` before requiring a `pipeline` config (dry runs never error when no pipeline is defined).

### Added
- `trello_task.py reopen <id>` — undo a completion (removes the `done` label, clears `dueComplete`).
- `trello_task.py resolve_or_create_label(name, color, …)` helper; `archive_old.card_is_done(card)` helper.
- `tests/test_setup_labels.py`, `tests/test_done_label.py`; `done`/`reopen`/`exclude_done` coverage in existing test files; `done agent` + `reopen` smoke entries.
- `docs/migrating-from-3.0.x.md` gains a "Migrating to 3.2.0" section; `docs/troubleshooting.md` gains a "done list / columns keep piling up → schedule archive_old.py" entry.

### Changed (docs)
- SKILL.md, executor + orchestrator templates, `docs/architecture.md`, `docs/quickstart.md`, `references/board-template.md`, `references/example-config.json` rewritten for the label-status model (no `done` list; pipeline documented as optional).
- README, `docs/quickstart.md`, `references/install.md`, `SKILL.md` bump `@v3.1.3` → `@v3.2.0`.
- `package.json` bumped to 3.2.0.

### Notes
- Minor release (new model + behaviour change), backward-compatible: existing boards keep working; a legacy `done` list simply stops receiving new cards. Adopt by running `setup_labels.py` (creates the `done` label), refreshing templates, and scheduling `archive_old.py`. See the migration note.
- Triggered by Igor's proposal to stop moving cards to an in-progress/done list (hundreds pile up) and convey status by label on the owner's column instead.

## [3.1.3] — 2026-05-28

### Fixed
- Executors no longer pick up cards already claimed by another agent. `trello_task.py get` gains a `--for-agent <agent_id>` flag that filters out cards carrying a `claim-<other-agent>` label client-side. The shipped `HEARTBEAT.md.template` and `AGENTS.md.template` now pass the flag and treat `claim` exit code 5 (`ALREADY_CLAIMED`) as an unconditional STOP instead of a recoverable "try next" hint. Setups where a card crosses executor lists (manual UI move, stray `move`/`next` call) are now safe — the wrong executor's heartbeat skips the card.

### Added
- `scripts/trello_task.py::is_claim_label`, `::claim_label_owner`, `::filter_cards_for_agent` — pure helpers exposed for tests and future reuse.
- `tests/test_get_filter.py` — 21 cases covering label-shape edge cases and the agent filter.
- `tests/smoke.sh` adds a dry-run entry for `get --for-agent`.
- `docs/troubleshooting.md` "Card showed up in the wrong executor's list" section, pointing at `trello_task.py history <card_id>` to audit who moved the card.

### Changed
- `SKILL.md` Rules section adds an explicit bullet: never work a card whose `claim-*` is for another agent. `SKILL.md` CLI reference documents `get --for-agent`.
- README, `docs/quickstart.md`, `references/install.md`, `SKILL.md` bump `@v3.1.2` → `@v3.1.3`.
- `package.json` bumped to 3.1.3.

### Notes
- Bugfix patch. `--for-agent` is opt-in for existing callers; default `get` behaviour is unchanged.
- Triggered by a real incident: card created in list `NEBULA` with label `claim-NEBULA` was worked by `VISION` after crossing lists.

## [3.1.2] — 2026-05-28

### Fixed
- `scripts/doctor.py::parse_openclaw_json` no longer destroys `https://...` URLs. The `//` line-comment stripper now uses a negative lookbehind (`(?<!:)//`) so URLs survive parsing. Before the fix, any `openclaw.json` containing a value like `"baseUrl": "https://api.minimax.io/anthropic"` would break parsing and CHECK 10 would FAIL with "openclaw.json could not be parsed".
- `scripts/doctor.py` CHECK 9 (`workspace_dirs`) and CHECK 10 (`heartbeat_config`) no longer hardcode the agent ids `orchestrator`/`executor`. The doctor now derives the expected agents from `agents.list[]` in `~/.openclaw/openclaw.json`. CHECK 10 PASSes when at least one agent has `trello-mission-control` in its own or inherited skills and every such agent has a non-zero `heartbeat.every`. CHECK 9 PASSes when each `agents.list[].id` has a corresponding `~/.openclaw/workspace-<id>/AGENTS.md`. The previous hardcoded list survives only as a fallback when `openclaw.json` is absent or has no agents yet (fresh install). Setups with custom agent names (`jarvis`, `vision`, `friday`, `sia`, `nebula`, `ultron`, …) now report PASS instead of a false FAIL.

### Added
- `scripts/doctor.py::agents_with_skill(cfg, skill_name)` — returns `agents.list[]` entries whose own or inherited skills include the given name.
- `scripts/doctor.py::agent_ids_for_workspaces(cfg, fallback)` — returns the agent ids whose workspace dirs the doctor expects on disk, with a fallback for fresh installs.
- `tests/test_doctor.py` adds `TestParseOpenclawJsonPreservesUrls` (4 cases: `https://`, `http://localhost`, real inline `//` comment, line-start `//` comment), `TestAgentsWithSkill` (own skills, defaults inheritance, empty), `TestAgentIdsForWorkspaces` (reads from cfg, fallback, none).
- `tests/test_bootstrap_board.py` adds `test_preserves_https_url_in_values` — the same regex bug shape applied to `bootstrap_board.py::auto_detect_agents`.

### Changed
- `scripts/bootstrap_board.py::auto_detect_agents` swaps its `(^|[^:])//[^\n]*` capture-group regex for `(?<!:)//[^\n]*`. Same effect, consistent with `doctor.py`, no capture group.
- `docs/troubleshooting.md` CHECK 9 and CHECK 10 sections updated: the Symptom shows the dynamic `workspace-<agent-id>/AGENTS.md` format, the Cause explains that the agent list is derived from `agents.list[]`, the Fix uses placeholder agent ids, and the Verify command invokes `doctor.agents_with_skill` directly. The "healthy doctor output" panel at the top of the troubleshooting page mirrors the new CHECK 9/10 wording.
- README, `docs/quickstart.md`, `references/install.md`, `SKILL.md` bump `@v3.1.1` → `@v3.1.2`.
- `package.json` bumped to 3.1.2.

### Notes
- Pure bugfix patch. No new capability. No behavior change for setups already using `orchestrator`/`executor` agent ids.
- Triggered by a tester running `doctor.py` against a real multi-agent setup (`sia`, `jarvis`, `vision`, `friday`, `nebula`, `ultron`) and getting `9/10 OK` with a false-negative CHECK 10 FAIL caused by both bugs at once.

## [3.1.1] — 2026-05-28

### Added
- `scripts/bootstrap_board.py` gains `--auto-detect`: reads `~/.openclaw/openclaw.json`, extracts `agents.list[].id`, skips `orchestrator`, and uses the remainder as the per-agent list set. `--openclaw-config` overrides the path. Falls back to the default `executor` list (with a WARN) if the file is missing or has no agents. The JSON5 parser tolerates `//` line comments, `/* … */` block comments, and trailing commas — the same dialect OpenClaw itself accepts.
- `tests/test_bootstrap_board.py` grows seven cases for `auto_detect_agents` (missing file, JSON5 input, `skip_ids` override, invalid JSON, empty list, case-insensitive dedup, plain JSON).
- `tests/smoke.sh` adds a dry-run entry that exercises `--auto-detect` against a deliberately missing path.

### Changed
- `SKILL.md` Step 0 now describes three explicit paths (`--auto-detect`, `--agents <ask-user-first>`, default `executor`) instead of a hardcoded `jarvis,vision,friday,sia` example. The phrasing makes it clear the installing agent should interview the user before passing `--agents`.
- `docs/quickstart.md` and `references/board-template.md` §0 mirror the three-path guidance. The flag table in board-template adds `--auto-detect` and `--openclaw-config`.
- README, `docs/quickstart.md`, `references/install.md`, `SKILL.md` bump `@v3.1.0` → `@v3.1.1`.
- `package.json` bumped to 3.1.1.

### Notes
- Patch, not minor — `--auto-detect` is an alternative input mode for the existing flag, not a new capability.
- Triggered by Igor flagging that a fresh installer agent might literally copy the previous `--agents jarvis,vision,friday,sia` example instead of asking the user.

## [3.1.0] — 2026-05-28

### Added
- `scripts/bootstrap_board.py` — one-shot Trello bootstrap. Creates the active board, the per-agent lists (`inbox`, `<agent>` × N, `done`, `_templates`), and the archive board via Trello's REST API. Writes every ID into `trello_config.json`, merging with any existing fields. `--with-labels` chains `setup_labels.py` to create the canonical labels in the same run. Flags: `--name`, `--archive-name`, `--agents`, `--workspace-id`, `--config`, `--with-labels`, `--dry`.
- `tests/test_bootstrap_board.py` — pure-helper coverage for `parse_agents`, `build_list_names`, `merge_config`, `build_agents_block`, and `slugify`.
- `tests/smoke.sh` adds a dry-run entry for `bootstrap_board.py`.

### Changed
- `SKILL.md` Quickstart Step 0 swaps the manual prep checklist for a single `bootstrap_board.py` invocation. Manual fallback still documented in `references/board-template.md`.
- `references/board-template.md` opens with a new **§0 Auto-bootstrap (recommended)** section explaining the script + flags table. The hand-driven §1–§6 stay as the manual route.
- `docs/quickstart.md` mirrors the SKILL.md Step 0 change.
- README, `docs/quickstart.md`, `references/install.md` bump `@v3.0.6` → `@v3.1.0`.
- `package.json` bumped to 3.1.0.

### Notes
- Token from <https://trello.com/power-ups/admin> grants `read,write,account` by default — sufficient to `POST /1/boards/` and `POST /1/lists/`. No additional auth flow needed.
- Re-running `bootstrap_board.py` is safe for the config merge but Trello has no native idempotency for board create — a second run yields a second board with the same name. Delete the old board in the UI first if you need to retry.
- This is a minor release because `bootstrap_board.py` is a new capability, not a behavior change to any existing script. Existing setups keep working unchanged.

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
