#!/usr/bin/env python3
"""Ensure the canonical v3 labels exist on the configured board.

Idempotent: only creates labels that are missing. Reads config.agents to derive
claim-<agent> labels (one per agent). Updates config.labels in-place.

Usage:
  python3 setup_labels.py [--dry]
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trello_task import (
    load_config,
    load_credentials,
    api,
    EXIT_CONFIG,
)


CANONICAL_LABELS = [
    ("urgente", "red"),
    ("bloqueado", "orange"),
    ("revisao", "yellow"),
    ("pediu", "purple"),
    ("stale", "lime"),
    ("qa-failed", "pink"),
]


def main():
    dry = "--dry" in sys.argv

    config, config_path = load_config()
    if not config or "board_id" not in config:
        print("ERROR: config missing or no board_id", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    creds = load_credentials()
    board_id = config["board_id"]

    desired = list(CANONICAL_LABELS)
    for agent_id in (config.get("agents") or {}).keys():
        desired.append((f"claim-{agent_id}", "sky"))

    if dry:
        print(f"DRY: would ensure {len(desired)} labels exist on board {board_id}:")
        for name, color in desired:
            print(f"  DRY: {name} ({color})")
        return

    existing = api(
        "GET",
        f"/boards/{board_id}/labels",
        {"fields": "id,name,color", "limit": "1000"},
        creds,
    )
    existing_by_name = {lbl["name"]: lbl for lbl in existing}

    cfg_labels = config.get("labels", {})
    created = 0
    updated_config = False

    for name, color in desired:
        if name in existing_by_name:
            lbl = existing_by_name[name]
            if cfg_labels.get(name) != lbl["id"]:
                cfg_labels[name] = lbl["id"]
                updated_config = True
            continue
        if dry:
            print(f"DRY: would create label {name} ({color})")
            continue
        new_lbl = api(
            "POST",
            f"/boards/{board_id}/labels",
            {"name": name, "color": color},
            creds,
        )
        cfg_labels[new_lbl["name"]] = new_lbl["id"]
        updated_config = True
        created += 1
        print(f"CREATED:{name}|{new_lbl['id']}")

    config["labels"] = cfg_labels

    if updated_config and config_path and not dry:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"CONFIG_UPDATED:{config_path}")

    print(f"LABELS_OK:total_desired={len(desired)}|created={created}")


if __name__ == "__main__":
    main()
