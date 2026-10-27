"""Análise Estrutural de Cadeira — Projeto A3 de Resistência dos Materiais.

Execute:  python main.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib  # noqa: E402

matplotlib.use("Qt5Agg")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from interface.janela import JanelaPrincipal  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Análise Estrutural de Cadeira")
    janela = JanelaPrincipal()
    janela.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
