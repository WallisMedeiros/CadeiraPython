"""Geração do relatório técnico / memorial de cálculo em PDF (ReportLab).

O documento é, ao mesmo tempo, a parte escrita do projeto acadêmico e o memorial
de cálculo completo da simulação feita no software.  Estrutura:

    Capa (integrantes, professores, turma)  ·  Sumário
    1 Introdução · 2 Objetivos · 3 Fundamentação teórica · 4 Metodologia
    (desenvolvimento, tecnologias, implementação, materiais e seções, parâmetros,
    modelagem) · 5 Memorial de cálculo (geometria, carregamento, reações, esforços,
    diagramas, tensões, deformações, verificação) · 6 Resultados e discussão
    (resultados, interpretação dos gráficos, discussão, limitações) · 7 Conclusão
    · Referências bibliográficas

Todos os números vêm do objeto `Resultados` produzido pelo núcleo de cálculo —
os mesmos exibidos nas interfaces web e desktop.
"""
from __future__ import annotations

import io
import os
import re
import shutil
import tempfile
from datetime import date

import matplotlib
from matplotlib import mathtext
from matplotlib.font_manager import FontProperties
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

from .calculos import G, EtapaMemorial, Passo, Resultados, _f
from .diagramas import (figura_distribuicao_tensoes, figura_modelo, figura_perna,
                        figura_tensoes, figura_travessa)
from .materiais import MATERIAIS

# Professores da Unidade Curricular (exibidos na capa)
PROFESSORES = ["Renato Galina", "Jordana Simoes Ribeiro Martins"]
UNIDADE_CURRICULAR = "Resistência dos Materiais e Elementos de Máquinas"

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
FUNDO_EQ = colors.HexColor("#f6f8fc")
VERDE = colors.HexColor("#0a7d0a")
VERMELHO = colors.HexColor("#c02f2f")

_base = getSampleStyleSheet()
EST = {
    "titulo": ParagraphStyle("titulo", parent=_base["Title"], fontName="DejaVu-B", fontSize=20,
                             leading=26, textColor=AZUL, alignment=TA_CENTER),
    "subtitulo": ParagraphStyle("subtitulo", parent=_base["Normal"], fontName="DejaVu", fontSize=12,
                                leading=16, alignment=TA_CENTER, textColor=CINZA),
    "capa_rot": ParagraphStyle("capa_rot", parent=_base["Normal"], fontName="DejaVu-B", fontSize=10.5,
                               leading=14, textColor=AZUL, spaceBefore=8, spaceAfter=2),
    "capa_item": ParagraphStyle("capa_item", parent=_base["Normal"], fontName="DejaVu", fontSize=10.5,
                                leading=14, leftIndent=10),
    "h1": ParagraphStyle("h1", parent=_base["Heading1"], fontName="DejaVu-B", fontSize=14,
                         leading=18, textColor=AZUL, spaceBefore=12, spaceAfter=6, keepWithNext=1),
    "h2": ParagraphStyle("h2", parent=_base["Heading2"], fontName="DejaVu-B", fontSize=11.5,
                         leading=15, textColor=colors.black, spaceBefore=10, spaceAfter=4,
                         keepWithNext=1),
    "h3": ParagraphStyle("h3", parent=_base["Heading3"], fontName="DejaVu-B", fontSize=10,
                         leading=13, textColor=AZUL, spaceBefore=8, spaceAfter=3,
                         keepWithNext=1),
    "p": ParagraphStyle("p", parent=_base["Normal"], fontName="DejaVu", fontSize=10, leading=14.5,
                        alignment=TA_JUSTIFY, spaceAfter=6),
    "p_int": ParagraphStyle("p_int", parent=_base["Normal"], fontName="DejaVu-I", fontSize=9.5,
                            leading=13.5, alignment=TA_JUSTIFY, spaceAfter=6, leftIndent=10,
                            textColor=colors.HexColor("#2b2b2b")),
    "item": ParagraphStyle("item", parent=_base["Normal"], fontName="DejaVu", fontSize=10,
                           leading=14, leftIndent=16, bulletIndent=5, spaceAfter=2, alignment=TA_JUSTIFY),
    "var": ParagraphStyle("var", parent=_base["Normal"], fontName="DejaVu", fontSize=9,
                          leading=12, leftIndent=28, spaceAfter=0),
    "calc": ParagraphStyle("calc", parent=_base["Normal"], fontName="DejaVu", fontSize=9.5,
                           leading=13.5, leftIndent=14, spaceAfter=1),
    "cel": ParagraphStyle("cel", parent=_base["Normal"], fontName="DejaVu", fontSize=8.3, leading=10.5,
                          alignment=TA_LEFT),
    "cel_b": ParagraphStyle("cel_b", parent=_base["Normal"], fontName="DejaVu-B", fontSize=8.3,
                            leading=10.5),
    "legenda": ParagraphStyle("legenda", parent=_base["Normal"], fontName="DejaVu-I", fontSize=8.5,
                              leading=11, alignment=TA_CENTER, textColor=CINZA, spaceAfter=6),
    "toc_tit": ParagraphStyle("toc_tit", parent=_base["Heading1"], fontName="DejaVu-B", fontSize=14,
                              leading=18, textColor=AZUL, spaceAfter=10),
}

_RE_SUB = re.compile(r"([A-Za-zσδελΣεφμ0-9₀])_([A-Za-z0-9áíéêç,]+)")


def _esc(t: str) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _m(t: str) -> str:
    """Escapa o texto e converte 'σ_adm' em σ<sub>adm</sub>."""
    return _RE_SUB.sub(r"\1<sub>\2</sub>", _esc(t))


def _p(texto, estilo="p"):
    return Paragraph(texto, EST[estilo])


def _itens(lista, estilo="item"):
    return [Paragraph(t, EST[estilo], bulletText="•") for t in lista]


# ------------------------------------------------------------------ equações
def _eq(latex: str, tamanho: float = 12.5):
    """Renderiza uma fórmula (mathtext do Matplotlib) como imagem centralizada."""
    buf = io.BytesIO()
    matplotlib.rcParams["mathtext.fontset"] = "dejavusans"
    dpi = 220
    mathtext.math_to_image(f"${latex}$", buf, prop=FontProperties(size=tamanho), dpi=dpi, format="png")
    buf.seek(0)
    from PIL import Image as PILImage
    with PILImage.open(io.BytesIO(buf.getvalue())) as im:
        w_px, h_px = im.size
    buf.seek(0)
    img = Image(buf, width=w_px / dpi * 72, height=h_px / dpi * 72)
    t = Table([[img]], colWidths=[17 * cm])
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
                           ("LINEBEFORE", (0, 0), (0, -1), 2.2, colors.HexColor("#b8c9e3")),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


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


def _tabela(linhas, larguras, cabecalho=True, destaque_ultima=False, destaques=()):
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
    for i in destaques:
        estilo.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#e7f0fb")))
    t.setStyle(TableStyle(estilo))
    return t


