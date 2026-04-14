---
name: trello-mission-control
description: "Manage cross-agent task delegation via Trello. Supports single-agent tasks, flexible pipeline projects, board overview, card details, member listing, archive, dry-run mode, checklists, due dates, attachments, search, overdue alerts, and activity logs. Config-driven: board lists, labels, and pipeline stages defined in trello_config.json. Credentials via TRELLO_API_KEY/TRELLO_TOKEN env vars."
---

# Trello Mission Control v2

Manage tasks across agents via Trello. Config-driven, no hardcoded IDs.

## Setup

### 1. Credentials

```bash
export TRELLO_API_KEY="your-key"
export TRELLO_TOKEN="your-token"
```

### 2. Config

Create `trello_config.json` in the script directory (or set `$TRELLO_CONFIG`):

```bash
python3 scripts/trello_task.py init
# Edit trello_config.json with your board IDs
```

Or see `references/example-config.json` for a full example.

### Config Structure

```json
{
  "board_id": "BOARD_ID",
  "lists": {
    "inbox": "LIST_ID",
    "jarvis": "LIST_ID",
    "vision": "LIST_ID",
    "done": "LIST_ID"
  },
  "labels": {
    "jarvis": "LABEL_ID",
    "vision": "LABEL_ID",
    "urgente": "LABEL_ID"
  },
  "pipeline": ["inbox", "em-andamento", "jarvis", "vision", "friday", "ultron", "done"]
}
```

- **lists**: Name→ID mapping. Used everywhere — pass names or IDs interchangeably.
- **labels**: Name→ID mapping. Same flexibility.
- **pipeline**: Ordered array of list names. Powers `next`, `prev`, `pipeline-status`.

Config lookup order: `$TRELLO_CONFIG` → `./trello_config.json` → `../trello_config.json`

## CLI Reference

```bash
SCRIPT="skills/trello-mission-control/scripts/trello_task.py"

# Setup
python3 $SCRIPT init                        # Generate config template

# Board overview
python3 $SCRIPT board                       # All lists with card counts
python3 $SCRIPT members                     # Board members
python3 $SCRIPT card <card_id>              # Full card details
python3 $SCRIPT archive <card_id>           # Archive card

# Pipeline
python3 $SCRIPT pipeline-status             # Show all cards across pipeline stages
python3 $SCRIPT next <card_id>              # Move to next pipeline stage
python3 $SCRIPT prev <card_id>              # Move to previous pipeline stage

# Cards (use list names or IDs)
python3 $SCRIPT get jarvis                  # Get open cards in jarvis list
python3 $SCRIPT create jarvis "Task name" "urgente,jarvis" 2026-04-20
python3 $SCRIPT done <card_id>              # Move to Done list
python3 $SCRIPT move <card_id> vision       # Move by name or ID
python3 $SCRIPT comment <card_id> "text"
python3 $SCRIPT desc <card_id> "description"
python3 $SCRIPT due <card_id> 2026-04-15
python3 $SCRIPT assign <card_id> <member_id>
python3 $SCRIPT activity <card_id>          # Activity log

# Labels (use names or IDs)
python3 $SCRIPT label <card_id> urgente
python3 $SCRIPT unlabel <card_id> urgente

# Checklists
python3 $SCRIPT checklist <card_id> create "Steps"
python3 $SCRIPT checklist <card_id> items <cl_id>
python3 $SCRIPT checklist <card_id> add <cl_id> "Do thing"
python3 $SCRIPT checklist <card_id> check <item_id>
python3 $SCRIPT checklist <card_id> uncheck <item_id>

# Attachments
python3 $SCRIPT attach <card_id> /path/to/file

# Search & Reports
python3 $SCRIPT search "query" [--label urgente]
python3 $SCRIPT overdue [--list jarvis]

# Dry run (any command)
python3 $SCRIPT --dry move <card_id> vision
python3 $SCRIPT --dry pipeline-status
```

## Two Task Modes

