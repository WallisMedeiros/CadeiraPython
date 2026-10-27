"""Geração do relatório técnico / memorial de cálculo em PDF (ReportLab).

Estrutura exigida no edital: Nomes dos integrantes, Introdução, Objetivos,
Metodologia, Resultados e Conclusão — além do memorial de cálculo completo e dos
diagramas de esforços internos solicitantes.
"""
from __future__ import annotations

import io
import os
from datetime import date

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from .calculos import Resultados, _f
from .diagramas import figura_modelo, figura_perna, figura_tensoes, figura_travessa

# ------------------------------------------------------------------ fontes
_DIR_FONTES = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(_DIR_FONTES, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-B", os.path.join(_DIR_FONTES, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-I", os.path.join(_DIR_FONTES, "DejaVuSans-Oblique.ttf")))
pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-B", italic="DejaVu-I",
                              boldItalic="DejaVu-B")

AZUL = colors.HexColor("#184f95")
CINZA = colors.HexColor("#52514e")
LINHA = colors.HexColor("#d9d8d3")
FUNDO_TAB = colors.HexColor("#f3f2ee")
VERDE = colors.HexColor("#0a7d0a")
VERMELHO = colors.HexColor("#c02f2f")

_base = getSampleStyleSheet()
EST = {
    "titulo": ParagraphStyle("titulo", parent=_base["Title"], fontName="DejaVu-B", fontSize=20,
                             leading=26, textColor=AZUL, alignment=TA_CENTER),
    "subtitulo": ParagraphStyle("subtitulo", parent=_base["Normal"], fontName="DejaVu", fontSize=12,
                                leading=16, alignment=TA_CENTER, textColor=CINZA),
    "h1": ParagraphStyle("h1", parent=_base["Heading1"], fontName="DejaVu-B", fontSize=14,
                         leading=18, textColor=AZUL, spaceBefore=10, spaceAfter=6),
    "h2": ParagraphStyle("h2", parent=_base["Heading2"], fontName="DejaVu-B", fontSize=11,
                         leading=14, textColor=colors.black, spaceBefore=8, spaceAfter=4),
    "p": ParagraphStyle("p", parent=_base["Normal"], fontName="DejaVu", fontSize=10, leading=14.5,
                        alignment=TA_JUSTIFY, spaceAfter=6),
    "item": ParagraphStyle("item", parent=_base["Normal"], fontName="DejaVu", fontSize=10,
                           leading=14, leftIndent=14, bulletIndent=4, spaceAfter=2),
    "formula": ParagraphStyle("formula", parent=_base["Normal"], fontName="DejaVu", fontSize=10,
                              leading=15, leftIndent=24, textColor=colors.HexColor("#1c1c1c")),
    "cel": ParagraphStyle("cel", parent=_base["Normal"], fontName="DejaVu", fontSize=8, leading=10),
    "cel_b": ParagraphStyle("cel_b", parent=_base["Normal"], fontName="DejaVu-B", fontSize=8, leading=10),
    "legenda": ParagraphStyle("legenda", parent=_base["Normal"], fontName="DejaVu-I", fontSize=8.5,
                              leading=11, alignment=TA_CENTER, textColor=CINZA, spaceAfter=8),
}


def _p(texto, estilo="p"):
    return Paragraph(texto, EST[estilo])


def _figura(fig, largura_cm=17.0, legenda=""):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170, facecolor=fig.get_facecolor())
    buf.seek(0)
    w, h = fig.get_size_inches()
    img = Image(buf, width=largura_cm * cm, height=largura_cm * cm * h / w)
    itens = [img]
    if legenda:
        itens.append(_p(legenda, "legenda"))
    return KeepTogether(itens)


def _tabela(linhas, larguras, cabecalho=True, destaque_ultima=False):
    dados = [[Paragraph(str(c), EST["cel_b" if (cabecalho and i == 0) else "cel"]) for c in linha]
             for i, linha in enumerate(linhas)]
    t = Table(dados, colWidths=[w * cm for w in larguras], repeatRows=1 if cabecalho else 0)
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if cabecalho:
        estilo.append(("BACKGROUND", (0, 0), (-1, 0), FUNDO_TAB))
    if destaque_ultima:
        estilo.append(("BACKGROUND", (0, -1), (-1, -1), FUNDO_TAB))
    t.setStyle(TableStyle(estilo))
    return t


