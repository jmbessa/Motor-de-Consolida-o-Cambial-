# Decisões técnicas e financeiras

Este documento consolida as **decisões conscientes** do projeto e serve de roteiro para a
apresentação. Cada seção referencia o código que a implementa e responde às perguntas do
enunciado (o mapeamento pergunta → seção está ao final de cada bloco).

> A filosofia da avaliação — "uma solução menor e bem justificada vale mais do que uma solução
> grande e sem raciocínio" — guiou cada escolha aqui: preferimos poucas decisões defensáveis a
> muitas features frágeis.

---

## 1. Modelagem da exposição cambial

Uma **exposição** (`domain/models.py::Exposicao`) é um compromisso financeiro futuro em moeda
estrangeira: `id`, `tipo` (`payable` | `receivable` | `intercompany`), `moeda`, `valor`,
`vencimento`, `descricao`.

Duas decisões de modelagem importam:

- **O `valor` é sempre positivo; a natureza (entra ou sai caixa) vem do `tipo`, não do sinal.**
  Um número negativo não representa "receber": representa dado corrompido, e é rejeitado na
  validação. Isso torna a direção do fluxo de caixa explícita e impossível de inferir errado.
- **Exposição ativa vs. passiva:**
  - **Passiva (`payable`)** — a empresa **deve** moeda estrangeira; é uma **saída** de caixa
    futura. A valorização em BRL é um **custo** — quanto mais caro o câmbio, pior.
  - **Ativa (`receivable`)** — a empresa **tem a receber** moeda estrangeira; é uma **entrada**
    de caixa futura. A valorização em BRL é uma **receita** — quanto mais caro o câmbio, melhor.
  - **`intercompany`** — transferência interna ao grupo; não é exposição de mercado a
    terceiros (ver §2).

O impacto cambial, portanto, é **assimétrico** por natureza: a mesma alta do dólar aumenta o
custo de um payable e a receita de um receivable. Por isso a consolidação separa as posições
por natureza (`visao_consolidada.py::TotalNatureza`) em vez de somar tudo num número único.

> Responde: item 9.1 (como modelou exposição; ativa vs. passiva) · item 8 (diferença
> receivable/payable; impacto cambial sobre contas a pagar/receber).

---

## 2. Seleção de taxa por tipo

Uma cotação de câmbio tem dois lados (`domain/rules/selecao_taxa.py`):

- **Compra (`cotacaoCompra`, bid)** — o preço pelo qual o mercado **compra** a moeda de você;
  é a taxa que você recebe ao **vender** moeda estrangeira.
- **Venda (`cotacaoVenda`, ask)** — o preço pelo qual o mercado **vende** a moeda para você;
  é a taxa que você paga ao **comprar** moeda estrangeira.

A diferença entre as duas é o **spread**. A regra do motor, por tipo:

| Tipo | Taxa usada | Por quê |
|---|---|---|
| **`payable`** | **Venda** (`cotacaoVenda`) | Para liquidar, a empresa **compra** a moeda no mercado. A taxa de venda é a mais **conservadora** do ponto de vista da saída de caixa: reconhece o compromisso pelo maior valor provável, evitando subestimar o custo. |
| **`receivable`** | **Compra** (`cotacaoCompra`) | Ao receber, a empresa **vende** a moeda recebida. A taxa de compra é a **coerente com a entrada** de caixa esperada: reconhece o recebível pelo valor que de fato se realizaria. |
| **`intercompany`** | **Mid** `(compra+venda)/2` | Operação **interna** ao grupo não cruza o spread de um dealer de mercado. O ponto médio é a valorização justa, sem penalizar nem favorecer artificialmente. **Premissa documentada** — o enunciado não especifica regra para intercompany. |

Implementação: `TipoExposicao` → `TipoTaxa` em `selecao_taxa.py`; a cotação normalizada expõe
`taxa_para(tipo)` (`models.py`), que devolve `taxa_compra`, `taxa_venda` ou o mid conforme o
caso. O tipo escolhido é **registrado** em cada conversão (`Conversao.tipo_taxa`), então a
decisão é auditável posição a posição (ver o campo `tipo_taxa` em
[`examples/consolidacao-exemplo.json`](examples/consolidacao-exemplo.json)).