def _leitura_grafico(itens: list[tuple[str, str]]):
    """Quadro 'Como ler este gráfico' com os 7 pontos de interpretação."""
    linhas = [[f"<b>{_esc(k)}</b>", v] for k, v in itens]
    dados = [[Paragraph(a, EST["cel"]), Paragraph(b, EST["cel"])] for a, b in linhas]
    t = Table(dados, colWidths=[3.6 * cm, 13.4 * cm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
        ("BACKGROUND", (0, 0), (0, -1), FUNDO_TAB),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [_p("<b>Como interpretar este gráfico</b>", "h3"), t, Spacer(1, 0.25 * cm)]


# ------------------------------------------------------------------ documento com sumário
class _Documento(BaseDocTemplate):
    def __init__(self, destino, **kw):
        super().__init__(destino, **kw)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        self.addPageTemplates([PageTemplate(id="pag", frames=[frame], onPage=_rodape)])
        self._n_marca = 0

    def beforeDocument(self):
        self._n_marca = 0  # chaves estáveis entre as passagens do multiBuild

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ("h1", "h2"):
            nivel = 0 if flowable.style.name == "h1" else 1
            texto = flowable.getPlainText()
            self._n_marca += 1
            chave = f"sec{self._n_marca}"
            self.canv.bookmarkPage(chave)
            self.canv.addOutlineEntry(texto, chave, level=nivel, closed=nivel > 0)
            self.notify("TOCEntry", (nivel, texto, self.page, chave))


def _rodape(canvas, doc):
    if doc.page == 1:
        return
    canvas.saveState()
    canvas.setFont("DejaVu", 7.5)
    canvas.setFillColor(CINZA)
    canvas.drawString(2 * cm, 1.2 * cm, "Análise de Resistência dos Materiais Aplicada a uma Cadeira — Projeto A3")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()


# ------------------------------------------------------------------ memorial (passos)
def _bloco_passo(p: Passo, numero: str) -> list:
    """Bloco didático de uma etapa: o que/por que, fórmula, variáveis, substituição, resultado."""
    itens = [_p(f"{numero} {_m(p.descricao)}", "h3")]
    if p.explicacao:
        itens.append(_p(_m(p.explicacao)))
    if p.latex:
        itens.append(_eq(p.latex))
    elif p.formula:
        itens.append(_p(f"<b>Fórmula:</b> {_m(p.formula)}", "calc"))
    if p.variaveis:
        itens.append(_p("onde:", "calc"))
        for s, sig in p.variaveis:
            itens.append(_p(f"<b>{_m(s)}</b> — {_m(sig)}", "var"))
    if p.substituicao:
        itens.append(_p(f"<b>Substituição:</b> {_m(p.formula.split('=')[0].strip()) + ' = ' if '=' in p.formula else ''}"
                        f"{_m(p.substituicao)}", "calc"))
    if p.desenvolvimento:
        itens.append(_p(f"<b>Desenvolvimento:</b> {_m(p.desenvolvimento)}", "calc"))
    if p.resultado:
        itens.append(_p(f"<b>Resultado:</b> <font color='#184f95'><b>{_m(p.resultado)}</b></font>", "calc"))
    if p.interpretacao:
        itens.append(Spacer(1, 2))
        itens.append(_p(f"<b>Interpretação:</b> {_m(p.interpretacao)}", "p_int"))
    return [KeepTogether(itens), Spacer(1, 0.1 * cm)]


def _blocos_etapa(etapa: EtapaMemorial, prefixo: str, inicio: int = 1) -> list:
    s = []
    k = inicio
    for p in etapa.passos:
        if not (p.explicacao or p.latex or p.variaveis):
            continue
        s += _bloco_passo(p, f"{prefixo}.{k}")
        k += 1
    return s


def _tabela_simples(etapa: EtapaMemorial) -> Table:
    linhas = [["Grandeza", "Símbolo", "Valor"]]
    for p in etapa.passos:
        linhas.append([_m(p.descricao), _m(p.formula), f"<b>{_m(p.resultado)}</b>"])
    return _tabela(linhas, [9.5, 2.5, 5.0])


# --------------------------------------------------------------------------- #
def gerar_relatorio(r: Resultados, caminho, integrantes: list[str] | None = None,
                    turma: str = "", instituicao: str = "Universidade São Judas Tadeu") -> str:
    """Gera o PDF em `caminho` (nome de arquivo ou objeto com .write)."""
    ent, mat, sec, sec_t = r.entradas, r.material, r.secao, r.secao_travessa
    integrantes = [n.strip() for n in (integrantes or []) if n.strip()]
    s: list = []
    s += _capa(r, integrantes, turma, instituicao)
    s += _sumario()
    s += _introducao_objetivos(r)
    s += _fundamentacao(r)
    s += _metodologia(r)
    s += _memorial(r)
    s += _resultados_discussao(r)
    s += _conclusao_referencias(r)

    with tempfile.TemporaryDirectory() as tmp:
        arq = os.path.join(tmp, "relatorio.pdf")
        doc = _Documento(arq, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                         topMargin=2 * cm, bottomMargin=2 * cm,
                         title="Memorial de cálculo — Análise estrutural de cadeira",
                         author=", ".join(integrantes) or "Grupo do Projeto A3",
                         subject=f"{UNIDADE_CURRICULAR} — Projeto A3")
        doc.multiBuild(s)
        if hasattr(caminho, "write"):
            with open(arq, "rb") as f:
                caminho.write(f.read())
        else:
            shutil.copyfile(arq, caminho)
    return caminho


# --------------------------------------------------------------------------- #
#  Capa e sumário
# --------------------------------------------------------------------------- #
def _capa(r, integrantes, turma, instituicao):
    s = [Spacer(1, 1.6 * cm), _p(instituicao, "subtitulo"),
         _p(f"{UNIDADE_CURRICULAR} — Projeto A3 (2026-2)", "subtitulo"),
         Spacer(1, 1.8 * cm),
         _p("Desenvolvimento de um Software de Análise de Resistência dos Materiais "
            "Aplicado a uma Cadeira", "titulo"),
         Spacer(1, 0.4 * cm),
         _p("Relatório técnico e memorial de cálculo", "subtitulo"),
         Spacer(1, 1.8 * cm)]
    s.append(_p("Integrantes do grupo", "capa_rot"))
    if integrantes:
        s += [_p(n, "capa_item") for n in integrantes]
    else:
        s.append(_p("<font color='#c02f2f'>Nomes dos integrantes não informados no software — "
                    "preencha-os antes de gerar a versão de entrega.</font>", "capa_item"))
    s.append(_p("Professores", "capa_rot"))
    s += [_p(f"Prof. {n}", "capa_item") for n in PROFESSORES]
    s.append(_p("Turma", "capa_rot"))
    s.append(_p(turma if turma else "<font color='#c02f2f'>não informada</font>", "capa_item"))
    s.append(_p("Data de emissão", "capa_rot"))
    s.append(_p(date.today().strftime("%d/%m/%Y"), "capa_item"))

    veredito = "SEGURA" if r.segura else "NÃO SEGURA"
    cor_v = VERDE if r.segura else VERMELHO
    caixa = Table([[Paragraph(f"<font color='white'><b>Resultado da análise: CADEIRA {veredito}</b></font>",
                              ParagraphStyle("v", fontName="DejaVu-B", fontSize=12, alignment=TA_CENTER))]],
                  colWidths=[17 * cm])
    caixa.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), cor_v),
                               ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    s += [Spacer(1, 1.2 * cm), caixa, PageBreak()]
    return s


def _sumario():
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("toc0", fontName="DejaVu-B", fontSize=10, leading=12.5, leftIndent=0,
                       firstLineIndent=0, spaceBefore=2),
        ParagraphStyle("toc1", fontName="DejaVu", fontSize=9.2, leading=10.9, leftIndent=16,
                       firstLineIndent=0),
    ]
    toc.dotsMinLevel = 0
    return [Paragraph("Sumário", EST["toc_tit"]), toc, PageBreak()]


# --------------------------------------------------------------------------- #
#  1 Introdução e 2 Objetivos
# --------------------------------------------------------------------------- #
def _introducao_objetivos(r):
    s = [_p("1. Introdução", "h1")]
    s.append(_p(
        "A cadeira é um dos produtos de engenharia mais comuns do cotidiano e, apesar da aparente "
        "simplicidade, é uma estrutura que precisa resistir com segurança ao peso do usuário. "
        "Uma falha nas pernas ou no quadro do assento pode "
        "causar quedas e lesões, de modo que o dimensionamento correto desses elementos é uma "
        "aplicação direta dos conceitos de Resistência dos Materiais."))
    s.append(_p(
        "Neste projeto foi desenvolvido um software em Python, acessível pelo navegador (aplicação "
        "web com Flask) e também como aplicativo desktop (PyQt5), que modela a cadeira como um "
        "conjunto de vigas e apoios. A partir do peso da pessoa, das dimensões da cadeira, da seção "
        "transversal e do material, o programa calcula as reações vinculares, os esforços internos "
        "solicitantes (normal, cortante e momento fletor), as tensões normais provenientes dos "
        "esforços axiais e dos momentos fletores e as deformações da estrutura. Com esses "
        "resultados, verifica se as peças trabalham dentro do limite de segurança do material "
        "escolhido (madeira de eucalipto, aço SAE 1020 ou alumínio 6061-T6) e emite este "
        "relatório. Adota-se um modelo simplificado, com carregamento estático e vertical "
        "(P = m·g), sem fator dinâmico, sem força horizontal e com a carga centrada no assento "
        "(excentricidade e = 0)."))
    s.append(_p(
        "Este documento reúne a parte escrita do projeto — introdução, objetivos, fundamentação "
        "teórica, metodologia, resultados e conclusão — e o memorial de cálculo completo da "
        "simulação realizada, com cada etapa explicada, as fórmulas empregadas, a substituição dos "
        "valores e a interpretação técnica dos resultados e dos gráficos. Todos os valores "
        "apresentados foram calculados pelo software para os parâmetros de entrada listados na "
        "seção 4.5, de modo que o memorial pode ser reproduzido integralmente a partir deles."))

    s.append(_p("2. Objetivos", "h1"))
    s.append(_p("2.1 Objetivo geral", "h2"))
    s.append(_p("Desenvolver um software capaz de analisar os esforços mecânicos em uma cadeira, "
                "permitindo calcular tensões e deformações e verificar se a estrutura suporta uma "
                "determinada carga aplicada por uma pessoa."))
    s.append(_p("2.2 Objetivos específicos", "h2"))
    s += _itens([
        "Modelar a estrutura da cadeira como um conjunto de vigas e apoios.",
        "Permitir a inserção do peso da pessoa (kg).",
        "Permitir a inserção das dimensões da cadeira: altura, largura do assento e espessura das pernas.",
        "Permitir a seleção do material da cadeira (madeira de eucalipto, aço SAE 1020 ou alumínio 6061-T6).",
        "Calcular as reações vinculares, os esforços internos e as tensões normais atuantes na estrutura.",
        "Verificar se a estrutura está dentro do limite de segurança do material.",
        "Gerar um relatório indicando se a cadeira suporta ou não a carga aplicada, com a tensão "
        "máxima nas pernas e o memorial de cálculo.",
    ])
    return s


