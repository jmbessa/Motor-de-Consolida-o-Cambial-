# Motor de Consolidação Cambial para Tesouraria

> Recebe uma lista de **exposições cambiais** (compromissos financeiros futuros em moeda
> estrangeira — `payable`, `receivable`, `intercompany`) e produz uma **visão consolidada em
> BRL** usando **duas fontes de cotação independentes** (PTAX/BCB e Frankfurter/BCE),
> destacando **divergências** e **alertas de materialidade**.

Teste técnico de Engenharia de Tesouraria (VTEX). A prioridade do projeto é **decisões
conscientes e bem justificadas** — as justificativas técnicas e financeiras estão em
[`DECISOES.md`](DECISOES.md).

---

## Visão geral

O motor carrega exposições de um arquivo JSON local e, para cada uma:

1. Busca a cotação **PTAX** (BCB, OData) e a cotação de referência **Frankfurter** (BCE) para a moeda e a data.
2. Converte o valor para BRL por **cada fonte**, escolhendo o tipo de taxa conforme a natureza da exposição (payable → venda; receivable → compra; intercompany → mid — ver [`DECISOES.md`](DECISOES.md)).
3. Calcula a **divergência** absoluta e percentual entre as duas visões.
4. Consolida **totais por moeda**, **posição por natureza** e **top 3 divergências**, e gera **alertas** (> 1,5% **ou** > R$ 10.000 por posição, limites configuráveis).
5. **Persiste** o resultado em MySQL de forma **idempotente** (reprocessar a mesma data com o mesmo conjunto não duplica o registro atual; o histórico é append-only) e **exporta** o resultado completo em JSON.

Entrega: **CLI + relatório de console + JSON exportado + persistência MySQL** (núcleo), mais um
**diferencial** — uma **API REST** (FastAPI) e um **dashboard de tesouraria** que a consome,
tudo orquestrado por `docker compose up`. Arquitetura **Hexagonal** (`adapters → application →
domain`, domínio puro, sem I/O): CLI e API são adapters *inbound* irmãos sobre o mesmo núcleo.

---

## Pré-requisitos

| Ferramenta | Para quê | Observação |
|---|---|---|
| **Docker** | Rodar o MySQL (persistência) | Inicie o Docker Desktop **antes** de `make run-cli`/`make run-dashboard`. |
| **Python 3.12+** | Rodar a aplicação (venv) | — |
| **Make** | Porta de entrada única | Padrão em Linux/macOS; no Windows, disponível via Git Bash, Chocolatey ou WSL. |

