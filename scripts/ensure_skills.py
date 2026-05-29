#!/usr/bin/env python3
"""Read required_skills from a card's meta block and install any missing.

Flow per missing skill:
  1. clawhub search <name>           -> first match's slug
  2. clawhub inspect <slug>          -> metadata; extract repository URL
  3. git clone --depth 1 <repo> tmp  -> local folder for inspection
  4. python3 skill_audit.py <folder> -> exit 0 = pass, exit 8 = fail
  5. openclaw skills install <folder> [--global]
  6. Continue to next; final return code reports total state.

The flow uses `clawhub inspect` + `git clone` instead of a (non-existent)
`clawhub download --no-install`. This lets the audit run on the on-disk skill
folder before the OpenClaw runtime ever loads it.

If any audit or step fails, the script:
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
    """Run a subprocess and return (returncode, stdout, stderr)."""
    if dry:
        print(f"DRY: {' '.join(cmd)}")
        return 0, "", ""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
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


def _normalize_result(item):
    """Normalize one clawhub search result into {slug, desc, repo}.

    Resilient to schema drift: accepts a bare string (slug only) or a dict
    with any of the common slug/description/repo key spellings.
    """
    if isinstance(item, str):
        parts = item.strip().split()
        return {"slug": parts[0], "desc": "", "repo": None} if parts else None
    if not isinstance(item, dict):
        return None
    slug = item.get("slug") or item.get("id") or item.get("name")
    if not slug:
        return None
    desc = item.get("description") or item.get("desc") or item.get("summary") or ""
    return {"slug": slug, "desc": desc, "repo": repo_url_from_metadata(item)}


def search_clawhub_all(query, limit, dry):
    """Return up to `limit` normalized search results for `query`.

    Each result is a dict {"slug", "desc", "repo"}. Empty list on no
    matches or a non-zero `clawhub search` exit. `repo` may be None — the
    caller resolves it with `inspect_clawhub` when needed.
    """
    code, out, _ = run(["clawhub", "search", query, "--json"], dry)
    if dry:
        return [{"slug": f"dry-{query}", "desc": "dry-run candidate", "repo": None}]
    if code != 0:
        return []
    try:
        results = json.loads(out)
    except json.JSONDecodeError:
        results = [line.strip() for line in out.splitlines() if line.strip()]
    if not isinstance(results, list):
        return []
    normalized = []
    for item in results:
        norm = _normalize_result(item)
        if norm:
            normalized.append(norm)
        if limit and len(normalized) >= limit:
            break
    return normalized


def search_clawhub(name, dry):
    """Return the first matching slug for `name`, or None."""
    results = search_clawhub_all(name, limit=1, dry=dry)
    return results[0]["slug"] if results else None


def inspect_clawhub(slug, dry):
    """Return metadata dict for a slug, or None.

    The inspect command output includes (at least) the slug, the repository
    URL, the version, and the description. We need the repo URL to clone.
    """
    code, out, _ = run(["clawhub", "inspect", slug, "--json"], dry)
    if dry:
        return {
            "slug": slug,
            "repository": f"https://example.invalid/dry-run/{slug}.git",
        }
    if code != 0:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def repo_url_from_metadata(meta):
    """Find the git repository URL in clawhub inspect output.

    Tries several common keys to be resilient to schema changes.
    """
    if not isinstance(meta, dict):
        return None
    for key in ("repository", "repo", "repoUrl", "source", "git", "homepage"):
        v = meta.get(key)
        if isinstance(v, str) and v.startswith(("http://", "https://", "git@", "git://")):
            return v
        if isinstance(v, dict):
            inner = v.get("url") or v.get("git")
            if isinstance(inner, str) and inner.startswith(("http://", "https://", "git@", "git://")):
                return inner
    return None


def git_clone(repo_url, target_dir, dry):
    """Shallow-clone `repo_url` into `target_dir`. Returns (code, stderr)."""
    code, _, err = run(["git", "clone", "--depth", "1", repo_url, target_dir], dry)
    return code, err


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

    if dry:
        print(f"DRY: would read required_skills from card {card_id}")
        print(f"DRY: would compare against `openclaw skills list`")
        print(f"DRY: for each missing skill: search → inspect → git clone → audit → install")
        return

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

        slug = search_clawhub(name, dry)
        if not slug:
            failed.append((name, "not found on clawhub"))
            continue

        meta_inspect = inspect_clawhub(slug, dry)
        if not meta_inspect:
            failed.append((name, f"inspect failed for slug {slug}"))
            continue

        repo_url = repo_url_from_metadata(meta_inspect)
        if not repo_url:
            failed.append((name, f"no repository URL in inspect metadata for {slug}"))
            continue

        tmpdir = tempfile.mkdtemp(prefix="skill_")
        target = os.path.join(tmpdir, slug)

        code, err = git_clone(repo_url, target, dry)
        if code != 0:
            failed.append((name, f"git clone exit {code}: {err.strip()[:160]}"))
            continue

        code, _, err = run(["python3", audit_script, target], False)
        if code != 0:
            failed.append((name, f"audit failed: {err.strip()[:200]}"))
            continue

        code, _, err = run(["openclaw", "skills", "install", target], False)
        if code != 0:
            failed.append((name, f"install exit {code}: {err.strip()[:160]}"))
            continue

        installed_count += 1
        print(f"SKILL_INSTALLED:{name} (from {repo_url})")

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