# --------------------------------------------------------------------------- #
#  3 Fundamentação teórica
# --------------------------------------------------------------------------- #
def _fundamentacao(r):
    s = [PageBreak(), _p("3. Fundamentação teórica", "h1")]
    s.append(_p("Esta seção apresenta os conceitos de Resistência dos Materiais em que o software se "
                "baseia. As mesmas equações reaparecem, com os valores numéricos, no memorial de "
                "cálculo (seção 5)."))

    s.append(_p("3.1 Equilíbrio estático e reações vinculares", "h2"))
    s.append(_p("Um corpo está em equilíbrio quando a resultante das forças e a resultante dos "
                "momentos que atuam sobre ele são nulas. Em um problema plano, isso fornece três "
                "equações independentes:"))
    s.append(_eq(r"\Sigma F_x = 0 \qquad \Sigma F_y = 0 \qquad \Sigma M = 0"))
    s.append(_p("Vínculos (apoios) são as ligações que restringem os movimentos da estrutura; as "
                "forças que eles exercem são as <b>reações vinculares</b>. Na cadeira, o piso é o "
                "vínculo externo: em cada pé o piso exerce uma reação vertical (ele só empurra, não "
                "puxa). Como o modelo adotado não tem forças horizontais, não surgem reações "
                "horizontais. Conhecer as reações é o primeiro passo, pois são elas que carregam as "
                "pernas."))

    s.append(_p("3.2 Esforços internos solicitantes", "h2"))
    s.append(_p("Ao cortar imaginariamente uma barra em uma seção, cada parte exerce sobre a outra "
                "forças e momentos internos que mantêm o equilíbrio do trecho isolado (método das "
                "seções). No plano, esses esforços são:"))
    s += _itens([
        "<b>Esforço normal (N)</b> — força perpendicular à seção, ao longo do eixo da barra. "
        "Positivo quando traciona e negativo quando comprime.",
        "<b>Esforço cortante (V)</b> — força contida no plano da seção, que tende a fazer uma parte "
        "deslizar em relação à outra.",
        "<b>Momento fletor (M)</b> — momento que tende a curvar a barra, comprimindo as fibras de um "
        "lado e tracionando as do outro.",
    ])
    s.append(_p("Os <b>diagramas de esforços internos</b> mostram como N, V e M variam ao longo do "
                "comprimento da peça e permitem localizar a seção mais solicitada. Entre cortante e "
                "momento vale a relação diferencial dM/dx = V: o momento é máximo onde o cortante "
                "troca de sinal (ou na extremidade engastada, quando o cortante não se anula)."))

    s.append(_p("3.3 Tensões normais: esforço axial, flexão e flexo-compressão", "h2"))
    s.append(_p("Tensão é a intensidade de força por unidade de área. A tensão normal σ atua "
                "perpendicularmente à seção e é medida em MPa (1 MPa = 1 N/mm²). O esforço normal "
                "produz uma tensão uniforme na seção:"))
    s.append(_eq(r"\sigma_N = \dfrac{N}{A}"))
    s.append(_p("O momento fletor produz tensões que variam linearmente com a distância à linha "
                "neutra (fórmula da flexão), sendo nulas no centro e máximas nas fibras extremas:"))
    s.append(_eq(r"\sigma_M = \dfrac{M\,c}{I} = \dfrac{M}{W}"))
    s.append(_p("Quando os dois esforços atuam juntos (flexo-compressão), e o material está em regime "
                "elástico-linear, vale o <b>princípio da superposição</b>: as tensões se somam "
                "algebricamente. A fibra mais solicitada é aquela em que a flexão tem o mesmo "
                "sentido do esforço axial:"))
    s.append(_eq(r"\sigma_{\mathrm{máx}} = \dfrac{N}{A} + \dfrac{M}{W}"))

    s.append(_p("3.4 Lei de Hooke e deformações", "h2"))
    s.append(_p("No regime elástico, a deformação específica ε (variação relativa de comprimento) é "
                "proporcional à tensão; a constante de proporcionalidade é o módulo de elasticidade "
                "E do material. Integrando as deformações ao longo da peça obtêm-se os "
                "deslocamentos: o encurtamento de uma barra comprimida e a flecha de uma barra "
                "fletida (equação da linha elástica, E·I·v'' = −M)."))
    s.append(_eq(r"\sigma = E\,\varepsilon \qquad \delta = \dfrac{N\,H}{E\,A}"))

    s.append(_p("3.5 Características geométricas das seções", "h2"))
    s.append(_p("A resistência de uma peça depende não só do material, mas da forma e do tamanho "
                "de sua seção transversal. As grandezas utilizadas são a área A (resiste ao esforço "
                "normal), o momento de inércia I em relação à linha neutra (rigidez à flexão), a "
                "distância c da linha neutra à fibra extrema e o módulo resistente W = I/c "
                "(resistência à flexão). As fórmulas para as seções disponíveis no software estão "
                "na seção 4.4.2."))

    s.append(_p("3.6 Tensão admissível e fator de segurança", "h2"))
    s.append(_p("Para metais, a tensão limite σ<sub>lim</sub> adotada é a tensão de escoamento, a "
                "partir da qual surgem deformações permanentes. Para a madeira, adota-se a "
                "resistência característica à compressão paralela às fibras (NBR 7190). A tensão "
                "admissível é obtida dividindo-se σ<sub>lim</sub> por um fator de segurança FS, que "
                "cobre incertezas de carga, geometria e material. Uma peça é considerada resistente "
                "quando a maior tensão atuante não supera a admissível:"))
    s.append(_eq(r"\sigma_{\mathrm{adm}} = \dfrac{\sigma_{\mathrm{lim}}}{FS} \qquad\qquad "
                 r"\sigma_{\mathrm{atuante}} \leq \sigma_{\mathrm{adm}}"))
    return s


