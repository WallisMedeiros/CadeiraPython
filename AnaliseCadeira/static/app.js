/* Interface web da Análise Estrutural de Cadeira.
   Todo o cálculo é feito em Python (nucleo/) pelo servidor; aqui só há
   leitura do formulário, chamadas à API e desenho dos resultados. */
(() => {
  "use strict";

  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const ARMAZ = "cadeira.entradas.v1";

  // ------------------------------------------------------------------ API
  const API = {
    async opcoes() {
      const r = await fetch("api/opcoes");
      if (!r.ok) throw new Error("Não foi possível carregar as opções do servidor.");
      return r.json();
    },
    async analisar(entradas) {
      const r = await fetch("api/analisar", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(entradas),
      });
      const j = await r.json().catch(() => ({ erros: ["Resposta inválida do servidor."] }));
      if (!r.ok) return { erros: j.erros || ["Erro no servidor."] };
      return j;
    },
    async relatorio(payload) {
      const r = await fetch("api/relatorio", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error((j.erros || ["Não foi possível gerar o PDF."]).join(" "));
      }
      return r.blob();
    },
  };

  // ------------------------------------------------------------------ formatação
  const nf = {};
  const fmt = (v, casas = 2) => {
    if (v === null || v === undefined || !isFinite(v)) return "∞";
    nf[casas] ||= new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
    return nf[casas].format(Math.abs(v) < 0.5 * 10 ** -casas ? 0 : v);
  };
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // "σ_adm" -> σ<sub>adm</sub>
  const subHtml = (t) => esc(t).replace(/([A-Za-zσδελΣ0-9₀])_([A-Za-z0-9áíéêç,]+)/g, "$1<sub>$2</sub>");
  const subSvg = (t) => esc(t).replace(/([A-Za-zσδελΣ])_([A-Za-z0-9áíéç,]+)/g,
    '$1<tspan baseline-shift="sub" font-size="75%">$2</tspan>');

  // ------------------------------------------------------------------ campos
  const NUMERICOS = ["massa_kg", "altura_mm", "largura_mm", "profundidade_mm", "tensao_personalizada_mpa",
    "e_personalizado_gpa", "espessura_perna_mm", "altura_secao_perna_mm", "parede_mm", "b_travessa_mm",
    "h_travessa_mm", "parede_travessa_mm", "fator_dinamico", "coef_horizontal", "excentricidade_mm",
    "fator_seguranca", "k_flambagem"];
  const SELECTS = ["material", "tipo_secao", "tipo_secao_travessa"];
  const ROT_B = {
    "Quadrada maciça": ["Lado", "a"], "Retangular maciça": ["Largura", "b"], "Circular maciça": ["Diâmetro", "d"],
    "Tubo quadrado": ["Lado", "a"], "Tubo retangular": ["Largura", "b"], "Tubo circular": ["Diâmetro ext.", "D"],
  };
  let OPC = null;
  let PADRAO = null;
  let ultimo = null;

  function lerEntradas() {
    const e = {};
    NUMERICOS.forEach((id) => { e[id] = $("#" + id).value === "" ? null : Number($("#" + id).value); });
    SELECTS.forEach((id) => { e[id] = $("#" + id).value; });
    e.travessa_igual_perna = $("#travessa_igual_perna").checked;
    return e;
  }
  function aplicarEntradas(e) {
    NUMERICOS.forEach((id) => { if (e[id] !== undefined && e[id] !== null) $("#" + id).value = e[id]; });
    SELECTS.forEach((id) => { if (e[id]) $("#" + id).value = e[id]; });
    if (typeof e.travessa_igual_perna === "boolean") $("#travessa_igual_perna").checked = e.travessa_igual_perna;
    $("#massa_range").value = $("#massa_kg").value;
  }
  function salvar(e) { try { localStorage.setItem(ARMAZ, JSON.stringify(e)); } catch { /* sem armazenamento */ } }
  function carregar() { try { return JSON.parse(localStorage.getItem(ARMAZ) || "null"); } catch { return null; } }

  function atualizarVisibilidade() {
    const tubos = new Set(OPC.tubos), alt = new Set(OPC.com_altura);
    const mat = $("#material").value;
    $("#bloco-pers").hidden = mat !== "Personalizado";
    const m = OPC.materiais.find((x) => x.nome === mat);
    $("#info-material").innerHTML = m
      ? `σ<sub>lim</sub> <b>${fmt(m.tensao_limite_mpa, 0)} MPa</b> · E <b>${fmt(m.E_gpa, 1)} GPa</b> · ${esc(m.criterio)}`
      : "Informe a tensão limite e o módulo de elasticidade do material.";

    const ts = $("#tipo_secao").value;
    $("#c-h-perna").hidden = !alt.has(ts);
    $("#c-t-perna").hidden = !tubos.has(ts);
    $("#rot-b").innerHTML = `${ROT_B[ts][0]} <small>${ROT_B[ts][1]}</small>`;

    const igual = $("#travessa_igual_perna").checked;
    $("#bloco-trav").hidden = igual;
    const tt = $("#tipo_secao_travessa").value;
    $("#c-h-trav").hidden = !alt.has(tt);
    $("#c-t-trav").hidden = !tubos.has(tt);
    $("#rot-bt").innerHTML = `${ROT_B[tt][0]} <small>${ROT_B[tt][1]}</small>`;

    const e = lerEntradas();
    $("#resumo-param").textContent =
      `φ ${fmt(e.fator_dinamico, 1)} · μ ${fmt(e.coef_horizontal, 2)} · e ${fmt(e.excentricidade_mm, 0)} · FS ${fmt(e.fator_seguranca, 1)} · K ${fmt(e.k_flambagem, 1)}`;
  }

  // ------------------------------------------------------------------ cálculo
  let seq = 0, timer = null;
  function agendar() {
    atualizarVisibilidade();
    clearTimeout(timer);
    timer = setTimeout(calcular, 220);
  }
  async function calcular() {
    const meu = ++seq;
    const e = lerEntradas();
    salvar(e);
    const area = $(".resultados");
    area.classList.add("calculando");
    let r;
    try { r = await API.analisar(e); } catch { r = { erros: ["Sem conexão com o servidor de cálculo."] }; }
    if (meu !== seq) return;
    area.classList.remove("calculando");
    if (r.erros) return mostrarErros(r.erros);
    area.classList.remove("invalido");
    ultimo = { entradas: e, r };
    render(e, r);
  }

  function mostrarErros(erros) {
    $(".resultados").classList.add("invalido");
    const v = $("#veredito");
    v.dataset.estado = "erro";
    $("#ver-titulo").textContent = "Dados inválidos";
    $("#ver-sub").textContent = "Corrija os campos abaixo para recalcular.";
    $("#erros").hidden = false;
    $("#erros").innerHTML = erros.map((x) => `<li>${esc(x)}</li>`).join("");
  }

  // ------------------------------------------------------------------ render
  function render(e, r) {
    const v = $("#veredito");
    $("#erros").hidden = true;
    v.dataset.estado = r.segura ? "ok" : "falha";
    $("#ver-titulo").textContent = r.segura ? "Cadeira segura" : "Cadeira não segura";
    $("#ver-sub").textContent = r.segura
      ? `Suporta ${fmt(e.massa_kg, 0)} kg com FS ${fmt(e.fator_seguranca, 1)} em todas as verificações · ${r.material.nome}`
      : `Falha por ${r.motivos.join(", ")} · ${r.material.nome}`;
    $("#massa-max").textContent = fmt(r.verificacao.massa_maxima, 1);
    $("#massa-crit").textContent = `Elemento crítico: ${r.elemento_critico.toLowerCase()}`;

    const ver = r.verificacao, adm = ver.sigma_adm_mpa, fs = e.fator_seguranca;
    const checks = [
      { nome: "Pernas · flexo-compressão", ok: ver.ok_perna, valor: `${fmt(r.perna.sigma_max_mpa)} <small>MPa</small>`,
        uso: r.perna.sigma_max_mpa / adm, leg: `σ ≤ ${fmt(adm)} MPa` },
      { nome: "Travessa · flexão", ok: ver.ok_travessa, valor: `${fmt(r.travessa.sigma_mpa)} <small>MPa</small>`,
        uso: r.travessa.sigma_mpa / adm, leg: `σ ≤ ${fmt(adm)} MPa` },
      { nome: "Flambagem · Euler", ok: ver.ok_flambagem, valor: `${fmt(ver.fs_flambagem, 1)} <small>P<sub>cr</sub>/N</small>`,
        uso: ver.fs_flambagem ? fs / ver.fs_flambagem : 0, leg: `≥ ${fmt(fs, 1)}` },
      { nome: "Tombamento", ok: !r.reacoes.tomba, valor: `${fmt(r.reacoes.R_T_total, 0)} <small>N atrás</small>`,
        uso: r.reacoes.R_D_total / r.cargas.W, leg: "R<sub>T,tot</sub> ≥ 0" },
    ];
    $("#checks").innerHTML = checks.map((c) => `
      <li class="check">
        <div class="check-topo"><span class="check-nome">${c.nome}</span>
          <span class="pilula ${c.ok ? "ok" : "falha"}">${c.ok ? "Atende" : "Não atende"}</span></div>
        <div class="check-valor">${c.valor}</div>
        <div class="uso ${c.ok ? "" : "falha"}" role="img" aria-label="Aproveitamento ${fmt(c.uso * 100, 0)}%"><i style="width:${Math.min(Math.max(c.uso, 0), 1) * 100}%"></i></div>
        <div class="uso-leg"><span>uso ${fmt(c.uso * 100, 0)}%</span><span>${c.leg}</span></div>
      </li>`).join("");

    dl("#dados-modelo", [
      ["Peso estático P₀ = m·g", `${fmt(r.cargas.peso_estatico, 1)} N`],
      ["Carga de projeto W = P₀·φ", `${fmt(r.cargas.W, 1)} N`],
      ["Força horizontal F_H = μ·W", `${fmt(r.cargas.F_H, 1)} N`],
      ["Reação por perna dianteira R_D", `${fmt(r.reacoes.R_D, 1)} N`],
      ["Reação por perna traseira R_T", `${fmt(r.reacoes.R_T, 1)} N`],
      ["Horizontal em cada pé h", `${fmt(r.cargas.h, 2)} N`],
    ]);
    dl("#dados-perna", [
      ["Esforço normal N", `${fmt(r.perna.N, 1)} N`],
      ["Momento máximo M = h·H", `${fmt(r.perna.M, 2)} N·m`],
      ["σ_N = N/A", `${fmt(r.perna.sigma_axial_mpa, 3)} MPa`],
      ["σ_M = M/W", `${fmt(r.perna.sigma_flexao_mpa, 3)} MPa`],
      ["σ_máx = σ_N + σ_M", `${fmt(r.perna.sigma_max_mpa, 3)} MPa`],
      ["Deformação ε", `${fmt(r.perna.deformacao * 1e6, 1)} με`],
      ["Encurtamento δ_N", `${fmt(r.perna.delta_axial_mm, 4)} mm`],
      ["Deslocamento do pé δ_H", `${fmt(r.perna.delta_lateral_mm, 4)} mm`],
      ["Carga crítica P_cr", `${fmt(r.perna.P_cr, 0)} N`],
      ["Esbeltez λ", fmt(r.perna.esbeltez, 1)],
    ]);
    dl("#dados-travessa", [
      ["Carga Q = W/2", `${fmt(r.travessa.Q, 1)} N`],
      ["Posição a", `${fmt(r.travessa.a_mm, 0)} mm`],
      ["R_A (traseira)", `${fmt(r.travessa.R_A, 1)} N`],
      ["R_B (dianteira)", `${fmt(r.travessa.R_B, 1)} N`],
      ["M_máx = Q·a·b/P", `${fmt(r.travessa.M, 2)} N·m`],
      ["σ = M_máx/W", `${fmt(r.travessa.sigma_mpa, 3)} MPa`],
      ["Flecha máxima δ", `${fmt(r.travessa.delta_mm, 4)} mm`],
      ["Deformação ε", `${fmt(r.travessa.deformacao * 1e6, 1)} με`],
    ]);

    $("#svg-lateral").innerHTML = desenhoLateral(e, r);
    $("#svg-superior").innerHTML = desenhoSuperior(e, r);
    $("#svg-perna").innerHTML = desenhoPerna(e, r);
    $("#svg-travessa").innerHTML = desenhoTravessa(e, r);
    $("#svg-tensoes").innerHTML = desenhoTensoes(r);
    $("#secoes-info").innerHTML = cartaoSecao("Seção da perna", r.secao) +
      (e.travessa_igual_perna ? "" : cartaoSecao("Seção da travessa", r.secao_travessa));
    renderMemorial(r);
  }

  function dl(sel, pares) {
    $(sel).innerHTML = pares.map(([k, v]) => `<div><dt>${subHtml(k)}</dt><dd>${v}</dd></div>`).join("");
  }

  function renderMemorial(r) {
    const cls = (t) => (/^(ATENDE|CADEIRA SEGURA|OK)/.test(t) ? "r-ok" : /^(NÃO ATENDE|CADEIRA NÃO SEGURA|TOMBA)/.test(t) ? "r-falha" : "");
    $("#memorial").innerHTML = r.memorial.map((s) => `
      <section class="memo-sec"><h3>${esc(s.titulo)}</h3>
        <div class="tabela-rola"><table class="memo">
          <colgroup><col class="c1"><col class="c2"><col class="c3"><col></colgroup>
          <thead><tr><th>Descrição</th><th>Fórmula</th><th>Substituição</th><th>Resultado</th></tr></thead>
          <tbody>${s.passos.map((p) => `<tr><td>${esc(p.descricao)}</td><td>${subHtml(p.formula)}</td>
            <td>${subHtml(p.substituicao)}</td><td class="${cls(p.resultado)}">${subHtml(p.resultado)}</td></tr>`).join("")}</tbody>
        </table></div></section>`).join("");
  }

  // ------------------------------------------------------------------ SVG utilitários
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const svg = (w, h, corpo, rot = "") =>
    `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(rot)}" xmlns="http://www.w3.org/2000/svg">${corpo}</svg>`;
  const txt = (x, y, t, cls = "t", extra = "") => `<text x="${x}" y="${y}" class="${cls}" ${extra}>${subSvg(t)}</text>`;
  function seta(x1, y1, x2, y2, cor, lw = 2) {
    const ang = Math.atan2(y2 - y1, x2 - x1), L = 10, a = 0.42;
    const p1 = [x2 - L * Math.cos(ang - a), y2 - L * Math.sin(ang - a)];
    const p2 = [x2 - L * Math.cos(ang + a), y2 - L * Math.sin(ang + a)];
    const xe = x2 - 7 * Math.cos(ang), ye = y2 - 7 * Math.sin(ang);
    return `<line x1="${x1}" y1="${y1}" x2="${xe}" y2="${ye}" stroke="${cor}" stroke-width="${lw}"/>` +
      `<polygon points="${x2},${y2} ${p1} ${p2}" fill="${cor}"/>`;
  }
  function cota(x1, y1, x2, y2) {
    const ang = Math.atan2(y2 - y1, x2 - x1), L = 6, a = 0.5, c = css("--tinta-3");
    const ponta = (x, y, s) => `<polyline points="${x + s * L * Math.cos(ang - a)},${y + s * L * Math.sin(ang - a)} ${x},${y} ${x + s * L * Math.cos(ang + a)},${y + s * L * Math.sin(ang + a)}" class="cota"/>`;
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="cota"/>` + ponta(x1, y1, 1) + ponta(x2, y2, -1);
  }
  function ticks(min, max, n = 4) {
    if (min === max) { const d = Math.abs(min) || 1; min -= d; max += d; }
    const passoBruto = (max - min) / n, mag = 10 ** Math.floor(Math.log10(passoBruto));
    const passo = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((p) => p >= passoBruto);
    const out = [];
    for (let v = Math.ceil(min / passo) * passo; v <= max + passo * 1e-9; v += passo) out.push(Math.abs(v) < passo * 1e-9 ? 0 : v);
    return { out, passo };
  }
  const casasPara = (passo) => Math.max(0, Math.min(4, -Math.floor(Math.log10(passo) + 1e-9)));

  // ------------------------------------------------------------------ vista lateral
  function desenhoLateral(e, r) {
    const W = 560, Ht = 470, gy = 330, mxL = 112, mxR = 92;
    const H = e.altura_mm, P = e.profundidade_mm, t = e.espessura_perna_mm;
    const s = Math.min((W - mxL - mxR) / P, (gy - 105) / (H + t), (gy - 22) / (1.9 * H + t));
    const x0 = mxL + ((W - mxL - mxR) - s * P) / 2, x1 = x0 + s * P;
    const tw = Math.max(s * t, 5), seatY = gy - s * (H + t), seatH = Math.max(s * t, 6);
    const N = css("--c-n"), V = css("--c-v"), F = css("--falha");
    let g = "";
    // piso
    g += `<line x1="${x0 - 90}" y1="${gy}" x2="${x1 + 70}" y2="${gy}" class="chao"/>`;
    for (let x = x0 - 90; x < x1 + 70; x += 14) g += `<line x1="${x}" y1="${gy}" x2="${x - 8}" y2="${gy + 8}" class="chao"/>`;
    // peças
    g += `<rect x="${x0 - tw / 2}" y="${seatY + seatH}" width="${tw}" height="${gy - seatY - seatH}" class="peca"/>`;
    g += `<rect x="${x1 - tw / 2}" y="${seatY + seatH}" width="${tw}" height="${gy - seatY - seatH}" class="peca"/>`;
    g += `<rect x="${x0 - tw / 2}" y="${seatY}" width="${x1 - x0 + tw}" height="${seatH}" class="peca2"/>`;
    g += `<rect x="${x0 - tw / 2}" y="${seatY - s * 0.9 * H}" width="${tw}" height="${s * 0.9 * H}" class="peca"/>`;
    // carga W
    const xc = x0 + s * (P / 2 + e.excentricidade_mm);
    g += seta(xc, seatY - 78, xc, seatY - 3, F, 2.4);
    g += txt(xc + 9, seatY - 60, `W = ${fmt(r.cargas.W, 0)} N`, "t tb");
    // força horizontal
    if (r.cargas.F_H > 0) {
      const yh = seatY + seatH / 2;
      g += seta(x0 - tw / 2 - 72, yh, x0 - tw / 2 - 3, yh, V, 2.2);
      g += txt(x0 - tw / 2 - 74, yh - 9, `F_H = ${fmt(r.cargas.F_H, 0)} N`, "t");
    }
    // reações
    const corT = r.reacoes.tomba ? F : N;
    g += seta(x0, gy + 62, x0, gy + 4, corT, 2.2) + seta(x1, gy + 62, x1, gy + 4, N, 2.2);
    g += txt(x0 - 10, gy + 40, `R_T = ${fmt(r.reacoes.R_T_total, 0)} N`, "t tb", 'text-anchor="end"');
    g += txt(x0 - 10, gy + 56, "2 pernas", "t2", 'text-anchor="end"');
    g += txt(x1 + 10, gy + 40, `R_D = ${fmt(r.reacoes.R_D_total, 0)} N`, "t tb");
    g += txt(x1 + 10, gy + 56, "2 pernas", "t2");
    // cotas
    g += cota(x0, gy + 90, x1, gy + 90) + txt((x0 + x1) / 2, gy + 84, `P = ${fmt(P, 0)} mm`, "t2", 'text-anchor="middle"');
    const xd = x1 + 44;
    g += cota(xd, gy, xd, seatY + seatH) + txt(xd + 14, (gy + seatY) / 2, `H = ${fmt(H, 0)} mm`, "t2",
      `text-anchor="middle" transform="rotate(-90 ${xd + 14} ${(gy + seatY) / 2})"`);
    g += txt(x1 + 70, gy + 120, "frente →", "t2", 'text-anchor="end"');
    return svg(W, Ht, g, "Vista lateral da cadeira com cargas e reações");
  }

  // ------------------------------------------------------------------ vista superior
  function desenhoSuperior(e, r) {
    const W = 460, Ht = 430, P = e.profundidade_mm, L = e.largura_mm, t = e.espessura_perna_mm;
    const s = Math.min((W - 170) / P, (Ht - 150) / L);
    const x0 = 95 + ((W - 170) - s * P) / 2, y0 = 70 + ((Ht - 150) - s * L) / 2;
    const x1 = x0 + s * P, y1 = y0 + s * L, tw = Math.max(s * t, 8);
    const N = css("--c-n"), F = css("--falha");
    let g = `<rect x="${x0 - tw / 2}" y="${y0 - tw / 2}" width="${x1 - x0 + tw}" height="${y1 - y0 + tw}" class="contorno" rx="2"/>`;
    const pernas = [[x0, y0, "T", r.reacoes.R_T], [x0, y1, "T", r.reacoes.R_T], [x1, y0, "D", r.reacoes.R_D], [x1, y1, "D", r.reacoes.R_D]];
    pernas.forEach(([x, y, n, R]) => {
      g += `<rect x="${x - tw / 2}" y="${y - tw / 2}" width="${tw}" height="${tw}" class="peca"/>`;
      const acima = y === y0;
      g += txt(x, acima ? y - tw / 2 - 10 : y + tw / 2 + 20, `${n}: ${fmt(R, 0)} N`, "t tb",
        `text-anchor="middle" fill="${R < 0 ? F : N}" style="fill:${R < 0 ? F : N}"`);
    });
    const xc = x0 + s * (P / 2 + e.excentricidade_mm), yc = (y0 + y1) / 2;
    g += `<circle cx="${xc}" cy="${yc}" r="7" fill="${F}" stroke="${css("--folha-2")}" stroke-width="3"/>`;
    g += txt(xc, yc - 14, "centro da carga", "t2", 'text-anchor="middle"');
    g += cota(x0, y1 + 46, x1, y1 + 46) + txt((x0 + x1) / 2, y1 + 66, `P = ${fmt(P, 0)} mm`, "t2", 'text-anchor="middle"');
    const xl = x0 - 40;
    g += cota(xl, y0, xl, y1) + txt(xl - 10, yc, `L = ${fmt(L, 0)} mm`, "t2",
      `text-anchor="middle" transform="rotate(-90 ${xl - 10} ${yc})"`);
    g += txt(x1 + 46, yc, "FRENTE →", "t2", `text-anchor="middle" letter-spacing="2" transform="rotate(90 ${x1 + 46} ${yc})"`);
    return svg(W, Ht, g, "Vista superior com a reação em cada perna");
  }

  // ------------------------------------------------------------------ diagramas da perna
  function desenhoPerna(e, r) {
    const W = 780, Ht = 360, top = 52, bot = 300, H = e.altura_mm;
    const d = r.diagramas.perna;
    const paineis = [
      { nome: "Esforço normal N", un: "N  (− compressão)", val: d.N, cor: css("--c-n"), casas: 1 },
      { nome: "Esforço cortante V", un: "N", val: d.V, cor: css("--c-v"), casas: 2 },
      { nome: "Momento fletor M", un: "N·m", val: d.M, cor: css("--c-m"), casas: 2 },
    ];
    const larg = 232, esq0 = 62, gap = 22;
    const ys = (y) => bot - (y / H) * (bot - top);
    const yt = ticks(0, H, 4);
    let g = "";
    paineis.forEach((p, i) => {
      const L = esq0 + i * (larg + gap), R = L + larg - 14;
      const vmax = Math.max(...p.val), vmin = Math.min(...p.val), lim = Math.max(Math.abs(vmax), Math.abs(vmin), 1e-9) * 1.3;
      const a = Math.min(-0.15 * lim, vmin * 1.3), b = Math.max(0.15 * lim, vmax * 1.3);
      const xs = (v) => L + ((v - a) / (b - a)) * (R - L);
      yt.out.forEach((v) => { g += `<line x1="${L}" y1="${ys(v)}" x2="${R}" y2="${ys(v)}" class="grade-l"/>`; });
      const xt = ticks(a, b, 3);
      xt.out.forEach((v) => {
        g += `<line x1="${xs(v)}" y1="${top}" x2="${xs(v)}" y2="${bot}" class="grade-l"/>`;
        g += txt(xs(v), bot + 18, fmt(v, casasPara(xt.passo)), "t2", 'text-anchor="middle"');
      });
      if (i === 0) {
        yt.out.forEach((v) => { g += txt(L - 8, ys(v) + 4, fmt(v, 0), "t2", 'text-anchor="end"'); });
        g += txt(16, (top + bot) / 2, "y — altura a partir do pé [mm]", "t2",
          `text-anchor="middle" transform="rotate(-90 16 ${(top + bot) / 2})"`);
      }
      const pts = d.y_mm.map((y, k) => `${xs(p.val[k])},${ys(y)}`).join(" ");
      g += `<polygon points="${xs(0)},${ys(0)} ${pts} ${xs(0)},${ys(H)}" fill="${p.cor}" fill-opacity=".16"/>`;
      g += `<polyline points="${pts}" fill="none" stroke="${p.cor}" stroke-width="2.4"/>`;
      g += `<line x1="${xs(0)}" y1="${top - 4}" x2="${xs(0)}" y2="${bot}" class="eixo"/>`;
      const kk = p.val.length - 1; // máximo no engaste (y = H)
      const vk = p.val[kk];
      g += `<circle cx="${xs(vk)}" cy="${ys(d.y_mm[kk])}" r="3.5" fill="${p.cor}"/>`;
      g += txt(xs(vk) + (vk < 0 ? -6 : 6), ys(d.y_mm[kk]) - 9, fmt(vk, p.casas), "t tb", `text-anchor="${vk < 0 ? "end" : "start"}"`);
      g += `<rect x="${L}" y="14" width="10" height="10" rx="2" fill="${p.cor}"/>`;
      g += txt(L + 16, 23, p.nome, "tt");
      g += txt((L + R) / 2, bot + 38, `[${p.un}]`, "t2", 'text-anchor="middle"');
    });
    return svg(W, Ht, g, "Diagramas de esforço normal, cortante e momento fletor na perna");
  }

  // ------------------------------------------------------------------ diagramas da travessa
  function desenhoTravessa(e, r) {
    const W = 780, L = 78, R = 752, P = e.profundidade_mm, a = r.travessa.a_mm;
    const xs = (x) => L + (x / P) * (R - L);
    const T = r.travessa, Fc = css("--falha"), cN = css("--c-n");
    let g = "";
    // esquema
    const yb = 82;
    g += txt(L - 70, 22, "Carregamento", "tt");
    g += `<line x1="${xs(0)}" y1="${yb}" x2="${xs(P)}" y2="${yb}" stroke="${css("--peca-2")}" stroke-width="8"/>`;
    [0, P].forEach((x) => { g += `<polygon points="${xs(x)},${yb + 5} ${xs(x) - 9},${yb + 20} ${xs(x) + 9},${yb + 20}" fill="${css("--tinta-2")}"/>`; });
    g += seta(xs(a), yb - 54, xs(a), yb - 6, Fc, 2.4) + txt(xs(a) + 9, yb - 38, `Q = ${fmt(T.Q, 1)} N`, "t tb");
    g += seta(xs(0), yb + 62, xs(0), yb + 24, cN, 2) + txt(xs(0) + 10, yb + 52, `R_A = ${fmt(T.R_A, 1)} N · traseira`, "t");
    g += seta(xs(P), yb + 62, xs(P), yb + 24, cN, 2) + txt(xs(P) - 10, yb + 52, `R_B = ${fmt(T.R_B, 1)} N · dianteira`, "t", 'text-anchor="end"');

    function painel(y0, alt, titulo, un, pts, cor, rot, inverter) {
      // inverter: valores positivos desenhados para baixo
      const vals = pts.map((p) => p[1]);
      let mn = Math.min(0, ...vals), mx = Math.max(0, ...vals);
      const pad = (mx - mn || 1) * 0.28; mn -= pad * (inverter ? 0.35 : 1); mx += pad * (inverter ? 1 : 0.35);
      if (!inverter && mn === 0) mn = -pad * 0.35;
      const ys = (v) => inverter ? y0 + ((v - mn) / (mx - mn)) * alt : y0 + alt - ((v - mn) / (mx - mn)) * alt;
      let s = txt(L - 70, y0 - 14, titulo, "tt");
      const tk = ticks(mn, mx, 3);
      tk.out.forEach((v) => {
        s += `<line x1="${L}" y1="${ys(v)}" x2="${R}" y2="${ys(v)}" class="grade-l"/>`;
        s += txt(L - 8, ys(v) + 4, fmt(v, casasPara(tk.passo)), "t2", 'text-anchor="end"');
      });
      [0, P / 4, P / 2, 3 * P / 4, P].forEach((x) => { s += `<line x1="${xs(x)}" y1="${y0}" x2="${xs(x)}" y2="${y0 + alt}" class="grade-l"/>`; });
      const poly = pts.map(([x, v]) => `${xs(x)},${ys(v)}`).join(" ");
      s += `<polygon points="${xs(pts[0][0])},${ys(0)} ${poly} ${xs(pts[pts.length - 1][0])},${ys(0)}" fill="${cor}" fill-opacity=".16"/>`;
      s += `<polyline points="${poly}" fill="none" stroke="${cor}" stroke-width="2.4" stroke-linejoin="round"/>`;
      s += `<line x1="${L}" y1="${ys(0)}" x2="${R}" y2="${ys(0)}" class="eixo"/>`;
      s += txt(L - 70, y0 + alt / 2, `[${un}]`, "t2");
      rot.forEach(([x, v, t, abaixo]) => {
        s += txt(xs(x), ys(v) + (abaixo ? 17 : -8), t, "t tb", 'text-anchor="middle"');
      });
      return s;
    }
    const Vb = T.R_A - T.Q;
    g += painel(190, 110, "Esforço cortante V", "N",
      [[0, 0], [0, T.R_A], [a, T.R_A], [a, Vb], [P, Vb], [P, 0]], css("--c-v"),
      [[a / 2, T.R_A, fmt(T.R_A, 1), false], [(a + P) / 2, Vb, fmt(Vb, 1), true]], false);
    g += painel(360, 110, "Momento fletor M · lado tracionado", "N·m",
      [[0, 0], [a, T.M], [P, 0]], css("--c-m"),
      [[a, T.M, `M_máx = ${fmt(T.M, 2)} N·m`, true]], true);
    const dv = r.diagramas.travessa;
    const def = dv.x_mm.map((x, k) => [x, dv.v_mm[k]]);
    const k = dv.v_mm.reduce((m, v, j) => (v > dv.v_mm[m] ? j : m), 0);
    g += painel(530, 110, "Linha elástica · deflexão", "mm", def, css("--c-def"),
      [[dv.x_mm[k], dv.v_mm[k], `δ_máx = ${fmt(dv.v_mm[k], 3)} mm`, true]], true);
    [0, P / 4, P / 2, 3 * P / 4, P].forEach((x) => { g += txt(xs(x), 680, fmt(x, 0), "t2", 'text-anchor="middle"'); });
    g += txt((L + R) / 2, 702, "x — posição a partir do apoio traseiro [mm]", "t2", 'text-anchor="middle"');
    return svg(W, 712, g, "Carregamento, cortante, momento fletor e linha elástica da travessa");
  }

  // ------------------------------------------------------------------ tensões
  function desenhoTensoes(r) {
    const W = 780, L = 210, R = 640, adm = r.verificacao.sigma_adm_mpa;
    const barras = [
      ["Perna · axial σ_N", r.perna.sigma_axial_mpa, null],
      ["Perna · flexão σ_M", r.perna.sigma_flexao_mpa, null],
      ["Perna · total σ_máx", r.perna.sigma_max_mpa, r.verificacao.ok_perna],
      ["Travessa · flexão σ", r.travessa.sigma_mpa, r.verificacao.ok_travessa],
    ];
    const vmax = Math.max(adm, ...barras.map((b) => b[1])) * 1.12;
    const xs = (v) => L + (v / vmax) * (R - L);
    const top = 44, alt = 44;
    let g = "";
    const tk = ticks(0, vmax, 5);
    tk.out.forEach((v) => {
      g += `<line x1="${xs(v)}" y1="${top - 8}" x2="${xs(v)}" y2="${top + barras.length * alt}" class="grade-l"/>`;
      g += txt(xs(v), top + barras.length * alt + 18, fmt(v, casasPara(tk.passo)), "t2", 'text-anchor="middle"');
    });
    barras.forEach(([nome, v, ok], i) => {
      const y = top + i * alt + 8, cor = ok === null ? css("--c-n") : ok ? css("--ok") : css("--falha");
      g += txt(L - 12, y + 18, nome, "t", 'text-anchor="end"');
      g += `<rect x="${L}" y="${y}" width="${Math.max(xs(v) - L, 1)}" height="26" rx="3" fill="${cor}" fill-opacity="${ok === null ? 0.45 : 0.9}"/>`;
      g += txt(xs(v) + 8, y + 18, `${fmt(v, 2)} MPa${ok === null ? "" : ok ? "  ✓ atende" : "  ✗ não atende"}`, "t tb");
    });
    g += `<line x1="${xs(adm)}" y1="${top - 14}" x2="${xs(adm)}" y2="${top + barras.length * alt}" stroke="${css("--tinta")}" stroke-width="1.4" stroke-dasharray="5 4"/>`;
    g += txt(xs(adm) + 6, top - 18, `σ_adm = ${fmt(adm, 2)} MPa`, "t tb");
    g += txt((L + R) / 2, top + barras.length * alt + 40, "Tensão normal [MPa]", "t2", 'text-anchor="middle"');
    return svg(W, top + barras.length * alt + 52, g, "Tensões normais atuantes comparadas com a tensão admissível");
  }

  // ------------------------------------------------------------------ cartão de seção
  function cartaoSecao(titulo, s) {
    const c = 44, k = 70 / Math.max(s.b_mm, s.h_mm);
    const bw = s.b_mm * k, bh = s.h_mm * k, tw = Math.max(s.t_mm * k, 2.5);
    const cor = css("--peca-2"), fundo = css("--folha-2");
    let fig;
    if (s.tipo.startsWith("Circular")) fig = `<circle cx="${c}" cy="${c}" r="${bw / 2}" fill="${cor}"/>`;
    else if (s.tipo === "Tubo circular") fig = `<circle cx="${c}" cy="${c}" r="${bw / 2 - tw / 2}" fill="none" stroke="${cor}" stroke-width="${tw}"/>`;
    else if (s.tipo.startsWith("Tubo")) fig = `<rect x="${c - bw / 2 + tw / 2}" y="${c - bh / 2 + tw / 2}" width="${bw - tw}" height="${bh - tw}" fill="none" stroke="${cor}" stroke-width="${tw}"/>`;
    else fig = `<rect x="${c - bw / 2}" y="${c - bh / 2}" width="${bw}" height="${bh}" fill="${cor}"/>`;
    fig += `<line x1="${c - 42}" y1="${c}" x2="${c + 42}" y2="${c}" stroke="${css("--acento")}" stroke-width="1" stroke-dasharray="4 3"/>`;
    return `<div class="secao-card"><svg viewBox="0 0 88 88" aria-hidden="true"><rect width="88" height="88" fill="${fundo}"/>${fig}</svg>
      <div><h3>${esc(titulo)} · ${esc(s.descricao)}</h3><table>
        <tr><td>A</td><td>${fmt(s.A_mm2, 1)} mm²</td></tr>
        <tr><td>I</td><td>${fmt(s.I_mm4, 0)} mm⁴</td></tr>
        <tr><td>W</td><td>${fmt(s.W_mm3, 0)} mm³</td></tr>
        <tr><td>r<sub>mín</sub></td><td>${fmt(s.r_mm, 2)} mm</td></tr></table></div></div>`;
  }

  // ------------------------------------------------------------------ abas
  function ativarAba(nome) {
    $$(".abas button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.aba === nome)));
    $$(".aba").forEach((a) => { a.hidden = a.dataset.aba !== nome; });
    try { localStorage.setItem("cadeira.aba", nome); } catch { /* */ }
  }

  // ------------------------------------------------------------------ tema
  function alternarTema() {
    const raiz = document.documentElement;
    const escuroAgora = raiz.dataset.theme ? raiz.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    raiz.dataset.theme = escuroAgora ? "light" : "dark";
    try { localStorage.setItem("cadeira.tema", raiz.dataset.theme); } catch { /* */ }
    if (ultimo) render(ultimo.entradas, ultimo.r); // redesenha SVGs com as cores do tema
  }

  // ------------------------------------------------------------------ PDF
  async function gerarPdf() {
    const msg = $("#msg-pdf"), btn = $("#gerar-pdf");
    msg.hidden = true;
    btn.disabled = true; btn.textContent = "Gerando…";
    const integrantes = $("#integrantes").value.split("\n").map((s) => s.trim()).filter(Boolean);
    const turma = $("#turma").value.trim();
    try { localStorage.setItem("cadeira.relatorio", JSON.stringify({ integrantes, turma })); } catch { /* */ }
    try {
      const blob = await API.relatorio({ entradas: lerEntradas(), integrantes, turma });
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement("a"), { href: url, download: "Relatorio_Cadeira.pdf" });
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
      $("#dlg-pdf").close();
    } catch (err) {
      msg.textContent = err.message; msg.hidden = false;
    } finally {
      btn.disabled = false; btn.textContent = "Baixar PDF";
    }
  }

  // ------------------------------------------------------------------ início
  async function iniciar() {
    try { const tema = localStorage.getItem("cadeira.tema"); if (tema) document.documentElement.dataset.theme = tema; } catch { /* */ }
    try {
      OPC = await API.opcoes();
    } catch (err) {
      mostrarErros([err.message + " Verifique se o servidor Python está rodando (python app.py)."]);
      return;
    }
    $("#material").innerHTML = OPC.materiais.map((m) => `<option>${esc(m.nome)}</option>`).join("") + "<option>Personalizado</option>";
    const opts = OPC.secoes.map((s) => `<option>${esc(s)}</option>`).join("");
    $("#tipo_secao").innerHTML = opts;
    $("#tipo_secao_travessa").innerHTML = opts;

    // padrões da versão desktop
    PADRAO = { ...OPC.padrao, altura_secao_perna_mm: 40, parede_mm: 1.5, parede_travessa_mm: 1.5 };
    aplicarEntradas(PADRAO);
    const salvo = carregar();
    if (salvo) aplicarEntradas(salvo);

    try {
      const rel = JSON.parse(localStorage.getItem("cadeira.relatorio") || "null");
      if (rel) { $("#integrantes").value = (rel.integrantes || []).join("\n"); $("#turma").value = rel.turma || ""; }
      const aba = localStorage.getItem("cadeira.aba");
      if (aba && $(`.abas [data-aba="${aba}"]`)) ativarAba(aba);
    } catch { /* */ }

    $("#form").addEventListener("input", (ev) => {
      if (ev.target.id === "massa_range") $("#massa_kg").value = ev.target.value;
      if (ev.target.id === "massa_kg") $("#massa_range").value = ev.target.value;
      agendar();
    });
    $("#form").addEventListener("change", agendar);
    $("#form").addEventListener("submit", (ev) => ev.preventDefault());
    $("#restaurar").addEventListener("click", () => { aplicarEntradas(PADRAO); agendar(); });
    $$(".abas button").forEach((b) => b.addEventListener("click", () => ativarAba(b.dataset.aba)));
    $("#tema").addEventListener("click", alternarTema);
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => ultimo && render(ultimo.entradas, ultimo.r));
    $("#abrir-pdf").addEventListener("click", () => { $("#msg-pdf").hidden = true; $("#dlg-pdf").showModal(); });
    $("#gerar-pdf").addEventListener("click", gerarPdf);

    atualizarVisibilidade();
    calcular();
  }
  iniciar();
})();
