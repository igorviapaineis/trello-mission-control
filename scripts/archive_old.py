#!/usr/bin/env python3
"""Archive finished cards to the archive board.

Default: scan the whole active board and archive every card that carries the
`done` label and has had no activity for N days. This is the timer that keeps
each agent column compact in the single-owner / label-status model (cards never
leave their column on completion, so a periodic sweep removes the finished ones).

Legacy: `--from <list>` archives a whole named list by age (old behaviour).

Free-tier hygiene: keeps the active board well below the 5000 open cards cap.

Usage:
  python3 archive_old.py [--days 14] [--from <list>] [--dry]
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


def card_is_done(card):
    return any((l.get("name") == "done") for l in card.get("labels") or [])


def main():
    days = 14
    from_list = None
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

    board_id = config["board_id"]
    if dry:
        if from_list:
            print(f"DRY: would scan list '{from_list}' for cards older than {days}d and move them to archive board {archive_board_id}")
        else:
            print(f"DRY: would scan board {board_id} for `done`-labelled cards older than {days}d and move them to archive board {archive_board_id}")
        return

    if from_list:
        # Legacy: archive a whole named list by age.
        list_id = resolve_list(from_list, config)
        cards = api(
            "GET",
            f"/lists/{list_id}/cards",
            {"filter": "open", "fields": "id,name,desc,labels,dateLastActivity"},
            creds,
        )
        select = lambda c: True
    else:
        # Default: archive `done`-labelled cards anywhere on the board.
        cards = api(
            "GET",
            f"/boards/{board_id}/cards",
            {"filter": "open", "fields": "id,name,desc,labels,dateLastActivity"},
            creds,
        )
        select = card_is_done

    cutoff = time.time() - days * 86400
    to_archive = []
    for c in cards:
        if not select(c):
            continue
        dla = c.get("dateLastActivity") or ""
        t = parse_iso(dla)
        if t and time.mktime(t) < cutoff:
            to_archive.append((dla, c))

    label = f"cards from list '{from_list}'" if from_list else "done-labelled cards"
    print(f"ARCHIVE_PLAN:{len(to_archive)} {label} older than {days}d")

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