# --------------------------------------------------------------------------- #
#  4 Metodologia
# --------------------------------------------------------------------------- #
def _metodologia(r):
    ent, mat, sec, sec_t = r.entradas, r.material, r.secao, r.secao_travessa
    s = [PageBreak(), _p("4. Metodologia", "h1")]
    s.append(_p("4.1 Etapas do desenvolvimento do software", "h2"))
    s.append(_p("O trabalho foi conduzido nas seguintes etapas, partindo dos requisitos do edital "
                "até a validação dos resultados:"))
    s += _itens([
        "<b>Levantamento de requisitos:</b> identificação, no edital, das entradas obrigatórias "
        "(peso da pessoa, altura da cadeira, largura do assento, espessura das pernas e material), "
        "das saídas obrigatórias (tensão máxima nas pernas e indicação de segurança) e do conteúdo "
        "exigido para o memorial de cálculo.",
        "<b>Modelagem estrutural:</b> representação da cadeira como pernas (barras verticais) e "
        "travessas do assento (vigas), definição das cargas, dos apoios e das hipóteses "
        "simplificadoras (seção 4.6).",
        "<b>Implementação do núcleo de cálculo:</b> programação, em módulos Python independentes "
        "da interface, do banco de materiais, das propriedades geométricas das seções, do "
        "equilíbrio, dos esforços internos, das tensões, das deformações e da verificação.",
        "<b>Validação:</b> testes automatizados (pasta <i>testes/</i>) comparam os resultados do "
        "programa com cálculos feitos à mão para casos conhecidos — por exemplo, momento Q·L/4 e "
        "flecha Q·L³/(48·E·I) da viga bi-apoiada com carga central — e conferem o equilíbrio "
        "(ΣFy = 0) e a coerência entre diagramas e valores máximos.",
        "<b>Interfaces gráficas:</b> desenvolvimento da aplicação web (Flask) e da aplicação "
        "desktop (PyQt5), ambas utilizando o mesmo núcleo de cálculo.",
        "<b>Relatório automático:</b> geração deste documento em PDF com os dados da análise "
        "realizada na interface.",
    ])

    s.append(_p("4.2 Tecnologias utilizadas", "h2"))
    s.append(_tabela([
        ["Tecnologia", "Função no projeto"],
        ["Python 3", "Linguagem de programação de todo o núcleo de cálculo, das interfaces e do relatório."],
        ["NumPy", "Vetores de pontos usados para traçar os diagramas de esforços e a linha elástica."],
        ["Matplotlib", "Gráficos dos diagramas (aplicação desktop e relatório) e renderização das fórmulas."],
        ["Flask / Gunicorn", "Servidor da aplicação web: expõe o núcleo de cálculo por uma API HTTP."],
        ["HTML, CSS e JavaScript (SVG)", "Interface web executada no navegador; desenha os diagramas em SVG."],
        ["PyQt5", "Interface gráfica da aplicação desktop."],
        ["ReportLab", "Geração do relatório técnico em PDF."],
    ], [4.5, 12.5]))

    s.append(_p("4.3 Implementação do software", "h2"))
    s.append(_p("O código foi organizado de forma que toda a lógica de engenharia fique em um único "
                "pacote (<i>nucleo/</i>), compartilhado pelas duas interfaces. Assim, para as mesmas "
                "entradas, a aplicação web e a desktop produzem exatamente os mesmos resultados, "
                "gráficos e relatório."))
    s.append(_tabela([
        ["Módulo", "Responsabilidade"],
        ["nucleo/materiais.py", "Banco de materiais: tensão limite, módulo de elasticidade e densidade."],
        ["nucleo/secoes.py", "Seções transversais disponíveis e cálculo de A, I, c e W."],
        ["nucleo/calculos.py", "Carregamento, equilíbrio, esforços internos, tensões, deformações, "
                               "verificação de segurança e montagem do memorial de cálculo."],
        ["nucleo/diagramas.py", "Figuras do modelo, dos diagramas de esforços e das tensões."],
        ["nucleo/relatorio.py", "Montagem deste relatório em PDF."],
        ["app.py + static/", "Aplicação web (Flask): rotas /api/opcoes, /api/analisar e /api/relatorio."],
        ["main.py + interface/", "Aplicação desktop (PyQt5)."],
        ["testes/test_calculos.py", "Testes automatizados que comparam o software com cálculos manuais."],
    ], [4.5, 12.5]))
    s.append(_p("<b>Fluxo de execução.</b> O usuário preenche os dados na interface; a cada alteração "
                "os valores são enviados ao núcleo, que (1) valida as entradas, (2) obtém as "
                "propriedades do material e da seção, (3) calcula as cargas, (4) as reações "
                "vinculares, (5) os esforços internos, (6) as tensões normais, (7) as deformações e "
                "(8) faz a verificação de segurança. O resultado é exibido imediatamente (veredito, "
                "gráficos e memorial) e pode ser exportado como relatório PDF."))

    # ---------------------------------------------------- 4.4 materiais e seções
    s.append(_p("4.4 Materiais e seções transversais disponíveis", "h2"))
    s.append(_p("Esta seção documenta, separadamente, <b>(a)</b> as opções que o software oferece ao "
                "usuário e <b>(b)</b> as opções efetivamente escolhidas para a simulação apresentada "
                "neste relatório."))
    s.append(_p("4.4.1 Materiais disponíveis no software", "h3"))
    s.append(_p("O software oferece exclusivamente três materiais. Os valores são de referência "
                "(não resultados de ensaio das peças reais) e dependem da condição de cada material, "
                "declarada na tabela."))
    linhas = [["Material", "Condição / premissa", "σ<sub>lim</sub> [MPa]", "σ<sub>e</sub> / σ<sub>r</sub> [MPa]",
               "E [GPa]", "Fonte", "Nesta análise"]]
    sel = []
    for i, m in enumerate(MATERIAIS.values(), start=1):
        usado = m.nome == mat.nome
        if usado:
            sel.append(i)
        lim_txt = (f"{_f(m.escoamento_mpa, 0)} / {_f(m.ruptura_mpa, 0)}" if m.escoamento_mpa
                   else "não se aplica")
        linhas.append([m.nome, _m(m.condicao), _f(m.tensao_limite_mpa, 1),
                       lim_txt, _f(m.modulo_elasticidade_gpa, 1), _m(m.fonte),
                       "<b>selecionado</b>" if usado else "—"])
    s.append(_tabela(linhas, [2.6, 3.5, 1.5, 1.9, 1.2, 4.6, 1.7], destaques=sel))
    s.append(_p("σ<sub>lim</sub> = tensão limite usada na verificação: f<sub>c0,k</sub> (resistência "
                "característica à compressão paralela às fibras) para a madeira e o limite de "
                "escoamento σ<sub>e</sub> para os metais. σ<sub>r</sub> = limite de resistência à tração.",
                "legenda"))
    s += _itens([
        "<b>Madeira de eucalipto:</b> as propriedades variam com a espécie, o lote, a classificação e a "
        "umidade, por isso não há um valor universal. Adota-se a premissa de madeira de eucalipto "
        "<b>classificada na classe C40</b> das dicotiledôneas da NBR 7190:1997 (umidade de 12 %), com "
        "f<sub>c0,k</sub> = 40 MPa e E<sub>c0,m</sub> = 19 500 MPa. Os valores são os da classe; se a "
        "espécie ou o lote forem outros, a classificação precisa ser refeita. Estudos indicam que o "
        "módulo médio real de lotes enquadrados na C40 pode ser inferior ao valor normativo.",
        "<b>Aço SAE 1020:</b> condição <b>laminado a quente</b> — escoamento de 210 MPa, resistência de "
        "380 MPa e E = 200 GPa. Na condição trefilado a frio o escoamento é bem maior, por isso a "
        "condição precisa ser declarada.",
        "<b>Alumínio 6061-T6:</b> têmpera T6 (solubilizado e envelhecido artificialmente) — escoamento "
        "de 276 MPa, resistência de 310 MPa e E = 68,9 GPa.",
    ])

    s.append(_p("4.4.2 Seções transversais disponíveis no software", "h3"))
    s.append(_p("O software oferece quatro seções transversais, utilizáveis tanto nas pernas quanto "
                "nas travessas do assento. Os campos de entrada se adaptam à seção escolhida: as "
                "maciças pedem uma dimensão e as vazadas pedem a dimensão externa e a interna "
                "(que deve ser menor que a externa). Todas são duplamente simétricas, portanto o "
                "momento de inércia é o mesmo para flexão em qualquer direção principal."))
    s.append(_tabela([
        ["Seção", "Dimensões de entrada", "Área A", "Inércia I", "c", "Módulo resistente W"],
        ["Quadrada maciça", "lado a", "a²", "a⁴ / 12", "a / 2", "a³ / 6"],
        ["Circular maciça", "diâmetro d", "π·d² / 4", "π·d⁴ / 64", "d / 2", "π·d³ / 32"],
        ["Circular vazada", "diâmetro externo D, interno d", "π·(D² − d²) / 4", "π·(D⁴ − d⁴) / 64",
         "D / 2", "π·(D⁴ − d⁴) / (32·D)"],
        ["Quadrada vazada", "lado externo B, interno b", "B² − b²", "(B⁴ − b⁴) / 12", "B / 2",
         "(B⁴ − b⁴) / (6·B)"],
    ], [2.9, 3.6, 2.6, 2.8, 1.3, 3.8]))
    s.append(Spacer(1, 0.2 * cm))
    s.append(_p("Nas seções vazadas, o material retirado do centro fica perto da linha neutra, onde "
                "pouco contribui para a rigidez à flexão: com a mesma massa, um tubo tem momento de "
                "inércia maior que uma barra maciça."))

    s.append(_p("4.4.3 Opções selecionadas para a análise deste relatório", "h3"))
    linhas_sel = [
        ["Item", "Opção selecionada", "Propriedades utilizadas no cálculo"],
        ["Material", f"<b>{_esc(mat.nome)}</b> ({_m(mat.condicao)})",
         f"σ<sub>lim</sub> = {_f(mat.tensao_limite_mpa, 1)} MPa ({_m(mat.criterio)}); "
         f"E = {_f(mat.modulo_elasticidade_gpa, 1)} GPa"],
        ["Seção das pernas", f"<b>{_esc(sec.tipo)}</b><br/>{_esc(sec.dimensoes())}",
         f"A = {_f(sec.A * 1e6, 2)} mm²; I = {_f(sec.I * 1e12, 0)} mm⁴; c = {_f(sec.c * 1e3, 2)} mm; "
         f"W = {_f(sec.W * 1e9, 1)} mm³"],
        ["Seção das travessas",
         "<b>igual à das pernas</b>" if ent.travessa_igual_perna
         else f"<b>{_esc(sec_t.tipo)}</b><br/>{_esc(sec_t.dimensoes())}",
         f"A = {_f(sec_t.A * 1e6, 2)} mm²; I = {_f(sec_t.I * 1e12, 0)} mm⁴; c = {_f(sec_t.c * 1e3, 2)} mm; "
         f"W = {_f(sec_t.W * 1e9, 1)} mm³"],
    ]
    s.append(_tabela(linhas_sel, [3.2, 5.0, 8.8]))

    # ---------------------------------------------------- 4.5 parâmetros
    s.append(_p("4.5 Parâmetros de entrada e premissas fixas", "h2"))
    s.append(_p("A tabela reúne todos os valores informados no software para esta simulação. As "
                "cinco entradas exigidas pelo edital estão identificadas como “edital”; as demais "
                "(“modelo”) são parâmetros complementares; as linhas “fixo” são premissas do modelo, "
                "que o usuário não altera."))
    E_, C_, F_ = "edital", "modelo", "fixo"
    linhas_par = [
        ["Parâmetro", "Símbolo", "Valor", "Origem", "Função na análise"],
        ["Peso (massa) da pessoa", "m", f"{_f(ent.massa_kg, 1)} kg", E_, "gera a carga P = m·g"],
        ["Altura da cadeira (assento ao piso)", "H", f"{_f(ent.altura_mm, 0)} mm", E_,
         "comprimento das pernas; encurtamento"],
        ["Largura do assento", "L", f"{_f(ent.largura_mm, 0)} mm", E_,
         "posição lateral das pernas; validação da geometria"],
        ["Espessura das pernas", sec.simbolo, f"{_f(ent.espessura_perna_mm, 1)} mm", E_,
         "dimensão externa da seção das pernas"],
    ]
    if sec.vazada:
        linhas_par.append(["Dimensão interna das pernas", sec.simbolo_interno,
                           f"{_f(ent.interna_perna_mm, 1)} mm", C_, "furo da seção vazada"])
    linhas_par += [
        ["Material da cadeira", "—", _esc(mat.nome), E_, "define σ<sub>lim</sub> e E"],
        ["Seção transversal das pernas", "—", _esc(sec.tipo), C_, "fórmulas geométricas"],
        ["Profundidade do assento", "ℓ", f"{_f(ent.profundidade_mm, 0)} mm", C_,
         "distância entre pernas dianteira e traseira; vão da travessa"],
        ["Seção da travessa", "—",
         "igual à das pernas" if ent.travessa_igual_perna else _esc(sec_t.descricao()), C_,
         "propriedades da viga do assento"],
        ["Fator de segurança requerido", "FS", _f(ent.fator_seguranca, 2), C_, "σ<sub>adm</sub> = σ<sub>lim</sub>/FS"],
        ["Aceleração da gravidade", "g", f"{_f(G, 2)} m/s²", F_, "converte massa em peso"],
        ["Excentricidade da carga", "e", f"{_f(r.excentricidade_mm, 0)} mm", F_, "carga centrada no assento"],
    ]
    s.append(_tabela(linhas_par, [4.2, 1.9, 3.0, 1.8, 6.1]))

    # ---------------------------------------------------- 4.6 modelagem
    s.append(_p("4.6 Modelagem estrutural da cadeira", "h2"))
    s.append(_p("A cadeira real é uma estrutura tridimensional com ligações complexas. Para torná-la "
                "calculável com as ferramentas da Resistência dos Materiais, ela é representada como "
                "um conjunto de barras (pernas) e vigas (travessas) com apoios idealizados, adotando-se "
                "as premissas a seguir."))
    s += _itens([
        "<b>Carregamento estático:</b> a única ação é o peso do usuário, P = m·g, aplicado "
        "verticalmente. <b>Não se aplica fator dinâmico</b> (nenhum multiplicador de impacto).",
        "<b>Sem força horizontal:</b> o atrito e os esforços horizontais no assento não são "
        "considerados; logo não há reações horizontais no piso.",
        f"<b>Excentricidade adotada: e = {_f(r.excentricidade_mm, 0)} mm.</b> A carga atua no centro "
        "do assento, sem deslocamento em relação ao eixo de referência (meio da profundidade). "
        "Excentricidade nula não significa ausência de momentos: a travessa continua fletida pela "
        "carga, que atua transversalmente ao seu eixo.",
        "Material homogêneo, isotrópico e em regime elástico-linear (Lei de Hooke); para a madeira "
        "adotam-se as propriedades na direção paralela às fibras.",
        "Quatro pernas verticais idênticas, de comprimento H, nos cantos de um retângulo L × ℓ. "
        "Por simetria lateral, cada lado (perna dianteira, perna traseira e travessa lateral) recebe "
        "metade da carga, e a análise é feita na vista lateral (problema plano).",
        "Cada perna é uma barra vertical entre o quadro do assento e o piso, carregada apenas pela "
        "reação vertical alinhada com seu eixo: compressão simples (V = 0 e M = 0).",
        "Cada travessa lateral do assento é uma viga bi-apoiada sobre as pernas, de vão ℓ, com carga "
        "concentrada Q = P/2 no meio do vão — hipótese conservadora em relação à carga distribuída.",
        "Peso próprio da cadeira e encosto desprezados (pequenos frente à carga do usuário).",
    ])
    s.append(_figura(figura_modelo(r), 17, "Figura 1 — Modelo estrutural: carga aplicada e reações "
                                           "vinculares (vista lateral e vista superior)."))
    s += _leitura_grafico([
        ("O que representa", "O modelo de cálculo da cadeira: à esquerda, a vista lateral com a carga "
                             "P e as reações do piso; à direita, a vista superior com a posição das "
                             "pernas e a reação vertical em cada uma."),
        ("Grandezas", "Forças em newtons [N] e dimensões em milímetros [mm]."),
        ("Eixos e unidades", "Desenho em escala das dimensões H, ℓ e L informadas; não há eixos "
                             "numéricos, as cotas indicam as medidas."),
        ("Sentidos", "Seta para baixo: peso do usuário, aplicado no centro do assento (e = 0). Setas "
                     "para cima: reações do piso, de compressão nos pés. Não há forças horizontais."),
        ("Máximos e mínimos", f"Com a carga centrada, as quatro pernas recebem a mesma reação: "
                              f"{_f(r.R_D, 1)} N cada (P/4)."),
        ("Relação com a cadeira", "Mostra como o peso do usuário chega ao piso, dividido igualmente "
                                  "entre os quatro pés."),
        ("Importância", "As reações aqui indicadas são os carregamentos das pernas e das travessas "
                        "nas etapas seguintes do memorial."),
    ])
    return s


