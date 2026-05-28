#!/usr/bin/env python3
"""End-to-end setup verification for Trello Mission Control.

Runs 10 numbered checks and reports OK / FAIL / WARN per check. Exits 0
on full pass; exit code 9 (DOCTOR_FAIL) if any check returns FAIL. WARN
items do not change the exit code.

Usage:
  python3 doctor.py [--verbose] [--dry]
"""

import sys
import os
import re
import shutil
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trello_task import (
    load_config,
    api,
    EXIT_DOCTOR_FAIL,
)
from setup_labels import CANONICAL_LABELS


PASS = "OK"
FAIL = "FAIL"
WARN = "WARN"

DEFAULT_WORKSPACES = ["orchestrator", "executor"]
DEFAULT_OPENCLAW_CONFIG = os.path.expanduser("~/.openclaw/openclaw.json")


class Report:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.results = []

    def add(self, n, name, status, message="", detail=""):
        self.results.append((n, name, status, message, detail))
        line = f"CHECK {n:2d}:{name:<22} {status:4s} {message}"
        print(line)
        if self.verbose and detail:
            for d_line in detail.splitlines():
                print(f"    {d_line}")

    @property
    def failed(self):
        return any(r[2] == FAIL for r in self.results)


# --- Pure helpers (covered by tests) ---

def parse_openclaw_json(text):
    """Parse a JSON5-flavoured OpenClaw config file content.

    OpenClaw configs accept // comments and trailing commas in addition to
    plain JSON. This helper strips comments and trailing commas, then falls
    back to json.loads. Returns the parsed dict, or None if parsing fails.
    """
    import json
    if not text:
        return None
    # Remove // line comments
    stripped = re.sub(r"//[^\n]*", "", text)
    # Remove /* */ block comments
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)
    # Remove trailing commas before } or ]
    stripped = re.sub(r",(\s*[}\]])", r"\1", stripped)
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return None


def find_agent_in_config(cfg, agent_id):
    """Find the agents.list[] entry whose `id` is `agent_id`. Returns the entry or None."""
    if not isinstance(cfg, dict):
        return None
    agents = cfg.get("agents") or {}
    for entry in agents.get("list") or []:
        if isinstance(entry, dict) and entry.get("id") == agent_id:
            return entry
    return None


def missing_labels(existing_names, canonical_names):
    """Return canonical labels not present in existing_names (case-insensitive)."""
    existing_lower = {n.lower() for n in existing_names if isinstance(n, str)}
    return [c for c in canonical_names if c.lower() not in existing_lower]


def has_heartbeat(agent_entry, defaults):
    """True if agent has a non-zero heartbeat.every (own entry or inherited from defaults)."""
    candidates = []
    if isinstance(agent_entry, dict):
        candidates.append(agent_entry.get("heartbeat"))
    if isinstance(defaults, dict):
        candidates.append(defaults.get("heartbeat"))
    for h in candidates:
        if isinstance(h, dict):
            every = h.get("every")
            if isinstance(every, str) and every and every.strip() not in ("0m", "0s", "0", ""):
                return True
    return False


# --- Checks ---

def check_python_version(report):
    v = sys.version_info
    if v >= (3, 10):
        report.add(1, "python_version", PASS, f"{v.major}.{v.minor}.{v.micro}")
    else:
        report.add(1, "python_version", FAIL, f"need >=3.10, found {v.major}.{v.minor}")


def check_bin(report, n, name, label):
    path = shutil.which(name)
    if path:
        version = ""
        try:
            r = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=5)
            version = (r.stdout or r.stderr or "").splitlines()[0][:60]
        except (subprocess.TimeoutExpired, OSError):
            pass
        report.add(n, label, PASS, path, detail=version)
    else:
        report.add(n, label, FAIL, f"`{name}` not on PATH")


def check_env(report):
    key = os.environ.get("TRELLO_API_KEY") or ""
    token = os.environ.get("TRELLO_TOKEN") or ""
    missing = [v for v, val in (("TRELLO_API_KEY", key), ("TRELLO_TOKEN", token)) if not val]
    if missing:
        report.add(4, "env_credentials", FAIL, f"missing: {','.join(missing)}")
    else:
        report.add(4, "env_credentials", PASS, f"key={len(key)}ch token={len(token)}ch")


def check_config(report):
    cfg, path = load_config()
    if not cfg:
        report.add(5, "config_present", FAIL, "trello_config.json not found", detail="Run: python3 trello_task.py init")
        return None
    missing = [k for k in ("board_id", "archive_board_id", "lists") if not cfg.get(k)]
    if missing:
        report.add(5, "config_present", FAIL, f"missing keys: {','.join(missing)}", detail=f"in {path}")
        return cfg
    report.add(5, "config_present", PASS, path)
    return cfg


def check_trello_auth(report):
    try:
        me = api("GET", "/members/me", {"fields": "id,username,fullName"}, None)
    except SystemExit:
        report.add(6, "trello_auth", FAIL, "API rejected credentials")
        return False
    if isinstance(me, dict) and me.get("id"):
        report.add(6, "trello_auth", PASS, f"@{me.get('username', '?')}")
        return True
    report.add(6, "trello_auth", FAIL, "unexpected response from /members/me")
    return False


def check_board_reachable(report, cfg):
    board_id = cfg.get("board_id") if cfg else None
    if not board_id:
        report.add(7, "board_reachable", FAIL, "board_id missing in config")
        return None
    try:
        board = api("GET", f"/boards/{board_id}", {"fields": "id,name,closed"}, None)
    except SystemExit:
        report.add(7, "board_reachable", FAIL, f"could not GET board {board_id}")
        return None
    if isinstance(board, dict) and board.get("id"):
        report.add(7, "board_reachable", PASS, f"{board.get('name', '?')}")
        return board
    report.add(7, "board_reachable", FAIL, "board not found")
    return None