> Duas formas de executar, **ambas via `make`** — e você pode rodar as duas **ao mesmo tempo**
> (ver [Rodando os dois ao mesmo tempo](#rodando-os-dois-ao-mesmo-tempo)): `make run-cli` (só
> precisa do MySQL — a CLI chama a lógica de negócio direto, em processo, **sem** passar pela
> API) e `make run-dashboard` (db + API + frontend, tudo em containers). Ambos abaixo.

---

## Rodar em menos de 5 minutos

### `make run-cli` — CLI (venv; só precisa do MySQL)

```bash
make install     # cria o venv (.venv) e instala as dependências
make run-cli      # sobe o MySQL (Docker), aplica o schema e roda a CLI com os defaults
```

`make install` é necessário aqui porque a CLI roda **no seu host**, via um venv Python local —
sem ele, não há `python` local com as dependências instaladas. (O dashboard, abaixo, **não**
precisa disso: ele roda inteiramente em containers, e o próprio `Dockerfile` do backend instala
as dependências **dentro da imagem** durante o build — é o Docker, não o seu host, quem instala.)

Imprime o **relatório no console** e grava o **JSON completo** em
`data/output/consolidacao_<data>.json`. (`make run` é um alias do mesmo alvo.)

**Prova instantânea, sem Docker** (valida o núcleo de cálculo/conversão):

```bash
make test        # 313 testes unitários (~1s), sem rede nem banco
```

Um exemplo de saída já vem versionado em [`examples/`](examples/), para inspeção sem rodar nada.

### `make run-dashboard` — Dashboard completo (diferencial, tudo em containers)

```bash
make run-dashboard   # sobe db + API + frontend em containers (docker compose up --build --wait)
```

Abra **http://localhost:8080** — escolha a data, clique **Consolidar** e leia os KPIs, a matriz
de materialidade e a tabela com drill-down. A API fica em **http://localhost:8000** (Swagger
interativo em **http://localhost:8000/docs**). Encerrar: `make down`.

> **Primeira execução (máquina fria):** baixa as imagens `mysql:8.0` e `nginx:alpine` e instala
> as deps do backend — 1–3 min conforme a rede; as execuções seguintes são rápidas. Se algo
> local já ocupa as portas `3306`/`8000`/`8080`, libere-as antes.

### Rodando os dois ao mesmo tempo

**Sim, dá para rodar `make run-cli` enquanto o `make run-dashboard` está de pé** — sem conflito:
a CLI **não abre porta nenhuma** (não é um servidor), e os dois caminhos apontam para o **mesmo
MySQL** (o da Fatia 8's `docker-compose.yml`), então uma consolidação feita pela CLI já aparece
para quem consultar a API/dashboard pela mesma `(data, hash_conjunto)` — não são bancos
separados. `make up`/`make migrate` (que `run-cli` usa por trás) são idempotentes: se o
container já estiver de pé (por causa do dashboard), eles só confirmam que está saudável, sem
reiniciar nada.

**Única ressalva:** não rode `make api` (serve a API do venv, fora de container, na porta
`8000`) enquanto `make run-dashboard` também estiver de pé — os dois disputariam a mesma porta.
Use `make api` só quando o dashboard **não** estiver rodando (ex.: para depurar a API isolada).

---

## Modo live vs. cache

O enunciado permite cache local, mas exige um **modo live demonstrável**. Ambos existem:

| Comando | Comportamento |
|---|---|
| `make run-cli` | **Cache-first**: na 1ª execução bate nas APIs reais e popula `data/cache/`; nas seguintes serve do cache (rápido, offline). |
| `make run-live` | **Sempre ao vivo**: ignora o cache e consulta PTAX e Frankfurter a cada execução (`--live`). |

Como `data/cache/` não é versionado, a **primeira** `make run-cli` de um checkout limpo já
consome as duas APIs de verdade.

---

## Uso da CLI

A CLI é um comando único (não há subcomando). Todas as opções têm default — rodar sem flags
consolida `data/exposicoes.json` para a data de hoje.

| Flag | Default | Descrição |
|---|---|---|
| `--arquivo` | `data/exposicoes.json` | Arquivo JSON de exposições. |
| `--data` | hoje | Data de referência (`YYYY-MM-DD`). **Reprocessamento por data.** |
| `--live` / `--cache` | `--cache` | Busca ao vivo (ignora o cache) vs. cache-first. |
| `--limite-percentual` | `1.5` | Limite percentual de alerta (configurável). |
| `--limite-absoluto` | `10000` | Limite absoluto em BRL de alerta (configurável). |
| `--janela-dias` | `7` | Janela do fallback de data (dias retrocedidos). |
| `--saida` | `data/output/consolidacao_{data}.json` | Caminho do JSON exportado. |

### Reprocessar uma data informada pelo usuário

Para rodar com flags customizadas, suba o banco e invoque a CLI a partir do venv apontando
para o MySQL local:

```bash
make up                       # garante o MySQL de pé (Docker)
make migrate                  # aplica o schema (idempotente)
```

Ative o venv e rode (o `MOTOR_DB_HOST=127.0.0.1` faz o venv do host achar o MySQL do container):

```bash
# Linux / macOS
source .venv/bin/activate
MOTOR_DB_HOST=127.0.0.1 python -m motor_cambial.adapters.inbound.cli.app \
  --data 2026-07-03 --live --limite-percentual 2.0
```

```powershell
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
$env:MOTOR_DB_HOST = "127.0.0.1"
python -m motor_cambial.adapters.inbound.cli.app --data 2026-07-03 --live --limite-percentual 2.0
```

Reprocessar a **mesma data com o mesmo conjunto de exposições** é **idempotente**: o registro
atual é sobrescrito (não duplicado) e o histórico de reprocessamentos é preservado
(append-only). Ver [Idempotência](DECISOES.md#6-rastreabilidade-e-auditoria).

---

## O que o relatório entrega

O relatório de console tem estas seções (cada uma omitida se vazia):

- **Posições** — um bloco por exposição: o valor original e, para **cada fonte** (PTAX e Frankfurter), a data efetiva, a taxa aplicada (com o tipo — compra/venda/mid) e o BRL convertido; mais a divergência (% e absoluta) e o alerta.
- **Totais por moeda** — soma em BRL por moeda, pelas duas fontes.
- **Posição líquida por natureza** — soma por `payable` / `receivable` / `intercompany` (âncora PTAX).
- **Top divergências** — as 3 exposições com maior diferença absoluta em BRL entre as fontes.
- **Posições não avaliadas** — exposições com status `PARCIAL`/`FALHA` e o motivo (moeda não suportada, sem cotação na janela, etc.), mantidas **fora** dos totais para não contaminar a consolidação.

O **JSON exportado** (`data/output/…json`) é o registro exaustivo: cada posição carrega as
duas conversões completas com a **trilha de rastreabilidade** (fonte, data efetiva, tipo de
taxa, se houve fallback e a defasagem em dias).

---

## API REST e dashboard (diferencial)

Além da CLI, o pipeline é exposto por uma **API REST** (FastAPI) e um **dashboard** que a
consome. `make run-dashboard` sobe os três containers; então:

- **Dashboard** — http://localhost:8080. Cabeçalho com data + toggle ao vivo/cache + Consolidar;
  KPIs (exposição total, alertas, maior divergência); **matriz de materialidade** (impacto R$ ×
  divergência %, com as linhas de limite e a zona de risco destacada); comparação **PTAX ×
  Frankfurter** por moeda; e a tabela de posições com **drill-down** da trilha de rastreabilidade.
- **API** — http://localhost:8000 · Swagger interativo em `/docs`.

| Método | Rota | O que faz |
|---|---|---|
| `POST` | `/consolidacoes` | Consolida (body: `exposicoes` + `data_referencia`/`modo_live`/limites) e persiste. |
| `GET` | `/consolidacoes/{data}/{hash}` | Resultado atual persistido (404 se ausente). |
| `GET` | `/consolidacoes/{data}/{hash}/historico` | Trilha append-only de reprocessamentos. |
| `GET` | `/health` | Status do serviço. |

Para servir só a API do venv (dev, fora de container): `make api` (uvicorn em :8000) — **não**
rode junto com `make run-dashboard` (conflito de porta 8000; ver
[Rodando os dois ao mesmo tempo](#rodando-os-dois-ao-mesmo-tempo)). CORS habilitado para o front.

---

## Arquitetura

Monólito modular, estilo **Hexagonal (Ports & Adapters)**. Regra de dependência inviolável:
`adapters → application → domain`. O **domínio é puro** (sem I/O, sem framework); as bordas o
implementam via ports (`Protocol`). Injeção de dependências manual em `composition_root.py`.

```
src/motor_cambial/
  domain/        # PURO: models, enums, rules/ (selecao_taxa, fallback_data, alertas,
                 #        divergencia, idempotencia), services/ (conversor, consolidador)
  ports/         # interfaces: cotacao_provider, resultado_repository
  application/   # use_cases/: consolidar_exposicoes, reprocessar_por_data
  adapters/
    inbound/cli/     # loader, relatório, app (comando `consolidar`)
    inbound/api/     # FastAPI: POST /consolidacoes, GET por (data,hash), histórico, /health
    outbound/        # ptax/, frankfurter/, cache/, persistence/ (MySQL)
  config.py          # thresholds, timeouts, modo live/cache, CORS, conexão do banco
  composition_root.py
frontend/        # dashboard estático (HTML/CSS/JS puro) servido por nginx
tests/           # unit/ (domínio, alvo do TDD) · integration/ (APIs + MySQL reais, opt-in)
data/            # exposicoes.json (entrada) · output/ (resultados, gerado) · cache/ (gerado)
examples/        # exemplo de output versionado
```

Detalhes e justificativas de cada decisão: [`DECISOES.md`](DECISOES.md).

---

## Testes

```bash
make test              # 313 unitários (sem rede/DB): cálculo, conversão, seleção de taxa,
                       #   fallback, alertas, divergência, idempotência, normalização, cache, API
make test-integration  # 9 de integração (opt-in): sobe o MySQL e bate nas APIs reais (CLI + API)
```

Os testes de integração são **opt-in** (marcador `integration`) e requerem a variável
`MOTOR_TEST_DB_URL` — `make test-integration` a configura e sobe o banco automaticamente.

---

## Regras de negócio (resumo)

| Regra | Comportamento | Justificativa completa |
|---|---|---|
| **Payables** | Taxa de **venda** (`cotacaoVenda`) do BCB | [DECISOES.md §2](DECISOES.md#2-seleção-de-taxa-por-tipo) |
| **Receivables** | Taxa de **compra** (`cotacaoCompra`) do BCB | [DECISOES.md §2](DECISOES.md#2-seleção-de-taxa-por-tipo) |
| **Intercompany** | **Mid** `(compra+venda)/2` (premissa documentada) | [DECISOES.md §2](DECISOES.md#2-seleção-de-taxa-por-tipo) |
| **Fallback de data** | Retrocede dia a dia até achar cotação (janela configurável); rastreável | [DECISOES.md §4](DECISOES.md#4-fallback-de-data-e-moedas-não-suportadas) |
| **Alertas** | > 1,5% **ou** > R$ 10.000 por posição; limites configuráveis | [DECISOES.md §5](DECISOES.md#5-alertas-materialidade-e-priorização-de-risco) |
| **Rastreabilidade** | Cada conversão registra fonte, data efetiva e tipo de taxa | [DECISOES.md §6](DECISOES.md#6-rastreabilidade-e-auditoria) |

---

## Configuração

Defaults versionados em `src/motor_cambial/config.py`, sobrescrivíveis por variável de
ambiente (prefixo `MOTOR_`) ou por um arquivo `.env` (ver [`.env.example`](.env.example)).
Exemplos: `MOTOR_MODO_LIVE`, `MOTOR_HTTP_TIMEOUT_S`, `MOTOR_JANELA_FALLBACK_DIAS`,
`MOTOR_DB_HOST`. Onde há flag de CLI equivalente (`--live/--cache`, `--janela-dias`,
`--limite-percentual`, `--limite-absoluto`), a **flag tem precedência** sobre a env var quando
informada; omitida, vale a env var (ou o default versionado).

---

## Uso de IA generativa

Este projeto foi desenvolvido com uso explícito e rastreado de IA generativa (Claude Code),
seguindo uma metodologia **spec-driven** de três fases (plano → TDD → revisão adversarial).
O registro de **quais** skills/agentes foram usados e **em que fase** está em
[`.claude/skills/README.md`](.claude/skills/README.md).

---

## Escopo, limitações e o que faria diferente

**Nesta entrega (consciente):**

- **CLI + API REST + dashboard.** A CLI cumpre o entregável funcional; a API REST e o dashboard
  (diferencial do enunciado) foram implementados e sobem juntos via `docker compose up`.
- **App conteinerizada.** Backend e frontend rodam em containers; o venv permanece como caminho
  de dev/CLI e para os testes.
- **Schema por `create_all`**, não por migrações versionadas (Alembic fora de escopo para o prazo).
- **Concorrência fora de escopo** — assume escritor único na persistência.
- **Moedas** restritas ao conjunto suportado pelas fontes (enum fechado; moeda fora do
  conjunto vira erro explícito e rastreável, não silencioso).

**Com mais tempo:** migrações versionadas (Alembic); providers no `lifespan` da API (ciclo de
vida dos clients HTTP — ver DECISOES §9); um modo de demo sem Docker; autenticação/multiusuário;
e opção de netting real por natureza. Detalhes em
[DECISOES.md §9](DECISOES.md#9-trade-offs-e-o-que-faria-diferente-com-mais-tempo).
