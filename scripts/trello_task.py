#!/usr/bin/env python3
"""Trello Mission Control v3 — CLI for multi-agent task coordination via Trello.

Usage:
  python3 trello_task.py init
  python3 trello_task.py board
  python3 trello_task.py members
  python3 trello_task.py card <card_id>
  python3 trello_task.py archive <card_id>

  # Cards
  python3 trello_task.py get <list_name_or_id>
  python3 trello_task.py create <list_name_or_id> <name> [labels] [due] [member]
  python3 trello_task.py done <card_id>
  python3 trello_task.py move <card_id> <target_list_name_or_id>
  python3 trello_task.py next <card_id> [--expect <list>]
  python3 trello_task.py prev <card_id> [--expect <list>]
  python3 trello_task.py pipeline-status

  # Claim/release (v3)
  python3 trello_task.py claim <card_id> <agent>
  python3 trello_task.py release <card_id> <agent>
  python3 trello_task.py claimed-by <card_id>
  python3 trello_task.py release-all <agent>

  # Comments and activity
  python3 trello_task.py comment <card_id> [--tag claim|done|blocked|handoff|note] <text>
  python3 trello_task.py activity <card_id> [--filter tag,tag] [--since ISO]

  # Card metadata
  python3 trello_task.py label <card_id> <label_name_or_id>
  python3 trello_task.py unlabel <card_id> <label_name_or_id>
  python3 trello_task.py desc <card_id> <text>
  python3 trello_task.py due <card_id> <date>
  python3 trello_task.py assign <card_id> <member_id>

  # Pseudo custom fields (v3): JSON meta block at end of description
  python3 trello_task.py meta-get <card_id> <key>
  python3 trello_task.py meta-set <card_id> <key> <value>

  # Checklists
  python3 trello_task.py checklist <card_id> create <name>
  python3 trello_task.py checklist <card_id> items <cl_id>
  python3 trello_task.py checklist <card_id> add <cl_id> <text>
  python3 trello_task.py checklist <card_id> check <cl_item_id>
  python3 trello_task.py checklist <card_id> uncheck <cl_item_id>

  # Attachments
  python3 trello_task.py attach <card_id> <file_path>

  # Card template via copy (v3)
  python3 trello_task.py template <template_card_id> <target_list> <new_name>

  # Search and reports
  python3 trello_task.py search <query> [--label <label>]
  python3 trello_task.py overdue [--list <list>]

  # Rate limit budget (v3)
  python3 trello_task.py rate-budget

Flags:
  --dry        Simulate without executing
  --verbose    Print rate-limit headers after every API call

Exit codes:
  0 OK
  1 generic error
  2 auth/permission error
  3 rate limit exhausted
  4 missing config
  5 already claimed
  6 low rate-limit budget
  7 state drift (pipeline expect mismatch)
  8 skill audit failure (used by skill_audit.py)
"""

import sys, json, urllib.request, urllib.parse, os, mimetypes, uuid, time, re

BASE = "https://api.trello.com/1"
MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]
LOW_BUDGET_THRESHOLD = 20

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_AUTH = 2
EXIT_RATE_LIMIT = 3
EXIT_CONFIG = 4
EXIT_ALREADY_CLAIMED = 5
EXIT_LOW_BUDGET = 6
EXIT_STATE_DRIFT = 7
EXIT_SKILL_AUDIT = 8

VERBOSE = False
LAST_RATE = {"token_remaining": None, "key_remaining": None, "token_max": None, "key_max": None}

META_OPEN = "<!--meta"
META_CLOSE = "-->"
META_PATTERN = re.compile(r"<!--meta\s*(\{.*?\})\s*-->", re.DOTALL)


# --- Config ---

def load_config():
    env_path = os.environ.get("TRELLO_CONFIG")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if env_path:
        candidates.append(env_path)
    candidates.extend([
        os.path.join(script_dir, "../trello_config.json"),
        "./trello_config.json",
        "../trello_config.json",
    ])
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            with open(candidate) as f:
                return json.load(f), candidate
    return None, None