def check_canonical_labels(report, cfg):
    board_id = cfg.get("board_id") if cfg else None
    if not board_id:
        report.add(8, "canonical_labels", FAIL, "no board_id")
        return
    try:
        labels = api(
            "GET",
            f"/boards/{board_id}/labels",
            {"fields": "id,name", "limit": "1000"},
            None,
        )
    except SystemExit:
        report.add(8, "canonical_labels", FAIL, "could not GET labels")
        return
    names = [l.get("name") for l in (labels or []) if isinstance(l, dict)]
    canonical_names = [name for name, _ in CANONICAL_LABELS]
    agents_in_cfg = list((cfg.get("agents") or {}).keys())
    canonical_names += [f"claim-{a}" for a in agents_in_cfg]
    missing = missing_labels(names, canonical_names)
    if not missing:
        report.add(8, "canonical_labels", PASS, f"{len(canonical_names)} labels present")
    else:
        report.add(
            8,
            "canonical_labels",
            WARN,
            f"missing: {','.join(missing[:5])}",
            detail="Run: python3 scripts/setup_labels.py",
        )


def check_workspaces(report):
    home = os.path.expanduser("~/.openclaw")
    missing = []
    placeholders = []
    for agent in DEFAULT_WORKSPACES:
        workspace = os.path.join(home, f"workspace-{agent}")
        agents_md = os.path.join(workspace, "AGENTS.md")
        agents_template = agents_md + ".template"
        if os.path.isfile(agents_md):
            continue
        if os.path.isfile(agents_template):
            placeholders.append(agent)
        else:
            missing.append(agent)
    if missing:
        report.add(
            9,
            "workspace_dirs",
            FAIL,
            f"missing: {','.join(missing)}",
            detail="See Quickstart step 6 in SKILL.md.",
        )
        return
    if placeholders:
        report.add(
            9,
            "workspace_dirs",
            WARN,
            f"templates not renamed: {','.join(placeholders)}",
            detail="Drop .template suffix and fill placeholders.",
        )
        return
    report.add(9, "workspace_dirs", PASS, f"{len(DEFAULT_WORKSPACES)} workspaces ready")


def check_heartbeat_config(report):
    if not os.path.isfile(DEFAULT_OPENCLAW_CONFIG):
        report.add(
            10,
            "heartbeat_config",
            FAIL,
            "~/.openclaw/openclaw.json not found",
            detail="Merge references/snippets/openclaw-config.snippet.json5 first.",
        )
        return
    with open(DEFAULT_OPENCLAW_CONFIG) as f:
        text = f.read()
    cfg = parse_openclaw_json(text)
    if cfg is None:
        report.add(10, "heartbeat_config", FAIL, "openclaw.json could not be parsed")
        return
    defaults = (cfg.get("agents") or {}).get("defaults") or {}
    issues = []
    for agent_id in DEFAULT_WORKSPACES:
        entry = find_agent_in_config(cfg, agent_id)
        if not entry:
            issues.append(f"{agent_id}: no agents.list entry")
            continue
        skills = entry.get("skills") or defaults.get("skills") or []
        if "trello-mission-control" not in skills:
            issues.append(f"{agent_id}: skill not in allowlist")
        if not has_heartbeat(entry, defaults):
            issues.append(f"{agent_id}: no heartbeat.every")
    if issues:
        report.add(
            10,
            "heartbeat_config",
            FAIL,
            f"{len(issues)} issue(s)",
            detail="\n".join(issues),
        )
        return
    report.add(10, "heartbeat_config", PASS, f"{len(DEFAULT_WORKSPACES)} agents configured")


# --- Main ---

def main():
    verbose = "--verbose" in sys.argv
    dry = "--dry" in sys.argv

    if dry:
        print("DRY: would run 10 checks (python_version, openclaw, git, env_credentials, config_present, trello_auth, board_reachable, canonical_labels, workspace_dirs, heartbeat_config)")
        return

    report = Report(verbose=verbose)

    check_python_version(report)
    check_bin(report, 2, "openclaw", "openclaw_cli")
    check_bin(report, 3, "git", "git_cli")
    check_env(report)

    cfg = check_config(report)
    if cfg is None:
        # no point in trying API calls without config
        report.add(6, "trello_auth", FAIL, "skipped: no config")
        report.add(7, "board_reachable", FAIL, "skipped: no config")
        report.add(8, "canonical_labels", FAIL, "skipped: no config")
        check_workspaces(report)
        check_heartbeat_config(report)
        sys.exit(EXIT_DOCTOR_FAIL)

    # API-backed checks
    if check_trello_auth(report):
        check_board_reachable(report, cfg)
        check_canonical_labels(report, cfg)
    else:
        report.add(7, "board_reachable", FAIL, "skipped: auth failed")
        report.add(8, "canonical_labels", FAIL, "skipped: auth failed")

    check_workspaces(report)
    check_heartbeat_config(report)

    print("")
    n_pass = sum(1 for r in report.results if r[2] == PASS)
    n_warn = sum(1 for r in report.results if r[2] == WARN)
    n_fail = sum(1 for r in report.results if r[2] == FAIL)
    print(f"doctor: {n_pass} OK / {n_warn} WARN / {n_fail} FAIL")
    if report.failed:
        sys.exit(EXIT_DOCTOR_FAIL)


if __name__ == "__main__":
    main()