# --------------------------------------------------------------------------- #
#  5 Memorial de cálculo
# --------------------------------------------------------------------------- #
def _memorial(r):
    ent = r.entradas
    s = [PageBreak(), _p("5. Memorial de cálculo", "h1")]
    s.append(_p("O memorial apresenta todas as etapas de cálculo na ordem em que o software as "
                "executa. Para cada etapa indica-se o que é calculado e por quê, a fórmula, o "
                "significado das variáveis, a substituição numérica, o resultado e sua interpretação. "
                "Adota-se o sistema N–mm–MPa (1 MPa = 1 N/mm²) nas substituições."))

    # 5.1
    s.append(_p("5.1 Dados de entrada e propriedades do material", "h2"))
    s.append(_p(_m(r.etapa("dados").introducao)))
    s.append(_tabela_simples(r.etapa("dados")))
    s.append(Spacer(1, 0.2 * cm))
    et = r.etapa("material")
    s.append(_tabela([["Propriedade", "Símbolo", "Valor"]] +
                     [[_m(p.descricao), _m(p.formula.split('=')[0]), f"<b>{_m(p.resultado)}</b>"]
                      for p in et.passos[:2]], [9.5, 2.5, 5.0]))
    s.append(_p(_m(et.passos[0].explicacao) + " " + _m(et.passos[1].explicacao), "legenda"))
    s += _bloco_passo(et.passos[2], "5.1.1")

    # 5.2
    et = r.etapa("geometria")
    s.append(_p("5.2 Características geométricas dos elementos estruturais", "h2"))
    s.append(_p(_m(et.introducao)))
    s += _blocos_etapa(et, "5.2")
    if ent.travessa_igual_perna:
        s.append(_p("As travessas do assento têm a mesma seção das pernas; portanto utilizam os "
                    "mesmos valores de A, I, c e W."))

    # 5.3
    et = r.etapa("carregamento")
    s.append(_p("5.3 Carregamento", "h2"))
    s.append(_p(_m(et.introducao)))
    s += _blocos_etapa(et, "5.3")

    # 5.4
    et = r.etapa("reacoes")
    s.append(_p("5.4 Cálculo das reações vinculares", "h2"))
    s.append(_p(_m(et.introducao)))
    s += _blocos_etapa(et, "5.4")
    s.append(_tabela([
        ["Reação", "Por perna", "Total (2 pernas)"],
        ["Vertical — pernas dianteiras (R<sub>D</sub>)", f"{_f(r.R_D, 1)} N", f"{_f(r.R_D_total, 1)} N"],
        ["Vertical — pernas traseiras (R<sub>T</sub>)", f"{_f(r.R_T, 1)} N", f"{_f(r.R_T_total, 1)} N"],
        ["Horizontal em cada pé", "0 N", "0 N (sem forças horizontais)"],
        ["Conferência ΣFy: R<sub>D,tot</sub> + R<sub>T,tot</sub> = P", "",
         f"{_f(r.R_D_total + r.R_T_total, 1)} N = {_f(r.P, 1)} N"],
    ], [8.0, 4.0, 5.0], destaque_ultima=True))

    # 5.5
    et = r.etapa("esforcos")
    s.append(_p("5.5 Cálculo dos esforços internos solicitantes", "h2"))
    s.append(_p(_m(et.introducao)))
    s += _blocos_etapa(et, "5.5")

    # 5.6 diagramas
    s += _secao_diagramas(r)

    # 5.7 tensões
    et = r.etapa("tensoes")
    s.append(PageBreak())
    s.append(_p("5.7 Cálculo das tensões normais", "h2"))
    s.append(_p(_m(et.introducao)))
    s += _blocos_etapa(et, "5.7")
    s.append(_figura(figura_distribuicao_tensoes(r), 17,
                     "Figura 4 — Distribuição da tensão normal nas seções críticas: perna (compressão "
                     "uniforme) e travessa no meio do vão (flexão)."))
    s += _leitura_grafico([
        ("O que representa", "Como a tensão normal varia de uma face à outra da seção: à esquerda na "
                             "perna, à direita na travessa, na seção sob a carga (momento máximo)."),
        ("Grandeza", "Tensão normal σ [MPa]."),
        ("Eixos e unidades", "Horizontal: tensão σ [MPa]. Vertical: posição z na seção [mm], medida a "
                             "partir da linha neutra (z = 0) até as faces externas "
                             f"(perna: ±{_f(r.secao.c * 1e3, 1)} mm; travessa: ±{_f(r.secao_travessa.c * 1e3, 1)} mm)."),
        ("Sinais", "Valores negativos indicam compressão e positivos indicam tração. Na travessa, z "
                   "positivo é a face superior, que fica comprimida."),
        ("Máximos e mínimos", f"Perna: σ = −{_f(r.sigma_max_perna / 1e6, 3)} MPa constante em toda a seção. "
                              f"Travessa: −{_f(r.sigma_travessa / 1e6, 3)} MPa na face superior e "
                              f"+{_f(r.sigma_travessa / 1e6, 3)} MPa na inferior; zero na linha neutra."),
        ("Relação com a cadeira", "A perna apenas transmite o peso ao piso (compressão uniforme); a "
                                  "travessa sustenta o assento como uma viga, com tração e compressão "
                                  "nas faces opostas."),
        ("Importância", "Mostra que as tensões máximas usadas na verificação ocorrem em toda a seção da "
                        "perna e nas fibras extremas da travessa."),
    ])

    # 5.8 deformações
    et = r.etapa("deformacoes")
    s.append(_p("5.8 Cálculo das deformações", "h2"))
    s.append(_p(_m(et.introducao)))
    s += _blocos_etapa(et, "5.8")

    # 5.9 verificação
    et = r.etapa("verificacao")
    s.append(_p("5.9 Verificação da resistência do material", "h2"))
    s.append(_p(_m(et.introducao)))
    linhas = [["Verificação", "Condição", "FS real", "Situação"]]
    for p in et.passos[:2]:
        cor = "#0a7d0a" if p.resultado == "ATENDE" else "#c02f2f"
        linhas.append([_m(p.descricao), _m(p.formula), _m(p.substituicao),
                       f"<font color='{cor}'><b>{p.resultado}</b></font>"])
    s.append(_tabela(linhas, [4.5, 5.5, 4.4, 2.6]))
    s.append(Spacer(1, 0.2 * cm))
    s += _bloco_passo(et.passos[2], "5.9.1")
    return s