def load_credentials():
    key = os.environ.get("TRELLO_API_KEY", "")
    token = os.environ.get("TRELLO_TOKEN", "")
    if not key or not token:
        print("ERROR: TRELLO_API_KEY and/or TRELLO_TOKEN environment variables not set.", file=sys.stderr)
        print("Set them in your shell:\n  export TRELLO_API_KEY='your-key'\n  export TRELLO_TOKEN='your-token'", file=sys.stderr)
        sys.exit(EXIT_AUTH)
    return key, token


# --- API ---

def _capture_rate_headers(headers):
    """Capture x-rate-limit-* headers."""
    try:
        tr = headers.get("x-rate-limit-api-token-remaining")
        kr = headers.get("x-rate-limit-api-key-remaining")
        tm = headers.get("x-rate-limit-api-token-max")
        km = headers.get("x-rate-limit-api-key-max")
        if tr is not None:
            LAST_RATE["token_remaining"] = int(tr)
        if kr is not None:
            LAST_RATE["key_remaining"] = int(kr)
        if tm is not None:
            LAST_RATE["token_max"] = int(tm)
        if km is not None:
            LAST_RATE["key_max"] = int(km)
    except (ValueError, TypeError):
        pass
    if VERBOSE:
        print(
            f"RATE: token={LAST_RATE['token_remaining']}/{LAST_RATE['token_max']} "
            f"key={LAST_RATE['key_remaining']}/{LAST_RATE['key_max']}",
            file=sys.stderr,
        )


def api(method, path, params=None, creds=None, files=None, dry=False, raw=False):
    """Make a Trello API call with retry logic. Captures rate-limit headers."""
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
        final = [p if isinstance(p, bytes) else p.encode() for p in parts]
        body = b"\r\n".join(final)
    elif params:
        qs = urllib.parse.urlencode(params)
        if method in ("GET", "HEAD"):
            url += "&" + qs
        else:
            body = qs.encode()

    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=body, method=method)
            if files:
                req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            elif body:
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req) as r:
                _capture_rate_headers(r.headers)
                data = r.read()
                if raw:
                    return data
                if not data:
                    return None
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return data.decode(errors="replace")
        except urllib.error.HTTPError as e:
            try:
                _capture_rate_headers(e.headers)
            except Exception:
                pass
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
                continue
            else:
                print(f"ERROR: HTTP {e.code} — {e.reason}", file=sys.stderr)
                sys.exit(EXIT_GENERIC)
        except urllib.error.URLError as e:
            print(f"ERROR: Connection failed — {e.reason}", file=sys.stderr)
            sys.exit(EXIT_GENERIC)

    print(f"ERROR: Rate limit excedido após {MAX_RETRIES} tentativas.", file=sys.stderr)
    sys.exit(EXIT_RATE_LIMIT)


def api_delete(path, creds, dry=False):
    """DELETE request — Trello returns no body for some DELETEs."""
    if dry:
        return {"_dry": True, "method": "DELETE", "path": path}
    api_key, token = creds or load_credentials()
    url = f"{BASE}{path}?key={api_key}&token={token}"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req) as r:
            _capture_rate_headers(r.headers)
            return r.read()
    except urllib.error.HTTPError as e:
        try:
            _capture_rate_headers(e.headers)
        except Exception:
            pass
        if e.code in (401, 403):
            sys.exit(EXIT_AUTH)
        print(f"ERROR: DELETE {path} → HTTP {e.code}", file=sys.stderr)
        sys.exit(EXIT_GENERIC)


# --- Helpers ---

def resolve_list(name_or_id, config):
    lists = config.get("lists", {})
    if name_or_id in lists.values():
        return name_or_id
    lower = name_or_id.lower()
    for k, v in lists.items():
        if k.lower() == lower:
            return v
    return name_or_id


