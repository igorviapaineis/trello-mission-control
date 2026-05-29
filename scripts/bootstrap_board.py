#!/usr/bin/env python3
"""Bootstrap a fresh Trello board layout for trello-mission-control.

Creates the active board, the per-agent lists (`inbox`, `<agent>`*N, `done`,
`_templates`), and the archive board. Writes every ID into `trello_config.json`,
preserving any existing fields. Idempotent for the config-write step (it merges,
never clobbers unrelated keys).

Requires Trello API credentials with `write` scope — the standard tokens issued
from https://trello.com/power-ups/admin already grant `read,write,account`.

After bootstrap, run `setup_labels.py` to create the canonical labels (or pass
`--with-labels` to chain it inline).

Usage:
  bootstrap_board.py \\
    [--name "Mission Control"] \\
    [--archive-name "Mission Control — Archive"] \\
    [--agents jarvis,vision,friday,sia] \\
    [--workspace-id <id>] \\
    [--config <path>] \\
    [--with-labels] \\
    [--dry]

Defaults:
  --name           "Mission Control"
  --archive-name   "<name> — Archive"
  --agents         "executor"        (one default executor list)
  --config         trello_config.json in CWD or skill root
"""

import sys
import os
import json
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trello_task import (
    load_credentials,
    api,
    EXIT_OK,
    EXIT_GENERIC,
)


# --- Pure helpers (tested) ---

def parse_agents(spec):
    """Turn 'jarvis,vision,friday,sia' into ['jarvis','vision','friday','sia']."""
    if not spec:
        return ["executor"]
    out = []
    for raw in spec.split(","):
        name = raw.strip().lower()
        if not name:
            continue
        if not re.match(r"^[a-z][a-z0-9-]*$", name):
            raise ValueError(f"invalid agent slug: {raw!r}")
        if name not in out:
            out.append(name)
    return out or ["executor"]


def build_list_names(agents):
    """Return the ordered list-name layout for the active board.

    inbox → <agent>* → _templates

    No `done` list: completion is signalled by the `done` label (single-owner
    default). Pipeline users add stages via their own `pipeline` config.
    """
    return ["inbox"] + list(agents) + ["_templates"]