### Mode 1: Single Agent Task

Create directly in the agent's list:

```bash
SCRIPT="skills/trello-mission-control/scripts/trello_task.py"
python3 $SCRIPT create jarvis "Fix login bug" "jarvis,urgente"
python3 $SCRIPT desc <CARD_ID> "Check auth.ts timingSafeEqual"
```

### Mode 2: Pipeline Project

Card travels through all pipeline stages in sequence.

```bash
# Create in first pipeline stage
python3 $SCRIPT create inbox "Agent Office Hub v2" "revisao" 2026-04-20

# Create pipeline checklist
CL_ID=$(python3 $SCRIPT checklist <CARD_ID> create "Pipeline" | cut -d: -f2)
python3 $SCRIPT checklist <CARD_ID> add $CL_ID "Jarvis: Implement"
python3 $SCRIPT checklist <CARD_ID> add $CL_ID "Vision: Review"
python3 $SCRIPT checklist <CARD_ID> add $CL_ID "Friday: Deploy"

# Agent finishes → advance pipeline
python3 $SCRIPT checklist <CARD_ID> check <ITEM_ID>
python3 $SCRIPT comment <CARD_ID> "DONE: Features implemented."
python3 $SCRIPT next <CARD_ID>
```

## Heartbeat Checks

### Standard Agent
```bash
python3 $SCRIPT get <MY_LIST_NAME>  # e.g. get jarvis
# If NO_CARDS → NO_REPLY
```

### Coordinator (Sia)
```bash
python3 $SCRIPT pipeline-status      # Full pipeline overview
python3 $SCRIPT search "" --label urgente
python3 $SCRIPT overdue
python3 $SCRIPT board                # Quick counts per list
```

### Overdue Alert Format
```
⚠️ OVERDUE: 2 cards
- Task Name (due: 2026-04-10) — in jarvis
- Other Task (due: 2026-04-15) — in vision
```

## Error Handling

- **401** → Auth error (exit 2)
- **403** → Permission error (exit 2)
- **429** → Rate limit, retries with backoff (2s→4s→8s, exit 3 if exhausted)
- **Missing config** → Clear instructions (exit 4)
- **Missing credentials** → Clear instructions (exit 2)

## Rules

### 🔒 Task Delegation — EXCLUSIVAMENTE via Trello

- **TODAS as tarefas entre agentes passam pelo Trello Mission Control**
- **NUNCA usar sessions_send, sessions_spawn ou qualquer mensagem interna para delegar tarefas**
- Comunicação interna entre agentes é **apenas para chat/coordenação** (tirar dúvidas, alinhar, informar algo)
- Passagem de bastão = mover card no Trello + comentar o que foi feito
- Se um agente precisa que outro trabalhe em algo → cria/move card no Trello
- **Sem await, sem timeout, sem sessões cruzadas para tarefas**

### Fluxo correto
```
Agente A termina tarefa → comenta no card → move card pra lista do Agente B → acabou
Agente B verifica no heartbeat → pega o card → faz o trabalho → comenta → move pra próximo
```

### Fluxo ERRADO ❌
```
Agente A termina → sessions_send("faz isso") → espera resposta → timeout → retry
```

### Múltiplos cards na mesma lista
- **Ordem de prioridade:** label Urgente → mais antigo primeiro
- Processar **um por vez** — termina, comenta, move pra Done (ou próximo pipeline)
- Depois pega o próximo card
- Nunca mover cards sem concluir a tarefa

### Outras regras
- **Sia cria**, agentes processam em sequence
- **Always comment before moving** — creates audit trail
- **NUNCA pular etapas do pipeline** — depois de code review (Vision), SEMPRE move pra Friday (deploy) → Ultron (QA) → Done
- **Checklist items** track each agent's step in pipeline
- **Pipeline projects** start in first pipeline stage with label "revisao"
- **Bugs found** → "bloqueado" label + `prev` to send back
- **Igor requests** → label "igor"
- If no cards: NO_REPLY
