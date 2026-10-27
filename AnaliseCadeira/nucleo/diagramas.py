"""Figuras (matplotlib) usadas na interface e no relatório PDF.

Cada função devolve um `matplotlib.figure.Figure` independente do pyplot, para
poder ser embutida no PyQt (FigureCanvasQTAgg) ou salva como imagem.
"""
from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch, Rectangle

from .calculos import Resultados, _f

# Paleta: uma cor fixa por tipo de esforço, igual em todos os diagramas
COR_N = "#2a78d6"       # esforço normal
COR_V = "#eb6834"       # esforço cortante
COR_M = "#1baf7a"       # momento fletor
COR_DEF = "#6250d6"     # deformada / flecha
COR_OK = "#0ca30c"
COR_FALHA = "#d03b3b"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
GRADE = "#e4e3df"
FUNDO = "#fcfcfb"


def _estilo(ax, titulo: str = ""):
    ax.set_facecolor(FUNDO)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(TINTA_2)
        ax.spines[lado].set_linewidth(0.8)
    ax.tick_params(colors=TINTA_2, labelsize=8)
    ax.grid(True, color=GRADE, linewidth=0.6)
    ax.set_axisbelow(True)
    if titulo:
        ax.set_title(titulo, fontsize=10, color=TINTA, loc="left", fontweight="bold")


def _nova_figura(largura=10, altura=4):
    fig = Figure(figsize=(largura, altura), dpi=100, facecolor=FUNDO)
    return fig


def _seta(ax, xy_ini, xy_fim, cor=TINTA, lw=1.6):
    ax.add_patch(FancyArrowPatch(xy_ini, xy_fim, arrowstyle="-|>", mutation_scale=12,
                                 color=cor, linewidth=lw))


