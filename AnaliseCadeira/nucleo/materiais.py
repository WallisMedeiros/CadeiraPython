"""Banco de materiais usados na cadeira.

Valores típicos de literatura (valores de referência para fins didáticos):
- Madeiras: NBR 7190 (classes de resistência) -> f_c0,k e E_c0,m
- Aços: NBR 6650 / ASTM A36 / SAE 1020 laminado a quente
- Alumínio: ASM / Aluminum Association (ligas 6061-T6 e 6063-T5)

`tensao_limite` é a tensão de referência do material:
  - metais  -> tensão de escoamento (sigma_e)
  - madeira -> resistência característica à compressão paralela às fibras (f_c0,k)
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    nome: str
    categoria: str          # "Madeira", "Aço" ou "Alumínio"
    tensao_limite_mpa: float
    modulo_elasticidade_gpa: float
    densidade_kg_m3: float
    criterio: str           # descrição do que é a tensão limite

    @property
    def tensao_limite(self) -> float:          # Pa
        return self.tensao_limite_mpa * 1e6

    @property
    def E(self) -> float:                      # Pa
        return self.modulo_elasticidade_gpa * 1e9


MATERIAIS = {
    "Madeira - Pinus (C25)": Material(
        "Madeira - Pinus (C25)", "Madeira", 25.0, 8.5, 550,
        "resistência característica à compressão paralela f_c0,k (NBR 7190, conífera C25)"),
    "Madeira - Eucalipto (C40)": Material(
        "Madeira - Eucalipto (C40)", "Madeira", 40.0, 19.5, 950,
        "resistência característica à compressão paralela f_c0,k (NBR 7190, dicotiledônea C40)"),
    "Aço SAE 1020": Material(
        "Aço SAE 1020", "Aço", 210.0, 200.0, 7850,
        "tensão de escoamento σe (laminado a quente)"),
    "Aço ASTM A36": Material(
        "Aço ASTM A36", "Aço", 250.0, 200.0, 7850,
        "tensão de escoamento σe"),
    "Alumínio 6061-T6": Material(
        "Alumínio 6061-T6", "Alumínio", 276.0, 69.0, 2700,
        "tensão de escoamento σe"),
    "Alumínio 6063-T5": Material(
        "Alumínio 6063-T5", "Alumínio", 145.0, 69.0, 2700,
        "tensão de escoamento σe"),
}


def material_personalizado(tensao_mpa: float, e_gpa: float, densidade: float = 0.0) -> Material:
    return Material("Personalizado", "Personalizado", tensao_mpa, e_gpa, densidade,
                    "tensão limite informada pelo usuário")
