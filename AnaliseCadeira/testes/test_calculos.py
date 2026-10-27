"""Testes: confere o software com cálculos feitos à mão.

Execute:  python -m pytest testes   (ou)   python testes/test_calculos.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nucleo.calculos import Entradas, analisar  # noqa: E402
from nucleo.secoes import criar_secao  # noqa: E402


def perto(a, b, tol=1e-6):
    return math.isclose(a, b, rel_tol=tol, abs_tol=1e-12)


def test_secoes():
    s = criar_secao("Quadrada maciça", 40)
    assert perto(s.A, 0.04 ** 2) and perto(s.I, 0.04 ** 4 / 12) and perto(s.W, 0.04 ** 3 / 6)
    s = criar_secao("Tubo circular", 25.4, 1.2)
    D, d = 0.0254, 0.0254 - 0.0024
    assert perto(s.A, math.pi * (D ** 2 - d ** 2) / 4)
    assert perto(s.I, math.pi * (D ** 4 - d ** 4) / 64)
    s = criar_secao("Retangular maciça", 25, 0, 60)
    assert perto(s.I, 0.025 * 0.06 ** 3 / 12) and perto(s.I_min, 0.06 * 0.025 ** 3 / 12)


def test_caso_padrao_madeira():
    """100 kg, φ = 1,5, μ = 0,10, H = P = 0,40/0,45 m, eucalipto 40×40 mm."""
    r = analisar(Entradas())
    W = 100 * 9.81 * 1.5                      # 1471,5 N
    assert perto(r.W, W)
    F_H = 0.10 * W
    R_D_tot = (W * 0.2 + F_H * 0.45) / 0.4
    assert perto(r.R_D_total, R_D_tot)
    assert perto(r.R_D_total + r.R_T_total, W)          # ΣFy = 0
    A, Wr = 0.04 ** 2, 0.04 ** 3 / 6
    M = F_H / 4 * 0.45
    assert perto(r.M_perna, M)
    assert perto(r.sigma_max_perna, R_D_tot / 2 / A + M / Wr)
    # travessa: carga central -> M = Q·L/4, flecha = Q·L³/(48EI)
    Q = W / 2
    assert perto(r.M_travessa, Q * 0.4 / 4)
    assert perto(r.sigma_travessa, Q * 0.4 / 4 / Wr)
    EI = 19.5e9 * 0.04 ** 4 / 12
    assert perto(r.delta_travessa, Q * 0.4 ** 3 / (48 * EI))
    assert perto(r.P_cr, math.pi ** 2 * EI / (2 * 0.45) ** 2)
    assert r.segura


def test_diagramas_coerentes():
    r = analisar(Entradas(excentricidade_mm=80))
    x, V, M, v = r.diagramas_travessa()
    assert perto(M.max(), r.M_travessa, 1e-3)
    assert perto(v.max(), r.delta_travessa, 1e-3)
    assert perto(V[0], r.R_A) and perto(V[-1], r.R_A - r.Q_travessa)
    y, N, Vp, Mp = r.diagramas_perna()
    assert perto(Mp[-1], r.M_perna)


def test_tombamento():
    # carga na borda dianteira + grande força horizontal -> pernas traseiras descarregam
    r = analisar(Entradas(excentricidade_mm=200, coef_horizontal=0.3))
    assert r.tomba and not r.segura


def test_falha_por_tensao():
    r = analisar(Entradas(material="Alumínio 6063-T5", tipo_secao="Tubo quadrado",
                          espessura_perna_mm=15, parede_mm=0.8, massa_kg=150))
    assert not r.segura
    assert r.massa_maxima < 150


def test_massa_maxima_e_limite():
    """Com a massa máxima calculada, o elemento crítico fica exatamente em σ_adm."""
    r = analisar(Entradas())
    r2 = analisar(Entradas(massa_kg=r.massa_maxima))
    assert perto(r2.sigma_travessa, r2.sigma_adm, 1e-6)


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("OK ", nome)