# --------------------------------------------------------------------------- #
#  Esquema do modelo estrutural
# --------------------------------------------------------------------------- #
def figura_modelo(r: Resultados) -> Figure:
    ent = r.entradas
    H = ent.altura_mm
    P = ent.profundidade_mm
    L = ent.largura_mm
    t = ent.espessura_perna_mm
    fig = _nova_figura(10, 4.4)
    ax1 = fig.add_subplot(1, 2, 1)
    ax2 = fig.add_subplot(1, 2, 2)

    # ---- Vista lateral -----------------------------------------------------
    ax = ax1
    ax.set_facecolor(FUNDO)
    ax.set_title("Vista lateral — modelo e cargas", fontsize=10, loc="left",
                 fontweight="bold", color=TINTA)
    cor_peca = "#b9b7ae"
    ax.add_patch(Rectangle((-t / 2, 0), t, H, color=cor_peca))            # perna traseira
    ax.add_patch(Rectangle((P - t / 2, 0), t, H, color=cor_peca))         # perna dianteira
    ax.add_patch(Rectangle((-t / 2, H), P + t, t, color="#8e8c84"))       # assento/travessa
    ax.add_patch(Rectangle((-t / 2, H + t), t, 0.9 * H, color=cor_peca))  # encosto
    ax.plot([-0.25 * P, 1.25 * P], [0, 0], color=TINTA_2, lw=1)
    for xi in np.linspace(-0.25 * P, 1.25 * P, 18):
        ax.plot([xi, xi - 0.04 * P], [0, -0.04 * P], color=TINTA_2, lw=0.6)

    xc = P / 2 + ent.excentricidade_mm
    _seta(ax, (xc, H + t + 0.45 * H), (xc, H + t + 2), COR_FALHA, 2)
    ax.text(xc + 8, H + t + 0.30 * H, f"W = {_f(r.W, 0)} N", fontsize=8, color=TINTA)
    if r.F_H > 0:
        _seta(ax, (P / 2 - 0.35 * P, H + t / 2), (P / 2 - 0.02 * P, H + t / 2), COR_V, 2)
        ax.text(P / 2 - 0.35 * P, H + t * 1.6, f"F_H = {_f(r.F_H, 0)} N", fontsize=8, color=TINTA)

    for x, R, nome, ha, dx in ((0, r.R_T_total, "R_T", "right", -8), (P, r.R_D_total, "R_D", "left", 8)):
        _seta(ax, (x, -0.28 * H), (x, -0.02 * H), COR_N, 1.8)
        ax.text(x + dx, -0.25 * H, f"{nome} = {_f(R, 0)} N\n(2 pernas)", fontsize=8,
                color=TINTA, ha=ha)
    ax.annotate("", (0, -0.42 * H), (P, -0.42 * H),
                arrowprops=dict(arrowstyle="<->", color=TINTA_2, lw=0.8))
    ax.text(P / 2, -0.40 * H, f"P = {_f(P, 0)} mm", ha="center", va="bottom", fontsize=8, color=TINTA_2)
    ax.annotate("", (1.18 * P, 0), (1.18 * P, H),
                arrowprops=dict(arrowstyle="<->", color=TINTA_2, lw=0.8))
    ax.text(1.2 * P, H / 2, f"H = {_f(H, 0)} mm", rotation=90, va="center", fontsize=8, color=TINTA_2)
    ax.set_xlim(-0.55 * P, 1.55 * P)
    ax.set_ylim(-0.5 * H, 2.05 * H)
    ax.set_aspect("equal")
    ax.axis("off")

    # ---- Vista superior ----------------------------------------------------
    ax = ax2
    ax.set_facecolor(FUNDO)
    ax.set_title("Vista superior — posição das pernas", fontsize=10, loc="left",
                 fontweight="bold", color=TINTA)
    ax.add_patch(Rectangle((-t / 2, -t / 2), P + t, L + t, fill=False, ec="#8e8c84", lw=2))
    for (x, y, nome, R) in ((0, 0, "T", r.R_T), (0, L, "T", r.R_T),
                            (P, 0, "D", r.R_D), (P, L, "D", r.R_D)):
        ax.add_patch(Rectangle((x - t / 2, y - t / 2), t, t, color=cor_peca))
        ax.text(x, y + (t if y > 0 else -t), f"{nome}: {_f(R, 0)} N", ha="center",
                va="bottom" if y > 0 else "top", fontsize=8, color=TINTA)
    ax.plot(xc, L / 2, "o", ms=9, color=COR_FALHA, mec=FUNDO, mew=2)
    ax.text(xc, L / 2 + 0.06 * L, "centro da carga", ha="center", fontsize=8, color=TINTA)
    ax.text(P + 0.12 * P, L / 2, "FRENTE →", rotation=90, va="center", fontsize=8, color=TINTA_2)
    ax.annotate("", (0, -0.22 * L), (P, -0.22 * L),
                arrowprops=dict(arrowstyle="<->", color=TINTA_2, lw=0.8))
    ax.text(P / 2, -0.2 * L, f"P = {_f(P, 0)} mm", ha="center", va="bottom", fontsize=8, color=TINTA_2)
    ax.annotate("", (-0.18 * P, 0), (-0.18 * P, L),
                arrowprops=dict(arrowstyle="<->", color=TINTA_2, lw=0.8))
    ax.text(-0.2 * P, L / 2, f"L = {_f(L, 0)} mm", rotation=90, va="center", ha="right",
            fontsize=8, color=TINTA_2)
    ax.set_xlim(-0.4 * P, 1.3 * P)
    ax.set_ylim(-0.35 * L, 1.3 * L)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