def _secao_diagramas(r):
    """Seção 5.6 — diagramas de esforços internos solicitantes (perna e travessa)."""
    ent = r.entradas
    H = ent.altura_mm
    P = ent.profundidade_mm
    a_mm = r.a_carga * 1000
    s = [PageBreak(), _p("5.6 Diagramas de esforços internos solicitantes", "h2")]
    s.append(_p("Os diagramas mostram como os esforços internos calculados na seção 5.5 variam ao "
                "longo de cada peça. Eles são traçados pelo software com as mesmas expressões e os "
                "mesmos valores do memorial, de modo que os máximos lidos nos gráficos coincidem "
                "com os valores calculados."))
    s.append(_p("5.6.1 Conceitos e convenção de sinais", "h3"))
    s += _itens([
        "<b>Esforço cortante (V)</b> é a resultante das forças transversais de um lado da seção. "
        "Na cadeira, ele surge na travessa pelas reações das pernas e pela carga do usuário; na "
        "perna ele é nulo, porque nenhuma força atua transversalmente ao seu eixo. Indica a "
        "tendência de uma parte da peça deslizar em relação à outra.",
        "<b>Momento fletor (M)</b> é a resultante dos momentos das forças de um lado da seção. Ele "
        "curva a peça, comprimindo um lado e tracionando o outro. Mesmo com excentricidade nula, "
        "ele existe na travessa, porque o peso atua perpendicularmente ao eixo da viga; é o esforço "
        "que gera as maiores tensões normais da cadeira.",
        "<b>Esforço normal (N)</b> é negativo quando comprime. Nas pernas ele vem da parcela do peso "
        "que cada perna transmite ao piso.",
        "Na travessa, o diagrama de momento é desenhado do <b>lado tracionado</b> da viga (convenção "
        "usual em Resistência dos Materiais): o momento positivo, que traciona a fibra inferior, "
        "aparece abaixo do eixo.",
        "Para a perna, a coordenada y é medida a partir do pé (y = 0, no piso) até a ligação com o "
        "assento (y = H).",
    ])

    s.append(_p("5.6.2 Diagramas da perna", "h3"))
    s.append(_p(f"Condições de apoio e carregamento: barra vertical de comprimento H = {_f(H, 0)} mm, "
                f"entre o quadro do assento e o piso. No topo, a travessa transmite a força vertical "
                f"{_f(r.N_perna, 1)} N; no pé, o piso reage com R = {_f(r.N_perna, 1)} N, também "
                f"vertical e alinhada com o eixo. Cortando a perna a uma altura y e isolando o trecho "
                f"inferior: N(y) = −R, V(y) = 0 e M(y) = 0 — compressão simples."))
    s.append(_figura(figura_perna(r), 17,
                     "Figura 2 — Corpo livre e diagramas de esforço normal, cortante e momento fletor "
                     "na perna."))
    s += _leitura_grafico([
        ("O que representa", "A variação dos esforços internos ao longo da altura da perna. À "
                             "esquerda, o corpo livre com os vínculos e as forças."),
        ("Grandezas", "Esforço normal N [N], esforço cortante V [N] e momento fletor M [N·m]."),
        ("Eixos e unidades", "Eixo vertical: altura y a partir do pé [mm] (0 = piso; "
                             f"{_f(H, 0)} = ligação com o assento). Eixo horizontal: valor do esforço."),
        ("Sinais", "N negativo indica compressão em toda a perna. V e M são nulos, logo não há sinal "
                   "a interpretar."),
        ("Máximos e mínimos", f"N é constante ({_f(-r.N_perna, 1)} N): máximo e mínimo coincidem e "
                              f"qualquer seção da perna é igualmente solicitada. V = 0 e M = 0 em toda a perna."),
        ("Relação com a cadeira", "Com a carga vertical e centrada, a perna funciona como um pilar: "
                                  "apenas leva ao piso a parcela do peso que recebe da travessa."),
        ("Importância", "O valor de N lido neste diagrama é o usado em σ<sub>máx</sub> = N/A + M/W "
                        "(seção 5.7), com M = 0."),
    ])

    s.append(_p("5.6.3 Diagramas da travessa lateral do assento", "h3"))
    s.append(_p(f"Condições de apoio e carregamento: viga bi-apoiada sobre as pernas traseira (A, x = 0) "
                f"e dianteira (B, x = ℓ = {_f(P, 0)} mm), com carga concentrada Q = {_f(r.Q_travessa, 1)} N "
                f"no meio do vão, x = a = {_f(a_mm, 1)} mm (e = 0). Reações: R<sub>A</sub> = {_f(r.R_A, 1)} N e "
                f"R<sub>B</sub> = {_f(r.R_B, 1)} N."))
    s.append(_figura(figura_travessa(r), 16,
                     "Figura 3 — Carregamento, esforço cortante, momento fletor e linha elástica da "
                     "travessa lateral do assento."))
    s += _leitura_grafico([
        ("O que representa", "De cima para baixo: o esquema da viga (apoios, carga e reações), o "
                             "diagrama de esforço cortante, o diagrama de momento fletor e a deformada "
                             "(linha elástica) da travessa. A linha pontilhada marca a posição da carga."),
        ("Grandezas", "Cortante V [N], momento fletor M [N·m] e deslocamento vertical v [mm]."),
        ("Eixos e unidades", f"Eixo horizontal comum: posição x ao longo da travessa [mm], de 0 (perna "
                             f"traseira) a {_f(P, 0)} (perna dianteira). Eixos verticais: valor de cada grandeza."),
        ("Sinais", f"V é positivo à esquerda da carga ({_f(r.R_A, 1)} N) e negativo à direita "
                   f"({_f(r.R_A - r.Q_travessa, 1)} N): o salto tem o tamanho de Q. M é positivo em todo o "
                   "vão (fibra inferior tracionada) e está desenhado abaixo do eixo. A deflexão é para baixo."),
        ("Máximos e mínimos", f"M é nulo nos apoios e máximo sob a carga: M<sub>máx</sub> = "
                              f"{_f(r.M_travessa, 3)} N·m, exatamente onde V troca de sinal (dM/dx = V). "
                              f"A flecha máxima é {_f(r.delta_travessa * 1e3, 4)} mm."),
        ("Relação com a cadeira", "A travessa é a peça que recebe diretamente o peso do usuário e o "
                                  "leva às pernas; o diagrama mostra que o meio do assento é a região "
                                  "mais fletida. Com a carga centrada, os diagramas são simétricos."),
        ("Importância", "M<sub>máx</sub> é usado na tensão de flexão da travessa (σ<sub>t</sub> = M/W) e "
                        "a linha elástica mostra se o assento é rígido o bastante para o uso."),
    ])
    s.append(_p("5.6.4 Uso dos diagramas no restante do cálculo", "h3"))
    s.append(_p(f"Dos diagramas extraem-se os esforços da seção crítica de cada peça: na perna, "
                f"N = {_f(r.N_perna, 1)} N e M = 0 (qualquer seção); na travessa, "
                f"M = {_f(r.M_travessa, 3)} N·m (sob a carga). O esforço cortante não é usado na "
                f"verificação, que considera apenas as tensões normais, conforme o escopo do "
                f"projeto; ele é apresentado para completar o equilíbrio das peças e localizar o "
                f"momento máximo."))
    return s


