#!/usr/bin/env python3
"""Trello Mission Control v2 — CLI for agent task management.

Usage:
  python3 trello_task.py init                                    # Generate config template
  python3 trello_task.py get <list_name_or_id>                   # Get open cards
  python3 trello_task.py create <list_name_or_id> <name> [labels] [due] [member]
  python3 trello_task.py done <card_id>                          # Move to Done
  python3 trello_task.py move <card_id> <target_list_name_or_id># Move card
  python3 trello_task.py next <card_id>                          # Move to next pipeline stage
  python3 trello_task.py prev <card_id>                          # Move to previous pipeline stage
  python3 trello_task.py pipeline-status                         # Show all cards in pipeline
  python3 trello_task.py archive <card_id>                       # Archive card
  python3 trello_task.py board                                   # Board summary
  python3 trello_task.py card <card_id>                          # Card details
  python3 trello_task.py members                                 # List board members
  python3 trello_task.py comment <card_id> <text>                # Add comment
  python3 trello_task.py label <card_id> <label_name_or_id>      # Add label
  python3 trello_task.py unlabel <card_id> <label_name_or_id>    # Remove label
  python3 trello_task.py desc <card_id> <text>                   # Set description
  python3 trello_task.py due <card_id> <date>                    # Set due date (YYYY-MM-DD)
  python3 trello_task.py assign <card_id> <member_id>            # Assign member
  python3 trello_task.py checklist <card_id> create <name>       # Create checklist
  python3 trello_task.py checklist <card_id> items <cl_id>       # List checklist items
  python3 trello_task.py checklist <card_id> add <cl_id> <text>  # Add item to checklist
  python3 trello_task.py checklist <card_id> check <cl_item_id>  # Check an item
  python3 trello_task.py checklist <card_id> uncheck <cl_item_id># Uncheck an item
  python3 trello_task.py attach <card_id> <file_path>            # Attach file
  python3 trello_task.py search <query> [--label <label>]        # Search cards
  python3 trello_task.py overdue [--list <list>]                 # Find overdue cards
  python3 trello_task.py activity <card_id>                      # Get card activity log

Flags:
  --dry    Simulate without executing
"""

import sys, json, urllib.request, urllib.parse, os, mimetypes, uuid, time

BASE = "https://api.trello.com/1"
MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]

# Exit codes
EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_AUTH = 2
EXIT_RATE_LIMIT = 3
EXIT_CONFIG = 4


# --- Config ---

def load_config():
    """Load config from env var TRELLO_CONFIG, ./trello_config.json, or ../trello_config.json."""
    env_path = os.environ.get("TRELLO_CONFIG")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [os.path.join(script_dir, "../trello_config.json")]
    if env_path:
        candidates.insert(0, env_path)
    candidates.extend(["./trello_config.json", "../trello_config.json"])
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            with open(candidate) as f:
                return json.load(f), candidate
    return None, None


def load_credentials():
    """Load API credentials from environment."""
    key = os.environ.get("TRELLO_API_KEY", "")
    token = os.environ.get("TRELLO_TOKEN", "")
    if not key or not token:
        print("ERROR: TRELLO_API_KEY and/or TRELLO_TOKEN environment variables not set.", file=sys.stderr)
        print("Set them in your shell:\n  export TRELLO_API_KEY='your-key'\n  export TRELLO_TOKEN='your-token'", file=sys.stderr)
        sys.exit(EXIT_AUTH)
    return key, token


# --- API ---

