#!/usr/bin/env python3
"""Update a Trello card with a structured completion summary.

Implements the v3 "card hygiene" protocol: writes a structured description
(Goal / Result / Changes / Metrics / Notes), updates the Result checklist
(creating it if needed), attaches artifact files, and posts a brief done
comment with the canonical provenance tag.

All long content lives in the description and attachments. Comments stay brief.

Usage:
  python3 update_card_complete.py <card_id> \\
    --result "what was done" \\
    [--changes "file:line — text" --changes "file:line — text" ...] \\
    [--metric "Time: 25min" --metric "Tests: 12/12" ...] \\
    [--notes "gotchas..."] \\
    [--checklist-name "Result"] \\
    [--check-step "Build" --check-step "Test" ...] \\
    [--attach /path/to/file ...] \\
    [--comment "1-liner"] \\
    [--agent <id>] \\
    [--dry]

Backwards compatibility: the legacy flag `--resultado` is also accepted.
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trello_task import (
    load_config,
    load_credentials,
    api,
    parse_meta_block,
    serialize_meta_block,
    cmd_attach,
    cmd_comment,
    EXIT_CONFIG,
)


EN_SECTIONS = ["Goal", "Result", "Changes", "Metrics", "Notes"]

# Map legacy Portuguese section names (older cards from before v3.0.1) to the
# canonical English ones. parse_existing accepts both; render emits English only.
PT_TO_EN = {
    "Objetivo": "Goal",
    "Resultado": "Result",
    "Mudanças": "Changes",
    "Métricas": "Metrics",
    "Notas": "Notes",
}

SECTION_RE = re.compile(
    r"^##\s+(Goal|Result|Changes|Metrics|Notes|Objetivo|Resultado|Mudanças|Métricas|Notas)\s*$",
    re.MULTILINE,
)


def parse_existing(desc):
    """Split desc into ordered sections. Preserves text above the first heading as Goal.

    Accepts both English section headers (Goal/Result/Changes/Metrics/Notes)
    and the legacy Portuguese headers (Objetivo/Resultado/Mudanças/Métricas/Notas)
    so cards written before v3.0.1 keep parsing.
    """
    sections = {name: "" for name in EN_SECTIONS}
    if not desc:
        return sections
    matches = list(SECTION_RE.finditer(desc))
    if not matches:
        sections["Goal"] = desc.strip()
        return sections
    if matches[0].start() > 0:
        sections["Goal"] = desc[: matches[0].start()].strip()
    for i, m in enumerate(matches):
        raw = m.group(1)
        name = PT_TO_EN.get(raw, raw)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(desc)
        sections[name] = desc[m.end() : end].strip()
    return sections


def render(sections, meta):
    parts = []
    for name in EN_SECTIONS:
        body = sections.get(name, "").strip()
        if body:
            parts.append(f"## {name}\n{body}")
    out = "\n\n".join(parts)
    if meta:
        out = out.rstrip() + serialize_meta_block(meta)
    return out


def parse_args(argv):
    flags = {
        "result": None,
        "changes": [],
        "metrics": [],
        "notes": None,
        "checklist_name": "Result",
        "check_steps": [],
        "attachments": [],
        "comment": None,
        "agent": os.environ.get("OPENCLAW_AGENT_ID", "agent"),
        "dry": False,
    }
    pos = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dry":
            flags["dry"] = True
        elif a in ("--result", "--resultado") and i + 1 < len(argv):
            flags["result"] = argv[i + 1]; i += 1
        elif a == "--changes" and i + 1 < len(argv):
            flags["changes"].append(argv[i + 1]); i += 1
        elif a == "--metric" and i + 1 < len(argv):
            flags["metrics"].append(argv[i + 1]); i += 1
        elif a == "--notes" and i + 1 < len(argv):
            flags["notes"] = argv[i + 1]; i += 1
        elif a == "--checklist-name" and i + 1 < len(argv):
            flags["checklist_name"] = argv[i + 1]; i += 1
        elif a == "--check-step" and i + 1 < len(argv):
            flags["check_steps"].append(argv[i + 1]); i += 1
        elif a == "--attach" and i + 1 < len(argv):
            flags["attachments"].append(argv[i + 1]); i += 1
        elif a == "--comment" and i + 1 < len(argv):
            flags["comment"] = argv[i + 1]; i += 1
        elif a == "--agent" and i + 1 < len(argv):
            flags["agent"] = argv[i + 1]; i += 1
        else:
            pos.append(a)
        i += 1
    return pos, flags


def ensure_checklist(card_id, want_name, creds, dry):
    card = api(
        "GET",
        f"/cards/{card_id}",
        {"fields": "idChecklists"},
        creds,
    )
    for cl_id in card.get("idChecklists", []):
        cl = api(
            "GET",
            f"/checklists/{cl_id}",
            {"fields": "id,name", "checkItems": "all", "checkItem_fields": "id,name,state"},
            creds,
        )
        if cl.get("name") == want_name:
            return cl
    if dry:
        print(f"DRY: would create checklist '{want_name}'")
        return {"id": "dry-cl", "name": want_name, "checkItems": []}
    new_cl = api(
        "POST",
        f"/cards/{card_id}/checklists",
        {"name": want_name, "pos": "top"},
        creds,
    )
    return {"id": new_cl["id"], "name": want_name, "checkItems": []}


def main():
    pos, flags = parse_args(sys.argv[1:])
    if not pos:
        print("Usage: update_card_complete.py <card_id> ...", file=sys.stderr)
        sys.exit(1)
    card_id = pos[0]
    dry = flags["dry"]

    config, _ = load_config()
    if not config:
        print("ERROR: config missing", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    creds = load_credentials()

    card = api("GET", f"/cards/{card_id}", {"fields": "desc,name"}, creds)
    meta, human_desc = parse_meta_block(card.get("desc") or "")
    sections = parse_existing(human_desc)

    if flags["result"]:
        sections["Result"] = flags["result"]
    if flags["changes"]:
        sections["Changes"] = "\n".join(f"- {c}" for c in flags["changes"])
    if flags["metrics"]:
        sections["Metrics"] = "\n".join(f"- {m}" for m in flags["metrics"])
    if flags["notes"]:
        sections["Notes"] = flags["notes"]

    new_desc = render(sections, meta)

    if dry:
        print("DRY: new description:")
        print(new_desc[:500])
    else:
        api("PUT", f"/cards/{card_id}", {"desc": new_desc}, creds)
        print(f"DESC_UPDATED:{card_id}")

    cl = ensure_checklist(card_id, flags["checklist_name"], creds, dry)
    existing_items = {it["name"]: it for it in cl.get("checkItems", [])}
    for step in flags["check_steps"]:
        if step in existing_items:
            item = existing_items[step]
            if item.get("state") == "complete":
                continue
            if dry:
                print(f"DRY: would check item '{step}'")
                continue
            api(
                "PUT",
                f"/cards/{card_id}/checkItem/{item['id']}",
                {"state": "complete"},
                creds,
            )
            print(f"CHECKED:{step}")
        else:
            if dry:
                print(f"DRY: would add+check item '{step}'")
                continue
            new_item = api(
                "POST",
                f"/checklists/{cl['id']}/checkItems",
                {"name": step, "pos": "bottom", "checked": "true"},
                creds,
            )
            print(f"ITEM_ADDED:{new_item.get('id', '?')}|{step}")

    for path in flags["attachments"]:
        cmd_attach(card_id, path, creds, dry)

    if flags["comment"]:
        cmd_comment(card_id, flags["comment"], creds, dry, tag="done", agent=flags["agent"])
    else:
        cmd_comment(card_id, "completion summary updated", creds, dry, tag="done", agent=flags["agent"])

    print(f"CARD_COMPLETE:{card_id}")


if __name__ == "__main__":
    main()