# --------------------------------------------------------------------------- #
#  6 Resultados e discussão
# --------------------------------------------------------------------------- #
def _resultados_discussao(r):
    ent, mat = r.entradas, r.material
    veredito = "SEGURA" if r.segura else "NÃO SEGURA"
    uso_p = 100 * r.sigma_max_perna / r.sigma_adm
    uso_t = 100 * r.sigma_travessa / r.sigma_adm
    s = [PageBreak(), _p("6. Resultados e discussão", "h1")]
    s.append(_p("6.1 Resultados da simulação", "h2"))
    s.append(_p("Saídas exigidas pelo edital:", "p"))
    s.append(_tabela([
        ["Saída obrigatória", "Resultado"],
        ["Tensão máxima nas pernas da cadeira", f"<b>{_f(r.sigma_max_perna / 1e6, 3)} MPa</b> "
                                                 f"(admissível: {_f(r.sigma_adm / 1e6, 2)} MPa)"],
        ["Indicação se a cadeira é segura", f"<b>CADEIRA {veredito}</b>"],
    ], [8.0, 9.0], destaque_ultima=True))
    s.append(Spacer(1, 0.3 * cm))
    s.append(_p("Resumo de todos os resultados calculados (carga estática, sem força horizontal, e = 0):"))
    ok = lambda c: "atende" if c else "<font color='#c02f2f'>NÃO atende</font>"  # noqa: E731
    s.append(_tabela([
        ["Grandeza", "Valor", "Situação"],
        ["Material / seção das pernas", f"{_esc(mat.nome)} / {_esc(r.secao.descricao())}", ""],
        ["Peso do usuário P = m·g", f"{_f(r.P, 1)} N", ""],
        ["Reação por perna (dianteira / traseira)", f"{_f(r.R_D, 1)} N / {_f(r.R_T, 1)} N", ""],
        ["Esforço normal na perna", f"{_f(r.N_perna, 1)} N (compressão)", ""],
        ["Momento fletor — perna / travessa", f"0 / {_f(r.M_travessa, 3)} N·m", ""],
        ["Tensão normal máxima nas pernas (N/A)", f"{_f(r.sigma_max_perna / 1e6, 3)} MPa", ok(r.ok_perna)],
        ["Tensão normal máxima na travessa (M/W)", f"{_f(r.sigma_travessa / 1e6, 3)} MPa", ok(r.ok_travessa)],
        ["Tensão admissível (σ<sub>lim</sub>/FS)", f"{_f(r.sigma_adm / 1e6, 2)} MPa", ""],
        ["Fator de segurança real — pernas / travessa", f"{_f(r.fs_perna, 2)} / {_f(r.fs_travessa, 2)}",
         f"requerido ≥ {_f(ent.fator_seguranca, 2)}"],
        ["Encurtamento da perna", f"{_f(r.delta_axial * 1e3, 4)} mm", ""],
        ["Flecha máxima da travessa", f"{_f(r.delta_travessa * 1e3, 4)} mm", ""],
        ["Massa máxima admissível do usuário", f"{_f(r.massa_maxima, 1)} kg", ""],
        ["Resultado final", f"<b>CADEIRA {veredito}</b>", ""],
    ], [8.0, 5.5, 3.5], destaque_ultima=True))

    s.append(_p("6.2 Interpretação dos gráficos", "h2"))
    s.append(_p("Os gráficos das seções anteriores formam uma sequência: a Figura 1 mostra como a "
                "carga chega ao piso; as Figuras 2 e 3 mostram os esforços em cada peça; a Figura 4 "
                "mostra como a tensão se distribui nas seções críticas. A Figura 5, abaixo, resume a "
                "verificação comparando cada tensão com o limite admissível."))
    s.append(_figura(figura_tensoes(r), 17,
                     "Figura 5 — Tensões normais atuantes comparadas com a tensão admissível."))
    s += _leitura_grafico([
        ("O que representa", "A tensão normal máxima de cada elemento verificado, lado a lado, e a "
                             "linha tracejada da tensão admissível."),
        ("Grandeza", "Tensão normal [MPa]."),
        ("Eixos e unidades", "Eixo horizontal: tensão [MPa]. Eixo vertical: elemento verificado."),
        ("Sinais", "As tensões estão em módulo: a da perna é de compressão; a da travessa é a das fibras "
                   "extremas (compressão em cima, tração embaixo, de mesmo valor)."),
        ("Máximos e mínimos", f"Maior tensão: {'travessa' if r.sigma_travessa > r.sigma_max_perna else 'perna'} "
                              f"({_f(max(r.sigma_travessa, r.sigma_max_perna) / 1e6, 3)} MPa). Barras verdes "
                              "estão abaixo do limite; vermelhas o ultrapassam."),
        ("Relação com a cadeira", "Indica qual peça da cadeira falharia primeiro se a carga aumentasse."),
        ("Importância", f"A distância de cada barra até a linha tracejada é a reserva de resistência: "
                        f"a perna usa {_f(uso_p, 1)}% e a travessa {_f(uso_t, 1)}% da tensão admissível."),
    ])

    s.append(_p("6.3 Discussão dos resultados", "h2"))
    critico = r.elemento_critico.lower()
    s.append(_p(
        f"Para o usuário de {_f(ent.massa_kg, 1)} kg, o peso aplicado é P = {_f(r.P, 1)} N, usado "
        f"diretamente como carga estática. O elemento mais solicitado é: <b>{critico}</b>. A perna "
        f"trabalha com {_f(uso_p, 1)}% da tensão admissível e a travessa com {_f(uso_t, 1)}%."))
    razao = r.sigma_travessa / r.sigma_max_perna if r.sigma_max_perna > 0 else float("inf")
    s.append(_p(
        f"Com a carga vertical e centrada (e = 0) e sem força horizontal, as pernas trabalham em "
        f"compressão simples e cada uma recebe P/4 = {_f(r.N_perna, 1)} N. A travessa, ao contrário, "
        f"é fletida pelo peso que atua perpendicularmente ao seu eixo; por isso, mesmo recebendo "
        f"apenas metade do peso, ela tem tensão cerca de {_f(razao, 0)} vezes maior que a das "
        f"pernas: a flexão é muito mais exigente para uma seção do que a compressão axial."
        if razao != float("inf") else ""))
    rel_t = ent.profundidade_mm / (r.delta_travessa * 1e3) if r.delta_travessa > 0 else float("inf")
    s.append(_p(
        f"Quanto às deformações, calculadas com o módulo de elasticidade do {mat.nome} "
        f"(E = {_f(mat.modulo_elasticidade_gpa, 1)} GPa), a flecha da travessa é "
        f"{_f(r.delta_travessa * 1e3, 4)} mm"
        f"{f' (1/{_f(rel_t, 0)} do vão)' if rel_t != float('inf') else ''} e o encurtamento da "
        f"perna é {_f(r.delta_axial * 1e3, 4)} mm. " + _frase_deformacoes(r)))
    s.append(_p(
        f"Como todas as tensões são proporcionais à carga, a massa máxima admissível do usuário "
        f"para esta geometria e este material é de {_f(r.massa_maxima, 1)} kg, mantendo o fator de "
        f"segurança {_f(ent.fator_seguranca, 2)}. Pelas fórmulas da seção 4.4.2, o módulo resistente "
        f"cresce com a terceira potência da dimensão externa: aumentar a seção da travessa é a forma "
        f"mais eficiente de reduzir a tensão de flexão. Já a troca de material não altera as "
        f"tensões atuantes (que dependem só das cargas e da geometria), mas muda o limite "
        f"admissível e as deformações."))

    s.append(_p("6.4 Limitações do modelo", "h2"))
    s += _itens([
        "O carregamento é exclusivamente estático e vertical: não se consideram o impacto ao sentar "
        "(fator dinâmico), forças horizontais por atrito ou inclinação, nem carga fora do centro do "
        "assento (e = 0). Situações reais com essas ações produzem esforços maiores, inclusive "
        "flexão nas pernas.",
        "O escopo da verificação limita-se às tensões normais. Tensões de cisalhamento e "
        "verificações de outra natureza não são calculadas.",
        "As ligações (encaixes, cola, parafusos, soldas) não são verificadas; na prática elas "
        "costumam ser o ponto mais fraco de uma cadeira.",
        "Não são considerados concentração de tensões, fadiga por uso repetido, fluência e "
        "defeitos (nós e fissuras na madeira, por exemplo).",
        "A madeira é tratada como material isotrópico com as propriedades paralelas às fibras; o "
        "comportamento real é anisotrópico e influenciado pela umidade.",
        "A carga do usuário é representada por forças concentradas; o encosto e o peso próprio não "
        "são modelados.",
        "As propriedades dos materiais são valores de referência para a condição declarada "
        "(seção 4.4.1) e não resultados de ensaio das peças reais.",
    ])
    return s


