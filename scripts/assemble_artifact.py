#!/usr/bin/env python3
"""Join an executor's per-subtask part files into one complete artifact, attach it.

The executor decomposes a card into ordered subtasks and writes each subtask's
output to a part file under a working dir, named `NN-<slug>.<ext>` (the numeric
prefix sets the order). When every subtask is done, this script concatenates the
parts — in filename order — into a single complete file and attaches it to the
card. This is the "junte tudo e anexa o arquivo completo" step.

Only text parts are concatenated. For binary or multi-file deliverables, attach
directly with `trello_task.py attach` or `attach_dir.py` instead.

Usage:
  python3 assemble_artifact.py <card_id> --parts-dir <dir> \\
    [--output <file>] [--separator "<str>"] [--header-from-filename] \\
    [--no-attach] [--dry]

Exit codes: 0 OK; 1 no parts found / usage / missing config.
"""

import sys
import os
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trello_task import (  # noqa: E402  (path set above)
    load_config,
    load_credentials,
    cmd_attach,
    EXIT_CONFIG,
    EXIT_GENERIC,
)

DEFAULT_SEPARATOR = "\n\n"
COMPLETE_PREFIX = "_complete"


def parse_args(argv):
    flags = {
        "card_id": None,
        "parts_dir": None,
        "output": None,
        "separator": DEFAULT_SEPARATOR,
        "header_from_filename": False,
        "attach": True,
        "dry": False,
    }
    pos = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dry":
            flags["dry"] = True
        elif a == "--no-attach":
            flags["attach"] = False
        elif a == "--header-from-filename":
            flags["header_from_filename"] = True
        elif a == "--parts-dir" and i + 1 < len(argv):
            flags["parts_dir"] = argv[i + 1]; i += 1
        elif a == "--output" and i + 1 < len(argv):
            flags["output"] = argv[i + 1]; i += 1
        elif a == "--separator" and i + 1 < len(argv):
            flags["separator"] = argv[i + 1]; i += 1
        else:
            pos.append(a)
        i += 1
    if pos:
        flags["card_id"] = pos[0]
    return flags


def collect_parts(parts_dir):
    """Return part file paths in deterministic filename order.

    The assembled output (`_complete.*`) and dotfiles are skipped so a re-run is
    idempotent and never folds the previous result back into itself.
    """
    entries = []
    for path in glob.glob(os.path.join(parts_dir, "*")):
        if not os.path.isfile(path):
            continue
        name = os.path.basename(path)
        if name.startswith(".") or name.startswith(COMPLETE_PREFIX):
            continue
        entries.append(path)
    return sorted(entries, key=lambda p: os.path.basename(p))


def derive_output(parts_dir, parts, explicit):
    """Pick the output path: the explicit one, else `_complete.<ext>` in the dir.

    The extension is inherited when every part shares one, otherwise `.txt`.
    """
    if explicit:
        return explicit
    exts = {os.path.splitext(p)[1] for p in parts}
    ext = exts.pop() if len(exts) == 1 else ".txt"
    return os.path.join(parts_dir, f"{COMPLETE_PREFIX}{ext}")


def assemble(parts, separator, header_from_filename):
    """Concatenate part file contents in the given order into one string."""
    chunks = []
    for path in parts:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            body = f.read()
        if header_from_filename:
            chunks.append(f"<!-- {os.path.basename(path)} -->\n{body}")
        else:
            chunks.append(body)
    return separator.join(chunks)


def main():
    flags = parse_args(sys.argv[1:])
    if not flags["card_id"] or not flags["parts_dir"]:
        print(
            "Usage: assemble_artifact.py <card_id> --parts-dir <dir> [--output <file>] "
            "[--separator <str>] [--header-from-filename] [--no-attach] [--dry]",
            file=sys.stderr,
        )
        sys.exit(EXIT_GENERIC)

    parts_dir = flags["parts_dir"]
    if not os.path.isdir(parts_dir):
        print(f"ERROR: parts dir not found: {parts_dir}", file=sys.stderr)
        sys.exit(EXIT_GENERIC)

    parts = collect_parts(parts_dir)
    if not parts:
        print(f"NO_PARTS:{parts_dir}", file=sys.stderr)
        sys.exit(EXIT_GENERIC)

    output = derive_output(parts_dir, parts, flags["output"])

    if flags["dry"]:
        print(f"DRY: would assemble {len(parts)} part(s) in order:")
        for p in parts:
            print(f"DRY:   {os.path.basename(p)}")
        print(f"DRY: would write {output}")
        if flags["attach"]:
            print(f"DRY: would attach {output} to {flags['card_id']}")
        return

    content = assemble(parts, flags["separator"], flags["header_from_filename"])
    with open(output, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"ASSEMBLED:{output}|parts={len(parts)}")

    if flags["attach"]:
        config, _ = load_config()
        if not config:
            print("ERROR: config missing", file=sys.stderr)
            sys.exit(EXIT_CONFIG)
        creds = load_credentials()
        cmd_attach(flags["card_id"], output, creds, dry=False)


if __name__ == "__main__":
    main()