def resolve_label(name_or_id, config):
    labels = config.get("labels", {})
    if name_or_id in labels.values():
        return name_or_id
    lower = name_or_id.lower()
    for k, v in labels.items():
        if k.lower() == lower:
            return v
    return name_or_id


def claim_label_name(agent):
    return f"claim-{agent}"


def resolve_claim_label_id(agent, config, creds):
    """Find or create the claim-<agent> label on the board."""
    cfg_id = config.get("labels", {}).get(claim_label_name(agent))
    if cfg_id:
        return cfg_id
    board_id = config["board_id"]
    labels = api("GET", f"/boards/{board_id}/labels", {"fields": "id,name", "limit": "1000"}, creds)
    for lbl in labels:
        if lbl.get("name") == claim_label_name(agent):
            return lbl["id"]
    return None


def format_card(c):
    labels = ", ".join((l.get("name") or l.get("id") or "?") for l in c.get("labels", []))
    due = c.get("due") or ""
    members = ", ".join(m.get("fullName", m.get("username", ""))[:20] for m in c.get("members", []))
    desc = (c.get("desc") or "")[:120]
    checks = f"checklists={len(c.get('idChecklists', []))}" if c.get("idChecklists") else ""
    parts = [f"CARD:{c['id']}|{c['name']}|labels={labels}|members={members}|due={due}"]
    if checks:
        parts.append(checks)
    parts.append(desc)
    return "|".join(parts)


def iso_now():
    return time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())


def tag_prefix(agent, tag):
    return f"[{iso_now()} | @{agent} | {tag}]"


def parse_meta_block(desc):
    """Extract JSON meta block from end of description. Returns (meta_dict, desc_without_block)."""
    if not desc:
        return {}, ""
    match = META_PATTERN.search(desc)
    if not match:
        return {}, desc
    try:
        meta = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}, desc
    desc_without = desc[: match.start()].rstrip() + "\n" if match.start() > 0 else ""
    return meta, desc_without


def serialize_meta_block(meta):
    return f"\n\n{META_OPEN}\n{json.dumps(meta, indent=2, ensure_ascii=False)}\n{META_CLOSE}\n"


def check_low_budget():
    tr = LAST_RATE.get("token_remaining")
    if tr is not None and tr < LOW_BUDGET_THRESHOLD:
        print(f"WARN: low token budget: {tr} remaining", file=sys.stderr)
        return True
    return False


# --- Commands ---

def cmd_init():
    template = {
        "board_id": "YOUR_BOARD_ID",
        "archive_board_id": "ARCHIVE_BOARD_ID",
        "templates_list_id": "TEMPLATES_LIST_ID",
        "lists": {
            "inbox": "LIST_ID",
            "executor": "LIST_ID",
            "done": "LIST_ID",
            "_templates": "LIST_ID"
        },
        "labels": {
            "urgente": "LABEL_ID",
            "bloqueado": "LABEL_ID",
            "revisao": "LABEL_ID",
            "pediu": "LABEL_ID",
            "stale": "LABEL_ID",
            "qa-failed": "LABEL_ID",
            "claim-orchestrator": "LABEL_ID",
            "claim-executor": "LABEL_ID"
        },
        "pipeline": ["inbox", "executor", "done"],
        "agents": {
            "orchestrator": {"role": "orchestrator", "list_id": "LIST_ID"},
            "executor": {"role": "executor", "list_id": "LIST_ID"}
        }
    }
    path = "trello_config.json"
    with open(path, "w") as f:
        json.dump(template, f, indent=2)
    print(f"Config template created: {path}")
    print("Edit it with your board's IDs. Set TRELLO_API_KEY and TRELLO_TOKEN in env.")