def api(method, path, params=None, creds=None, files=None, dry=False):
    """Make a Trello API call with retry logic."""
    if dry:
        return {"_dry": True, "method": method, "path": path, "params": params}

    api_key, token = creds or load_credentials()
    auth = f"key={api_key}&token={token}"
    boundary = None
    if files:
        boundary = f"----TrelloFormBoundary{uuid.uuid4().hex}"

    url = f"{BASE}{path}?{auth}"
    body = None

    if files:
        parts = []
        for k, v in (params or {}).items():
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}".encode())
        for field_name, file_path in files.items():
            mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            fname = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                fdata = f.read()
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field_name}"; filename="{fname}"\r\n'
                f"Content-Type: {mime}\r\n\r\n".encode() + fdata
            )
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"\r\n".join(p for p in parts if isinstance(p, bytes))
        final = []
        for p in parts:
            final.append(p if isinstance(p, bytes) else p.encode())
        body = b"\r\n".join(final)
    elif params:
        qs = urllib.parse.urlencode(params)
        if method in ("GET", "HEAD"):
            url += "&" + qs
        else:
            body = qs.encode()

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=body, method=method)
            if files:
                req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            elif body:
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(f"ERROR: API key inválida (401). Verifique TRELLO_API_KEY e TRELLO_TOKEN.", file=sys.stderr)
                sys.exit(EXIT_AUTH)
            elif e.code == 403:
                print(f"ERROR: Sem permissão (403). Verifique as permissões do token.", file=sys.stderr)
                sys.exit(EXIT_AUTH)
            elif e.code == 429 and attempt < MAX_RETRIES:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                print(f"WARN: Rate limit (429). Retry {attempt+1}/{MAX_RETRIES} em {delay}s...", file=sys.stderr)
                time.sleep(delay)
                last_error = e
                continue
            else:
                print(f"ERROR: HTTP {e.code} — {e.reason}", file=sys.stderr)
                sys.exit(EXIT_GENERIC)
        except urllib.error.URLError as e:
            print(f"ERROR: Connection failed — {e.reason}", file=sys.stderr)
            sys.exit(EXIT_GENERIC)

    print(f"ERROR: Rate limit excedido após {MAX_RETRIES} tentativas.", file=sys.stderr)
    sys.exit(EXIT_RATE_LIMIT)


# --- Helpers ---

def resolve_list(name_or_id, config):
    """Resolve list name to ID using config."""
    lists = config.get("lists", {})
    if name_or_id in lists.values():
        return name_or_id
    lower = name_or_id.lower()
    for k, v in lists.items():
        if k.lower() == lower:
            return v
    return name_or_id  # assume it's an ID


def resolve_label(name_or_id, config):
    """Resolve label name to ID using config."""
    labels = config.get("labels", {})
    if name_or_id in labels.values():
        return name_or_id
    lower = name_or_id.lower()
    for k, v in labels.items():
        if k.lower() == lower:
            return v
    return name_or_id  # assume it's an ID


def format_card(c):
    labels = ", ".join(l["name"] or l["id"] for l in c.get("labels", []))
    due = c.get("due") or ""
    members = ", ".join(m.get("fullName", m.get("username", ""))[:20] for m in c.get("members", []))
    desc = (c.get("desc") or "")[:120]
    checks = f"checklists={c.get('idChecklists',[])}" if c.get("idChecklists") else ""
    parts = [f"CARD:{c['id']}|{c['name']}|labels={labels}|members={members}|due={due}"]
    if checks:
        parts.append(checks)
    parts.append(desc)
    return "|".join(parts)


# --- Commands ---

def cmd_init():
    template = {
        "board_id": "YOUR_BOARD_ID",
        "lists": {
            "inbox": "LIST_ID",
            "in-progress": "LIST_ID",
            "done": "LIST_ID"
        },
        "labels": {
            "urgent": "LABEL_ID",
            "bug": "LABEL_ID"
        },
        "pipeline": ["inbox", "in-progress", "done"]
    }
    path = "trello_config.json"
    with open(path, "w") as f:
        json.dump(template, f, indent=2)
    print(f"Config template created: {path}")
    print("Edit it with your board's IDs. Set TRELLO_API_KEY and TRELLO_TOKEN in env.")


def cmd_board(config, creds, dry):
    board_id = config["board_id"]
    lists = api("GET", f"/boards/{board_id}/lists", {"fields": "id,name"}, creds=creds, dry=dry)
    for lst in lists:
        count = api("GET", f"/lists/{lst['id']}/cards", {"filter": "open", "fields": "id"}, creds=creds, dry=dry)
        n = len(count)
        print(f"LIST:{lst['name']}|{lst['id']}|cards={n}")


def cmd_members(config, creds, dry):
    board_id = config["board_id"]
    members = api("GET", f"/boards/{board_id}/members", {"fields": "id,username,fullName"}, creds, dry)
    for m in members:
        print(f"MEMBER:{m['id']}|{m.get('fullName', m['username'])}|@{m['username']}")


