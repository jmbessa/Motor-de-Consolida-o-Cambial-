"use strict";

/* Motor de Consolidação Cambial — dashboard de tesouraria.
   JS puro, sem dependências. Consome a API REST (POST /consolidacoes, GET).
   Decimais chegam como STRING; formatamos a partir da string para não perder
   precisão. Campos vindos da entrada são escapados (anti-XSS) ao renderizar. */

// A API é publicada na 8000 do mesmo host onde o browser abre o dashboard.
const API_BASE = `${location.protocol}//${location.hostname || "localhost"}:8000`;

const DEFAULT_EXPOSICOES = [
  { id: "1", tipo: "payable", moeda: "USD", valor: "125000", vencimento: "2026-06-05", descricao: "AWS invoice" },
  { id: "2", tipo: "receivable", moeda: "EUR", valor: "98000", vencimento: "2026-06-08", descricao: "Marketplace settlement" },
  { id: "3", tipo: "payable", moeda: "GBP", valor: "45000", vencimento: "2026-06-12", descricao: "Vendor payment" },
  { id: "4", tipo: "intercompany", moeda: "USD", valor: "300000", vencimento: "2026-06-15", descricao: "Intercompany funding" },
  { id: "5", tipo: "receivable", moeda: "CAD", valor: "22000", vencimento: "2026-06-20", descricao: "Cross-border receivable" },
];

const LIMITE_PCT = 1.5;
const LIMITE_ABS = 10000;

// ---- Helpers ----
const $ = (id) => document.getElementById(id);

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const num = (s) => Number(s); // só para escala de pixels; nunca para exibir dinheiro

// "646462.50" -> centavos inteiros (soma exata de BRL 2 casas).
// Assume 2 casas: todo dinheiro sai quantizado do servidor (ROUND_HALF_UP);
// casas além da 2ª seriam truncadas — não deve ocorrer com o payload da API.
function centavos(s) {
  const neg = String(s).trim().startsWith("-");
  const [i, d = ""] = String(s).replace("-", "").split(".");
  const cents = parseInt(i || "0", 10) * 100 + parseInt((d + "00").slice(0, 2), 10);
  return neg ? -cents : cents;
}
function milhar(intStr) {
  return intStr.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}
function fmtCentsBRL(cents) {
  const neg = cents < 0;
  const abs = Math.abs(cents);
  const reais = milhar(String(Math.floor(abs / 100)));
  const dec = String(abs % 100).padStart(2, "0");
  return `${neg ? "-" : ""}R$ ${reais},${dec}`;
}
// BRL a partir da string decimal (preserva as 2 casas)
function fmtBRL(s) { return fmtCentsBRL(centavos(s)); }
// número estrangeiro (sem R$), preservando eventuais casas
function fmtNum(s) {
  const [i, d] = String(s).split(".");
  return milhar(i) + (d ? "," + d : "");
}
function fmtPct(s) { return num(s).toFixed(2).replace(".", ",") + "%"; }
function fmtTaxa(s) { return String(s).replace(".", ","); }

function svgEl(tag, attrs, text) {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (text != null) e.textContent = text;
  return e;
}

// Extrai uma mensagem legível do corpo de erro da API. Os handlers custom
// devolvem {erro: "..."}; a validação de corpo do FastAPI devolve
// {detail: [{loc, msg, ...}]} — uma LISTA, que precisa ser achatada.
function extrairErro(texto) {
  try {
    const j = JSON.parse(texto);
    if (j.erro) return j.erro;
    if (Array.isArray(j.detail)) {
      return j.detail
        .map((e) => `${(e.loc || []).slice(1).join(".") || "corpo"}: ${e.msg}`)
        .join(" · ");
    }
    if (j.detail) return j.detail;
  } catch (_) { /* corpo não-JSON: cai no texto cru */ }
  return texto;
}

// ---- Estado / ciclo ----
document.addEventListener("DOMContentLoaded", () => {
  const hoje = new Date().toISOString().slice(0, 10);
  $("data").value = hoje;
  $("exposicoes").value = JSON.stringify(DEFAULT_EXPOSICOES, null, 2);
  $("controls").addEventListener("submit", consolidar);
});