def cmd_board(config, creds, dry):
    board_id = config["board_id"]
    lists = api("GET", f"/boards/{board_id}/lists", {"fields": "id,name"}, creds=creds, dry=dry)
    cards = api(
        "GET",
        f"/boards/{board_id}/cards",
        {"filter": "visible", "fields": "id,idList"},
        creds=creds,
        dry=dry,
    )
    if dry:
        print("DRY: Would summarize board")
        return
    counts = {}
    for c in cards:
        counts[c["idList"]] = counts.get(c["idList"], 0) + 1
    for lst in lists:
        n = counts.get(lst["id"], 0)
        print(f"LIST:{lst['name']}|{lst['id']}|cards={n}")


def cmd_members(config, creds, dry):
    board_id = config["board_id"]
    members = api("GET", f"/boards/{board_id}/members", {"fields": "id,username,fullName"}, creds, dry=dry)
    if dry:
        print("DRY: Would list members")
        return
    for m in members:
        print(f"MEMBER:{m['id']}|{m.get('fullName', m['username'])}|@{m['username']}")


def cmd_card_detail(card_id, creds, dry):
    if dry:
        print(f"DRY: Would fetch card {card_id}")
        return
    card = api(
        "GET",
        f"/cards/{card_id}",
        {"fields": "id,name,desc,labels,idList,due,members,idChecklists,shortUrl,url,dueComplete"},
        creds,
    )
    print(f"ID: {card['id']}")
    print(f"Name: {card['name']}")
    print(f"List: {card.get('idList', '?')}")
    print(f"URL: {card.get('shortUrl', card.get('url', '?'))}")
    print(f"Due: {card.get('due') or 'none'} (complete={card.get('dueComplete', False)})")
    labels = ", ".join((l.get('name') or l.get('id')) for l in card.get('labels', []))
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
        return
    for c in cards:
        print(format_card(c))


def cmd_create(list_name_or_id, name, config, creds, dry, label_ids="", due=None, member_id=None):
    list_id = resolve_list(list_name_or_id, config)
    resolved_labels = []
    for lbl in (label_ids or "").split(","):
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
    api("PUT", f"/cards/{card_id}", {"idList": done_id, "dueComplete": "true"}, creds)
    print(f"DONE:{card_id}")


def cmd_move(card_id, target, config, creds, dry):
    target_id = resolve_list(target, config)
    if dry:
        print(f"DRY: Would move card {card_id} to {target} ({target_id})")
        return
    api("PUT", f"/cards/{card_id}", {"idList": target_id}, creds)
    print(f"MOVED:{card_id}->{target_id}")


