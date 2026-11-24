"""Versão web da Análise Estrutural de Cadeira (Projeto A3).

O motor de cálculo (pasta `nucleo/`) é exatamente o mesmo da versão desktop:
este arquivo só expõe esse motor por HTTP e serve a interface em `static/`.

Executar localmente:
    pip install -r requirements.txt
    python app.py              -> http://localhost:5000

Em produção (Render, Railway, etc.):
    gunicorn app:app
"""
from __future__ import annotations

import io
import math
import os
import re
from dataclasses import fields

import matplotlib

matplotlib.use("Agg")  # sem janela: gera imagens em memória

from flask import Flask, jsonify, request, send_file, send_from_directory  # noqa: E402

from nucleo.calculos import G, Entradas, Resultados, analisar  # noqa: E402
from nucleo.materiais import MATERIAIS  # noqa: E402
from nucleo.secoes import DIMENSAO, TIPOS_SECAO  # noqa: E402

PASTA = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(PASTA, "static"), static_url_path="/static")

_CAMPOS = {f.name: f for f in fields(Entradas)}


# --------------------------------------------------------------------------- #
#  Conversões
# --------------------------------------------------------------------------- #
def _num(valor):
    """float JSON-seguro (inf/NaN viram None)."""
    if valor is None:
        return None
    valor = float(valor)
    return None if (math.isinf(valor) or math.isnan(valor)) else valor


def _lista(arr, casas=6):
    return [round(float(v), casas) for v in arr]


def ler_entradas(dados: dict) -> Entradas:
    """Monta `Entradas` a partir do JSON, ignorando chaves desconhecidas."""
    padrao = Entradas()
    valores = {}
    for nome, campo in _CAMPOS.items():
        if nome not in dados or dados[nome] in (None, ""):
            continue
        bruto = dados[nome]
        atual = getattr(padrao, nome)
        try:
            if isinstance(atual, bool):
                valores[nome] = bruto if isinstance(bruto, bool) else str(bruto).lower() in ("1", "true", "sim")
            elif isinstance(atual, float):
                valores[nome] = float(str(bruto).replace(",", "."))
            else:
                valores[nome] = str(bruto)
        except ValueError as erro:
            raise ValueError(f"Valor inválido para '{nome}': {bruto}") from erro
    return Entradas(**valores)


def _secao_json(s):
    return {
        "tipo": s.tipo, "descricao": s.descricao(),
        "externa_mm": s.externa_mm, "interna_mm": s.interna_mm, "vazada": s.vazada,
        "simbolo": s.simbolo, "simbolo_interno": s.simbolo_interno, "dimensoes": s.dimensoes(),
        "A_mm2": s.A * 1e6, "I_mm4": s.I * 1e12, "c_mm": s.c * 1000, "W_mm3": s.W * 1e9,
    }


