#!/usr/bin/env python3
"""Read required_skills from a card's meta block and install any missing.

Flow per missing skill:
  1. clawhub search <name>            -> first match's id
  2. clawhub download <id> --no-install -> local folder
  3. python3 skill_audit.py <folder>  -> exit 0 = pass
  4. openclaw skills install <folder>
  5. Continue to next; final return code reports total state.

If any audit fails, the script:
  - comments on the card with --tag blocked
  - adds label `bloqueado`
  - exits 8

Usage:
  python3 ensure_skills.py <card_id> [--dry]
"""

import sys
import os
import subprocess
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trello_task import (
    load_config,
    load_credentials,
    api,
    parse_meta_block,
    cmd_comment,
    cmd_label,
    EXIT_CONFIG,
    EXIT_SKILL_AUDIT,
)


def run(cmd, dry):
    if dry:
        print(f"DRY: {' '.join(cmd)}")
        return 0, "", ""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        return 127, "", f"{cmd[0]} not on PATH"
    return r.returncode, r.stdout, r.stderr


def list_installed(dry):
    code, out, _ = run(["openclaw", "skills", "list", "--json"], dry)
    if dry or code != 0:
        return set()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        names = set()
        for line in out.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                names.add(line.split()[0])
        return names
    return {s.get("name") for s in data if isinstance(s, dict) and s.get("name")}


def search_clawhub(name, dry):
    code, out, _ = run(["clawhub", "search", name, "--json"], dry)
    if dry:
        return f"dry-{name}"
    if code != 0:
        return None
    try:
        results = json.loads(out)
    except json.JSONDecodeError:
        for line in out.splitlines():
            line = line.strip()
            if line:
                return line.split()[0]
        return None
    if results and isinstance(results, list):
        return results[0].get("id") or results[0].get("name")
    return None


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        print("Usage: ensure_skills.py <card_id> [--dry]", file=sys.stderr)
        sys.exit(1)
    card_id = sys.argv[1]
    dry = "--dry" in sys.argv

    config, _ = load_config()
    if not config or "board_id" not in config:
        print("ERROR: config missing or no board_id", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    creds = load_credentials()

    card = api("GET", f"/cards/{card_id}", {"fields": "desc"}, creds)
    meta, _ = parse_meta_block(card.get("desc") or "")
    required = meta.get("required_skills") or []
    if isinstance(required, str):
        required = [s.strip() for s in required.split(",") if s.strip()]
    if not required:
        print("NO_REQUIRED_SKILLS")
        return

    installed = list_installed(dry)
    agent = os.environ.get("OPENCLAW_AGENT_ID", "agent")

    audit_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skill_audit.py")
    failed = []
    installed_count = 0
    skipped_count = 0

    for name in required:
        if name in installed:
            skipped_count += 1
            print(f"SKILL_PRESENT:{name}")
            continue
        skill_id = search_clawhub(name, dry)
        if not skill_id:
            failed.append((name, "not found on clawhub"))
            continue
        tmpdir = tempfile.mkdtemp(prefix="skill_")
        target = os.path.join(tmpdir, name)
        code, _, err = run(["clawhub", "download", skill_id, "--no-install", "--out", target], dry)
        if code != 0:
            failed.append((name, f"download exit {code}: {err.strip()[:120]}"))
            continue
        if dry:
            print(f"DRY: would audit {target}")
            print(f"DRY: would install {target}")
            installed_count += 1
            continue
        code, _, err = run(["python3", audit_script, target], False)
        if code != 0:
            failed.append((name, f"audit failed: {err.strip()[:200]}"))
            continue
        code, _, err = run(["openclaw", "skills", "install", target], False)
        if code != 0:
            failed.append((name, f"install exit {code}: {err.strip()[:120]}"))
            continue
        installed_count += 1
        print(f"SKILL_INSTALLED:{name}")

    if failed:
        msg_lines = [f"missing skills for card: {len(failed)} failed"]
        for n, reason in failed:
            msg_lines.append(f"- {n}: {reason}")
        msg = "\n".join(msg_lines)
        cmd_comment(card_id, msg, creds, dry, tag="blocked", agent=agent)
        cmd_label(card_id, "bloqueado", config, creds, dry)
        print(f"BLOCKED:{card_id}|failed={len(failed)}", file=sys.stderr)
        sys.exit(EXIT_SKILL_AUDIT)

    print(f"SKILLS_OK:installed={installed_count}|present={skipped_count}")


if __name__ == "__main__":
    main()
