"""Janela principal do software (PyQt5)."""
from __future__ import annotations

import os

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from PyQt5.QtCore import QLocale, Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
                             QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
                             QScrollArea, QSplitter, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from nucleo.calculos import Entradas, Resultados, _f, analisar
from nucleo.calculos import EXCENTRICIDADE_MM, G
from nucleo.diagramas import (figura_distribuicao_tensoes, figura_modelo, figura_perna,
                              figura_tensoes, figura_travessa)
from nucleo.materiais import MATERIAIS
from nucleo.relatorio import PROFESSORES
from nucleo.secoes import DIMENSAO, TIPOS_SECAO

VERDE = "#0a7d0a"
VERMELHO = "#c02f2f"

ESTILO = """
QMainWindow, QWidget { background: #f9f9f7; color: #0b0b0b; font-size: 10pt; }
QGroupBox { border: 1px solid #d9d8d3; border-radius: 8px; margin-top: 14px; padding: 8px 8px 6px 8px;
            background: #fcfcfb; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #184f95; }
QDoubleSpinBox, QComboBox, QLineEdit, QPlainTextEdit { background: white; border: 1px solid #c9c8c2;
            border-radius: 5px; padding: 3px 5px; font-weight: normal; }
QDoubleSpinBox:disabled, QComboBox:disabled { background: #eeede9; color: #9a9890; }
QLabel { font-weight: normal; background: transparent; }
QPushButton { background: #184f95; color: white; border: none; border-radius: 6px; padding: 8px 14px;
            font-weight: bold; }
QPushButton:hover { background: #256abf; }
QPushButton#secundario { background: #e4e3df; color: #0b0b0b; }
QPushButton#secundario:hover { background: #d6d5d0; }
QTabWidget::pane { border: 1px solid #d9d8d3; border-radius: 6px; background: #fcfcfb; }
QTabBar::tab { padding: 7px 14px; background: #eeede9; border-top-left-radius: 6px;
               border-top-right-radius: 6px; margin-right: 2px; }
QTabBar::tab:selected { background: #fcfcfb; color: #184f95; font-weight: bold; }
QFrame#cartao { background: #fcfcfb; border: 1px solid #d9d8d3; border-radius: 8px; }
"""


def _spin(valor, minimo, maximo, casas=1, passo=1.0, sufixo=""):
    s = QDoubleSpinBox()
    s.setRange(minimo, maximo)
    s.setDecimals(casas)
    s.setSingleStep(passo)
    s.setValue(valor)
    if sufixo:
        s.setSuffix(f" {sufixo}")
    s.setKeyboardTracking(False)
    s.setLocale(QLocale(QLocale.Portuguese, QLocale.Brazil))
    s.setMinimumWidth(120)
    return s


class Cartao(QFrame):
    """Pequeno cartão com um rótulo e um valor de destaque."""

    def __init__(self, titulo: str):
        super().__init__()
        self.setObjectName("cartao")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        self.titulo = QLabel(titulo)
        self.titulo.setStyleSheet("color:#52514e; font-size:9pt;")
        self.valor = QLabel("—")
        self.valor.setStyleSheet("font-size:15pt; font-weight:bold;")
        self.detalhe = QLabel("")
        self.detalhe.setStyleSheet("color:#52514e; font-size:8.5pt;")
        lay.addWidget(self.titulo)
        lay.addWidget(self.valor)
        lay.addWidget(self.detalhe)

    def definir(self, valor: str, detalhe: str = "", ok: bool | None = None):
        self.valor.setText(valor)
        cor = "#0b0b0b" if ok is None else (VERDE if ok else VERMELHO)
        self.valor.setStyleSheet(f"font-size:15pt; font-weight:bold; color:{cor};")
        self.detalhe.setText(detalhe)


class PainelFigura(QWidget):
    """Aba com figura(s) do matplotlib e um texto de leitura; substituída a cada recálculo."""

    def __init__(self, texto: str = ""):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.texto = texto
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.lay.addWidget(self.scroll)

    def mostrar(self, figuras, alturas, textos=None):
        """`figuras` e `alturas` são listas; `textos` opcional (um por figura)."""
        conteudo = QWidget()
        lay = QVBoxLayout(conteudo)
        textos = textos or [self.texto] + [""] * (len(figuras) - 1)
        for fig, alt, txt in zip(figuras, alturas, textos):
            if txt:
                rot = QLabel(txt)
                rot.setWordWrap(True)
                rot.setTextFormat(Qt.RichText)
                rot.setStyleSheet("color:#52514e; font-size:9.5pt; padding:4px 2px;")
                lay.addWidget(rot)
            canvas = FigureCanvasQTAgg(fig)
            canvas.setMinimumHeight(alt)
            lay.addWidget(canvas)
        self.scroll.setWidget(conteudo)


class JanelaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Análise Estrutural de Cadeira — Resistência dos Materiais (Projeto A3)")
        self.resize(1400, 860)
        self.setStyleSheet(ESTILO)
        self.resultado: Resultados | None = None

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.calcular)

        divisor = QSplitter(Qt.Horizontal)
        divisor.addWidget(self._painel_entradas())
        divisor.addWidget(self._painel_resultados())
        divisor.setStretchFactor(1, 1)
        divisor.setSizes([480, 920])
        self.setCentralWidget(divisor)

        self._atualizar_habilitados()
        self.calcular()

    # ------------------------------------------------------------------ entradas
    def _painel_entradas(self) -> QWidget:
        conteudo = QWidget()
        lay = QVBoxLayout(conteudo)

        titulo = QLabel("Dados de entrada")
        titulo.setStyleSheet("font-size:14pt; font-weight:bold; color:#184f95;")
        lay.addWidget(titulo)

        # Usuário
        g = QGroupBox("Usuário")
        f = QFormLayout(g)
        self.massa = _spin(100, 1, 1000, 1, 5, "kg")
        f.addRow("Peso da pessoa:", self.massa)
        lay.addWidget(g)

        # Geometria
        g = QGroupBox("Dimensões da cadeira")
        f = QFormLayout(g)
        self.altura = _spin(450, 100, 1500, 0, 10, "mm")
        self.largura = _spin(400, 150, 1500, 0, 10, "mm")
        self.profundidade = _spin(400, 150, 1500, 0, 10, "mm")
        f.addRow("Altura da cadeira (assento):", self.altura)
        f.addRow("Largura do assento:", self.largura)
        f.addRow("Profundidade do assento:", self.profundidade)
        lay.addWidget(g)

        # Material e pernas
        g = QGroupBox("Material e pernas")
        f = QFormLayout(g)
        self.material = QComboBox()
        self.material.addItems(list(MATERIAIS.keys()))
        self.material.setCurrentText(Entradas().material)
        self.info_material = QLabel("")
        self.info_material.setWordWrap(True)
        self.info_material.setStyleSheet("color:#52514e; font-size:8.5pt;")
        self.secao = QComboBox()
        self.secao.addItems(TIPOS_SECAO)
        self.espessura = _spin(40, 0.1, 300, 1, 1, "mm")
        self.rot_espessura = QLabel("Espessura das pernas (lado a):")
        self.interna = _spin(32, 0.1, 300, 1, 1, "mm")
        self.rot_interna = QLabel("Dimensão interna:")
        f.addRow("Material:", self.material)
        f.addRow(self.info_material)
        f.addRow("Seção das pernas:", self.secao)
        f.addRow(self.rot_espessura, self.espessura)
        f.addRow(self.rot_interna, self.interna)
        nota = QLabel("Seções: quadrada maciça (a), circular maciça (d), circular vazada (D, d) e "
                      "quadrada vazada (B, b). A dimensão interna deve ser menor que a externa.")
        nota.setWordWrap(True)
        nota.setStyleSheet("color:#52514e; font-size:8.5pt;")
        f.addRow(nota)
        lay.addWidget(g)

        # Travessa
        g = QGroupBox("Travessa lateral do assento")
        f = QFormLayout(g)
        self.trav_igual = QCheckBox("Mesma seção das pernas")
        self.trav_igual.setChecked(True)
        self.trav_secao = QComboBox()
        self.trav_secao.addItems(TIPOS_SECAO)
        self.trav_secao.setCurrentText(Entradas().tipo_secao_travessa)
        self.trav_dim = _spin(Entradas().dimensao_travessa_mm, 0.1, 300, 1, 1, "mm")
        self.rot_trav_dim = QLabel("Lado (a):")
        self.trav_int = _spin(32, 0.1, 300, 1, 1, "mm")
        self.rot_trav_int = QLabel("Dimensão interna:")
        f.addRow(self.trav_igual)
        f.addRow("Seção:", self.trav_secao)
        f.addRow(self.rot_trav_dim, self.trav_dim)
        f.addRow(self.rot_trav_int, self.trav_int)
        lay.addWidget(g)

        # Parâmetros
        g = QGroupBox("Parâmetros da análise")
        f = QFormLayout(g)
        self.fs = _spin(2.0, 1, 10, 2, 0.1)
        self.fs.setToolTip("Tensão admissível: σ_adm = σ_lim / FS.")
        f.addRow("Fator de segurança FS:", self.fs)
        premissas = QLabel(f"Premissas fixas: carga estática P = m·g (g = {_f(G, 0)} m/s²), sem força "
                           f"horizontal, excentricidade e = {_f(EXCENTRICIDADE_MM, 0)} mm.")
        premissas.setWordWrap(True)
        premissas.setStyleSheet("color:#52514e; font-size:8.5pt;")
        f.addRow(premissas)
        lay.addWidget(g)

        # Relatório
        g = QGroupBox("Dados do relatório")
        f = QVBoxLayout(g)
        f.addWidget(QLabel("Integrantes do grupo (um por linha):"))
        self.integrantes = QPlainTextEdit()
        self.integrantes.setPlaceholderText("Nome completo — RA")
        self.integrantes.setFixedHeight(90)
        f.addWidget(self.integrantes)
        f.addWidget(QLabel("Turma:"))
        self.turma = QLineEdit()
        f.addWidget(self.turma)
        prof = QLabel("Professores (incluídos na capa): " + "; ".join(PROFESSORES))
        prof.setWordWrap(True)
        prof.setStyleSheet("color:#52514e; font-size:8.5pt;")
        f.addWidget(prof)
        lay.addWidget(g)

        botoes = QHBoxLayout()
        b_pdf = QPushButton("Gerar relatório PDF")
        b_pdf.clicked.connect(self.gerar_pdf)
        b_reset = QPushButton("Restaurar padrões")
        b_reset.setObjectName("secundario")
        b_reset.clicked.connect(self.restaurar)
        botoes.addWidget(b_pdf)
        botoes.addWidget(b_reset)
        lay.addLayout(botoes)
        lay.addStretch(1)

        # recálculo automático
        for w in (self.massa, self.altura, self.largura, self.profundidade, self.espessura,
                  self.interna, self.trav_dim, self.trav_int, self.fs):
            w.valueChanged.connect(self._agendar)
        for w in (self.material, self.secao, self.trav_secao):
            w.currentIndexChanged.connect(self._agendar)
        self.trav_igual.toggled.connect(self._agendar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(conteudo)
        scroll.setMinimumWidth(470)
        return scroll

    # ------------------------------------------------------------------ resultados
    def _painel_resultados(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        self.banner = QLabel("—")
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setMinimumHeight(54)
        lay.addWidget(self.banner)

        grade = QGridLayout()
        self.c_perna = Cartao("Tensão máxima nas pernas")
        self.c_trav = Cartao("Tensão máxima na travessa")
        self.c_adm = Cartao("Tensão admissível (σ_lim / FS)")
        self.c_flecha = Cartao("Flecha máxima da travessa")
        self.c_massa = Cartao("Massa máxima admissível")
        for i, c in enumerate((self.c_perna, self.c_trav, self.c_adm, self.c_flecha, self.c_massa)):
            grade.addWidget(c, 0, i)
        lay.addLayout(grade)

        self.abas = QTabWidget()
        self.aba_modelo = PainelFigura(
            "Modelo de cálculo: peso P = m·g estático e centrado (e = 0) no assento, sem força horizontal; "
            "reações verticais do piso iguais em todas as pernas (P/4).")
        self.aba_perna = PainelFigura(
            "<b>Como ler:</b> eixo vertical = altura a partir do pé (0 = piso; H = ligação com o assento). "
            "N negativo = compressão constante; V e M são nulos (carga vertical centrada, sem força "
            "horizontal). A tensão é σ<sub>máx</sub> = N/A + M/W com M = 0.")
        self.aba_trav = PainelFigura(
            "<b>Como ler:</b> x vai da perna traseira (0) à dianteira (ℓ). O cortante troca de sinal sob a "
            "carga, onde o momento é máximo; o momento é desenhado do lado tracionado (fibra inferior) e é "
            "nulo nos apoios. A linha elástica mostra a flecha do assento.")
        self.aba_tensoes = PainelFigura()
        self.memorial = QTextBrowser()
        self.memorial.setOpenExternalLinks(False)
        self.abas.addTab(self.aba_modelo, "Modelo e reações")
        self.abas.addTab(self.aba_perna, "Diagramas — perna")
        self.abas.addTab(self.aba_trav, "Diagramas — travessa")
        self.abas.addTab(self.aba_tensoes, "Tensões")
        self.abas.addTab(self.memorial, "Memorial de cálculo")
        lay.addWidget(self.abas, 1)
        return w

    # ------------------------------------------------------------------ lógica
    def _agendar(self, *_):
        self._atualizar_habilitados()
        self._timer.start()

    def _atualizar_habilitados(self):
        m = MATERIAIS[self.material.currentText()]
        self.info_material.setText(f"σ_lim = {_f(m.tensao_limite_mpa, 1)} MPa ({m.criterio}); "
                                   f"E = {_f(m.modulo_elasticidade_gpa, 1)} GPa; condição: {m.condicao}.")
        (nome, simb), interna = DIMENSAO[self.secao.currentText()]
        self.rot_espessura.setText(f"Espessura das pernas ({nome.lower()} {simb}):")
        self._campo_interno(interna, self.rot_interna, self.interna, self.espessura)
        igual = self.trav_igual.isChecked()
        (nome_t, simb_t), interna_t = DIMENSAO[self.trav_secao.currentText()]
        self.rot_trav_dim.setText(f"{nome_t} ({simb_t}):")
        self._campo_interno(interna_t, self.rot_trav_int, self.trav_int, self.trav_dim)
        self.trav_secao.setEnabled(not igual)
        self.trav_dim.setEnabled(not igual)
        self.trav_int.setEnabled(not igual)

    @staticmethod
    def _campo_interno(interna, rotulo, campo, externo):  # noqa: ARG004
        """Mostra o campo de dimensão interna só nas seções vazadas."""
        rotulo.setVisible(bool(interna))
        campo.setVisible(bool(interna))
        if interna:
            rotulo.setText(f"{interna[0]} ({interna[1]}):")

    def ler_entradas(self) -> Entradas:
        return Entradas(
            massa_kg=self.massa.value(),
            altura_mm=self.altura.value(),
            largura_mm=self.largura.value(),
            profundidade_mm=self.profundidade.value(),
            material=self.material.currentText(),
            tipo_secao=self.secao.currentText(),
            espessura_perna_mm=self.espessura.value(),
            interna_perna_mm=self.interna.value() if DIMENSAO[self.secao.currentText()][1] else 0.0,
            travessa_igual_perna=self.trav_igual.isChecked(),
            tipo_secao_travessa=self.trav_secao.currentText(),
            dimensao_travessa_mm=self.trav_dim.value(),
            interna_travessa_mm=self.trav_int.value() if DIMENSAO[self.trav_secao.currentText()][1] else 0.0,
            fator_seguranca=self.fs.value(),
        )

    def calcular(self):
        try:
            r = analisar(self.ler_entradas())
        except ValueError as erro:
            self.resultado = None
            self.banner.setText("⚠  Dados inválidos:  " + str(erro).replace("\n", "  •  "))
            self.banner.setStyleSheet("background:#fab219; color:#0b0b0b; font-size:11pt; "
                                      "font-weight:bold; border-radius:8px; padding:8px;")
            return
        self.resultado = r
        self._mostrar(r)

    def _mostrar(self, r: Resultados):
        if r.segura:
            texto = "✔  CADEIRA SEGURA — a estrutura suporta a carga aplicada"
            cor = VERDE
        else:
            motivo = []
            if not r.ok_perna:
                motivo.append("tensão nas pernas")
            if not r.ok_travessa:
                motivo.append("tensão na travessa")
            texto = "✖  CADEIRA NÃO SEGURA — falha por: " + ", ".join(motivo)
            cor = VERMELHO
        self.banner.setText(texto)
        self.banner.setStyleSheet(f"background:{cor}; color:white; font-size:14pt; font-weight:bold; "
                                  "border-radius:8px; padding:8px;")

        self.c_perna.definir(f"{_f(r.sigma_max_perna / 1e6, 3)} MPa",
                             f"N/A, compressão (N = {_f(r.N_perna, 0)} N)", r.ok_perna)
        self.c_trav.definir(f"{_f(r.sigma_travessa / 1e6, 3)} MPa",
                            f"M_máx = {_f(r.M_travessa)} N·m", r.ok_travessa)
        self.c_adm.definir(f"{_f(r.sigma_adm / 1e6)} MPa",
                           f"σ_lim = {_f(r.material.tensao_limite_mpa, 1)} MPa")
        self.c_flecha.definir(f"{_f(r.delta_travessa * 1e3, 3)} mm", "δ = Q·ℓ³/(48·E·I)")
        self.c_massa.definir(f"{_f(r.massa_maxima, 1)} kg", f"crítico: {r.elemento_critico}",
                             r.massa_maxima >= r.entradas.massa_kg)

        self.aba_modelo.mostrar([figura_modelo(r)], [440])
        self.aba_perna.mostrar([figura_perna(r)], [440])
        self.aba_trav.mostrar([figura_travessa(r)], [720])
        self.aba_tensoes.mostrar(
            [figura_tensoes(r), figura_distribuicao_tensoes(r)], [280, 330],
            ["Tensões normais atuantes × tensão admissível σ<sub>adm</sub> = σ<sub>lim</sub>/FS. Barras "
             "verdes atendem; vermelhas ultrapassam.",
             "Distribuição da tensão normal nas seções críticas: na perna, compressão uniforme (N/A); na "
             "travessa, flexão linear (compressão em cima, tração embaixo). Negativo = compressão."])
        self.memorial.setHtml(self._html_memorial(r))

    @staticmethod
    def _html_memorial(r: Resultados) -> str:
        partes = ["<style>table{border-collapse:collapse;width:100%;margin-bottom:10px}"
                  "td,th{border:1px solid #d9d8d3;padding:4px 6px;font-size:9.5pt}"
                  "th{background:#eeede9;text-align:left}h3{color:#184f95;margin:12px 0 4px 0}"
                  "</style>"]
        for et in r.memorial:
            partes.append(f"<h3>{et.titulo}</h3><p style='color:#52514e'>{et.introducao}</p>"
                          "<table><tr><th>Descrição</th><th>Fórmula</th>"
                          "<th>Substituição</th><th>Resultado</th></tr>")
            for p in et.passos:
                cor = ""
                if p.resultado in ("ATENDE", "CADEIRA SEGURA") or p.resultado.startswith("OK"):
                    cor = f" style='color:{VERDE}'"
                elif p.resultado in ("NÃO ATENDE", "CADEIRA NÃO SEGURA"):
                    cor = f" style='color:{VERMELHO}'"
                notas = "".join(f"<br><span style='color:#6b6a66; font-size:8.5pt'>{t}</span>"
                                for t in (p.explicacao, p.interpretacao) if t)
                partes.append(f"<tr><td>{p.descricao}{notas}</td><td>{p.formula}</td>"
                              f"<td>{p.substituicao}</td><td{cor}><b>{p.resultado}</b></td></tr>")
            partes.append("</table>")
        return "".join(partes)

    def restaurar(self):
        padrao = Entradas()
        widgets = [self.massa, self.altura, self.largura, self.profundidade, self.espessura,
                   self.interna, self.trav_dim, self.trav_int, self.fs]
        for w in widgets:
            w.blockSignals(True)
        self.massa.setValue(padrao.massa_kg)
        self.altura.setValue(padrao.altura_mm)
        self.largura.setValue(padrao.largura_mm)
        self.profundidade.setValue(padrao.profundidade_mm)
        self.espessura.setValue(padrao.espessura_perna_mm)
        self.interna.setValue(0.8 * padrao.espessura_perna_mm)
        self.trav_dim.setValue(padrao.dimensao_travessa_mm)
        self.trav_int.setValue(0.8 * padrao.dimensao_travessa_mm)
        self.fs.setValue(padrao.fator_seguranca)
        for w in widgets:
            w.blockSignals(False)
        self.material.setCurrentText(padrao.material)
        self.secao.setCurrentText(padrao.tipo_secao)
        self.trav_secao.setCurrentText(padrao.tipo_secao_travessa)
        self.trav_igual.setChecked(True)
        self._agendar()

    def gerar_pdf(self):
        self.calcular()
        if self.resultado is None:
            QMessageBox.warning(self, "Relatório", "Corrija os dados de entrada antes de gerar o relatório.")
            return
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar relatório", os.path.join(os.path.expanduser("~"), "Relatorio_Cadeira.pdf"),
            "PDF (*.pdf)")
        if not caminho:
            return
        if not caminho.lower().endswith(".pdf"):
            caminho += ".pdf"
        from nucleo.relatorio import gerar_relatorio
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            gerar_relatorio(self.resultado, caminho,
                            self.integrantes.toPlainText().splitlines(), self.turma.text())
        except Exception as erro:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Relatório", f"Não foi possível gerar o PDF:\n{erro}")
            return
        QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "Relatório", f"Relatório salvo em:\n{caminho}")
