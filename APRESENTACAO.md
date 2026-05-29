# Trello Mission Control 📋

### Transforme um quadro do Trello no centro de comando da sua frota de agentes de IA.

> Você fala com **um** agente. Ele transforma o pedido em cards. Seus agentes especialistas pegam o trabalho sozinhos, instalam as ferramentas certas, executam e devolvem o resultado pronto — tudo visível, auditável e rodando no **Trello grátis**.

---

## O problema

Coordenar vários agentes de IA vira caos rápido:

- 🔀 **Ninguém sabe quem está fazendo o quê.** Dois agentes pegam a mesma tarefa. Trabalho duplicado, conflito.
- 🕳️ **Zero visibilidade.** O trabalho acontece dentro de sessões que somem. Você não consegue auditar nada.
- 🧩 **Cada agente faz do seu jeito.** Sem padrão de entrega, sem rastro de decisões, sem histórico.
- 🛠️ **As ferramentas certas nunca estão instaladas** na hora certa — e quando estão, ninguém sabe se são seguras.
- 📦 **A entrega vem solta.** Pedaços de output espalhados, nada montado num artefato final.

Você não precisa de mais um framework de orquestração complexo. Você precisa de um **quadro Kanban que os agentes entendem**.

---

## A solução

**Trello Mission Control** é uma skill que dá aos seus agentes um protocolo simples e à prova de corrida para coordenar trabalho através de **cards do Trello** — nada de mensagens cruzadas, nada de estado escondido.

```
Você  ──fala──►  Orquestrador  ──cria card──►  Quadro Trello  ──heartbeat──►  Especialista
                                                                                    │
                                                                          executa + devolve no card
```

- **O orquestrador** conversa com você, entende o pedido e cria um card bem-formado.
- **Os especialistas** monitoram suas colunas, pegam os cards, executam e escrevem o resultado de volta.
- **A comunicação é só pelo card.** Toda decisão, todo arquivo, todo status fica registrado e auditável.

O Trello é a **fonte única da verdade**. Você acompanha tudo pelo celular.

---

## Como funciona — o ciclo de vida de um card

1. **Você pede** algo ao orquestrador, em linguagem natural.
2. **O orquestrador busca no ClawHub** as melhores skills para a tarefa, escolhe, e cria o card: objetivo, skills escolhidas, prioridade, subtarefas.
3. **O especialista acorda** no heartbeat (ou na hora, se for `urgente`), **dá claim** no card (trava atômica — ninguém mais pega) e **instala as skills** que faltam, com auditoria de segurança antes.
4. **Ele quebra a tarefa** em subtarefas pequenas, **executa uma por vez**, e grava cada pedaço.
5. **Monta tudo** num único arquivo completo e **anexa ao card**.
6. **Fecha o card** com descrição estruturada (Objetivo / Resultado / Mudanças / Métricas / Notas), checklist marcado e um comentário curto.
7. **O card descansa** na coluna do dono. Cards concluídos são **arquivados automaticamente** no tempo certo.

---

## Por que entrega valor

### 🔒 Nunca dois agentes na mesma tarefa
Toda execução começa com um **claim atômico** (label `claim-<agente>`). Se outro agente já pegou, o segundo recebe `ALREADY_CLAIMED` e **para na hora**. Trava distribuída, sem servidor extra.

### 👁️ Visibilidade e auditoria totais
Todo comentário é etiquetado `[ISO | @agente | tag]`. Toda mudança vira seção no card. Todo artefato vira anexo. Você abre o Trello e **vê o trabalho inteiro** — quem fez, quando, o quê, e por quê.

### 🧠 Descoberta ativa de skills (v3.3.0)
O orquestrador **busca no ClawHub** as melhores ferramentas para cada tarefa — não chuta de memória. Ele ranqueia candidatos, escolhe os 1–3 melhores e grava no card. O especialista instala o que falta. Seus agentes ficam sempre com a **ferramenta certa para o trabalho**.

### 🧩 Decomposição + montagem (v3.3.0)
O especialista quebra o objetivo em **subtarefas pequenas e ordenadas**, executa uma por vez (agentes acertam muito mais em passos focados) e **monta tudo num arquivo completo** entregue como anexo. Qualidade de execução, não só de planejamento.