def resultado_json(r: Resultados) -> dict:
    motivos = []
    if not r.ok_perna:
        motivos.append("tensão nas pernas")
    if not r.ok_travessa:
        motivos.append("tensão na travessa")

    y, N, V, M = r.diagramas_perna(n=41)
    x, Vt, Mt, vt = r.diagramas_travessa(n=201)
    mat = r.material
    return {
        "segura": r.segura,
        "motivos": motivos,
        "elemento_critico": r.elemento_critico,
        "material": {"nome": mat.nome, "categoria": mat.categoria,
                     "tensao_limite_mpa": mat.tensao_limite_mpa,
                     "E_gpa": mat.modulo_elasticidade_gpa, "criterio": mat.criterio,
                     "condicao": mat.condicao, "fonte": mat.fonte},
        "secao": _secao_json(r.secao),
        "secao_travessa": _secao_json(r.secao_travessa),
        "premissas": {"excentricidade_mm": r.excentricidade_mm, "g": G},
        "cargas": {"P": r.P},
        "reacoes": {"R_D_total": r.R_D_total, "R_T_total": r.R_T_total,
                    "R_D": r.R_D, "R_T": r.R_T},
        "perna": {
            "N": r.N_perna, "V": r.V_perna, "M": r.M_perna,
            "sigma_axial_mpa": r.sigma_axial / 1e6,
            "sigma_flexao_mpa": r.sigma_flexao_perna / 1e6,
            "sigma_max_mpa": r.sigma_max_perna / 1e6,
            "delta_axial_mm": r.delta_axial * 1000,
            "deformacao": r.deformacao_perna,
        },
        "travessa": {
            "Q": r.Q_travessa, "a_mm": r.a_carga * 1000, "R_A": r.R_A, "R_B": r.R_B,
            "M": r.M_travessa, "sigma_mpa": r.sigma_travessa / 1e6,
            "delta_mm": r.delta_travessa * 1000, "deformacao": r.deformacao_travessa,
        },
        "verificacao": {
            "sigma_adm_mpa": r.sigma_adm / 1e6,
            "fs_perna": _num(r.fs_perna), "fs_travessa": _num(r.fs_travessa),
            "ok_perna": r.ok_perna, "ok_travessa": r.ok_travessa,
            "massa_maxima": _num(r.massa_maxima),
        },
        "diagramas": {
            "perna": {"y_mm": _lista(y * 1000, 3), "N": _lista(N, 4), "V": _lista(V, 4),
                      "M": _lista(M, 5)},
            "travessa": {"x_mm": _lista(x * 1000, 3), "V": _lista(Vt, 4), "M": _lista(Mt, 5),
                         "v_mm": _lista(vt * 1000, 6)},
        },
        "memorial": [
            {"titulo": et.titulo, "introducao": et.introducao,
             "passos": [{"descricao": p.descricao, "formula": p.formula,
                         "substituicao": p.substituicao, "resultado": p.resultado,
                         "explicacao": p.explicacao, "interpretacao": p.interpretacao}
                        for p in et.passos]}
            for et in r.memorial
        ],
    }


# --------------------------------------------------------------------------- #
#  Rotas
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/opcoes")
def opcoes():
    padrao = Entradas()
    return jsonify({
        "materiais": [{"nome": m.nome, "categoria": m.categoria,
                       "tensao_limite_mpa": m.tensao_limite_mpa,
                       "E_gpa": m.modulo_elasticidade_gpa,
                       "densidade": m.densidade_kg_m3, "criterio": m.criterio,
                       "condicao": m.condicao, "fonte": m.fonte}
                      for m in MATERIAIS.values()],
        "secoes": TIPOS_SECAO,
        "dimensao": {t: {"externa": list(DIMENSAO[t][0]),
                         "interna": list(DIMENSAO[t][1]) if DIMENSAO[t][1] else None}
                     for t in TIPOS_SECAO},
        "padrao": {f: getattr(padrao, f) for f in _CAMPOS},
    })


@app.post("/api/analisar")
def api_analisar():
    try:
        r = analisar(ler_entradas(request.get_json(force=True) or {}))
    except ValueError as erro:
        return jsonify({"erros": str(erro).split("\n")}), 400
    return jsonify(resultado_json(r))


@app.post("/api/relatorio")
def api_relatorio():
    dados = request.get_json(force=True) or {}
    try:
        r = analisar(ler_entradas(dados.get("entradas", {})))
    except ValueError as erro:
        return jsonify({"erros": str(erro).split("\n")}), 400

    from nucleo.relatorio import gerar_relatorio

    integrantes = [str(n)[:120] for n in dados.get("integrantes", [])][:12]
    turma = str(dados.get("turma", ""))[:80]
    # ReportLab interpreta marcação; escapa o texto livre do usuário
    esc = lambda t: re.sub(r"[<>&]", lambda m: {"<": "&lt;", ">": "&gt;", "&": "&amp;"}[m.group()], t)  # noqa: E731
    buf = io.BytesIO()
    gerar_relatorio(r, buf, [esc(n) for n in integrantes], esc(turma))
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                     download_name="Relatorio_Cadeira.pdf")


@app.get("/saude")
def saude():
    return {"status": "ok"}


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    print(f"\n  Análise Estrutural de Cadeira  ->  http://localhost:{porta}\n")
    app.run(host="0.0.0.0", port=porta, debug=False)