def merge_config(existing, new_fields):
    """Deep-merge `new_fields` into `existing` without dropping unrelated keys.

    Top-level scalars are overwritten; dicts at top level are merged one level.
    Lists are overwritten (no element merge).
    """
    out = dict(existing or {})
    for key, value in (new_fields or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = {**out[key], **value}
        else:
            out[key] = value
    return out


def build_agents_block(agents, list_ids):
    """For each agent, emit `{role: executor, list_id: <id>}` keyed by slug."""
    return {
        name: {"role": "executor", "list_id": list_ids[name]}
        for name in agents
        if name in list_ids
    }


# --- IO helpers ---

def find_config_path(explicit):
    if explicit:
        return os.path.abspath(explicit)
    candidates = [
        os.environ.get("TRELLO_CONFIG"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "trello_config.json"),
        "./trello_config.json",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    # default destination
    return os.path.abspath("trello_config.json")


def load_existing_config(path):
    if not os.path.isfile(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def write_config(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


# --- API wrappers ---

def create_board(name, workspace_id, creds, dry):
    """POST /1/boards/ — returns dict with `id` and `shortUrl`."""
    params = {
        "name": name,
        "defaultLists": "false",
        "defaultLabels": "false",
    }
    if workspace_id:
        params["idOrganization"] = workspace_id
    if dry:
        print(f"DRY: would create board {name!r}")
        return {"id": f"dry-board-{slugify(name)}", "shortUrl": "https://trello.com/b/dry"}
    return api("POST", "/boards/", params, creds=creds)


def create_list(board_id, name, position, creds, dry):
    params = {"name": name, "idBoard": board_id, "pos": position}
    if dry:
        print(f"DRY: would create list {name!r} on {board_id}")
        return {"id": f"dry-list-{slugify(name)}", "name": name}
    return api("POST", "/lists/", params, creds=creds)


def slugify(text):
    return re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")


def auto_detect_agents(openclaw_config_path=None, skip_ids=("orchestrator",)):
    """Read ~/.openclaw/openclaw.json and return executor agent slugs.

    Strips the orchestrator (which talks to the user, no list of its own) and
    any other ids in `skip_ids`. Returns [] if the file is missing or the agents
    list is empty — caller falls back to its own default.

    Accepts JSON5 (line comments, block comments, trailing commas) the same way
    OpenClaw does. Parser is intentionally permissive: strip C/JS comments
    + trailing commas, then json.loads.
    """
    path = openclaw_config_path or os.path.expanduser("~/.openclaw/openclaw.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path) as f:
            text = f.read()
    except OSError:
        return []
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    # Negative lookbehind: don't strip // inside URLs like https://api.example.com
    text = re.sub(r"(?<!:)//[^\n]*", "", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        cfg = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []
    agents = (cfg.get("agents") or {}).get("list") or []
    out = []
    skip = set(skip_ids)
    for a in agents:
        if not isinstance(a, dict):
            continue
        aid = a.get("id")
        if not isinstance(aid, str):
            continue
        if aid in skip:
            continue
        if aid not in out:
            out.append(aid.lower())
    return out


# --- Main ---

def parse_args(argv):
    flags = {
        "name": "Mission Control",
        "archive_name": None,
        "agents": None,
        "auto_detect": False,
        "workspace_id": None,
        "config": None,
        "openclaw_config": None,
        "with_labels": False,
        "dry": False,
    }
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--name" and i + 1 < len(argv):
            flags["name"] = argv[i + 1]; i += 1
        elif a == "--archive-name" and i + 1 < len(argv):
            flags["archive_name"] = argv[i + 1]; i += 1
        elif a == "--agents" and i + 1 < len(argv):
            flags["agents"] = argv[i + 1]; i += 1
        elif a == "--auto-detect":
            flags["auto_detect"] = True
        elif a == "--openclaw-config" and i + 1 < len(argv):
            flags["openclaw_config"] = argv[i + 1]; i += 1
        elif a == "--workspace-id" and i + 1 < len(argv):
            flags["workspace_id"] = argv[i + 1]; i += 1
        elif a == "--config" and i + 1 < len(argv):
            flags["config"] = argv[i + 1]; i += 1
        elif a == "--with-labels":
            flags["with_labels"] = True
        elif a == "--dry":
            flags["dry"] = True
        elif a in ("-h", "--help"):
            print(__doc__); sys.exit(EXIT_OK)
        else:
            print(f"unknown arg: {a}", file=sys.stderr)
            sys.exit(EXIT_GENERIC)
        i += 1
    if flags["archive_name"] is None:
        flags["archive_name"] = f"{flags['name']} — Archive"
    return flags


def resolve_agent_list(flags):
    """Apply --auto-detect / --agents / default in that order of precedence.

    Returns (agents_list, source_label) for the plan printout.
    """
    if flags["agents"]:
        try:
            return parse_agents(flags["agents"]), f"--agents {flags['agents']}"
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(EXIT_GENERIC)
    if flags["auto_detect"]:
        detected = auto_detect_agents(flags["openclaw_config"])
        if detected:
            return detected, f"auto-detected from {flags['openclaw_config'] or '~/.openclaw/openclaw.json'}"
        print(
            "WARN: --auto-detect found no agents in OpenClaw config; falling back to ['executor']",
            file=sys.stderr,
        )
    return ["executor"], "default"


def main():
    flags = parse_args(sys.argv[1:])

    agents, agents_source = resolve_agent_list(flags)

    list_names = build_list_names(agents)
    config_path = find_config_path(flags["config"])

    print(f"Plan:")
    print(f"  active board:  {flags['name']!r}")
    print(f"  lists:         {', '.join(list_names)}")
    print(f"  archive board: {flags['archive_name']!r}")
    print(f"  agents:        {', '.join(agents)}  ({agents_source})")
    print(f"  config:        {config_path}")
    print(f"  workspace:     {flags['workspace_id'] or '<personal>'}")

    if flags["dry"]:
        print(f"DRY: would POST {len(list_names) + 2} Trello resources and write {config_path}")
        return

    creds = load_credentials()

    print("\nCreating active board ...")
    active = create_board(flags["name"], flags["workspace_id"], creds, flags["dry"])
    board_id = active["id"]
    print(f"  board_id={board_id} url={active.get('shortUrl')}")

    print("\nCreating lists ...")
    list_ids = {}
    for idx, name in enumerate(list_names):
        # `pos=<number>` works; smaller = leftmost
        lst = create_list(board_id, name, str((idx + 1) * 1000), creds, flags["dry"])
        list_ids[name] = lst["id"]
        print(f"  {name:14s} {lst['id']}")

    print("\nCreating archive board ...")
    archive = create_board(flags["archive_name"], flags["workspace_id"], creds, flags["dry"])
    archive_id = archive["id"]
    print(f"  archive_board_id={archive_id} url={archive.get('shortUrl')}")

    new_fields = {
        "board_id": board_id,
        "archive_board_id": archive_id,
        "templates_list_id": list_ids.get("_templates", ""),
        "lists": list_ids,
        "agents": build_agents_block(agents, list_ids),
    }
    existing = load_existing_config(config_path)
    merged = merge_config(existing, new_fields)
    write_config(config_path, merged)
    print(f"\nWrote {config_path}")

    print(f"\nBOARD_READY:active={active.get('shortUrl')}|archive={archive.get('shortUrl')}")

    if flags["with_labels"]:
        print("\nRunning setup_labels.py ...")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.environ["TRELLO_CONFIG"] = config_path
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(script_dir, "setup_labels.py")])
        if r.returncode != 0:
            print(f"WARN: setup_labels.py exit {r.returncode}", file=sys.stderr)
            sys.exit(r.returncode)


if __name__ == "__main__":
    main()
