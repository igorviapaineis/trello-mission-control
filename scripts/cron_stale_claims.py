#!/usr/bin/env python3
"""Release claim-* labels whose card has no activity for N minutes.

Safety net for the lifecycle work that the inline HEARTBEAT release does
during normal operation. If an executor session crashes between the last
claim and the next heartbeat, the claim would otherwise stay on the card
forever. This cron sweep clears it.

Default threshold: 30 minutes. The threshold is configurable via
--minutes; the default is conservative enough that it does not fight a
healthy heartbeat (30 min default tick) but small enough that recovery is
fast.

Usage:
  python3 cron_stale_claims.py [--minutes N] [--dry]
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trello_task import (
    load_config,
    load_credentials,
    api,
    api_delete,
    cmd_comment,
    EXIT_CONFIG,
)


def parse_iso(d):
    try:
        return time.strptime(d[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return None


def find_stale_claims(cards, cutoff_epoch):
    """Return [(card, claim_label_dict)] pairs whose dateLastActivity is older than cutoff.

    A card with multiple claim-* labels (which should not happen, but be safe) yields
    one tuple per claim label found.
    """
    stale = []
    for c in cards:
        dla = c.get("dateLastActivity") or ""
        t = parse_iso(dla)
        if not t:
            continue
        if time.mktime(t) >= cutoff_epoch:
            continue
        for lbl in c.get("labels", []) or []:
            name = (lbl.get("name") or "")
            if name.startswith("claim-"):
                stale.append((c, lbl))
    return stale


def main():
    minutes = 30
    dry = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--minutes" and i + 1 < len(args):
            minutes = int(args[i + 1]); i += 1
        elif a == "--dry":
            dry = True
        i += 1

    config, _ = load_config()
    if not config or "board_id" not in config:
        print("ERROR: config missing or no board_id", file=sys.stderr)
        sys.exit(EXIT_CONFIG)

    if dry:
        print(f"DRY: would scan board for claim-* labels with dateLastActivity older than {minutes}m")
        return

    creds = load_credentials()
    board_id = config["board_id"]
    cards = api(
        "GET",
        f"/boards/{board_id}/cards",
        {
            "filter": "visible",
            "fields": "id,name,labels,dateLastActivity",
        },
        creds,
    )

    cutoff = time.time() - minutes * 60
    stale = find_stale_claims(cards, cutoff)

    if not stale:
        print(f"STALE_CLAIMS:0 (threshold={minutes}m)")
        return

    cleaned = 0
    for c, lbl in stale:
        label_id = lbl.get("id")
        label_name = lbl.get("name") or "?"
        if not label_id:
            continue
        try:
            api_delete(f"/cards/{c['id']}/idLabels/{label_id}", creds)
        except SystemExit:
            print(f"  FAILED to unlabel {c['id']} (label {label_name})", file=sys.stderr)
            continue
        agent_id = label_name[len("claim-"):] if label_name.startswith("claim-") else label_name
        cmd_comment(
            c["id"],
            f"auto-released: stale claim by @{agent_id} (no activity {minutes}m+)",
            creds,
            False,
            tag="note",
            agent="cron",
        )
        cleaned += 1
        print(f"  released: {label_name} on {c['name']} [{c['id'][:8]}]")

    print(f"STALE_CLAIMS:cleaned={cleaned}|scanned={len(cards)}|threshold={minutes}m")


if __name__ == "__main__":
    main()
