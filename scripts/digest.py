#!/usr/bin/env python3
"""Single-call digest for orchestrator/coordinator agents.

Replaces sequence: board + pipeline-status + overdue + search "" --label urgente.
One GET /boards/{id}/cards returns everything needed.

Usage:
  python3 digest.py [--stale-days N] [--dry]
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trello_task import (
    load_config,
    load_credentials,
    api,
    EXIT_CONFIG,
)


def parse_iso(d):
    try:
        return time.strptime(d[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return None


def main():
    stale_days = 7
    dry = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--stale-days" and i + 1 < len(args):
            stale_days = int(args[i + 1])
            i += 1
        elif a == "--dry":
            dry = True
        i += 1

    config, _ = load_config()
    if not config or "board_id" not in config:
        print("ERROR: config missing or no board_id", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    creds = load_credentials()

    if dry:
        print("DRY: Would fetch board cards and digest")
        return

    board_id = config["board_id"]
    lists = api(
        "GET",
        f"/boards/{board_id}/lists",
        {"fields": "id,name"},
        creds,
    )
    cards = api(
        "GET",
        f"/boards/{board_id}/cards",
        {
            "filter": "visible",
            "fields": "id,name,idList,labels,due,dueComplete,dateLastActivity,members",
        },
        creds,
    )

    list_names = {lst["id"]: lst["name"] for lst in lists}
    pipeline = config.get("pipeline", [])
    lists_cfg = config.get("lists", {})

    counts = {}
    overdue = []
    urgent = []
    stale = []
    claimed = []

    now = time.time()
    stale_cutoff = now - stale_days * 86400

    for c in cards:
        counts[c["idList"]] = counts.get(c["idList"], 0) + 1
        if c.get("due") and not c.get("dueComplete"):
            t = parse_iso(c["due"])
            if t and time.mktime(t) < now:
                overdue.append(c)
        label_names = [(l.get("name") or "") for l in c.get("labels", [])]
        if "urgente" in label_names:
            urgent.append(c)
        dla = c.get("dateLastActivity") or ""
        t = parse_iso(dla)
        if t and time.mktime(t) < stale_cutoff:
            stale.append(c)
        claim_lbl = next((n for n in label_names if n.startswith("claim-")), None)
        if claim_lbl:
            claimed.append((claim_lbl, c))

    print("DIGEST:")
    print(f"  pipeline:")
    for stage in pipeline or sorted(list_names.values()):
        lid = lists_cfg.get(stage) if pipeline else None
        if lid is None:
            for lst_id, name in list_names.items():
                if name == stage:
                    lid = lst_id
                    break
        n = counts.get(lid, 0) if lid else 0
        print(f"    {stage}: {n}")
    print(f"  overdue: {len(overdue)}")
    for c in overdue[:10]:
        print(f"    - {c['name']} [{c['id'][:8]}] due={c.get('due', '')[:10]}")
    print(f"  urgent: {len(urgent)}")
    for c in urgent[:10]:
        print(f"    - {c['name']} [{c['id'][:8]}] list={list_names.get(c['idList'], '?')}")
    print(f"  stale_{stale_days}d: {len(stale)}")
    for c in stale[:10]:
        print(f"    - {c['name']} [{c['id'][:8]}] last={c.get('dateLastActivity', '')[:10]}")
    print(f"  claimed: {len(claimed)}")
    for label, c in claimed[:10]:
        print(f"    - {label} → {c['name']} [{c['id'][:8]}]")


if __name__ == "__main__":
    main()