def cmd_card_detail(card_id, creds, dry):
    card = api("GET", f"/cards/{card_id}", {"fields": "id,name,desc,labels,idList,due,members,idChecklists,shortUrl,url"}, creds, dry)
    if dry:
        print(f"DRY: Would fetch card {card_id}")
        return
    print(f"ID: {card['id']}")
    print(f"Name: {card['name']}")
    print(f"List: {card.get('idList', '?')}")
    print(f"URL: {card.get('shortUrl', card.get('url', '?'))}")
    print(f"Due: {card.get('due') or 'none'}")
    labels = ", ".join(l["name"] or l["id"] for l in card.get("labels", []))
    print(f"Labels: {labels}")
    members = ", ".join(m.get("fullName", m.get("username", "")) for m in card.get("members", []))
    print(f"Members: {members or 'none'}")
    print(f"Checklists: {len(card.get('idChecklists', []))}")
    print(f"Desc: {card.get('desc') or 'none'}")


def cmd_archive(card_id, creds, dry):
    if dry:
        print(f"DRY: Would archive card {card_id}")
        return
    api("PUT", f"/cards/{card_id}", {"closed": "true"}, creds)
    print(f"ARCHIVED:{card_id}")


def cmd_get(list_name_or_id, config, creds, dry):
    list_id = resolve_list(list_name_or_id, config)
    if dry:
        print(f"DRY: Would get cards from list {list_name_or_id} ({list_id})")
        return
    params = {"filter": "open", "fields": "id,name,desc,labels,idList,due,members,idChecklists"}
    cards = api("GET", f"/lists/{list_id}/cards", params, creds)
    if not cards:
        print("NO_CARDS")
    for c in cards:
        print(format_card(c))


def cmd_create(list_name_or_id, name, config, creds, dry, label_ids="", due=None, member_id=None):
    list_id = resolve_list(list_name_or_id, config)
    # Resolve label names to IDs
    resolved_labels = []
    for lbl in label_ids.split(","):
        lbl = lbl.strip()
        if lbl:
            resolved_labels.append(resolve_label(lbl, config))
    label_str = ",".join(resolved_labels)

    params = {"idList": list_id, "name": name, "pos": "top"}
    if label_str:
        params["idLabels"] = label_str
    if due:
        params["due"] = due
    if member_id:
        params["idMembers"] = member_id
    if dry:
        print(f"DRY: Would create card '{name}' in list {list_name_or_id} ({list_id}) labels={label_str}")
        return
    card = api("POST", "/cards", params, creds)
    print(f"CREATED:{card['id']}|{card['name']}|{card.get('shortUrl','')}")