**Taxa oficial de referência vs. taxa operacional.** A PTAX é uma taxa **oficial de
referência** (média calculada pelo BCB), não o preço que uma mesa fecharia numa operação real
(taxa **operacional**, que embute spread comercial, volume, horário). O motor usa referências
oficiais das duas fontes de propósito: são reproduzíveis, auditáveis e independentes de
relação bancária. Numa tesouraria real, a taxa operacional entraria no momento da execução; a
referência serve para **marcação, comparação e sinalização de risco** — que é o escopo aqui.

> Responde: item 9.2 (qual taxa do BCB em cada cenário) · item 9.3 (compra/venda na prática) ·
> item 8 (diferença compra/venda e quando cada uma se aplica; oficial vs. operacional).

---

## 3. PTAX e Frankfurter não são fontes equivalentes

Uma tesouraria compara **duas fontes** em vez de confiar numa só porque uma única fonte é um
**ponto cego**: não há como saber se uma cotação está atípica (erro de publicação, dia
ilíquido, defasagem) sem uma referência independente para confrontá-la. A divergência entre
fontes é, ela própria, um **sinal de risco**.

Mas — ponto central — **o desvio entre PTAX e Frankfurter não é apenas "diferença de
mercado".** Ele mistura pelo menos três componentes:

1. **Metodologia diferente.** A **PTAX/BCB** parte do **mercado interbancário brasileiro** e
   publica **compra e venda** (tem spread). A **Frankfurter/BCE** publica a **taxa de
   referência do BCE**, calculada às **16h CET** a partir do **mercado europeu**, como um
   **valor único** (mid, sem spread). São dois processos de cálculo distintos, sobre mercados
   distintos, em horários distintos.
2. **Spread vs. mid.** Como a PTAX tem lados e a Frankfurter não, comparar "BRL pela PTAX" com
   "BRL pela Frankfurter" já embute a diferença **compra/venda vs. ponto médio** — parte do
   desvio é estrutural, não movimento de preço.
3. **Data efetiva (quando há fallback).** Se as fontes recaem em datas efetivas diferentes
   (fim de semana/feriado resolvidos de forma independente), o desvio passa a incluir também
   **movimento entre dias distintos**. O motor sinaliza isso com
   `PosicaoAvaliada.datas_efetivas_divergem`.

Por isso o motor **preserva a informação metodológica** em vez de escondê-la: a cotação
normalizada carrega `possui_spread` (`True` para PTAX, `False` para Frankfurter), e a
divergência é apresentada como um **indicador a interpretar**, não como "erro" de uma das
fontes. A divergência percentual é calculada relativa à PTAX (âncora oficial no Brasil):
`abs(brl_ptax − brl_frankfurter) / brl_ptax × 100` (em pontos percentuais).

> Responde: item 9.4 (equivalência PTAX/Frankfurter; por que o desvio não é só mercado) ·
> item 8 (por que comparar fontes).

---

## 4. Fallback de data e moedas não suportadas

**Datas sem cotação** (fim de semana, feriado). Regra
(`domain/rules/fallback_data.py::resolver_data_efetiva`):

- **Direção backward:** retrocede dia a dia a partir da data solicitada até encontrar uma
  cotação, respeitando uma **janela máxima** (default **7 dias**, configurável via
  `MOTOR_JANELA_FALLBACK_DIAS` ou `--janela-dias`). Retroceder — nunca avançar — garante que
  **nunca se usa uma cotação do futuro** para marcar uma posição.
- **Se nada dentro da janela:** levanta `SemCotacaoNaJanela` — a posição fica **não avaliada**,
  em vez de usar uma taxa arbitrariamente defasada **em silêncio**.
- **Rastreável:** cada conversão registra `data_solicitada`, `data_efetiva`, `houve_fallback` e
  `defasagem_dias`. Cada fonte resolve seu fallback de forma independente, e a divergência de
  datas entre fontes é sinalizada (§3). Ver o exemplo real em
  [`examples/`](examples/consolidacao-exemplo.json) (domingo → sexta, defasagem 2 dias).

