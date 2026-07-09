# Skills e agentes de IA usados neste projeto

Este diretório **evidencia o uso de IA generativa** no desenvolvimento — resposta
direta à pergunta da apresentação: *"Onde e como você usou IA generativa? Seja
específico."*

Aqui registramos **quais** capacidades de IA foram adotadas, **em que fase** da
metodologia cada uma entra e **por quê**. O skill de projeto
[`desenvolvimento-de-fatia`](desenvolvimento-de-fatia/SKILL.md) codifica o nosso
fluxo spec-driven de forma reutilizável.

## Metodologia (spec-driven, 3 fases)

Cada funcionalidade ("fatia") passa por: **1) plano → 2) TDD → 3) revisão
adversarial**. Ver `CLAUDE.md` e o skill de projeto.

## Skills externas adotadas

| Skill | Fase | Para quê |
|---|---|---|
| `superpowers:brainstorming` | 1 — Plano | Explorar intenção/requisitos antes de projetar cada fatia |
| `superpowers:writing-plans` | 1 — Plano | Escrever o plano de implementação da fatia |
| `superpowers:test-driven-development` | 2 — Dev | Ciclo red-green-refactor nas partes críticas de cálculo/conversão |
| `superpowers:requesting-code-review` | 3 — Revisão | Solicitar revisão ao concluir a fatia |
| `superpowers:receiving-code-review` | 3 — Revisão | Incorporar feedback com rigor técnico (verificar, não concordar por reflexo) |
| `superpowers:verification-before-completion` | 3 — Revisão | Exigir evidência (testes rodando) antes de declarar "pronto" |
| `superpowers:systematic-debugging` | qualquer | Depurar falhas de forma sistemática |
| `frontend-design` | Fatia 8b-ii | **Acionada** — design intencional do dashboard (paleta/tipografia/layout específicos do domínio de tesouraria, não um template genérico) |
| `dataviz` | — **não acionada** | Os gráficos (matriz de materialidade, barras PTAX×Frankfurter) foram construídos como SVG hand-rolled dentro do `frontend-design`, sem invocar este skill específico |
| `context7` (MCP) | qualquer | Docs atualizadas de pydantic, SQLAlchemy, PyMySQL, httpx, typer, FastAPI, Docker |

## Agentes usados

O único agente **customizado** deste projeto é o `lv10-dev` (em `.claude/agents/`).
Os demais usados são agentes **built-in** do Claude Code.

| Agente | Tipo | Papel |
|---|---|---|
| `lv10-dev` | customizado | **Revisão adversarial obrigatória (Fase 3)** — assume que o design está errado e caça falhas silenciosas e piores casos |
| `Plan` | built-in | Desenho de planos de implementação por fatia |
| `Explore` | built-in | Buscas amplas read-only no código |

## Registro por fatia

Registro de quais skills/agentes foram de fato acionados em cada fatia (para a
apresentação ser específica). O padrão base — `brainstorming` (decisões) →
`writing-plans` + agente `Plan` (plano) → `test-driven-development` (impl.) →
agente `lv10-dev` (revisão adversarial) — se repete; abaixo, os destaques por fatia.

- **Fatia 1 — Modelagem do domínio:** `writing-plans` + agente `Plan`;
  `test-driven-development`; agente `lv10-dev`.
- **Fatia 2 — Regras de negócio (seleção de taxa, fallback, alertas):** `brainstorming`
  (justificativas compra/venda, semântica dos alertas); `writing-plans`;
  `test-driven-development`; `lv10-dev`.
- **Fatia 3 — Adapters das APIs (PTAX + Frankfurter):** `brainstorming`; `writing-plans`;
  `test-driven-development` (normalização, timeout/retry, respostas incompletas);
  `context7` (httpx); `lv10-dev`.
- **Fatia 4 — Use case de consolidação (conversão, divergência, rastreabilidade):**
  `brainstorming`; `writing-plans`; `test-driven-development`; `lv10-dev`.
- **Fatia 5 — Serviço de consolidação (totais, top 3, posição por natureza):**
  `brainstorming`; `writing-plans`; `test-driven-development`; `lv10-dev`.
- **Fatia 6a — Persistência + idempotência (MySQL, hash do conjunto, histórico):**
  `brainstorming` (tradeoffs de schema e auditoria append-only); `writing-plans`;
  `test-driven-development`; `context7` (SQLAlchemy); `lv10-dev`.
- **Fatia 6b — Infra Docker + MySQL (compose, Makefile):** `brainstorming`;
  `writing-plans`; validação ao vivo (containers reais); `context7` (Docker); `lv10-dev`.
- **Fatia 7 — CLI + relatório:** `brainstorming`; `writing-plans`;
  `subagent-driven-development` (implementer + reviewer por tarefa); `test-driven-development`;
  validação ao vivo (APIs + MySQL reais); `lv10-dev` + `requesting-code-review` (revisão final).
- **Fatia 9 — Documentação (README, exemplo de output, decisões):** `brainstorming`;
  `writing-plans` (spec); investigação por subagentes (auditoria de cobertura do enunciado);
  validação ao vivo do README (< 5 min); `lv10-dev`.
- **Fatia 8a — API REST (diferencial):** `brainstorming` (decisão de decompor 8a/8b, contrato dos
  endpoints); `writing-plans`; `subagent-driven-development` (implementer + reviewer por tarefa);
  validação ao vivo (POST/GET reais contra APIs + MySQL); `lv10-dev`.
- **Fatia 8b-i — Backend em container + fix do ciclo de vida dos providers:** `brainstorming`
  (como preservar `modo_live` por requisição sem vazar `httpx.Client`); `writing-plans`;
  `subagent-driven-development`; validação ao vivo (`docker compose up` real); `lv10-dev`.
- **Fatia 8b-ii — Dashboard de tesouraria (diferencial):** `brainstorming` (dashboard híbrido:
  KPIs + matriz de materialidade + comparação PTAX×Frankfurter + drill-down); `frontend-design`
  (construção do dashboard); validação visual real via `claude-in-chrome` (screenshot, interação,
  sem erro de console); `lv10-dev`.
