#!/usr/bin/env python3
"""Move cards older than N days from a list (default: done) to the archive board.

Free-tier hygiene: keeps the active board well below the 5000 open cards cap.

Usage:
  python3 archive_old.py --days 30 --from done [--dry]
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trello_task import (
    load_config,
    load_credentials,
    api,
    resolve_list,
    EXIT_CONFIG,
    EXIT_GENERIC,
)


def parse_iso(d):
    try:
        return time.strptime(d[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return None


def archive_month_list(archive_board_id, month_key, creds):
    """Find or create a list named archived-YYYY-MM on the archive board."""
    lists = api(
        "GET",
        f"/boards/{archive_board_id}/lists",
        {"fields": "id,name"},
        creds,
    )
    target_name = f"archived-{month_key}"
    for lst in lists:
        if lst["name"] == target_name:
            return lst["id"]
    new_list = api(
        "POST",
        f"/boards/{archive_board_id}/lists",
        {"name": target_name, "pos": "bottom"},
        creds,
    )
    return new_list["id"]


def main():
    days = 30
    from_list = "done"
    dry = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--days" and i + 1 < len(args):
            days = int(args[i + 1])
            i += 1
        elif a == "--from" and i + 1 < len(args):
            from_list = args[i + 1]
            i += 1
        elif a == "--dry":
            dry = True
        i += 1

    config, _ = load_config()
    if not config or "board_id" not in config:
        print("ERROR: config missing or no board_id", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    archive_board_id = config.get("archive_board_id")
    if not archive_board_id:
        print("ERROR: archive_board_id not set in config", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    creds = load_credentials()

    list_id = resolve_list(from_list, config)
    if dry:
        print(f"DRY: would scan list '{from_list}' ({list_id}) for cards older than {days}d and move them to archive board {archive_board_id}")
        return
    cards = api(
        "GET",
        f"/lists/{list_id}/cards",
        {
            "filter": "open",
            "fields": "id,name,desc,labels,dateLastActivity",
        },
        creds,
    )

    cutoff = time.time() - days * 86400
    to_archive = []
    for c in cards:
        dla = c.get("dateLastActivity") or ""
        t = parse_iso(dla)
        if t and time.mktime(t) < cutoff:
            to_archive.append((dla, c))

    print(f"ARCHIVE_PLAN:{len(to_archive)} cards from list '{from_list}' older than {days}d")

    archived = 0
    for dla, c in to_archive:
        month_key = dla[:7] if dla else time.strftime("%Y-%m", time.gmtime())
        target_list_id = archive_month_list(archive_board_id, month_key, creds)
        try:
            api(
                "POST",
                f"/cards/{c['id']}",
                None,
                creds,
            )
        except SystemExit:
            pass
        api(
            "PUT",
            f"/cards/{c['id']}",
            {"idBoard": archive_board_id, "idList": target_list_id, "closed": "true"},
            creds,
        )
        archived += 1
        print(f"  archived: {c['name']} [{c['id'][:8]}] → archive/{month_key}")
    print(f"ARCHIVED:{archived}")


if __name__ == "__main__":
    main()
