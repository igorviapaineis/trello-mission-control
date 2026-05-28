#!/usr/bin/env python3
"""Release all cards claimed by a given agent.

Called by the plugin onSessionStop hook so cards left in-progress when an agent
session ends are returned to the queue for the next heartbeat.

Usage:
  python3 release_my_claims.py <agent_id> [--dry]
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trello_task import (
    load_config,
    load_credentials,
    cmd_release_all,
    EXIT_CONFIG,
)


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        print("Usage: release_my_claims.py <agent_id> [--dry]", file=sys.stderr)
        sys.exit(1)
    agent = sys.argv[1]
    dry = "--dry" in sys.argv

    config, _ = load_config()
    if not config or "board_id" not in config:
        print("ERROR: config missing or no board_id", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    creds = load_credentials()

    cmd_release_all(agent, config, creds, dry)


if __name__ == "__main__":
    main()