#  Diagramas da perna (barra vertical)
# --------------------------------------------------------------------------- #
def _diagrama_vertical(ax, y, valores, cor, titulo, unidade, fator=1.0):
    v = valores * fator
    ax.fill_betweenx(y, 0, v, color=cor, alpha=0.18, linewidth=0)
    ax.plot(v, y, color=cor, lw=2)
    ax.axvline(0, color=TINTA, lw=1.2)
    _estilo(ax, titulo)
    ax.set_ylabel("y — altura a partir do pé [mm]", fontsize=8, color=TINTA_2)
    ax.set_xlabel(unidade, fontsize=8, color=TINTA_2)
    i = int(np.argmax(np.abs(v)))
    ax.annotate(f"{_f(v[i], 2)}", (v[i], y[i]), textcoords="offset points",
                xytext=(0, 6), ha="center", fontsize=8, color=TINTA, fontweight="bold")
    lim = max(abs(v).max(), 1e-9) * 1.35
    ax.set_xlim(min(-0.15 * lim, v.min() * 1.35), max(0.15 * lim, v.max() * 1.35))


def figura_perna(r: Resultados) -> Figure:
    y, N, V, M = r.diagramas_perna()
    y_mm = y * 1000
    fig = _nova_figura(10, 4.2)
    axs = fig.subplots(1, 3, sharey=True)
    _diagrama_vertical(axs[0], y_mm, N, COR_N, "Esforço normal N", "N [N]  (− compressão)")
    _diagrama_vertical(axs[1], y_mm, V, COR_V, "Esforço cortante V", "V [N]")
    _diagrama_vertical(axs[2], y_mm, M, COR_M, "Momento fletor M", "M [N·m]")
    for ax in axs[1:]:
        ax.set_ylabel("")
    fig.suptitle("Diagramas de esforços internos — perna mais carregada "
                 "(engaste no assento em y = H)", fontsize=10, color=TINTA, x=0.01, ha="left")
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
#  Diagramas da travessa (viga bi-apoiada)
# --------------------------------------------------------------------------- #
def figura_travessa(r: Resultados) -> Figure:
    x, V, M, v = r.diagramas_travessa()
    x_mm = x * 1000
    P_mm = r.entradas.profundidade_mm
    a_mm = r.a_carga * 1000
    fig = _nova_figura(10, 7.4)
    axs = fig.subplots(4, 1, sharex=True,
                       gridspec_kw={"height_ratios": [0.8, 1, 1, 1]})

    # esquema de carregamento
    ax = axs[0]
    ax.set_facecolor(FUNDO)
    ax.plot([0, P_mm], [0, 0], color="#8e8c84", lw=6, solid_capstyle="butt")
    for xs in (0, P_mm):
        ax.plot(xs, -0.18, marker="^", ms=12, color=TINTA_2)
    _seta(ax, (a_mm, 1.0), (a_mm, 0.1), COR_FALHA, 2)
    ax.text(a_mm + 6, 0.7, f"Q = {_f(r.Q_travessa, 1)} N", fontsize=8, color=TINTA)
    ax.text(0, -0.55, f"R_A = {_f(r.R_A, 1)} N  (traseira)", fontsize=8, color=TINTA)
    ax.text(P_mm, -0.55, f"R_B = {_f(r.R_B, 1)} N  (dianteira)", fontsize=8, ha="right", color=TINTA)
    ax.set_ylim(-0.8, 1.2)
    ax.axis("off")
    ax.set_title("Travessa lateral do assento — viga bi-apoiada com carga concentrada",
                 fontsize=10, loc="left", fontweight="bold", color=TINTA)

    def _plot(ax, val, cor, titulo, unidade, step=False):
        if step:
            ax.fill_between(x_mm, 0, val, color=cor, alpha=0.18, linewidth=0, step=None)
        else:
            ax.fill_between(x_mm, 0, val, color=cor, alpha=0.18, linewidth=0)
        ax.plot(x_mm, val, color=cor, lw=2)
        ax.axhline(0, color=TINTA, lw=1.2)
        _estilo(ax, titulo)
        ax.set_ylabel(unidade, fontsize=8, color=TINTA_2)

    _plot(axs[1], V, COR_V, "Esforço cortante V", "V [N]", step=True)
    axs[1].annotate(f"{_f(r.R_A, 1)}", (a_mm / 2, r.R_A), textcoords="offset points",
                    xytext=(0, 4), ha="center", fontsize=8, color=TINTA, fontweight="bold")
    axs[1].annotate(f"{_f(r.R_A - r.Q_travessa, 1)}", ((a_mm + P_mm) / 2, r.R_A - r.Q_travessa),
                    textcoords="offset points", xytext=(0, -12), ha="center", fontsize=8,
                    color=TINTA, fontweight="bold")
    lim = max(abs(V).max(), 1) * 1.4
    axs[1].set_ylim(-lim, lim)

    # Momento: convenção de engenharia (positivo para baixo, lado tracionado)
    _plot(axs[2], -M, COR_M, "Momento fletor M (traçado do lado tracionado)", "M [N·m]")
    axs[2].annotate(f"M_máx = {_f(r.M_travessa, 2)} N·m", (a_mm, -r.M_travessa),
                    textcoords="offset points", xytext=(0, -13), ha="center", fontsize=8,
                    color=TINTA, fontweight="bold")
    axs[2].set_ylim(-r.M_travessa * 1.45, r.M_travessa * 0.25)
    axs[2].yaxis.set_major_formatter(lambda val, pos: _f(abs(val), 0))

    v_mm = -v * 1000
    _plot(axs[3], v_mm, COR_DEF, "Linha elástica (deflexão)", "v [mm]")
    i = int(np.argmin(v_mm))
    axs[3].annotate(f"δ_máx = {_f(-v_mm[i], 3)} mm", (x_mm[i], v_mm[i]),
                    textcoords="offset points", xytext=(0, -13), ha="center", fontsize=8,
                    color=TINTA, fontweight="bold")
    axs[3].set_ylim(v_mm.min() * 1.5, -v_mm.min() * 0.25)
    axs[3].set_xlabel("x — posição a partir do apoio traseiro [mm]", fontsize=8, color=TINTA_2)
    axs[3].set_xlim(-0.03 * P_mm, 1.03 * P_mm)
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
#  Comparação de tensões
# --------------------------------------------------------------------------- #
def figura_tensoes(r: Resultados) -> Figure:
    fig = _nova_figura(10, 3.4)
    ax = fig.add_subplot(1, 1, 1)
    nomes = ["Perna — axial σ_N", "Perna — flexão σ_M", "Perna — total σ_máx", "Travessa — flexão σ"]
    vals = np.array([r.sigma_axial, r.sigma_flexao_perna, r.sigma_max_perna, r.sigma_travessa]) / 1e6
    adm = r.sigma_adm / 1e6
    cores = []
    for i, v in enumerate(vals):
        if i < 2:
            cores.append("#86b6ef")                 # parcelas: tom claro
        else:
            cores.append(COR_OK if v <= adm else COR_FALHA)
    yy = np.arange(len(nomes))[::-1]
    ax.barh(yy, vals, color=cores, height=0.55, edgecolor=FUNDO, linewidth=2)
    ax.axvline(adm, color=TINTA, lw=1.2, ls="--")
    ax.text(adm, len(nomes) - 0.45, f"  σ_adm = {_f(adm, 2)} MPa", fontsize=8, color=TINTA, va="bottom")
    for yi, v, i in zip(yy, vals, range(len(vals))):
        rot = "" if i < 2 else ("  ✓ atende" if v <= adm else "  ✗ não atende")
        ax.text(v, yi, f"  {_f(v, 2)} MPa{rot}", va="center", fontsize=8, color=TINTA)
    ax.set_yticks(yy, nomes, fontsize=8)
    _estilo(ax, "Tensões normais atuantes × tensão admissível")
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Tensão [MPa]", fontsize=8, color=TINTA_2)
    ax.set_xlim(0, max(vals.max(), adm) * 1.45)
    ax.set_ylim(-0.6, len(nomes) - 0.1)
    fig.tight_layout()
    return fig