**Moedas não suportadas.** O conjunto de moedas é um **enum fechado** (`domain/enums.py::Moeda`).
Uma moeda fora do conjunto vira **erro de validação explícito** na entrada, não um
processamento silenciosamente errado. Se uma fonte específica não cobre uma moeda que ela
deveria, o adapter levanta `MoedaNaoSuportadaPelaFonte`, e a posição é reportada como **não
avaliada** com o motivo — transparência em vez de um zero enganoso.

> Responde: item 9.5 (moedas não suportadas / datas sem cotação).

---

## 5. Alertas, materialidade e priorização de risco

Nem todo desvio importa. **Materialidade** é a régua que separa ruído de risco relevante. O
motor sinaliza uma posição (`domain/rules/alertas.py`) quando:

- a **divergência percentual** entre as fontes é **> 1,5%**, **ou**
- a **divergência absoluta** é **> R$ 10.000**.

Decisões conscientes:

- **Semântica OU (não E).** Uma diferença pequena em % mas grande em BRL (posição enorme)
  importa tanto quanto uma diferença grande em % sobre uma posição pequena. São dois `if`
  independentes; uma posição pode gerar 0, 1 ou 2 alertas.
- **`>` estrito** ("acima de"): o limite exato não dispara, seguindo a redação do enunciado.
- **Comparação em precisão plena**, antes de qualquer arredondamento de exibição.
- **Limites configuráveis** — por flag de CLI (`--limite-percentual`, `--limite-absoluto`) ou
  em código (`ConfiguracaoAlerta`). O default (1,5% / R$ 10.000) é o do enunciado.

**Priorização.** Além do sinal binário de alerta, a consolidação ordena e destaca as **top 3
exposições** por divergência absoluta em BRL (`visao_consolidada.py::TopDivergencia`) — a
tesouraria olha primeiro onde o dinheiro está, não a lista inteira.

> Responde: item 8 (materialidade e priorização de risco).

---

## 6. Rastreabilidade e auditoria

**Toda conversão é autoexplicativa.** O modelo `Conversao` (`domain/resultado.py`) carrega a
trilha completa: `fonte`, `moeda`, `valor_origem`, `data_solicitada`, `data_efetiva`,
`houve_fallback`, `defasagem_dias`, `tipo_taxa`, `taxa_aplicada`, `valor_brl`. A rastreabilidade
é um **atributo do dado no domínio** — segue o resultado, não depende da borda que o exibe.

**Persistência para auditoria** (`adapters/outbound/persistence/`):

- **`consolidacao`** — o **estado atual** por chave natural (`data_referencia + hash_conjunto`),
  uma linha por execução lógica (UPSERT: preserva `criado_em`, avança `atualizado_em` e
  `num_processamentos`).
- **`consolidacao_historico`** — trilha **append-only**: cada reprocessamento adiciona uma
  linha, nunca sobrescreve. Responde à pergunta de auditoria "o que este conjunto valia quando
  foi processado pela 1ª vez, e o que mudou desde então?".

**Como garantiria em produção.** O desenho já separa "estado atual" de "histórico imutável",
que é a fundação de auditoria. Em produção, eu acrescentaria: identidade de quem/o que
disparou cada processamento; versão do código e das regras aplicadas em cada registro;
migrações de schema versionadas (Alembic) para evoluir sem perder trilha; e retenção/backup do
histórico. A chave natural + hash já garante que o mesmo insumo é reconhecível entre execuções.

> Responde: item 9.6 (rastreabilidade para auditoria em produção).

---

## 7. O que a solução faz para evitar resultados financeiros enganosos

Um relatório financeiro errado é pior que nenhum. Escolhas explícitas contra isso:

- **`Decimal` em todo dinheiro, nunca `float`.** A entrada rejeita `float` na validação (evita
  imprecisão binária silenciosa). As taxas são guardadas na **precisão da fonte**; a
  multiplicação é feita em **precisão plena**; só o **BRL final** é quantizado a 2 casas, com
  **`ROUND_HALF_UP`** (convenção financeira BR — não o banker's rounding default do Python, que
  distorceria totais).
