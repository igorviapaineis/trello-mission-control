#!/usr/bin/env python3
"""Package a directory into a single .tar.gz and attach it to a Trello card.

Useful for attaching log directories or artifact bundles without uploading many
small files. Respects Trello Free's 10 MB per-attachment cap — fails clearly if
the archive exceeds it after gzip.

Usage:
  python3 attach_dir.py <card_id> <dir_path> [archive_name] [--dry]
"""

import sys
import os
import tarfile
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trello_task import (
    load_credentials,
    cmd_attach,
    EXIT_GENERIC,
)


def main():
    args = [a for a in sys.argv[1:] if a != "--dry"]
    dry = "--dry" in sys.argv
    if len(args) < 2:
        print("Usage: attach_dir.py <card_id> <dir_path> [archive_name] [--dry]", file=sys.stderr)
        sys.exit(1)
    card_id = args[0]
    dir_path = args[1]
    archive_name = args[2] if len(args) > 2 else os.path.basename(dir_path.rstrip("/")) + ".tar.gz"

    if not os.path.isdir(dir_path):
        print(f"ERROR: not a directory: {dir_path}", file=sys.stderr)
        sys.exit(EXIT_GENERIC)

    tmpdir = tempfile.mkdtemp(prefix="attach_")
    out_path = os.path.join(tmpdir, archive_name)

    with tarfile.open(out_path, "w:gz") as tar:
        tar.add(dir_path, arcname=os.path.basename(dir_path.rstrip("/")))

    size = os.path.getsize(out_path)
    if size > 10 * 1024 * 1024:
        print(f"ERROR: archive {size} bytes > 10MB Trello free cap", file=sys.stderr)
        sys.exit(EXIT_GENERIC)

    creds = load_credentials()
    cmd_attach(card_id, out_path, creds, dry)
    print(f"ARCHIVED_DIR:{dir_path}|size={size}")


if __name__ == "__main__":
    main()