def _pipeline_step(card_id, config, creds, dry, direction, expect=None):
    pipeline = config.get("pipeline", [])
    if not pipeline:
        print("ERROR: No pipeline defined in config.", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    lists = config.get("lists", {})
    if dry:
        if expect:
            print(f"DRY: Would {direction} {card_id} from expected={expect}")
        else:
            print(f"DRY: Would {direction} {card_id} along pipeline {pipeline}")
        return
    card = api("GET", f"/cards/{card_id}", {"fields": "idList"}, creds)
    current_list_id = card["idList"]
    current_name = None
    for name, lid in lists.items():
        if lid == current_list_id and name in pipeline:
            current_name = name
            break
    if expect and current_name != expect:
        print(f"STATE_DRIFT:{card_id}|expected={expect}|actual={current_name}", file=sys.stderr)
        sys.exit(EXIT_STATE_DRIFT)
    if current_name is None:
        print(f"PIPELINE_UNKNOWN:{card_id}|not in pipeline")
        return
    idx = pipeline.index(current_name)
    if direction == "next":
        if idx >= len(pipeline) - 1:
            print(f"PIPELINE_END:{card_id}|already at final stage")
            return
        target_name = pipeline[idx + 1]
    else:
        if idx <= 0:
            print(f"PIPELINE_START:{card_id}|already at first stage")
            return
        target_name = pipeline[idx - 1]
    target_id = lists.get(target_name)
    if not target_id:
        print(f"ERROR: pipeline stage '{target_name}' missing list_id", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    if dry:
        print(f"DRY: Would move {card_id} {current_name}->{target_name}")
        return
    api("PUT", f"/cards/{card_id}", {"idList": target_id}, creds)
    tag = "PIPELINE_NEXT" if direction == "next" else "PIPELINE_PREV"
    print(f"{tag}:{card_id}|{current_name}->{target_name}")


def cmd_pipeline_next(card_id, config, creds, dry, expect=None):
    _pipeline_step(card_id, config, creds, dry, "next", expect)


def cmd_pipeline_prev(card_id, config, creds, dry, expect=None):
    _pipeline_step(card_id, config, creds, dry, "prev", expect)


def cmd_pipeline_status(config, creds, dry):
    pipeline = config.get("pipeline", [])
    if not pipeline:
        print("ERROR: No pipeline defined in config.", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    lists_cfg = config.get("lists", {})
    if dry:
        print(f"DRY: Would show pipeline status for stages: {pipeline}")
        return
    board_id = config["board_id"]
    cards = api(
        "GET",
        f"/boards/{board_id}/cards",
        {
            "filter": "visible",
            "fields": "id,name,idList,labels,due,members",
        },
        creds,
    )
    by_list = {}
    for c in cards:
        by_list.setdefault(c["idList"], []).append(c)
    print("PIPELINE_STATUS:")
    for stage_name in pipeline:
        list_id = lists_cfg.get(stage_name)
        if not list_id:
            print(f"  {stage_name}: NOT CONFIGURED")
            continue
        stage_cards = by_list.get(list_id, [])
        print(f"  {stage_name} ({len(stage_cards)} cards):")
        for c in stage_cards:
            labels = ", ".join((l.get("name") or "?") for l in c.get("labels", []))
            due = c.get("due", "")[:10] if c.get("due") else ""
            members = ", ".join(m.get("username", "") for m in c.get("members", []))
            print(f"    - {c['name']} [{c['id'][:8]}] labels={labels} due={due} members={members}")


def cmd_comment(card_id, text, creds, dry, tag=None, agent=None):
    if tag:
        if not agent:
            agent = os.environ.get("OPENCLAW_AGENT_ID") or os.environ.get("USER") or "agent"
        text = f"{tag_prefix(agent, tag)} {text}"
    if dry:
        print(f"DRY: Would comment on {card_id}: {text[:120]}")
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
    if dry:
        print(f"DRY: Would remove label {label_name_or_id} ({label_id}) from {card_id}")
        return
    api_delete(f"/cards/{card_id}/idLabels/{label_id}", creds)
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
        cl_data = api(
            "GET",
            f"/checklists/{cl_id}",
            {"fields": "id,name", "checkItems": "all", "checkItem_fields": "id,name,state"},
            creds,
        )
        for item in cl_data.get("checkItems", []):
            state = "[X]" if item.get("state") == "complete" else "[ ]"
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
    if not os.path.isfile(file_path):
        print(f"ERROR: file not found: {file_path}", file=sys.stderr)
        sys.exit(EXIT_GENERIC)
    size = os.path.getsize(file_path)
    if size > 10 * 1024 * 1024:
        print(f"ERROR: file > 10MB Trello free cap ({size} bytes)", file=sys.stderr)
        sys.exit(EXIT_GENERIC)
    api(
        "POST",
        f"/cards/{card_id}/attachments",
        {"name": os.path.basename(file_path)},
        creds,
        files={"file": file_path},
    )
    print(f"ATTACHED:{card_id}|{os.path.basename(file_path)}")


def cmd_search(query, config, creds, dry, label_id=None):
    params = {
        "query": query,
        "idBoards": config["board_id"],
        "card_fields": "id,name,desc,labels,idList,due,members,idChecklists",
    }
    if label_id:
        params["idLabels"] = resolve_label(label_id, config)
    if dry:
        print(f"DRY: Would search '{query}'")
        return
    result = api("GET", "/search", params, creds)
    cards = result.get("cards", [])
    if not cards:
        print("NO_RESULTS")
        return
    for c in cards:
        print(format_card(c))


def cmd_overdue(config, creds, dry, list_name=None):
    if dry:
        scope = f"list '{list_name}'" if list_name else "whole board"
        print(f"DRY: Would check overdue cards on {scope}")
        return
    params = {"filter": "open", "fields": "id,name,desc,labels,idList,due,members,dueComplete"}
    if list_name:
        list_id = resolve_list(list_name, config)
        cards = api("GET", f"/lists/{list_id}/cards", params, creds)
    else:
        cards = api("GET", f"/boards/{config['board_id']}/cards", params, creds)
    overdue = []
    for c in cards:
        if c.get("due") and not c.get("dueComplete"):
            overdue.append((c["due"][:10], c))
    if not overdue:
        print("NO_OVERDUE")
        return
    overdue.sort(key=lambda x: x[0])
    for due_date, c in overdue:
        print(f"OVERDUE:{due_date}|{format_card(c)}")


def cmd_activity(card_id, creds, dry, filter_tags=None, since=None):
    if dry:
        print(f"DRY: Would get activity for {card_id}")
        return
    params = {
        "filter": "commentCard,updateCard:idList,updateCard:closed,createCard,addAttachmentToCard",
        "limit": "30",
    }
    if since:
        params["since"] = since
    actions = api("GET", f"/cards/{card_id}/actions", params, creds)
    if not actions:
        print("NO_ACTIVITY")
        return
    filters = set(filter_tags or [])
    for a in actions:
        dt = a.get("date", "")[:19].replace("T", " ")
        actor = a.get("memberCreator", {}).get("username", "?")
        action_type = a.get("type", "")
        if action_type == "commentCard":
            text = a.get("data", {}).get("text", "")[:200]
            if filters:
                matched = any(f"| {t}]" in text for t in filters)
                if not matched:
                    continue
            print(f"[{dt}] @{actor} commented: {text}")
        elif action_type == "createCard":
            if filters:
                continue
            print(f"[{dt}] @{actor} created card")
        elif "idList" in str(a.get("data", {})):
            if filters:
                continue
            text = a.get("data", {}).get("listAfter", {}).get("name", "?")
            print(f"[{dt}] @{actor} moved to: {text}")
        elif "closed" in str(a.get("data", {})):
            if filters:
                continue
            print(f"[{dt}] @{actor} archived card")
        elif action_type == "addAttachmentToCard":
            if filters:
                continue
            name = a.get("data", {}).get("attachment", {}).get("name", "?")
            print(f"[{dt}] @{actor} attached: {name}")


# --- Claim/Release (v3) ---

def cmd_claim(card_id, agent, config, creds, dry):
    if dry:
        print(f"DRY: Would claim {card_id} for {agent}")
        return
    card = api("GET", f"/cards/{card_id}", {"fields": "id,labels"}, creds)
    existing_claim = None
    for lbl in card.get("labels", []):
        name = lbl.get("name") or ""
        if name.startswith("claim-"):
            existing_claim = name
            break
    if existing_claim and existing_claim != claim_label_name(agent):
        print(f"ALREADY_CLAIMED:{card_id}|{existing_claim}", file=sys.stderr)
        sys.exit(EXIT_ALREADY_CLAIMED)
    label_id = resolve_claim_label_id(agent, config, creds)
    if not label_id:
        board_id = config["board_id"]
        lbl = api(
            "POST",
            f"/boards/{board_id}/labels",
            {"name": claim_label_name(agent), "color": "sky"},
            creds,
        )
        label_id = lbl["id"]
    if not existing_claim:
        api("POST", f"/cards/{card_id}/idLabels", {"value": label_id}, creds)
    api(
        "POST",
        f"/cards/{card_id}/actions/comments",
        {"text": f"{tag_prefix(agent, 'claim')} working"},
        creds,
    )
    print(f"CLAIMED:{card_id}|{agent}")


def cmd_release(card_id, agent, config, creds, dry):
    if dry:
        print(f"DRY: Would release {card_id} from {agent}")
        return
    label_id = resolve_claim_label_id(agent, config, creds)
    if not label_id:
        print(f"NO_CLAIM_LABEL:{agent}")
        return
    api_delete(f"/cards/{card_id}/idLabels/{label_id}", creds)
    print(f"RELEASED:{card_id}|{agent}")


def cmd_claimed_by(card_id, creds, dry):
    if dry:
        print(f"DRY: Would check claimed-by for {card_id}")
        return
    card = api("GET", f"/cards/{card_id}", {"fields": "labels"}, creds)
    for lbl in card.get("labels", []):
        name = lbl.get("name") or ""
        if name.startswith("claim-"):
            print(f"CLAIMED_BY:{name[len('claim-'):]}")
            return
    print("NONE")


def cmd_release_all(agent, config, creds, dry):
    if dry:
        print(f"DRY: Would release all claims of {agent}")
        return
    label_id = resolve_claim_label_id(agent, config, creds)
    if not label_id:
        print(f"NO_CLAIM_LABEL:{agent}")
        return
    board_id = config["board_id"]
    cards = api(
        "GET",
        f"/boards/{board_id}/cards",
        {"filter": "visible", "fields": "id,labels"},
        creds,
    )
    count = 0
    for c in cards:
        for lbl in c.get("labels", []):
            if lbl.get("id") == label_id:
                api_delete(f"/cards/{c['id']}/idLabels/{label_id}", creds)
                count += 1
                break
    print(f"RELEASED_ALL:{agent}|count={count}")


# --- Meta block (v3) ---

def cmd_meta_get(card_id, key, creds, dry):
    if dry:
        print(f"DRY: Would get meta {key} from {card_id}")
        return
    card = api("GET", f"/cards/{card_id}", {"fields": "desc"}, creds)
    meta, _ = parse_meta_block(card.get("desc") or "")
    val = meta.get(key)
    if val is None:
        print("NONE")
    else:
        if isinstance(val, (dict, list)):
            print(json.dumps(val, ensure_ascii=False))
        else:
            print(val)


def cmd_meta_set(card_id, key, value, creds, dry):
    if dry:
        print(f"DRY: Would set meta {key}={value} on {card_id}")
        return
    card = api("GET", f"/cards/{card_id}", {"fields": "desc"}, creds)
    desc = card.get("desc") or ""
    meta, human_desc = parse_meta_block(desc)
    # try parse value as JSON, fallback to string
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        parsed = value
    meta[key] = parsed
    new_desc = (human_desc or "").rstrip() + serialize_meta_block(meta)
    api("PUT", f"/cards/{card_id}", {"desc": new_desc}, creds)
    print(f"META_SET:{card_id}|{key}={value}")


# --- Card template (v3) ---

def cmd_template(template_card_id, target_list, new_name, config, creds, dry):
    list_id = resolve_list(target_list, config)
    if dry:
        print(f"DRY: Would copy template {template_card_id} into {target_list} ({list_id}) as '{new_name}'")
        return
    card = api(
        "POST",
        "/cards",
        {
            "idCardSource": template_card_id,
            "idList": list_id,
            "name": new_name,
            "keepFromSource": "checklists,labels,due,attachments",
            "pos": "top",
        },
        creds,
    )
    print(f"TEMPLATED:{card['id']}|{card['name']}|{card.get('shortUrl','')}")


# --- Rate budget (v3) ---

def cmd_rate_budget(config, creds, dry):
    if dry:
        print("DRY: Would query rate budget")
        return
    api("GET", f"/boards/{config['board_id']}", {"fields": "id"}, creds)
    tr = LAST_RATE.get("token_remaining")
    kr = LAST_RATE.get("key_remaining")
    tm = LAST_RATE.get("token_max")
    km = LAST_RATE.get("key_max")
    print(f"RATE_BUDGET:token={tr}/{tm}|key={kr}/{km}")
    if tr is not None and tr < LOW_BUDGET_THRESHOLD:
        sys.exit(EXIT_LOW_BUDGET)


# --- Main ---

def parse_args(argv):
    """Extract flags. Returns (clean_args, flags_dict)."""
    global VERBOSE
    clean = []
    flags = {"dry": False, "tag": None, "filter": None, "since": None, "expect": None, "label": None, "list": None}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dry":
            flags["dry"] = True
        elif a == "--verbose":
            VERBOSE = True
        elif a == "--tag" and i + 1 < len(argv):
            flags["tag"] = argv[i + 1]
            i += 1
        elif a == "--filter" and i + 1 < len(argv):
            flags["filter"] = argv[i + 1].split(",")
            i += 1
        elif a == "--since" and i + 1 < len(argv):
            flags["since"] = argv[i + 1]
            i += 1
        elif a == "--expect" and i + 1 < len(argv):
            flags["expect"] = argv[i + 1]
            i += 1
        elif a == "--label" and i + 1 < len(argv):
            flags["label"] = argv[i + 1]
            i += 1
        elif a == "--list" and i + 1 < len(argv):
            flags["list"] = argv[i + 1]
            i += 1
        else:
            clean.append(a)
        i += 1
    return clean, flags


def main():
    args, flags = parse_args(sys.argv[1:])
    dry = flags["dry"]
    if not args:
        print(__doc__)
        sys.exit(EXIT_GENERIC)

    cmd = args[0]

    if cmd == "init":
        cmd_init()
        sys.exit(EXIT_OK)

    config, _ = load_config()
    if not config:
        print("ERROR: trello_config.json not found.", file=sys.stderr)
        print("Run: python3 trello_task.py init", file=sys.stderr)
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
            cmd_pipeline_next(args[1], config, creds, dry, flags.get("expect"))
        elif cmd == "prev" and len(args) >= 2:
            cmd_pipeline_prev(args[1], config, creds, dry, flags.get("expect"))
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
            agent = os.environ.get("OPENCLAW_AGENT_ID")
            cmd_comment(args[1], " ".join(args[2:]), creds, dry, tag=flags.get("tag"), agent=agent)
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
            label = flags.get("label")
            query = " ".join(args[1:])
            cmd_search(query, config, creds, dry, label)
        elif cmd == "overdue":
            cmd_overdue(config, creds, dry, flags.get("list"))
        elif cmd == "activity" and len(args) >= 2:
            cmd_activity(args[1], creds, dry, flags.get("filter"), flags.get("since"))
        elif cmd == "claim" and len(args) >= 3:
            cmd_claim(args[1], args[2], config, creds, dry)
        elif cmd == "release" and len(args) >= 3:
            cmd_release(args[1], args[2], config, creds, dry)
        elif cmd == "claimed-by" and len(args) >= 2:
            cmd_claimed_by(args[1], creds, dry)
        elif cmd == "release-all" and len(args) >= 2:
            cmd_release_all(args[1], config, creds, dry)
        elif cmd == "meta-get" and len(args) >= 3:
            cmd_meta_get(args[1], args[2], creds, dry)
        elif cmd == "meta-set" and len(args) >= 4:
            cmd_meta_set(args[1], args[2], " ".join(args[3:]), creds, dry)
        elif cmd == "template" and len(args) >= 4:
            cmd_template(args[1], args[2], " ".join(args[3:]), config, creds, dry)
        elif cmd == "rate-budget":
            cmd_rate_budget(config, creds, dry)
        else:
            print(f"Invalid args. Usage:\n{__doc__}")
            sys.exit(EXIT_GENERIC)
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR:{e}", file=sys.stderr)
        sys.exit(EXIT_GENERIC)

    if check_low_budget() and cmd != "rate-budget":
        sys.exit(EXIT_LOW_BUDGET)


if __name__ == "__main__":
    main()
