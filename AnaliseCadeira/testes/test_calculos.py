"""Testes: confere o software com cálculos feitos à mão.

Execute:  python -m pytest testes   (ou)   python testes/test_calculos.py
"""
import io
import itertools
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

from nucleo.calculos import EXCENTRICIDADE_MM, G, Entradas, analisar  # noqa: E402
from nucleo.materiais import MATERIAIS  # noqa: E402
from nucleo.secoes import TIPOS_SECAO, criar_secao  # noqa: E402

SECOES = {  # tipo -> (externa, interna) em mm
    "Quadrada maciça": (40, 0),
    "Circular maciça": (40, 0),
    "Circular vazada": (40, 32),
    "Quadrada vazada": (40, 32),
}


def perto(a, b, tol=1e-9):
    return math.isclose(a, b, rel_tol=tol, abs_tol=1e-15)


# --------------------------------------------------------------------------- geometria
def test_somente_quatro_secoes():
    assert TIPOS_SECAO == ["Quadrada maciça", "Circular maciça", "Circular vazada", "Quadrada vazada"]
    for removida in ("Retangular maciça", "Tubo quadrado", "Tubo retangular", "Tubo circular"):
        try:
            criar_secao(removida, 30)
        except ValueError:
            continue
        raise AssertionError(f"seção removida aceita: {removida}")


def test_propriedades_geometricas():
    a = 0.040
    s = criar_secao("Quadrada maciça", 40)
    assert perto(s.A, a ** 2) and perto(s.I, a ** 4 / 12) and perto(s.c, a / 2) and perto(s.W, a ** 3 / 6)
    d = 0.030
    s = criar_secao("Circular maciça", 30)
    assert perto(s.A, math.pi * d ** 2 / 4) and perto(s.I, math.pi * d ** 4 / 64)
    assert perto(s.W, math.pi * d ** 3 / 32)
    D, d = 0.0254, 0.022
    s = criar_secao("Circular vazada", 25.4, 22)
    assert perto(s.A, math.pi * (D ** 2 - d ** 2) / 4) and perto(s.I, math.pi * (D ** 4 - d ** 4) / 64)
    assert perto(s.c, D / 2) and perto(s.W, math.pi * (D ** 4 - d ** 4) / (32 * D))
    B, b = 0.030, 0.026
    s = criar_secao("Quadrada vazada", 30, 26)
    assert perto(s.A, B ** 2 - b ** 2) and perto(s.I, (B ** 4 - b ** 4) / 12)
    assert perto(s.c, B / 2) and perto(s.W, (B ** 4 - b ** 4) / (6 * B))
    # maciça ignora a dimensão interna
    assert perto(criar_secao("Quadrada maciça", 40, 10).A, 0.04 ** 2)


def test_validacao_dimensoes():
    invalidas = [("Circular vazada", 30, 30), ("Circular vazada", 30, 35), ("Quadrada vazada", 30, 30),
                 ("Quadrada vazada", 30, 0), ("Circular vazada", 30, -2), ("Quadrada maciça", 0, 0),
                 ("Circular maciça", -5, 0), ("Quadrada vazada", 0, 10)]
    for tipo, ext, inn in invalidas:
        try:
            criar_secao(tipo, ext, inn)
        except ValueError:
            pass
        else:
            raise AssertionError(f"dimensão inválida aceita: {tipo} {ext}/{inn}")
        try:
            analisar(Entradas(tipo_secao=tipo, espessura_perna_mm=ext, interna_perna_mm=inn))
        except ValueError:
            pass
        else:
            raise AssertionError(f"análise aceitou dimensão inválida: {tipo} {ext}/{inn}")
    try:
        analisar(Entradas(travessa_igual_perna=False, tipo_secao_travessa="Quadrada vazada",
                          dimensao_travessa_mm=20, interna_travessa_mm=25))
    except ValueError:
        pass
    else:
        raise AssertionError("travessa com interno ≥ externo aceita")