- **Nada de zero enganoso.** Posições que não puderam ser convertidas ficam com status
  `PARCIAL`/`FALHA` e são **excluídas dos totais** — aparecem numa seção própria "não
  avaliadas" com o motivo. Um total nunca embute silenciosamente uma posição que falhou.
- **Fallback nunca silencioso.** Se não há cotação na janela, a posição não é "chutada" com uma
  taxa velha — é reportada como não avaliada (§4).
- **A divergência é exibida como sinal, não escondida** (§3), e a divergência de datas efetivas
  entre fontes é sinalizada — o número consolidado não finge uma precisão que não tem.
- **Comparações em precisão plena** antes de arredondar para exibição, para o alerta não
  depender de erro de arredondamento.

> Responde: item 9.7 (evitar resultados financeiros enganosos).

---

## 8. Uso de IA generativa

O projeto foi desenvolvido com **Claude Code**, de forma explícita e rastreada, sob uma
metodologia **spec-driven de três fases** para cada fatia: **(1)** brainstorm → spec → plano
(aprovados por mim antes de qualquer código); **(2)** implementação em **TDD** (teste que falha
→ código mínimo → refatora); **(3)** **revisão adversarial** por um agente customizado
(`lv10-dev`) que assume que o design está errado e caça falhas silenciosas.

O registro de **quais** skills e agentes foram usados, **em que fase** cada um entra e **por
quê** está em [`.claude/skills/README.md`](.claude/skills/README.md), com um registro por
fatia. A metodologia está codificada no `CLAUDE.md` e no skill de projeto
`desenvolvimento-de-fatia`. O único agente **customizado** é o `lv10-dev` (revisão adversarial
obrigatória); os demais são built-in do Claude Code.

> Responde: item 9.8 (onde e como usou IA generativa — seja específico).

---

## 9. Trade-offs e o que faria diferente com mais tempo

Escolhas de escopo, conscientes para o prazo de 5 dias:

- **CLI + API REST + dashboard (diferencial completo).** A CLI cumpre o entregável funcional; a
  **API REST** (FastAPI, adapter inbound irmão — `make api`, Swagger em `/docs`) e um **dashboard
  de tesouraria** que a consome foram implementados e sobem juntos via `docker compose up`
  (db + backend + frontend). Front-end é "diferencial", não requisito do enunciado.
- **Ciclo de vida dos clients HTTP na API.** Os providers (com os `httpx.Client`) são criados
  **uma vez** no `criar_app` e compartilhados por todas as requisições; só o envelope de cache é
  refeito por requisição (barato, preservando o `modo_live` por requisição). **Com mais tempo:**
  um `lifespan` fechando os clients no shutdown (hoje o SO os recupera na saída do processo).
- **Docker ainda é pré-requisito** (para o MySQL, em qualquer um dos dois caminhos de execução —
  ver README). **Com mais tempo:** um modo de demo **sem Docker** (ex.: SQLite) para eliminar
  esse pré-requisito e reduzir ainda mais o atrito do "roda em < 5 min".
- **Schema por `create_all`**, não migrações versionadas. **Com mais tempo:** Alembic, para
  evoluir o schema preservando a trilha de auditoria.
- **Relatório de console detalhado por posição.** Cada exposição mostra o valor original e —
  para cada fonte — a data efetiva, a taxa aplicada (com o tipo: compra/venda/mid) e o BRL
  convertido, além da divergência e do alerta. O JSON exportado segue como o registro exaustivo.
- **Posição líquida por natureza = soma bruta** (payable, receivable e intercompany somados
  separadamente), sem netting entre naturezas — fiel ao que o enunciado pede e mais
  transparente. **Com mais tempo:** ofereceria também a posição líquida real (receivable −
  payable) como visão opcional.
- **Concorrência fora de escopo** — assume escritor único na persistência.
- **Conjunto fechado de moedas** — moeda fora do conjunto é tratada e documentada, não
  implementada (decisão explícita do enunciado).

> Responde: item 10 — Autonomia (justificativa de trade-offs e o que faria diferente em
> produção).