### 🛡️ Segurança antes de instalar
Nenhuma skill do ClawHub roda sem passar por uma **auditoria estática**: bloqueia `curl|sh`, `sudo`, `rm -rf /`, `eval`, URLs inseguras e mais. O agente que falha a auditoria **bloqueia o card** em vez de executar código suspeito.

### 🧹 Roda no Trello grátis, pra sempre
Status por **label** (não por mover cards entre listas) elimina o acúmulo. O `archive_old.py` varre cards concluídos para um quadro de arquivo. Anexos grandes viram `.gz`. Tudo dentro dos limites do plano gratuito do Trello.

### ⚡ Acorda na urgência
Card marcado `urgente` dispara `wake_on_urgent.py` — o especialista acorda **em segundos** em vez de esperar o próximo heartbeat.

### 📊 Resumo de uma chamada
O `digest.py` dá ao orquestrador uma visão completa do quadro numa única chamada de API: o que está em andamento, atrasado, urgente, parado e concluído por coluna.

---

## Um exemplo real

> **Você:** "Cria uma landing page em Next.js pro lançamento, com testes."
>
> **Orquestrador:** busca `discover_skills.py "nextjs landing page tests"` → escolhe `nextjs` + `vitest` → cria o card na coluna do `jarvis` com a seção `## Skills` e 5 subtarefas. *"Card criado em `jarvis` com skills `nextjs`, `vitest`. Especialista pega no próximo heartbeat."*
>
> **Jarvis (especialista):** dá claim → instala `nextjs` e `vitest` (auditadas) → executa as 5 subtarefas uma a uma, gravando cada parte → monta `_complete.tsx` → anexa ao card → preenche Resultado/Mudanças/Métricas → marca `done`.
>
> **Você:** abre o Trello, vê o card verde, baixa o arquivo pronto. **Sem ruído. Com rastro completo.**

---

## Comece em minutos

```bash
# 1. Instale a skill
openclaw skills install git:github.com/igorviapaineis/trello-mission-control@v3.3.0

# 2. Exporte as credenciais do Trello
export TRELLO_API_KEY='...'
export TRELLO_TOKEN='...'

# 3. Auto-bootstrap do quadro (cria board + listas + arquivo + labels em ~10s)
python3 scripts/bootstrap_board.py --auto-detect --with-labels

# 4. Verifique tudo (10 checagens)
python3 scripts/doctor.py

# 5. Mande o primeiro card pelo chat do orquestrador
```

Quadro montado. Agentes coordenados. Pronto.

---

## Para quem é

| Cenário | O que você ganha |
|---|---|
| **Frota de agentes especialistas** (dev, review, QA, deploy) | Cada um na sua coluna, pegando trabalho sozinho, sem colisão |
| **Pipelines multi-estágio** (implementa → revisa → publica) | Handoff explícito entre agentes via `next`/`prev`, sem corrida |
| **Operação solo com vários agentes** | Um chat, um quadro, controle total pelo celular |
| **Quem precisa de auditoria** | Histórico etiquetado de cada decisão e entrega |

---

## Em resumo

| Recurso | Entrega |
|---|---|
| 🔒 Claim atômico | Zero trabalho duplicado |
| 👁️ Status por label, single-owner | Quadro limpo, sem acúmulo |
| 🧠 Busca de skills no ClawHub | Ferramenta certa, automaticamente |
| 🧩 Decomposição + montagem | Execução melhor, artefato único |
| 🛡️ Auditoria de skills | Nada suspeito roda |
| 🧹 Arquivamento automático | Cabe no Trello grátis |
| ⚡ Wake-on-urgent | Resposta em segundos |
| 📊 Digest de 1 chamada | Visão geral instantânea |
| 🔌 Zero lock-in | É só Trello + Python + ClawHub |

---

### Pare de gerenciar agentes no escuro. Dê a eles um quadro que eles entendem.

```bash
openclaw skills install git:github.com/igorviapaineis/trello-mission-control@v3.3.0
```

📋 **Trello Mission Control** — orquestração de agentes que você consegue ver, auditar e confiar.

*MIT · roda no Trello Free · [github.com/igorviapaineis/trello-mission-control](https://github.com/igorviapaineis/trello-mission-control)*