# --------------------------------------------------------------------------- materiais
def test_somente_tres_materiais():
    assert list(MATERIAIS) == ["Madeira - Eucalipto (C40)", "Aço SAE 1020", "Alumínio 6061-T6"]
    for removido in ("Madeira - Pinus (C25)", "Aço ASTM A36", "Alumínio 6063-T5", "Personalizado"):
        try:
            analisar(Entradas(material=removido))
        except ValueError:
            continue
        raise AssertionError(f"material removido aceito: {removido}")


def test_propriedades_materiais():
    m = MATERIAIS["Madeira - Eucalipto (C40)"]
    assert (m.tensao_limite_mpa, m.modulo_elasticidade_gpa) == (40.0, 19.5)
    m = MATERIAIS["Aço SAE 1020"]
    assert (m.tensao_limite_mpa, m.escoamento_mpa, m.ruptura_mpa, m.modulo_elasticidade_gpa) == (210, 210, 380, 200)
    m = MATERIAIS["Alumínio 6061-T6"]
    assert (m.tensao_limite_mpa, m.escoamento_mpa, m.ruptura_mpa, m.modulo_elasticidade_gpa) == (276, 276, 310, 68.9)
    for m in MATERIAIS.values():
        assert m.condicao and m.fonte


# --------------------------------------------------------------------------- premissas
def test_parametros_removidos():
    """Atrito, fator dinâmico e excentricidade não existem mais como entradas."""
    nomes = set(Entradas.__dataclass_fields__)
    for removido in ("fator_dinamico", "coef_horizontal", "excentricidade_mm",
                     "tensao_personalizada_mpa", "e_personalizado_gpa", "k_flambagem"):
        assert removido not in nomes, removido
        try:
            Entradas(**{removido: 1.0})
        except TypeError:
            pass
        else:
            raise AssertionError(f"parâmetro removido aceito: {removido}")
    assert EXCENTRICIDADE_MM == 0.0


def test_carga_estatica_e_centrada():
    r = analisar(Entradas(massa_kg=87))
    assert perto(r.P, 87 * G)                         # P = m·g, sem fator dinâmico
    assert r.excentricidade_mm == 0
    assert perto(r.a_carga, 0.2)                      # carga no meio do vão (ℓ/2)
    assert perto(r.R_D, r.P / 4) and perto(r.R_T, r.P / 4)   # sem força horizontal
    assert perto(r.R_D_total + r.R_T_total, r.P)
    assert r.V_perna == 0 and r.M_perna == 0          # perna em compressão simples
    assert r.M_travessa > 0                           # e = 0 não elimina o momento da travessa


# --------------------------------------------------------------------------- cálculos
def test_caso_padrao_manual():
    """100 kg, eucalipto C40, quadrada 40 mm, ℓ = 400 mm, H = 450 mm."""
    r = analisar(Entradas())
    P = 1000.0
    A, I, W = 0.04 ** 2, 0.04 ** 4 / 12, 0.04 ** 3 / 6
    E = 19.5e9
    assert perto(r.P, P)
    assert perto(r.sigma_max_perna, (P / 4) / A)
    Q = P / 2
    assert perto(r.M_travessa, Q * 0.4 / 4)
    assert perto(r.sigma_travessa, Q * 0.4 / 4 / W)
    assert perto(r.delta_travessa, Q * 0.4 ** 3 / (48 * E * I))
    assert perto(r.delta_axial, (P / 4) * 0.45 / (E * A))
    assert perto(r.sigma_adm, 20e6)
    assert r.segura
    assert perto(r.massa_maxima, 100 * (40e6 / r.sigma_travessa) / 2)