async function consolidar(ev) {
  ev.preventDefault();
  $("expos-msg").textContent = "";

  let exposicoes;
  try {
    exposicoes = JSON.parse($("exposicoes").value);
    if (!Array.isArray(exposicoes) || exposicoes.length === 0) {
      throw new Error("informe ao menos uma exposição (lista JSON não vazia)");
    }
  } catch (e) {
    $("expos-msg").textContent = "JSON de exposições inválido: " + e.message;
    $("expos").open = true;
    return;
  }

  const corpo = {
    exposicoes,
    data_referencia: $("data").value || undefined,
    modo_live: $("live").checked,
  };

  const btn = $("run");
  btn.disabled = true;
  setStatus("Consolidando exposições…");

  try {
    const resp = await fetch(`${API_BASE}/consolidacoes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
    });
    const texto = await resp.text();
    if (!resp.ok) {
      throw new Error(`API respondeu ${resp.status}: ${extrairErro(texto)}`);
    }
    render(JSON.parse(texto));
    setStatus("");
  } catch (e) {
    const dica = e.message.includes("Failed to fetch")
      ? `não foi possível falar com a API em ${API_BASE}. O backend está de pé? (docker compose up / make api)`
      : e.message;
    setStatus("Erro: " + dica, true);
    $("dash").hidden = true;
  } finally {
    btn.disabled = false;
  }
}

function setStatus(msg, isError) {
  const s = $("status");
  s.textContent = msg;
  s.classList.toggle("error", !!isError);
}

// ---- Render ----
function render(resultado) {
  const posicoes = resultado.posicoes || [];
  const consolidadas = posicoes.filter((p) => p.status === "consolidada");
  const visao = resultado.visao || {};

  renderKpis(visao, consolidadas);
  drawMatrix(consolidadas);
  drawCmp(visao.totais_por_moeda || []);
  renderTable(consolidadas);
  renderNaoAvaliadas(visao.posicoes_nao_avaliadas || []);

  const hashCurto = (resultado.hash_conjunto || "").slice(0, 12);
  $("meta").textContent =
    `data de referência ${resultado.data_referencia} · conjunto ${hashCurto}… · ` +
    `${consolidadas.length}/${posicoes.length} posições consolidadas`;

  $("dash").hidden = false;
}

function renderKpis(visao, consolidadas) {
  const totais = visao.totais_por_moeda || [];
  const totalCents = totais.reduce((acc, t) => acc + centavos(t.total_brl_ptax), 0);
  $("kpi-total").textContent = fmtCentsBRL(totalCents);
  $("kpi-total-foot").textContent = `${totais.length} moeda(s) · ${consolidadas.length} posição(ões)`;

  const emAlerta = consolidadas.filter((p) => (p.alertas || []).length > 0).length;
  $("kpi-alertas").textContent = String(emAlerta);

  const top = (visao.top_divergencias || [])[0];
  if (top) {
    $("kpi-maior").textContent = fmtBRL(top.divergencia_absoluta_brl);
    // textContent já é seguro (não precisa de esc; esc aqui exibiria entidades literais).
    $("kpi-maior-foot").textContent = `${fmtPct(top.divergencia_percentual)} · exposição ${top.exposicao_id}`;
  } else {
    $("kpi-maior").textContent = "—";
    $("kpi-maior-foot").textContent = "";
  }
}

// ---- Matriz de materialidade (assinatura) ----
function drawMatrix(consolidadas) {
  const svg = $("matrix");
  svg.textContent = "";
  const W = 520, H = 380, padL = 62, padR = 22, padT = 22, padB = 46;
  const plotW = W - padL - padR, plotH = H - padT - padB;

  const divs = consolidadas.map((p) => num(p.divergencia.percentual));
  const imps = consolidadas.map((p) => num(p.divergencia.absoluta_brl));
  const xMax = Math.max(LIMITE_PCT * 1.15, ...divs, 0.01) * 1.05;
  const yMax = Math.max(LIMITE_ABS * 1.15, ...imps, 1) * 1.05;

  const sx = (v) => padL + (v / xMax) * plotW;
  const sy = (v) => padT + plotH - (v / yMax) * plotH;

  // zona de risco (alto impacto E alta divergência)
  svg.appendChild(svgEl("rect", {
    x: sx(LIMITE_PCT), y: padT, width: padL + plotW - sx(LIMITE_PCT), height: sy(LIMITE_ABS) - padT,
    class: "risk-zone",
  }));

  // eixos
  svg.appendChild(svgEl("line", { x1: padL, y1: padT, x2: padL, y2: padT + plotH, class: "axis-line" }));
  svg.appendChild(svgEl("line", { x1: padL, y1: padT + plotH, x2: padL + plotW, y2: padT + plotH, class: "axis-line" }));

  // linhas de limite
  svg.appendChild(svgEl("line", { x1: sx(LIMITE_PCT), y1: padT, x2: sx(LIMITE_PCT), y2: padT + plotH, class: "limit-line" }));
  svg.appendChild(svgEl("line", { x1: padL, y1: sy(LIMITE_ABS), x2: padL + plotW, y2: sy(LIMITE_ABS), class: "limit-line" }));
  svg.appendChild(svgEl("text", { x: sx(LIMITE_PCT) + 4, y: padT + 11, class: "limit-label" }, "1,5%"));
  svg.appendChild(svgEl("text", { x: padL + 4, y: sy(LIMITE_ABS) - 4, class: "limit-label" }, "R$ 10k"));

  // ticks
  svg.appendChild(svgEl("text", { x: padL, y: padT + plotH + 16, class: "tick-label" }, "0%"));
  svg.appendChild(svgEl("text", { x: padL + plotW, y: padT + plotH + 16, class: "tick-label", "text-anchor": "end" }, fmtPct(String(xMax))));
  svg.appendChild(svgEl("text", { x: padL - 6, y: padT + plotH, class: "tick-label", "text-anchor": "end" }, "0"));
  svg.appendChild(svgEl("text", { x: padL - 6, y: padT + 4, class: "tick-label", "text-anchor": "end" }, "R$ " + milhar(String(Math.round(yMax)))));

  // rótulos de eixo
  svg.appendChild(svgEl("text", { x: padL + plotW / 2, y: H - 8, class: "axis-label", "text-anchor": "middle" }, "divergência entre fontes (%)"));
  const yl = svgEl("text", { x: 16, y: padT + plotH / 2, class: "axis-label", "text-anchor": "middle", transform: `rotate(-90 16 ${padT + plotH / 2})` }, "impacto absoluto (R$)");
  svg.appendChild(yl);

  // tamanho do ponto pela exposição (BRL PTAX)
  const valores = consolidadas.map((p) => num(p.conversao_ptax.valor_brl));
  const vMax = Math.max(...valores, 1);
  const raio = (v) => 5 + (Math.sqrt(v / vMax)) * 9;

  for (const p of consolidadas) {
    const x = sx(num(p.divergencia.percentual));
    const y = sy(num(p.divergencia.absoluta_brl));
    const alerta = (p.alertas || []).length > 0;
    const r = raio(num(p.conversao_ptax.valor_brl));
    const c = svgEl("circle", {
      cx: x, cy: y, r, "fill-opacity": 0.85, "stroke-width": 1.5,
      class: "pt " + (alerta ? "pt-alert" : "pt-ok"),
    });
    c.appendChild(svgEl("title", {},
      `Exposição ${p.exposicao.id} · ${p.exposicao.tipo} ${p.exposicao.moeda}\n` +
      `divergência ${fmtPct(p.divergencia.percentual)} · ${fmtBRL(p.divergencia.absoluta_brl)}\n` +
      `PTAX ${fmtBRL(p.conversao_ptax.valor_brl)} · Frankfurter ${fmtBRL(p.conversao_frankfurter.valor_brl)}`));
    svg.appendChild(c);
    // rótulo acima do ponto; se colar no topo do gráfico, joga para baixo
    const ly = (y - r - 3 < padT + 8) ? y + r + 11 : y - r - 3;
    svg.appendChild(svgEl("text", { x, y: ly, class: "pt-label" }, p.exposicao.id));
  }
}

// ---- PTAX × Frankfurter ----
function drawCmp(totais) {
  const svg = $("cmp");
  svg.textContent = "";
  const W = 360, H = 380, padL = 44, padR = 96, padT = 14, padB = 14;
  const plotW = W - padL - padR;
  const n = totais.length || 1;
  const rowH = (H - padT - padB) / n;
  const barMax = Math.max(...totais.flatMap((t) => [num(t.total_brl_ptax), num(t.total_brl_frankfurter)]), 1);
  const bw = (v) => (v / barMax) * plotW;

  totais.forEach((t, i) => {
    const yTop = padT + i * rowH;
    const h = Math.min(13, rowH / 3.2);
    const gap = 4;
    const yPtax = yTop + rowH / 2 - h - gap / 2;
    const yFrank = yTop + rowH / 2 + gap / 2;

    svg.appendChild(svgEl("text", { x: 0, y: yTop + rowH / 2 + 4, class: "bar-cur" }, t.moeda));

    svg.appendChild(svgEl("rect", { x: padL, y: yPtax, width: Math.max(1, bw(num(t.total_brl_ptax))), height: h, rx: 2, class: "bar-ptax" }));
    svg.appendChild(svgEl("rect", { x: padL, y: yFrank, width: Math.max(1, bw(num(t.total_brl_frankfurter))), height: h, rx: 2, class: "bar-frank" }));

    svg.appendChild(svgEl("text", { x: W, y: yPtax + h - 2, class: "bar-val" }, fmtBRL(t.total_brl_ptax)));
    svg.appendChild(svgEl("text", { x: W, y: yFrank + h - 2, class: "bar-val" }, fmtBRL(t.total_brl_frankfurter)));
  });
}

// ---- Tabela + drill-down ----
function renderTable(consolidadas) {
  const body = $("positions-body");
  body.textContent = "";

  consolidadas.forEach((p, idx) => {
    const alerta = (p.alertas || []).length > 0;
    const tr = document.createElement("tr");
    tr.className = "row-main" + (alerta ? " is-alert" : "");
    tr.tabIndex = 0;
    tr.setAttribute("role", "button");
    tr.setAttribute("aria-expanded", "false");
    tr.innerHTML =
      `<td class="col-id">${esc(p.exposicao.id)}</td>` +
      `<td class="txt">${esc(p.exposicao.tipo)}</td>` +
      `<td>${esc(p.exposicao.moeda)}</td>` +
      `<td class="num">${fmtNum(p.conversao_ptax.valor_origem)}</td>` +
      `<td class="num">${fmtBRL(p.conversao_ptax.valor_brl)}</td>` +
      `<td class="num">${fmtBRL(p.conversao_frankfurter.valor_brl)}</td>` +
      `<td class="num">${fmtPct(p.divergencia.percentual)}</td>` +
      `<td class="col-flag"><span class="flag ${alerta ? "flag-on" : "flag-off"}">${alerta ? "● sim" : "—"}</span>` +
      `<span class="caret" aria-hidden="true">▸</span></td>`;

    const drill = document.createElement("tr");
    drill.className = "row-drill";
    drill.hidden = true;
    const td = document.createElement("td");
    td.colSpan = 8;
    td.appendChild(trilha(p));
    drill.appendChild(td);

    const toggle = () => {
      const open = drill.hidden;
      drill.hidden = !open;
      tr.setAttribute("aria-expanded", String(open));
    };
    tr.addEventListener("click", toggle);
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
    });

    body.appendChild(tr);
    body.appendChild(drill);
  });
}

function trilha(p) {
  const box = document.createElement("div");
  box.className = "drill";
  box.appendChild(cardFonte("PTAX · BCB", "src-ptax", p.conversao_ptax));
  box.appendChild(cardFonte("Frankfurter · BCE", "src-frank", p.conversao_frankfurter));
  return box;
}

function cardFonte(titulo, cls, c) {
  const el = document.createElement("div");
  el.className = "trail " + cls;
  const badge = c.houve_fallback
    ? ` <span class="fallback-badge">fallback ${c.defasagem_dias}d</span>` : "";
  el.innerHTML =
    `<h4>${esc(titulo)}${badge}</h4>` +
    `<dl>` +
    `<dt>Data efetiva</dt><dd>${esc(c.data_efetiva)}</dd>` +
    `<dt>Tipo de taxa</dt><dd>${esc(c.tipo_taxa)}</dd>` +
    `<dt>Taxa aplicada</dt><dd>${fmtTaxa(c.taxa_aplicada)}</dd>` +
    `<dt>Valor origem</dt><dd>${fmtNum(c.valor_origem)} ${esc(c.moeda)}</dd>` +
    `<dt>Convertido</dt><dd>${fmtBRL(c.valor_brl)}</dd>` +
    `</dl>`;
  return el;
}

function renderNaoAvaliadas(lista) {
  const box = $("nao-avaliadas");
  const ul = $("nao-avaliadas-list");
  ul.textContent = "";
  if (!lista.length) { box.hidden = true; return; }
  box.hidden = false;
  for (const na of lista) {
    const motivos = [na.erro_ptax, na.erro_frankfurter].filter(Boolean).join(" · ");
    const li = document.createElement("li");
    li.textContent = `Exposição ${na.exposicao_id} (${na.status}): ${motivos}`;
    ul.appendChild(li);
  }
}