def _rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("DejaVu", 7.5)
    canvas.setFillColor(CINZA)
    canvas.drawString(2 * cm, 1.2 * cm, "Análise de Resistência dos Materiais Aplicada a uma Cadeira — Projeto A3")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()


# --------------------------------------------------------------------------- #
def gerar_relatorio(r: Resultados, caminho: str, integrantes: list[str] | None = None,
                    turma: str = "", instituicao: str = "Universidade São Judas Tadeu") -> str:
    ent, mat, sec, sec_t = r.entradas, r.material, r.secao, r.secao_travessa
    integrantes = [n.strip() for n in (integrantes or []) if n.strip()]
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm,
                            title="Memorial de cálculo — Análise estrutural de cadeira",
                            author=", ".join(integrantes) or "Grupo do Projeto A3")
    s = []

    # ---------------------------------------------------------------- capa
    s += [Spacer(1, 2.2 * cm), _p(instituicao, "subtitulo"),
          _p("Resistência dos Materiais e Elementos de Máquinas — Projeto A3 (2026-2)", "subtitulo"),
          Spacer(1, 2.2 * cm),
          _p("Desenvolvimento de um Software de Análise de Resistência dos Materiais "
             "Aplicado a uma Cadeira", "titulo"),
          Spacer(1, 0.4 * cm),
          _p("Relatório técnico e memorial de cálculo", "subtitulo"),
          Spacer(1, 2.4 * cm)]
    s.append(_p("<b>Integrantes do grupo</b>", "h2"))
    if integrantes:
        for nome in integrantes:
            s.append(_p(nome, "item"))
    else:
        s.append(_p("(preencha os nomes dos integrantes no software antes de gerar o relatório)", "item"))
    if turma:
        s += [Spacer(1, 0.3 * cm), _p(f"<b>Turma:</b> {turma}", "item")]
    s += [Spacer(1, 0.3 * cm), _p(f"<b>Data:</b> {date.today().strftime('%d/%m/%Y')}", "item")]

    veredito = "SEGURA" if r.segura else "NÃO SEGURA"
    cor_v = VERDE if r.segura else VERMELHO
    caixa = Table([[Paragraph(f"<font color='white'><b>Resultado da análise: CADEIRA {veredito}</b></font>",
                              ParagraphStyle("v", fontName="DejaVu-B", fontSize=12, alignment=TA_CENTER))]],
                  colWidths=[17 * cm])
    caixa.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), cor_v),
                               ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    s += [Spacer(1, 1.6 * cm), caixa, PageBreak()]

    # ---------------------------------------------------------------- 1. Introdução
    s.append(_p("1. Introdução", "h1"))
    s.append(_p(
        "A cadeira é um dos produtos de engenharia mais comuns do cotidiano e, apesar da aparente "
        "simplicidade, é uma estrutura que precisa resistir com segurança a cargas variáveis: o peso "
        "do usuário, o impacto ao sentar-se bruscamente e as forças horizontais geradas quando a "
        "pessoa se inclina ou arrasta o móvel. Uma falha nas pernas ou no quadro do assento pode "
        "causar quedas e lesões, de modo que o dimensionamento correto desses elementos é uma "
        "aplicação direta dos conceitos de Resistência dos Materiais."))
    s.append(_p(
        "Neste projeto foi desenvolvido um software em Python, acessível pelo navegador (interface web "
        "com Flask) e também como aplicativo desktop (PyQt5), que "
        "modela a cadeira como um conjunto de vigas e apoios, calcula as reações vinculares, os "
        "esforços internos solicitantes (normal, cortante e momento fletor), as tensões normais "
        "provenientes dos esforços axiais e dos momentos fletores, as deformações e a estabilidade "
        "das pernas à flambagem. Com esses resultados, o programa verifica se a estrutura trabalha "
        "dentro do limite de segurança do material escolhido (madeira, aço ou alumínio) e emite este "
        "relatório com o memorial de cálculo completo."))

    # ---------------------------------------------------------------- 2. Objetivos
    s.append(_p("2. Objetivos", "h1"))
    s.append(_p("<b>Objetivo geral:</b> desenvolver um software de análise estrutural simplificada "
                "capaz de avaliar a resistência mecânica de uma cadeira submetida ao peso de um usuário."))
    s.append(_p("<b>Objetivos específicos:</b>"))
    for item in [
        "modelar a estrutura da cadeira como um conjunto de vigas e apoios;",
        "permitir a inserção do peso da pessoa, das dimensões da cadeira (altura, largura do assento, "
        "espessura das pernas) e do tipo de material (madeira, aço, alumínio);",
        "calcular as reações vinculares, os diagramas de esforços internos e as tensões normais "
        "devidas aos esforços axiais e aos momentos fletores;",
        "verificar se a estrutura está dentro do limite de segurança do material;",
        "gerar um relatório indicando se a cadeira suporta ou não a carga aplicada.",
    ]:
        s.append(Paragraph(item, EST["item"], bulletText="•"))

    # ---------------------------------------------------------------- 3. Metodologia
    s.append(_p("3. Metodologia", "h1"))
    s.append(_p("3.1 Modelo estrutural e hipóteses", "h2"))
    for item in [
        "Material homogêneo, isotrópico e em regime elástico-linear (Lei de Hooke, σ = E·ε); para a "
        "madeira adotam-se as propriedades na direção paralela às fibras.",
        "A cadeira possui 4 pernas verticais idênticas, de comprimento H, posicionadas nos cantos do "
        "assento (largura L × profundidade P). Por simetria, cada lateral (perna dianteira, perna "
        "traseira e travessa lateral) recebe metade da carga.",
        "Carga de projeto W = m·g·φ, em que φ é o fator dinâmico que representa o impacto de sentar-se "
        "bruscamente. A carga pode ser deslocada de uma excentricidade e em direção à frente do assento.",
        "Força horizontal F_H = μ·W aplicada na altura do assento, no sentido da frente (sentido mais "
        "desfavorável), equilibrada por quatro reações horizontais iguais nos pés (h = F_H/4).",
        "Cada perna é modelada como uma barra engastada no quadro do assento e livre no piso, sujeita "
        "à compressão R e à força horizontal h no pé (flexo-compressão).",
        "Cada travessa lateral do assento é modelada como viga bi-apoiada sobre as pernas, com vão P e "
        "carga concentrada Q = W/2 — hipótese conservadora em relação à carga distribuída.",
        "Peso próprio da cadeira desprezado (pequeno frente à carga do usuário).",
    ]:
        s.append(Paragraph(item, EST["item"], bulletText="•"))

    s.append(_p("3.2 Equações utilizadas", "h2"))
    s.append(_p("<b>Equilíbrio global (reações vinculares)</b> — ΣFx = 0, ΣFy = 0, ΣM = 0:"))
    for eq in ["R_D,tot = [W·(P/2 + e) + F_H·H] / P", "R_T,tot = W − R_D,tot",
               "R_D = R_D,tot / 2     R_T = R_T,tot / 2     (tombamento se R_T,tot &lt; 0)"]:
        s.append(_p(eq, "formula"))
    s.append(_p("<b>Perna (flexo-compressão)</b>:"))
    for eq in ["N = −R  (constante)     V = h  (constante)     M(y) = h·y  →  M_máx = h·H",
               "σ_máx = N/A + M/W   (tensões normais do esforço axial e do momento fletor)",
               "ε = σ/E     δ_N = N·H/(E·A)     δ_H = h·H³/(3·E·I)",
               "P_cr = π²·E·I_mín/(K·H)²   (flambagem de Euler)"]:
        s.append(_p(eq, "formula"))
    s.append(_p("<b>Travessa (flexão simples)</b>:"))
    for eq in ["R_A = Q·b/P     R_B = Q·a/P     (a = P/2 + e, b = P − a)",
               "M_máx = Q·a·b/P     σ = M_máx/W",
               "δ_máx = Q·b·(P² − b²)^1,5 / (9·√3·P·E·I)"]:
        s.append(_p(eq, "formula"))
    s.append(_p("<b>Critério de segurança</b>:"))
    for eq in ["σ_adm = σ_lim / FS",
               "Segura se: σ_máx,perna ≤ σ_adm,  σ_travessa ≤ σ_adm,  P_cr/N ≥ FS  e  sem tombamento"]:
        s.append(_p(eq, "formula"))
    s.append(_p(
        f"Para metais, σ_lim é a tensão de escoamento; para madeira, a resistência característica à "
        f"compressão paralela às fibras (NBR 7190). Neste cálculo: {mat.nome} — {mat.criterio}."))

    s.append(_p("3.3 Implementação do software", "h2"))
    s.append(_p(
        "O programa foi escrito em Python 3 e organizado em módulos: <i>materiais</i> (banco de "
        "propriedades), <i>secoes</i> (características geométricas de seções maciças e tubulares), "
        "<i>calculos</i> (equilíbrio, esforços, tensões, deformações, flambagem e verificação), "
        "<i>diagramas</i> (gráficos dos esforços internos com Matplotlib) e <i>relatorio</i> (geração "
        "deste PDF com ReportLab). O mesmo núcleo de cálculo atende a interface web, servida por Flask, "
        "e a interface desktop em PyQt5; ambas recalculam os resultados automaticamente a cada "
        "alteração dos dados de entrada."))

    # ---------------------------------------------------------------- 4. Resultados
    s.append(PageBreak())
    s.append(_p("4. Resultados", "h1"))
    s.append(_p("4.1 Resumo", "h2"))
    resumo = [
        ["Grandeza", "Valor", "Situação"],
        ["Tensão normal máxima nas pernas", f"{_f(r.sigma_max_perna / 1e6)} MPa",
         "atende" if r.ok_perna else "NÃO atende"],
        ["Tensão normal máxima na travessa", f"{_f(r.sigma_travessa / 1e6)} MPa",
         "atende" if r.ok_travessa else "NÃO atende"],
        ["Tensão admissível (σ_lim / FS)", f"{_f(r.sigma_adm / 1e6)} MPa", ""],
        ["Fator de segurança real — pernas", _f(r.fs_perna), ""],
        ["Fator de segurança real — travessa", _f(r.fs_travessa), ""],
        ["Fator de segurança à flambagem", _f(r.fs_flambagem),
         "atende" if r.ok_flambagem else "NÃO atende"],
        ["Tombamento", "não tomba" if not r.tomba else "TOMBA", "atende" if not r.tomba else "NÃO atende"],
        ["Massa máxima admissível do usuário", f"{_f(r.massa_maxima, 1)} kg", ""],
        ["Resultado final", f"CADEIRA {veredito}", ""],
    ]
    s.append(_tabela(resumo, [8, 5, 4], destaque_ultima=True))
    s.append(Spacer(1, 0.3 * cm))
    s.append(_figura(figura_modelo(r), 17, "Figura 1 — Modelo estrutural: cargas aplicadas e reações vinculares."))

    s.append(_p("4.2 Memorial de cálculo", "h2"))
    for titulo, passos in r.memorial:
        bloco = [_p(titulo, "h2")]
        linhas = [["Descrição", "Fórmula", "Substituição", "Resultado"]]
        for p in passos:
            linhas.append([p.descricao, p.formula, p.substituicao, f"<b>{p.resultado}</b>"])
        bloco.append(_tabela(linhas, [4.6, 4.3, 5.0, 3.1]))
        s.append(KeepTogether(bloco) if len(passos) < 12 else bloco[0])
        if len(passos) >= 12:
            s.append(bloco[1])

    s.append(PageBreak())
    s.append(_p("4.3 Diagramas de esforços internos solicitantes", "h2"))
    s.append(_figura(figura_perna(r), 17,
                     "Figura 2 — Diagramas de esforço normal, cortante e momento fletor na perna mais carregada."))
    s.append(_figura(figura_travessa(r), 16,
                     "Figura 3 — Carregamento, esforço cortante, momento fletor e linha elástica da travessa lateral."))
    s.append(_figura(figura_tensoes(r), 17,
                     "Figura 4 — Comparação entre as tensões normais atuantes e a tensão admissível."))

    # ---------------------------------------------------------------- 5. Conclusão
    s.append(_p("5. Conclusão", "h1"))
    s.append(_p(_texto_conclusao(r)))
    s.append(_p(
        "O software atendeu aos objetivos propostos: a partir de poucos dados de entrada ele modela a "
        "cadeira como um sistema de vigas e apoios, determina reações, esforços internos, tensões "
        "normais e deformações, e conclui de forma objetiva se a estrutura é segura. Por se tratar de "
        "um modelo simplificado, os resultados não substituem ensaios normalizados (por exemplo, "
        "ABNT NBR 13962 e EN 1728 para móveis), nem consideram ligações coladas/parafusadas, "
        "concentração de tensões, fadiga ou defeitos da madeira; ainda assim, fornecem uma estimativa "
        "rápida e fundamentada para o pré-dimensionamento das peças."))

    s.append(_p("Referências", "h1"))
    for ref in [
        "HIBBELER, R. C. <i>Resistência dos Materiais</i>. 10. ed. São Paulo: Pearson, 2018.",
        "BEER, F. P.; JOHNSTON, E. R.; DEWOLF, J. T.; MAZUREK, D. F. <i>Mecânica dos Materiais</i>. "
        "8. ed. Porto Alegre: AMGH, 2021.",
        "ASSOCIAÇÃO BRASILEIRA DE NORMAS TÉCNICAS. <i>NBR 7190: Projeto de estruturas de madeira</i>. "
        "Rio de Janeiro: ABNT, 2022.",
        "ASSOCIAÇÃO BRASILEIRA DE NORMAS TÉCNICAS. <i>NBR 13962: Móveis para escritório — Cadeiras — "
        "Requisitos e métodos de ensaio</i>. Rio de Janeiro: ABNT.",
        "ASM INTERNATIONAL. <i>ASM Handbook, Vol. 2: Properties and Selection — Nonferrous Alloys</i>. 1990.",
    ]:
        s.append(Paragraph(ref, EST["item"], bulletText="•"))

    doc.build(s, onFirstPage=lambda c, d: None, onLaterPages=_rodape)
    return caminho


