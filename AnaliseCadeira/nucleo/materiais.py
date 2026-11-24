"""Banco de materiais da cadeira — três opções: eucalipto, aço SAE 1020 e alumínio 6061-T6.

`tensao_limite` é a tensão de referência usada na verificação (σ_lim):
  - metais   -> limite de escoamento σ_e (a partir dele surgem deformações permanentes)
  - madeira  -> resistência característica à compressão paralela às fibras f_c0,k

PREMISSAS E FONTES (valores de referência, não resultados de ensaio das peças reais)

* Madeira de eucalipto — as propriedades dependem da espécie, do lote, da classificação
  e da umidade.  Adota-se a premissa de que a madeira foi CLASSIFICADA na classe de
  resistência C40 das dicotiledôneas da ABNT NBR 7190:1997 (umidade de referência 12 %):
  f_c0,k = 40 MPa, E_c0,m = 19 500 MPa, densidade aparente 950 kg/m³.  Os valores são
  os da classe, não os de uma espécie específica de eucalipto; estudos indicam que o
  módulo médio real de lotes C40 pode ser menor que o valor normativo.

* Aço SAE 1020 — condição LAMINADO A QUENTE: limite de escoamento 210 MPa e limite de
  resistência 380 MPa (valores mínimos estimados para barras laminadas a quente, dados
  SAE/ASM), E = 200 GPa, densidade 7 850 kg/m³.  Na condição trefilado a frio o
  escoamento é bem maior (≈ 350 MPa); por isso a condição precisa ser declarada.

* Alumínio 6061-T6 — têmpera T6 (solubilizado e envelhecido artificialmente): limite de
  escoamento 276 MPa, limite de resistência 310 MPa, E = 68,9 GPa, densidade 2 700 kg/m³
  (ASM Material Data Sheet / Aluminum Association, valores típicos).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    nome: str
    categoria: str              # "Madeira", "Aço" ou "Alumínio"
    tensao_limite_mpa: float    # σ_lim usada na verificação
    modulo_elasticidade_gpa: float
    densidade_kg_m3: float
    criterio: str               # o que é a tensão limite
    escoamento_mpa: float | None    # limite de escoamento (metais)
    ruptura_mpa: float | None       # limite de resistência à tração (metais)
    condicao: str               # premissa de condição/classificação do material
    fonte: str                  # origem dos valores

    @property
    def tensao_limite(self) -> float:          # Pa
        return self.tensao_limite_mpa * 1e6

    @property
    def E(self) -> float:                      # Pa
        return self.modulo_elasticidade_gpa * 1e9


MATERIAIS = {
    "Madeira - Eucalipto (C40)": Material(
        "Madeira - Eucalipto (C40)", "Madeira", 40.0, 19.5, 950,
        "resistência característica à compressão paralela às fibras f_c0,k",
        None, None,
        "eucalipto classificado na classe C40 das dicotiledôneas, umidade de referência 12 %",
        "ABNT NBR 7190:1997, classes de resistência das dicotiledôneas (C40)"),
    "Aço SAE 1020": Material(
        "Aço SAE 1020", "Aço", 210.0, 200.0, 7850,
        "limite de escoamento σ_e",
        210.0, 380.0,
        "laminado a quente",
        "SAE/ASM — propriedades mínimas estimadas de barras de aço 1020 laminadas a quente"),
    "Alumínio 6061-T6": Material(
        "Alumínio 6061-T6", "Alumínio", 276.0, 68.9, 2700,
        "limite de escoamento σ_e",
        276.0, 310.0,
        "têmpera T6 (solubilizado e envelhecido artificialmente)",
        "ASM Material Data Sheet (Aluminum Association) — valores típicos 6061-T6"),
}