def test_matriz_secoes_materiais():
    """Todas as 4 seções × 3 materiais: tensões usam A e I da geometria escolhida."""
    for (tipo, (ext, inn)), nome in itertools.product(SECOES.items(), MATERIAIS):
        r = analisar(Entradas(material=nome, tipo_secao=tipo, espessura_perna_mm=ext,
                              interna_perna_mm=inn))
        s, m = r.secao, MATERIAIS[nome]
        assert perto(r.sigma_max_perna, r.N_perna / s.A)
        assert perto(r.sigma_travessa, r.M_travessa * s.c / s.I)
        assert perto(r.delta_travessa, r.Q_travessa * 0.4 ** 3 / (48 * m.E * s.I))
        assert perto(r.sigma_adm, m.tensao_limite / 2)
        assert r.segura == (r.sigma_max_perna <= r.sigma_adm and r.sigma_travessa <= r.sigma_adm)


def test_diagramas_coerentes():
    r = analisar(Entradas(tipo_secao="Circular vazada", espessura_perna_mm=30, interna_perna_mm=24))
    x, V, M, v = r.diagramas_travessa()
    assert math.isclose(M.max(), r.M_travessa, rel_tol=1e-3)
    assert math.isclose(v.max(), r.delta_travessa, rel_tol=1e-3)
    assert perto(V[0], r.R_A) and perto(V[-1], r.R_A - r.Q_travessa)
    y, N, Vp, Mp = r.diagramas_perna()
    assert (Vp == 0).all() and (Mp == 0).all() and perto(-N[0], r.N_perna)


def test_falha_e_massa_maxima():
    r = analisar(Entradas(material="Alumínio 6061-T6", tipo_secao="Quadrada vazada",
                          espessura_perna_mm=15, interna_perna_mm=13, massa_kg=150))
    assert not r.segura and r.massa_maxima < 150
    r = analisar(Entradas())
    r2 = analisar(Entradas(massa_kg=r.massa_maxima))
    assert math.isclose(r2.sigma_travessa, r2.sigma_adm, rel_tol=1e-9)


# --------------------------------------------------------------------------- relatório e API
def test_relatorio_pdf():
    from nucleo.relatorio import gerar_relatorio
    for tipo, (ext, inn) in SECOES.items():
        buf = io.BytesIO()
        gerar_relatorio(analisar(Entradas(tipo_secao=tipo, espessura_perna_mm=ext, interna_perna_mm=inn,
                                          material="Aço SAE 1020")), buf, ["Integrante — RA"], "Turma")
        dados = buf.getvalue()
        assert dados.startswith(b"%PDF") and len(dados) > 50_000


def test_api_web_igual_ao_nucleo():
    """A API Flask devolve os mesmos resultados do núcleo (mesma base da versão desktop)."""
    try:
        import app as web
    except ImportError:  # Flask não instalado: teste ignorado
        return
    cli = web.app.test_client()
    for (tipo, (ext, inn)), nome in itertools.product(SECOES.items(), MATERIAIS):
        dados = {"massa_kg": 85, "material": nome, "tipo_secao": tipo, "espessura_perna_mm": ext,
                 "interna_perna_mm": inn,
                 # parâmetros removidos enviados de propósito: precisam ser ignorados
                 "fator_dinamico": 3, "coef_horizontal": 0.5, "excentricidade_mm": 150}
        resp = cli.post("/api/analisar", json=dados).get_json()
        r = analisar(Entradas(massa_kg=85, material=nome, tipo_secao=tipo, espessura_perna_mm=ext,
                              interna_perna_mm=inn))
        assert perto(resp["perna"]["sigma_max_mpa"], r.sigma_max_perna / 1e6)
        assert perto(resp["travessa"]["sigma_mpa"], r.sigma_travessa / 1e6)
        assert perto(resp["cargas"]["P"], 85 * G) and resp["premissas"]["excentricidade_mm"] == 0
        assert resp["segura"] == r.segura
    op = cli.get("/api/opcoes").get_json()
    assert op["secoes"] == TIPOS_SECAO and [m["nome"] for m in op["materiais"]] == list(MATERIAIS)
    assert cli.post("/api/analisar", json={"material": "Personalizado"}).status_code == 400


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("OK ", nome)