def _texto_conclusao(r: Resultados) -> str:
    ent = r.entradas
    base = (f"Para um usuário de {_f(ent.massa_kg, 1)} kg (carga de projeto W = {_f(r.W, 1)} N, "
            f"com fator dinâmico {_f(ent.fator_dinamico)}), em uma cadeira de {r.material.nome} com "
            f"pernas de seção {r.secao.descricao().lower()}, a tensão normal máxima nas pernas é "
            f"{_f(r.sigma_max_perna / 1e6)} MPa e na travessa do assento é "
            f"{_f(r.sigma_travessa / 1e6)} MPa, frente a uma tensão admissível de "
            f"{_f(r.sigma_adm / 1e6)} MPa (FS = {_f(ent.fator_seguranca)}). ")
    if r.segura:
        return base + (
            f"Todas as verificações foram atendidas e, portanto, <b>a cadeira suporta a carga "
            f"aplicada com segurança</b>. O elemento mais solicitado é: {r.elemento_critico.lower()}, "
            f"e a massa máxima admissível estimada para o usuário é de {_f(r.massa_maxima, 1)} kg.")
    falhas = []
    if not r.ok_perna:
        falhas.append("a tensão nas pernas supera a admissível")
    if not r.ok_travessa:
        falhas.append("a tensão na travessa do assento supera a admissível")
    if not r.ok_flambagem:
        falhas.append("o fator de segurança à flambagem das pernas é insuficiente")
    if r.tomba:
        falhas.append("a cadeira tomba com a posição de carga considerada")
    return base + (
        "<b>A cadeira NÃO é segura</b> para essa condição, pois " + "; ".join(falhas) + ". "
        f"A massa máxima admissível com a geometria atual é de {_f(r.massa_maxima, 1)} kg. "
        "Recomenda-se aumentar a seção das peças, escolher um material mais resistente ou "
        "reduzir a altura/vão da estrutura.")
