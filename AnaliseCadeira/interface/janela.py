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
from nucleo.diagramas import figura_modelo, figura_perna, figura_tensoes, figura_travessa
from nucleo.materiais import MATERIAIS
from nucleo.secoes import COM_ALTURA, TIPOS_SECAO, TUBOS

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
    """Aba com uma figura do matplotlib que é substituída a cada recálculo."""

    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.canvas = None
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.lay.addWidget(self.scroll)

    def mostrar(self, fig, altura_min=380):
        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(altura_min)
        self.scroll.setWidget(canvas)
        self.canvas = canvas


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
        self.material.addItems(list(MATERIAIS.keys()) + ["Personalizado"])
        self.material.setCurrentText("Madeira - Eucalipto (C40)")
        self.secao = QComboBox()
        self.secao.addItems(TIPOS_SECAO)
        self.espessura = _spin(40, 1, 300, 1, 1, "mm")
        self.altura_secao = _spin(40, 1, 300, 1, 1, "mm")
        self.parede = _spin(1.5, 0.1, 50, 2, 0.1, "mm")
        self.tensao_pers = _spin(100, 1, 3000, 1, 5, "MPa")
        self.e_pers = _spin(10, 0.1, 400, 1, 1, "GPa")
        f.addRow("Material:", self.material)
        f.addRow("Tensão limite (personalizado):", self.tensao_pers)
        f.addRow("Módulo E (personalizado):", self.e_pers)
        f.addRow("Seção das pernas:", self.secao)
        f.addRow("Espessura / diâmetro (b):", self.espessura)
        f.addRow("Altura da seção (h):", self.altura_secao)
        f.addRow("Parede do tubo (t):", self.parede)
        lay.addWidget(g)

        # Travessa
        g = QGroupBox("Travessa lateral do assento")
        f = QFormLayout(g)
        self.trav_igual = QCheckBox("Mesma seção das pernas")
        self.trav_igual.setChecked(True)
        self.trav_secao = QComboBox()
        self.trav_secao.addItems(TIPOS_SECAO)
        self.trav_secao.setCurrentText("Retangular maciça")
        self.trav_b = _spin(25, 1, 300, 1, 1, "mm")
        self.trav_h = _spin(60, 1, 300, 1, 1, "mm")
        self.trav_t = _spin(1.5, 0.1, 50, 2, 0.1, "mm")
        f.addRow(self.trav_igual)
        f.addRow("Seção:", self.trav_secao)
        f.addRow("Largura / diâmetro (b):", self.trav_b)
        f.addRow("Altura (h):", self.trav_h)
        f.addRow("Parede (t):", self.trav_t)
        lay.addWidget(g)

        # Parâmetros
        g = QGroupBox("Parâmetros da análise")
        f = QFormLayout(g)
        self.fi = _spin(1.5, 1, 5, 2, 0.1)
        self.mu = _spin(0.10, 0, 1, 2, 0.01)
        self.exc = _spin(0, -750, 750, 0, 10, "mm")
        self.fs = _spin(2.0, 1, 10, 2, 0.1)
        self.k = _spin(2.0, 0.5, 2.5, 2, 0.1)
        self.fi.setToolTip("Fator dinâmico φ: amplifica o peso para o impacto ao sentar (1,0 = estático).")
        self.mu.setToolTip("F_H = μ·W: força horizontal no assento (inclinar-se, arrastar).")
        self.exc.setToolTip("Deslocamento do centro da carga em relação ao centro do assento (+ frente).")
        self.k.setToolTip("Coeficiente de comprimento efetivo: 2,0 engastado-livre; 1,0 bi-rotulado; 0,7; 0,5.")
        f.addRow("Fator dinâmico φ:", self.fi)
        f.addRow("Coef. força horizontal μ:", self.mu)
        f.addRow("Excentricidade e (+ frente):", self.exc)
        f.addRow("Fator de segurança FS:", self.fs)
        f.addRow("Coef. flambagem K:", self.k)
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
                  self.altura_secao, self.parede, self.tensao_pers, self.e_pers, self.trav_b,
                  self.trav_h, self.trav_t, self.fi, self.mu, self.exc, self.fs, self.k):
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
        self.c_flamb = Cartao("Segurança à flambagem (P_cr / N)")
        self.c_massa = Cartao("Massa máxima admissível")
        for i, c in enumerate((self.c_perna, self.c_trav, self.c_adm, self.c_flamb, self.c_massa)):
            grade.addWidget(c, 0, i)
        lay.addLayout(grade)

        self.abas = QTabWidget()
        self.aba_modelo = PainelFigura()
        self.aba_perna = PainelFigura()
        self.aba_trav = PainelFigura()
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
        pers = self.material.currentText() == "Personalizado"
        self.tensao_pers.setEnabled(pers)
        self.e_pers.setEnabled(pers)
        tipo = self.secao.currentText()
        self.altura_secao.setEnabled(tipo in COM_ALTURA)
        self.parede.setEnabled(tipo in TUBOS)
        igual = self.trav_igual.isChecked()
        tt = self.trav_secao.currentText()
        self.trav_secao.setEnabled(not igual)
        self.trav_b.setEnabled(not igual)
        self.trav_h.setEnabled(not igual and tt in COM_ALTURA)
        self.trav_t.setEnabled(not igual and tt in TUBOS)

    def ler_entradas(self) -> Entradas:
        return Entradas(
            massa_kg=self.massa.value(),
            altura_mm=self.altura.value(),
            largura_mm=self.largura.value(),
            profundidade_mm=self.profundidade.value(),
            material=self.material.currentText(),
            tipo_secao=self.secao.currentText(),
            espessura_perna_mm=self.espessura.value(),
            parede_mm=self.parede.value(),
            altura_secao_perna_mm=self.altura_secao.value(),
            travessa_igual_perna=self.trav_igual.isChecked(),
            tipo_secao_travessa=self.trav_secao.currentText(),
            b_travessa_mm=self.trav_b.value(),
            h_travessa_mm=self.trav_h.value(),
            parede_travessa_mm=self.trav_t.value(),
            fator_dinamico=self.fi.value(),
            coef_horizontal=self.mu.value(),
            excentricidade_mm=self.exc.value(),
            fator_seguranca=self.fs.value(),
            k_flambagem=self.k.value(),
            tensao_personalizada_mpa=self.tensao_pers.value(),
            e_personalizado_gpa=self.e_pers.value(),
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
            if not r.ok_flambagem:
                motivo.append("flambagem")
            if r.tomba:
                motivo.append("tombamento")
            texto = "✖  CADEIRA NÃO SEGURA — falha por: " + ", ".join(motivo)
            cor = VERMELHO
        self.banner.setText(texto)
        self.banner.setStyleSheet(f"background:{cor}; color:white; font-size:14pt; font-weight:bold; "
                                  "border-radius:8px; padding:8px;")

        self.c_perna.definir(f"{_f(r.sigma_max_perna / 1e6)} MPa",
                             f"axial {_f(r.sigma_axial / 1e6)} + flexão {_f(r.sigma_flexao_perna / 1e6)}",
                             r.ok_perna)
        self.c_trav.definir(f"{_f(r.sigma_travessa / 1e6)} MPa",
                            f"M_máx = {_f(r.M_travessa)} N·m", r.ok_travessa)
        self.c_adm.definir(f"{_f(r.sigma_adm / 1e6)} MPa",
                           f"σ_lim = {_f(r.material.tensao_limite_mpa, 1)} MPa")
        self.c_flamb.definir(_f(r.fs_flambagem), f"P_cr = {_f(r.P_cr, 0)} N", r.ok_flambagem)
        self.c_massa.definir(f"{_f(r.massa_maxima, 1)} kg", f"crítico: {r.elemento_critico}",
                             r.massa_maxima >= r.entradas.massa_kg and not r.tomba)

        self.aba_modelo.mostrar(figura_modelo(r), 440)
        self.aba_perna.mostrar(figura_perna(r), 420)
        self.aba_trav.mostrar(figura_travessa(r), 720)
        self.aba_tensoes.mostrar(figura_tensoes(r), 340)
        self.memorial.setHtml(self._html_memorial(r))

    @staticmethod
    def _html_memorial(r: Resultados) -> str:
        partes = ["<style>table{border-collapse:collapse;width:100%;margin-bottom:10px}"
                  "td,th{border:1px solid #d9d8d3;padding:4px 6px;font-size:9.5pt}"
                  "th{background:#eeede9;text-align:left}h3{color:#184f95;margin:12px 0 4px 0}"
                  "</style>"]
        for titulo, passos in r.memorial:
            partes.append(f"<h3>{titulo}</h3><table><tr><th>Descrição</th><th>Fórmula</th>"
                          "<th>Substituição</th><th>Resultado</th></tr>")
            for p in passos:
                cor = ""
                if p.resultado in ("ATENDE", "CADEIRA SEGURA") or p.resultado.startswith("OK"):
                    cor = f" style='color:{VERDE}'"
                elif p.resultado in ("NÃO ATENDE", "CADEIRA NÃO SEGURA", "TOMBA"):
                    cor = f" style='color:{VERMELHO}'"
                partes.append(f"<tr><td>{p.descricao}</td><td>{p.formula}</td>"
                              f"<td>{p.substituicao}</td><td{cor}><b>{p.resultado}</b></td></tr>")
            partes.append("</table>")
        return "".join(partes)

    def restaurar(self):
        padrao = Entradas()
        widgets = [self.massa, self.altura, self.largura, self.profundidade, self.espessura,
                   self.altura_secao, self.parede, self.trav_b, self.trav_h, self.trav_t,
                   self.fi, self.mu, self.exc, self.fs, self.k]
        for w in widgets:
            w.blockSignals(True)
        self.massa.setValue(padrao.massa_kg)
        self.altura.setValue(padrao.altura_mm)
        self.largura.setValue(padrao.largura_mm)
        self.profundidade.setValue(padrao.profundidade_mm)
        self.espessura.setValue(padrao.espessura_perna_mm)
        self.altura_secao.setValue(40)
        self.parede.setValue(1.5)
        self.trav_b.setValue(padrao.b_travessa_mm)
        self.trav_h.setValue(padrao.h_travessa_mm)
        self.trav_t.setValue(1.5)
        self.fi.setValue(padrao.fator_dinamico)
        self.mu.setValue(padrao.coef_horizontal)
        self.exc.setValue(padrao.excentricidade_mm)
        self.fs.setValue(padrao.fator_seguranca)
        self.k.setValue(padrao.k_flambagem)
        for w in widgets:
            w.blockSignals(False)
        self.material.setCurrentText(padrao.material)
        self.secao.setCurrentText(padrao.tipo_secao)
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
