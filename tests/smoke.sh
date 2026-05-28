#!/usr/bin/env bash
# Smoke test: run every CLI command in --dry mode with fake credentials and
# assert each prints a DRY: line and exits 0.
#
# Run from the repository root:
#   bash tests/smoke.sh

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

export TRELLO_API_KEY=fake
export TRELLO_TOKEN=fake
export TRELLO_CONFIG="$ROOT/references/example-config.json"
export OPENCLAW_AGENT_ID=executor

PASS=0
FAIL=0
FAILED_CMDS=()

check() {
    local label="$1"
    shift
    local out
    out=$("$@" 2>&1)
    local rc=$?
    if [ $rc -ne 0 ]; then
        echo "FAIL ($rc): $label"
        echo "  output: $out"
        FAILED_CMDS+=("$label")
        FAIL=$((FAIL + 1))
        return
    fi
    if ! echo "$out" | grep -q '^DRY:'; then
        echo "FAIL (no DRY): $label"
        echo "  output: $out"
        FAILED_CMDS+=("$label")
        FAIL=$((FAIL + 1))
        return
    fi
    PASS=$((PASS + 1))
}

# trello_task.py commands
check "board" python3 scripts/trello_task.py --dry board
check "members" python3 scripts/trello_task.py --dry members
check "card" python3 scripts/trello_task.py --dry card CARDID
check "get inbox" python3 scripts/trello_task.py --dry get inbox
check "create" python3 scripts/trello_task.py --dry create inbox "test name" "urgente"
check "done" python3 scripts/trello_task.py --dry done CARDID
check "move" python3 scripts/trello_task.py --dry move CARDID executor
check "next --expect" python3 scripts/trello_task.py --dry next CARDID --expect inbox
check "prev --expect" python3 scripts/trello_task.py --dry prev CARDID --expect executor
check "claim" python3 scripts/trello_task.py --dry claim CARDID executor
check "release" python3 scripts/trello_task.py --dry release CARDID executor
check "claimed-by" python3 scripts/trello_task.py --dry claimed-by CARDID
check "release-all" python3 scripts/trello_task.py --dry release-all executor
check "comment --tag" python3 scripts/trello_task.py --dry comment CARDID --tag note "hi"
check "activity --filter" python3 scripts/trello_task.py --dry activity CARDID --filter claim,done
check "label" python3 scripts/trello_task.py --dry label CARDID urgente
check "unlabel" python3 scripts/trello_task.py --dry unlabel CARDID urgente
check "desc" python3 scripts/trello_task.py --dry desc CARDID "new desc"
check "due" python3 scripts/trello_task.py --dry due CARDID 2026-12-01
check "assign" python3 scripts/trello_task.py --dry assign CARDID MEMBERID
check "meta-get" python3 scripts/trello_task.py --dry meta-get CARDID priority
check "meta-set" python3 scripts/trello_task.py --dry meta-set CARDID priority P0
check "template" python3 scripts/trello_task.py --dry template TPLID inbox "new name"
check "rate-budget" python3 scripts/trello_task.py --dry rate-budget
check "attach" python3 scripts/trello_task.py --dry attach CARDID /etc/hostname
check "archive" python3 scripts/trello_task.py --dry archive CARDID
check "search" python3 scripts/trello_task.py --dry search "test" --label urgente
check "overdue" python3 scripts/trello_task.py --dry overdue --list executor

# helper scripts
check "digest" python3 scripts/digest.py --dry
check "archive_old" python3 scripts/archive_old.py --dry --days 30 --from done
check "setup_labels" python3 scripts/setup_labels.py --dry
check "release_my_claims" python3 scripts/release_my_claims.py executor --dry

echo ""
echo "smoke: $PASS pass / $FAIL fail"
if [ $FAIL -ne 0 ]; then
    echo "failed: ${FAILED_CMDS[*]}"
    exit 1
fi
exit 0