def cmd_done(card_id, config, creds, dry):
    done_id = config.get("lists", {}).get("done")
    if not done_id:
        print("ERROR: 'done' list not defined in config.", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    if dry:
        print(f"DRY: Would move card {card_id} to done ({done_id})")
        return
    api("PUT", f"/cards/{card_id}", {"idList": done_id}, creds)
    print(f"DONE:{card_id}")


def cmd_move(card_id, target, config, creds, dry):
    target_id = resolve_list(target, config)
    if dry:
        print(f"DRY: Would move card {card_id} to {target} ({target_id})")
        return
    api("PUT", f"/cards/{card_id}", {"idList": target_id}, creds)
    print(f"MOVED:{card_id}->{target_id}")


def cmd_pipeline_next(card_id, config, creds, dry):
    pipeline = config.get("pipeline", [])
    if not pipeline:
        print("ERROR: No pipeline defined in config.", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    card = api("GET", f"/cards/{card_id}", {"fields": "idList"}, creds)
    current_list_id = card["idList"]
    lists = config.get("lists", {})
    # Find current position
    current_idx = None
    for name, lid in lists.items():
        if lid == current_list_id and name in pipeline:
            current_idx = pipeline.index(name)
            break
    if current_idx is None or current_idx >= len(pipeline) - 1:
        print(f"PIPELINE_END:{card_id}|already at final stage or not in pipeline")
        return
    next_name = pipeline[current_idx + 1]
    next_id = lists[next_name]
    if dry:
        print(f"DRY: Would move {card_id} from '{pipeline[current_idx]}' to '{next_name}' ({next_id})")
        return
    api("PUT", f"/cards/{card_id}", {"idList": next_id}, creds)
    print(f"PIPELINE_NEXT:{card_id}|{pipeline[current_idx]}->{next_name}")


def cmd_pipeline_prev(card_id, config, creds, dry):
    pipeline = config.get("pipeline", [])
    if not pipeline:
        print("ERROR: No pipeline defined in config.", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    card = api("GET", f"/cards/{card_id}", {"fields": "idList"}, creds)
    current_list_id = card["idList"]
    lists = config.get("lists", {})
    current_idx = None
    for name, lid in lists.items():
        if lid == current_list_id and name in pipeline:
            current_idx = pipeline.index(name)
            break
    if current_idx is None or current_idx <= 0:
        print(f"PIPELINE_START:{card_id}|already at first stage or not in pipeline")
        return
    prev_name = pipeline[current_idx - 1]
    prev_id = lists[prev_name]
    if dry:
        print(f"DRY: Would move {card_id} from '{pipeline[current_idx]}' back to '{prev_name}' ({prev_id})")
        return
    api("PUT", f"/cards/{card_id}", {"idList": prev_id}, creds)
    print(f"PIPELINE_PREV:{card_id}|{pipeline[current_idx]}->{prev_name}")


def cmd_pipeline_status(config, creds, dry):
    pipeline = config.get("pipeline", [])
    if not pipeline:
        print("ERROR: No pipeline defined in config.", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    lists = config.get("lists", {})
    if dry:
        print(f"DRY: Would show pipeline status for stages: {pipeline}")
        return
    print("PIPELINE_STATUS:")
    for stage_name in pipeline:
        list_id = lists.get(stage_name)
        if not list_id:
            print(f"  {stage_name}: NOT CONFIGURED")
            continue
        cards = api("GET", f"/lists/{list_id}/cards", {"filter": "open", "fields": "id,name,labels,due,members"}, creds)
        print(f"  {stage_name} ({len(cards)} cards):")
        for c in cards:
            labels = ", ".join(l["name"] or "?" for l in c.get("labels", []))
            due = c.get("due", "")[:10] if c.get("due") else ""
            members = ", ".join(m.get("username", "") for m in c.get("members", []))
            print(f"    - {c['name']} [{c['id'][:8]}] labels={labels} due={due} members={members}")


def cmd_comment(card_id, text, creds, dry):
    if dry:
        print(f"DRY: Would comment on {card_id}: {text[:80]}")
        return
    api("POST", f"/cards/{card_id}/actions/comments", {"text": text}, creds)
    print(f"COMMENTED:{card_id}")


def cmd_label(card_id, label_name_or_id, config, creds, dry):
    label_id = resolve_label(label_name_or_id, config)
    if dry:
        print(f"DRY: Would add label {label_name_or_id} ({label_id}) to {card_id}")
        return
    api("POST", f"/cards/{card_id}/idLabels", {"value": label_id}, creds)
    print(f"LABELED:{card_id}|{label_id}")


def cmd_unlabel(card_id, label_name_or_id, config, creds, dry):
    label_id = resolve_label(label_name_or_id, config)
    api_key, token = creds or load_credentials()
    auth = f"key={api_key}&token={token}"
    if dry:
        print(f"DRY: Would remove label {label_name_or_id} ({label_id}) from {card_id}")
        return
    req = urllib.request.Request(f"{BASE}/cards/{card_id}/idLabels/{label_id}?{auth}", method="DELETE")
    with urllib.request.urlopen(req) as r:
        print(f"UNLABELED:{card_id}|{label_id}")


def cmd_desc(card_id, text, creds, dry):
    if dry:
        print(f"DRY: Would set desc on {card_id}")
        return
    api("PUT", f"/cards/{card_id}", {"desc": text}, creds)
    print(f"DESC_UPDATED:{card_id}")


def cmd_due(card_id, date_str, creds, dry):
    if len(date_str) == 10:
        date_str += "T23:59:00.000Z"
    if dry:
        print(f"DRY: Would set due {date_str} on {card_id}")
        return
    api("PUT", f"/cards/{card_id}", {"due": date_str}, creds)
    print(f"DUE_SET:{card_id}|{date_str}")


def cmd_assign(card_id, member_id, creds, dry):
    if dry:
        print(f"DRY: Would assign {member_id} to {card_id}")
        return
    api("POST", f"/cards/{card_id}/idMembers", {"value": member_id}, creds)
    print(f"ASSIGNED:{card_id}|{member_id}")


def cmd_checklist(card_id, action, creds, dry, *args):
    if action == "create":
        name = args[0]
        if dry:
            print(f"DRY: Would create checklist '{name}' on {card_id}")
            return
        cl = api("POST", f"/cards/{card_id}/checklists", {"name": name, "pos": "top"}, creds)
        print(f"CHECKLIST_CREATED:{cl['id']}|{cl['name']}|card={card_id}")
    elif action == "items":
        cl_id = args[0]
        if dry:
            print(f"DRY: Would list items of checklist {cl_id}")
            return
        cl_data = api("GET", f"/checklists/{cl_id}", {"fields": "id,name,idBoard", "checkItems": "all", "checkItem_fields": "id,name,state"}, creds)
        for item in cl_data.get("checkItems", []):
            state = "✅" if item.get("state") == "complete" else "⬜"
            print(f"ITEM:{item['id']}|{state} {item['name']}")
    elif action == "add":
        cl_id, text = args[0], " ".join(args[1:])
        if dry:
            print(f"DRY: Would add item '{text}' to checklist {cl_id}")
            return
        item = api("POST", f"/checklists/{cl_id}/checkItems", {"name": text, "pos": "bottom"}, creds)
        print(f"ITEM_ADDED:{item['id']}|{text}")
    elif action == "check":
        cl_item_id = args[0]
        if dry:
            print(f"DRY: Would check item {cl_item_id}")
            return
        api("PUT", f"/cards/{card_id}/checkItem/{cl_item_id}", {"state": "complete"}, creds)
        print(f"CHECKED:{cl_item_id}")
    elif action == "uncheck":
        cl_item_id = args[0]
        if dry:
            print(f"DRY: Would uncheck item {cl_item_id}")
            return
        api("PUT", f"/cards/{card_id}/checkItem/{cl_item_id}", {"state": "incomplete"}, creds)
        print(f"UNCHECKED:{cl_item_id}")
    else:
        print(f"Unknown checklist action: {action}", file=sys.stderr)
        sys.exit(EXIT_GENERIC)


def cmd_attach(card_id, file_path, creds, dry):
    if dry:
        print(f"DRY: Would attach {file_path} to {card_id}")
        return
    api("POST", f"/cards/{card_id}/attachments", {"name": os.path.basename(file_path)}, creds, files={"file": file_path})
    print(f"ATTACHED:{card_id}|{os.path.basename(file_path)}")


def cmd_search(query, config, creds, dry, label_id=None):
    params = {"query": query, "idBoards": config["board_id"], "card_fields": "id,name,desc,labels,idList,due,members,idChecklists"}
    if label_id:
        params["idLabels"] = resolve_label(label_id, config)
    if dry:
        print(f"DRY: Would search '{query}'")
        return
    result = api("GET", "/search", params, creds)
    cards = result.get("cards", [])
    if not cards:
        print("NO_RESULTS")
    for c in cards:
        print(format_card(c))


def cmd_overdue(config, creds, dry, list_name=None):
    params = {"filter": "open", "fields": "id,name,desc,labels,idList,due,members"}
    if list_name:
        list_id = resolve_list(list_name, config)
        cards = api("GET", f"/lists/{list_id}/cards", params, creds)
    else:
        cards = api("GET", f"/boards/{config['board_id']}/cards", params, creds)
    if dry:
        print(f"DRY: Would check overdue cards")
        return
    overdue = []
    for c in cards:
        if c.get("due") and not c.get("dueComplete"):
            overdue.append((c["due"][:10], c))
    if not overdue:
        print("NO_OVERDUE")
    else:
        overdue.sort(key=lambda x: x[0])
        for due_date, c in overdue:
            print(f"OVERDUE:{due_date}|{format_card(c)}")


def cmd_activity(card_id, creds, dry):
    if dry:
        print(f"DRY: Would get activity for {card_id}")
        return
    actions = api("GET", f"/cards/{card_id}/actions", {"filter": "commentCard,updateCard:idList,updateCard:closed,createCard,addAttachmentToCard", "limit": "30"}, creds)
    if not actions:
        print("NO_ACTIVITY")
    for a in actions:
        dt = a.get("date", "")[:19].replace("T", " ")
        actor = a.get("memberCreator", {}).get("username", "?")
        action_type = a.get("type", "")
        if action_type == "commentCard":
            text = a.get("data", {}).get("text", "")[:150]
            print(f"[{dt}] @{actor} commented: {text}")
        elif action_type == "createCard":
            print(f"[{dt}] @{actor} created card")
        elif "idList" in str(a.get("data", {})):
            text = a.get("data", {}).get("listAfter", {}).get("name", "?")
            print(f"[{dt}] @{actor} moved to: {text}")
        elif "closed" in str(a.get("data", {})):
            print(f"[{dt}] @{actor} archived card")
        elif action_type == "addAttachmentToCard":
            name = a.get("data", {}).get("attachment", {}).get("name", "?")
            print(f"[{dt}] @{actor} attached: {name}")


# --- Main ---

def parse_args(argv):
    """Parse args, extract --dry flag."""
    clean = []
    dry = False
    for a in argv:
        if a == "--dry":
            dry = True
        else:
            clean.append(a)
    return clean, dry


if __name__ == "__main__":
    args, dry = parse_args(sys.argv[1:])
    if not args:
        print(__doc__)
        sys.exit(EXIT_GENERIC)

    cmd = args[0]
    config = None
    creds = None

    # Commands that don't need config
    if cmd == "init":
        cmd_init()
        sys.exit(EXIT_OK)

    # Everything else needs config + creds
    config, config_path = load_config()
    if not config:
        print("ERROR: trello_config.json not found.", file=sys.stderr)
        print("Run: python3 trello_task.py init", file=sys.stderr)
        print("Or set env var TRELLO_CONFIG=/path/to/config.json", file=sys.stderr)
        sys.exit(EXIT_CONFIG)

    if "board_id" not in config:
        print("ERROR: Invalid config — 'board_id' missing.", file=sys.stderr)
        sys.exit(EXIT_CONFIG)

    creds = load_credentials()

    try:
        if cmd == "board":
            cmd_board(config, creds, dry)
        elif cmd == "members":
            cmd_members(config, creds, dry)
        elif cmd == "card" and len(args) >= 2:
            cmd_card_detail(args[1], creds, dry)
        elif cmd == "archive" and len(args) >= 2:
            cmd_archive(args[1], creds, dry)
        elif cmd == "pipeline-status":
            cmd_pipeline_status(config, creds, dry)
        elif cmd == "next" and len(args) >= 2:
            cmd_pipeline_next(args[1], config, creds, dry)
        elif cmd == "prev" and len(args) >= 2:
            cmd_pipeline_prev(args[1], config, creds, dry)
        elif cmd == "get" and len(args) >= 2:
            cmd_get(args[1], config, creds, dry)
        elif cmd == "create" and len(args) >= 3:
            label_ids = args[3] if len(args) > 3 else ""
            due = args[4] if len(args) > 4 else None
            member = args[5] if len(args) > 5 else None
            cmd_create(args[1], args[2], config, creds, dry, label_ids, due, member)
        elif cmd == "done" and len(args) >= 2:
            cmd_done(args[1], config, creds, dry)
        elif cmd == "move" and len(args) >= 3:
            cmd_move(args[1], args[2], config, creds, dry)
        elif cmd == "comment" and len(args) >= 3:
            cmd_comment(args[1], " ".join(args[2:]), creds, dry)
        elif cmd == "label" and len(args) >= 3:
            cmd_label(args[1], args[2], config, creds, dry)
        elif cmd == "unlabel" and len(args) >= 3:
            cmd_unlabel(args[1], args[2], config, creds, dry)
        elif cmd == "desc" and len(args) >= 3:
            cmd_desc(args[1], " ".join(args[2:]), creds, dry)
        elif cmd == "due" and len(args) >= 3:
            cmd_due(args[1], args[2], creds, dry)
        elif cmd == "assign" and len(args) >= 3:
            cmd_assign(args[1], args[2], creds, dry)
        elif cmd == "checklist" and len(args) >= 4:
            cmd_checklist(args[1], args[2], creds, dry, *args[3:])
        elif cmd == "attach" and len(args) >= 3:
            cmd_attach(args[1], args[2], creds, dry)
        elif cmd == "search":
            label = None
            clean_args = list(args[1:])
            if "--label" in clean_args:
                idx = clean_args.index("--label")
                label = clean_args[idx + 1]
                clean_args = clean_args[:idx] + clean_args[idx + 2:]
            query = " ".join(clean_args)
            cmd_search(query, config, creds, dry, label)
        elif cmd == "overdue":
            list_name = None
            if "--list" in args:
                idx = args.index("--list")
                list_name = args[idx + 1]
            cmd_overdue(config, creds, dry, list_name)
        elif cmd == "activity" and len(args) >= 2:
            cmd_activity(args[1], creds, dry)
        else:
            print(f"Invalid args. Usage:\n{__doc__}")
            sys.exit(EXIT_GENERIC)
    except Exception as e:
        print(f"ERROR:{e}", file=sys.stderr)
        sys.exit(EXIT_GENERIC)
