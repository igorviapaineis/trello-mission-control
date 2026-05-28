#!/usr/bin/env python3
"""Wake an OpenClaw agent immediately (used after creating an urgent card).

Wraps `openclaw heartbeat wake <agent> --now` so the executor reacts in seconds
instead of waiting the 30-minute heartbeat default.

Usage:
  python3 wake_on_urgent.py <agent_id>
"""

import sys
import subprocess


def main():
    if len(sys.argv) < 2:
        print("Usage: wake_on_urgent.py <agent_id>", file=sys.stderr)
        sys.exit(1)
    agent = sys.argv[1]
    try:
        result = subprocess.run(
            ["openclaw", "heartbeat", "wake", agent, "--now"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        print("ERROR: openclaw CLI not on PATH", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"ERROR: openclaw heartbeat wake {agent} timed out", file=sys.stderr)
        sys.exit(1)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        sys.exit(result.returncode)
    print(f"WAKE_REQUESTED:{agent}")
    if result.stdout:
        sys.stdout.write(result.stdout)


if __name__ == "__main__":
    main()
