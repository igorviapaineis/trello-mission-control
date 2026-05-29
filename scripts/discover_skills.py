#!/usr/bin/env python3
"""Discover the best ClawHub skill(s) for a task (orchestrator-side).

The orchestrator runs this BEFORE writing `required_skills` on a card. It
searches ClawHub for the task's keywords, inspects the top candidates for a
description and repo URL, flags which are already installed locally, and prints
a ranked candidate list. The orchestrator reads the list, picks the best 1-3,
and writes them into the card's `required_skills` meta + a `## Skills` section.

This is the *selection* half of the skill pipeline; `ensure_skills.py` is the
*install* half the executor runs once the card declares its skills.

Usage:
  python3 discover_skills.py "<task summary / keywords>" [--limit 5] [--json] [--dry]

Output (default — human + parseable):
  DISCOVER: query="..." candidates=N installed=M
  CANDIDATE:1|slug=<slug>|installed=yes|repo=<url>|desc=<one line>
  ...
No matches: NO_CANDIDATES (exit 0). `--json` emits a JSON array instead.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ensure_skills import (  # noqa: E402  (path set above)
    list_installed,
    search_clawhub_all,
    inspect_clawhub,
    repo_url_from_metadata,
)

DEFAULT_LIMIT = 5
DESC_WIDTH = 100


def parse_args(argv):
    flags = {"query": None, "limit": DEFAULT_LIMIT, "json": False, "dry": False}
    pos = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dry":
            flags["dry"] = True
        elif a == "--json":
            flags["json"] = True
        elif a == "--limit" and i + 1 < len(argv):
            try:
                flags["limit"] = max(1, int(argv[i + 1]))
            except ValueError:
                pass
            i += 1
        else:
            pos.append(a)
        i += 1
    if pos:
        flags["query"] = " ".join(pos)
    return flags


def one_line(text, width=DESC_WIDTH):
    """Collapse whitespace and truncate to a single readable line."""
    line = " ".join((text or "").split())
    if len(line) > width:
        return line[: width - 1] + "…"
    return line


def discover(query, limit, dry):
    """Return a ranked list of candidate dicts for `query`.

    Each candidate: {rank, slug, installed, repo, desc}. ClawHub's own search
    order is preserved as the ranking (most relevant first). When a search hit
    lacks a repo URL or description, `inspect_clawhub` fills the gap.
    """
    installed = list_installed(dry)
    results = search_clawhub_all(query, limit, dry)
    candidates = []
    for rank, res in enumerate(results, start=1):
        slug = res["slug"]
        repo = res.get("repo")
        desc = res.get("desc") or ""
        if not repo or not desc:
            meta = inspect_clawhub(slug, dry)
            if meta:
                repo = repo or repo_url_from_metadata(meta)
                if not desc:
                    desc = (
                        meta.get("description")
                        or meta.get("desc")
                        or meta.get("summary")
                        or ""
                    )
        candidates.append(
            {
                "rank": rank,
                "slug": slug,
                "installed": slug in installed,
                "repo": repo,
                "desc": one_line(desc),
            }
        )
    return candidates


def main():
    flags = parse_args(sys.argv[1:])
    if not flags["query"]:
        print(
            'Usage: discover_skills.py "<task summary / keywords>" '
            "[--limit 5] [--json] [--dry]",
            file=sys.stderr,
        )
        sys.exit(1)

    candidates = discover(flags["query"], flags["limit"], flags["dry"])

    if flags["json"]:
        print(json.dumps(candidates, indent=2))
        return

    if not candidates:
        print("NO_CANDIDATES")
        return

    installed_count = sum(1 for c in candidates if c["installed"])
    print(
        f'DISCOVER: query="{flags["query"]}" '
        f"candidates={len(candidates)} installed={installed_count}"
    )
    for c in candidates:
        print(
            f"CANDIDATE:{c['rank']}|slug={c['slug']}|"
            f"installed={'yes' if c['installed'] else 'no'}|"
            f"repo={c['repo'] or '-'}|desc={c['desc'] or '-'}"
        )


if __name__ == "__main__":
    main()