# --------------------------------------------------------------------------- #
#  7 Conclusão e referências
# --------------------------------------------------------------------------- #
def _conclusao_referencias(r):
    s = [_p("7. Conclusão", "h1")]
    s.append(_p(_texto_conclusao(r)))
    s.append(_p(
        "Do ponto de vista do comportamento estrutural, o modelo mostra que o peso do usuário é "
        "levado pelas travessas do assento, que trabalham em flexão, às pernas, que o transmitem ao "
        "piso em compressão simples; o meio do vão da travessa é a região mais solicitada da "
        "cadeira. " + _frase_deformacoes(r)))
    s.append(_p(
        "O software atendeu aos objetivos propostos: a partir do peso da pessoa, das dimensões da "
        "cadeira, da seção transversal e do material, modela a estrutura como um sistema de vigas e "
        "apoios, determina reações vinculares, esforços internos, tensões normais e deformações, e "
        "informa de forma objetiva se a cadeira é segura, tanto na versão web quanto na desktop. Os "
        "resultados correspondem a um modelo simplificado, sob carregamento estático, vertical e "
        "centrado, com as limitações listadas na seção 6.4, e servem como estimativa fundamentada "
        "para o pré-dimensionamento das peças; não substituem ensaios físicos da cadeira nem a "
        "verificação das ligações."))

    s.append(_p("Referências bibliográficas", "h1"))
    s += _itens([
        "HIBBELER, R. C. <i>Resistência dos Materiais</i>. 10. ed. São Paulo: Pearson, 2018.",
        "BEER, F. P.; JOHNSTON, E. R.; DEWOLF, J. T.; MAZUREK, D. F. <i>Mecânica dos Materiais</i>. "
        "8. ed. Porto Alegre: AMGH, 2021.",
        "ASSOCIAÇÃO BRASILEIRA DE NORMAS TÉCNICAS. <i>NBR 7190: Projeto de estruturas de madeira</i>. "
        "Rio de Janeiro: ABNT, 1997. (classe de resistência C40 das dicotiledôneas — eucalipto)",
        "ASM INTERNATIONAL. <i>ASM Handbook, Vol. 1: Properties and Selection — Irons, Steels, and "
        "High-Performance Alloys</i>. Materials Park: ASM International, 1990. (aço SAE 1020 "
        "laminado a quente)",
        "ASM INTERNATIONAL. <i>ASM Handbook, Vol. 2: Properties and Selection — Nonferrous Alloys "
        "and Special-Purpose Materials</i>. Materials Park: ASM International, 1990. (alumínio "
        "6061-T6)",
    ])
    return s


def _frase_deformacoes(r: Resultados) -> str:
    ent = r.entradas
    if r.delta_travessa <= 0:
        return ""
    return (f"A maior deformação relativa é a flecha da travessa, igual a ℓ/"
            f"{_f(ent.profundidade_mm / (r.delta_travessa * 1e3), 0)}; o encurtamento das pernas é "
            f"desprezível em comparação. O software não adota limite de deslocamento como critério "
            f"de aprovação, de modo que esses valores servem para avaliar a rigidez percebida no uso.")


def _texto_conclusao(r: Resultados) -> str:
    ent = r.entradas
    base = (f"Para um usuário de {_f(ent.massa_kg, 1)} kg (peso aplicado P = {_f(r.P, 1)} N, carga "
            f"estática, vertical e centrada), em uma cadeira de {r.material.nome} com "
            f"pernas de seção {r.secao.descricao()[0].lower() + r.secao.descricao()[1:]}, a tensão "
            f"normal máxima nas pernas é {_f(r.sigma_max_perna / 1e6, 3)} MPa (compressão) e na "
            f"travessa do assento é {_f(r.sigma_travessa / 1e6, 3)} MPa (flexão), frente a uma "
            f"tensão admissível de {_f(r.sigma_adm / 1e6)} MPa (σ<sub>lim</sub> = "
            f"{_f(r.material.tensao_limite_mpa, 1)} MPa e FS = {_f(ent.fator_seguranca)}). A flecha "
            f"máxima da travessa é {_f(r.delta_travessa * 1e3, 3)} mm e o encurtamento da perna, "
            f"{_f(r.delta_axial * 1e3, 4)} mm. ")
    if r.segura:
        return base + (
            f"Todas as verificações foram atendidas e, portanto, <b>a cadeira é APROVADA: suporta a "
            f"carga aplicada com segurança</b>. O elemento mais solicitado é: "
            f"{r.elemento_critico.lower()}, e a massa máxima admissível estimada para o usuário é "
            f"de {_f(r.massa_maxima, 1)} kg.")
    falhas = []
    if not r.ok_perna:
        falhas.append("a tensão nas pernas supera a admissível")
    if not r.ok_travessa:
        falhas.append("a tensão na travessa do assento supera a admissível")
    return base + (
        "<b>A cadeira é REPROVADA: não é segura</b> para essa condição, pois " + "; ".join(falhas) + ". "
        f"A massa máxima admissível com a geometria atual é de {_f(r.massa_maxima, 1)} kg. "
        "Recomenda-se aumentar a seção das peças, escolher um material mais resistente ou "
        "reduzir o vão da travessa.")
