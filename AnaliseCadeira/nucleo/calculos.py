"""Motor de cálculo da análise estrutural simplificada da cadeira.

MODELO ESTRUTURAL (vista lateral, plano xz)
-------------------------------------------
* O assento é sustentado por 4 pernas verticais de comprimento H (altura do
  assento ao piso), dispostas nos cantos de um retângulo L (largura) × P
  (profundidade).  A cadeira é simétrica em relação ao plano médio lateral, então
  cada lado (par perna dianteira + perna traseira + travessa lateral) recebe
  metade da carga.

* Carga do usuário:  W = m · g · φ   (φ = fator dinâmico, sentar "de uma vez")
  aplicada no assento com excentricidade e (positiva para a frente) em relação ao
  centro do assento.

* Força horizontal no assento:  F_H = μ · W  (inclinar-se, arrastar, atrito).
  Aplicada na altura H, no sentido da frente (sentido mais desfavorável, que
  sobrecarrega as pernas dianteiras).  O piso reage com 4 forças horizontais
  iguais h = F_H / 4 (uma em cada pé).

* Reações verticais (equilíbrio global, ΣM nos pés traseiros):
      R_D,total · P = W·(P/2 + e) + F_H·H
      R_T,total     = W − R_D,total
  Cada perna dianteira: R_D = R_D,total / 2 ;  traseira: R_T = R_T,total / 2.
  Se R_T,total < 0 a cadeira tomba.

* PERNA (barra engastada no quadro do assento, extremidade livre no piso):
      N(y) = −R          (compressão constante)
      V(y) =  h          (cortante constante)
      M(y) =  h · y      (y medido a partir do pé; máximo no engaste: M = h·H)
  Tensão normal máxima (flexo-compressão):
      σ_máx = N/A + M/W
  Deformações: δ_axial = R·H/(E·A), δ_lateral = h·H³/(3·E·I), ε = σ/E
  Flambagem (Euler): P_cr = π²·E·I / (K·H)²

* TRAVESSA LATERAL DO ASSENTO (viga bi-apoiada nas pernas, vão = P):
  carga concentrada Q = W/2 na posição a = P/2 + e (medida a partir da perna
  traseira) — hipótese conservadora em relação à carga distribuída.
      R_A = Q·(P − a)/P   (apoio traseiro)     R_B = Q·a/P (apoio dianteiro)
      M_máx = Q·a·b / P   (b = P − a)
      σ_máx = M_máx / W
      δ_máx = Q·b·(P² − b²)^(3/2) / (9·√3·P·E·I)   (b = menor distância)

* VERIFICAÇÃO:  σ_adm = σ_lim / FS ;  segura se σ_máx ≤ σ_adm nas pernas e na
  travessa, P_cr/R ≥ FS e não houver tombamento.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math

import numpy as np

from .materiais import MATERIAIS, Material, material_personalizado
from .secoes import Secao, criar_secao

G = 9.81  # m/s²


# --------------------------------------------------------------------------- #
#  Entradas
# --------------------------------------------------------------------------- #
@dataclass
class Entradas:
    massa_kg: float = 100.0
    altura_mm: float = 450.0            # altura do assento ao piso = comprimento das pernas
    largura_mm: float = 400.0           # largura do assento (entre pernas, esquerda-direita)
    profundidade_mm: float = 400.0      # profundidade do assento (entre pernas, frente-trás)
    material: str = "Madeira - Eucalipto (C40)"
    tipo_secao: str = "Quadrada maciça"
    espessura_perna_mm: float = 40.0    # lado ou diâmetro externo
    parede_mm: float = 0.0              # só para tubos
    altura_secao_perna_mm: float = 0.0  # h (só seções retangulares)
    # travessa lateral do assento
    travessa_igual_perna: bool = True
    tipo_secao_travessa: str = "Retangular maciça"
    b_travessa_mm: float = 25.0
    h_travessa_mm: float = 60.0
    parede_travessa_mm: float = 0.0
    fator_dinamico: float = 1.5         # φ
    coef_horizontal: float = 0.10       # μ  (F_H = μ·W)
    excentricidade_mm: float = 0.0      # e  (+ para a frente)
    fator_seguranca: float = 2.0        # FS requerido
    k_flambagem: float = 2.0            # K (engastado-livre = 2,0)
    # material personalizado (usado quando material == "Personalizado")
    tensao_personalizada_mpa: float = 100.0
    e_personalizado_gpa: float = 10.0

    def validar(self) -> None:
        erros = []
        if self.massa_kg <= 0:
            erros.append("O peso (massa) da pessoa deve ser maior que zero.")
        if self.altura_mm <= 0:
            erros.append("A altura da cadeira deve ser maior que zero.")
        if self.largura_mm <= 0:
            erros.append("A largura do assento deve ser maior que zero.")
        if self.profundidade_mm <= 0:
            erros.append("A profundidade do assento deve ser maior que zero.")
        if self.espessura_perna_mm <= 0:
            erros.append("A espessura das pernas deve ser maior que zero.")
        if self.espessura_perna_mm >= min(self.largura_mm, self.profundidade_mm) / 2:
            erros.append("A espessura das pernas é incompatível com as dimensões do assento.")
        if self.fator_dinamico < 1:
            erros.append("O fator dinâmico deve ser ≥ 1,0.")
        if self.coef_horizontal < 0:
            erros.append("O coeficiente de força horizontal não pode ser negativo.")
        if self.fator_seguranca < 1:
            erros.append("O fator de segurança deve ser ≥ 1,0.")
        if self.k_flambagem <= 0:
            erros.append("O coeficiente K de flambagem deve ser maior que zero.")
        if abs(self.excentricidade_mm) > self.profundidade_mm / 2:
            erros.append("A excentricidade deve ficar dentro do assento (|e| ≤ P/2).")
        if self.material not in MATERIAIS and self.material != "Personalizado":
            erros.append(f"Material desconhecido: {self.material}")
        if self.material == "Personalizado" and (self.tensao_personalizada_mpa <= 0
                                                 or self.e_personalizado_gpa <= 0):
            erros.append("Informe tensão limite e módulo E positivos para o material personalizado.")
        if erros:
            raise ValueError("\n".join(erros))

    def obter_material(self) -> Material:
        if self.material == "Personalizado":
            return material_personalizado(self.tensao_personalizada_mpa, self.e_personalizado_gpa)
        return MATERIAIS[self.material]


# --------------------------------------------------------------------------- #
#  Resultados
# --------------------------------------------------------------------------- #
@dataclass
class Passo:
    descricao: str
    formula: str
    substituicao: str
    resultado: str


@dataclass
class Resultados:
    entradas: Entradas
    material: Material
    secao: Secao
    secao_travessa: Secao
    # cargas
    peso_estatico: float = 0.0
    W: float = 0.0
    F_H: float = 0.0
    h_perna: float = 0.0
    # reações
    R_D_total: float = 0.0
    R_T_total: float = 0.0
    R_D: float = 0.0
    R_T: float = 0.0
    tomba: bool = False
    # perna crítica
    N_perna: float = 0.0
    M_perna: float = 0.0
    sigma_axial: float = 0.0
    sigma_flexao_perna: float = 0.0
    sigma_max_perna: float = 0.0
    sigma_traseira: float = 0.0
    delta_axial: float = 0.0
    delta_lateral: float = 0.0
    deformacao_perna: float = 0.0
    P_cr: float = 0.0
    esbeltez: float = 0.0
    # travessa
    Q_travessa: float = 0.0
    a_carga: float = 0.0
    R_A: float = 0.0
    R_B: float = 0.0
    M_travessa: float = 0.0
    sigma_travessa: float = 0.0
    delta_travessa: float = 0.0
    deformacao_travessa: float = 0.0
    # verificação
    sigma_adm: float = 0.0
    fs_perna: float = 0.0
    fs_travessa: float = 0.0
    fs_flambagem: float = 0.0
    ok_perna: bool = False
    ok_travessa: bool = False
    ok_flambagem: bool = False
    segura: bool = False
    massa_maxima: float = 0.0
    elemento_critico: str = ""
    memorial: list[tuple[str, list[Passo]]] = field(default_factory=list)

    # ----------------------------------------------------------------- #
    #  Diagramas de esforços internos (arrays para plotagem)
    # ----------------------------------------------------------------- #
    def diagramas_perna(self, n: int = 101):
        """y [m] a partir do pé; N [N], V [N], M [N·m] da perna mais carregada."""
        H = self.entradas.altura_mm / 1000
        y = np.linspace(0, H, n)
        N = np.full_like(y, -self.N_perna)
        V = np.full_like(y, self.h_perna)
        M = self.h_perna * y
        return y, N, V, M

    def diagramas_travessa(self, n: int = 401):
        """x [m] a partir do apoio traseiro; V [N], M [N·m], deflexão v [m] (para baixo +)."""
        P = self.entradas.profundidade_mm / 1000
        a, Q = self.a_carga, self.Q_travessa
        b = P - a
        x = np.linspace(0, P, n)
        V = np.where(x < a, self.R_A, self.R_A - Q)
        M = np.where(x <= a, self.R_A * x, self.R_A * x - Q * (x - a))
        EI = self.material.E * self.secao_travessa.I
        # linha elástica de viga bi-apoiada com carga concentrada (positivo = para baixo)
        v = np.where(
            x <= a,
            Q * b * x * (P ** 2 - b ** 2 - x ** 2) / (6 * P * EI),
            Q * a * (P - x) * (P ** 2 - a ** 2 - (P - x) ** 2) / (6 * P * EI),
        )
        return x, V, M, v


# --------------------------------------------------------------------------- #
#  Formatação
# --------------------------------------------------------------------------- #
def _f(valor: float, casas: int = 2) -> str:
    """Formata número no padrão brasileiro (vírgula decimal)."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _e(valor: float, casas: int = 3) -> str:
    """Notação científica com vírgula."""
    return f"{valor:.{casas}e}".replace(".", ",")


# --------------------------------------------------------------------------- #
#  Análise
# --------------------------------------------------------------------------- #
def analisar(ent: Entradas) -> Resultados:
    ent.validar()
    mat = ent.obter_material()
    sec = criar_secao(ent.tipo_secao, ent.espessura_perna_mm, ent.parede_mm,
                      ent.altura_secao_perna_mm)
    if ent.travessa_igual_perna:
        sec_t = sec
    else:
        sec_t = criar_secao(ent.tipo_secao_travessa, ent.b_travessa_mm,
                            ent.parede_travessa_mm, ent.h_travessa_mm)
    r = Resultados(ent, mat, sec, sec_t)

    H = ent.altura_mm / 1000
    P = ent.profundidade_mm / 1000
    e = ent.excentricidade_mm / 1000
    E = mat.E
    A, I, W_res = sec.A, sec.I, sec.W

    # 1) Cargas -----------------------------------------------------------
    r.peso_estatico = ent.massa_kg * G
    r.W = r.peso_estatico * ent.fator_dinamico
    r.F_H = ent.coef_horizontal * r.W
    r.h_perna = r.F_H / 4

    # 2) Reações de apoio (equilíbrio global) ------------------------------
    r.R_D_total = (r.W * (P / 2 + e) + r.F_H * H) / P
    r.R_T_total = r.W - r.R_D_total
    r.tomba = r.R_T_total < -1e-9
    r.R_D = r.R_D_total / 2
    r.R_T = r.R_T_total / 2

    # 3) Perna crítica (dianteira, mais carregada) ------------------------
    r.N_perna = max(r.R_D, r.R_T)
    r.M_perna = r.h_perna * H
    r.sigma_axial = r.N_perna / A
    r.sigma_flexao_perna = r.M_perna / W_res
    r.sigma_max_perna = r.sigma_axial + r.sigma_flexao_perna
    r.sigma_traseira = max(r.R_T, 0) / A + r.sigma_flexao_perna
    r.delta_axial = r.N_perna * H / (E * A)
    r.delta_lateral = r.h_perna * H ** 3 / (3 * E * I)
    r.deformacao_perna = r.sigma_max_perna / E
    Le = ent.k_flambagem * H
    r.P_cr = math.pi ** 2 * E * sec.I_min / Le ** 2
    r.esbeltez = Le / sec.r

    # 4) Travessa lateral -------------------------------------------------
    r.Q_travessa = r.W / 2
    r.a_carga = P / 2 + e
    b = P - r.a_carga
    r.R_A = r.Q_travessa * b / P
    r.R_B = r.Q_travessa * r.a_carga / P
    r.M_travessa = r.Q_travessa * r.a_carga * b / P
    r.sigma_travessa = r.M_travessa / sec_t.W
    bm = min(r.a_carga, b)
    r.delta_travessa = (r.Q_travessa * bm * (P ** 2 - bm ** 2) ** 1.5
                        / (9 * math.sqrt(3) * P * E * sec_t.I))
    r.deformacao_travessa = r.sigma_travessa / E

    # 5) Verificação ------------------------------------------------------
    r.sigma_adm = mat.tensao_limite / ent.fator_seguranca
    r.fs_perna = mat.tensao_limite / r.sigma_max_perna if r.sigma_max_perna > 0 else math.inf
    r.fs_travessa = mat.tensao_limite / r.sigma_travessa if r.sigma_travessa > 0 else math.inf
    r.fs_flambagem = r.P_cr / r.N_perna if r.N_perna > 0 else math.inf
    r.ok_perna = r.sigma_max_perna <= r.sigma_adm
    r.ok_travessa = r.sigma_travessa <= r.sigma_adm
    r.ok_flambagem = r.fs_flambagem >= ent.fator_seguranca
    r.segura = r.ok_perna and r.ok_travessa and r.ok_flambagem and not r.tomba

    # todas as solicitações são proporcionais a W -> massa máxima admissível
    fs_min = min(r.fs_perna, r.fs_travessa, r.fs_flambagem)
    r.massa_maxima = ent.massa_kg * fs_min / ent.fator_seguranca
    criticos = {"Pernas (flexo-compressão)": r.fs_perna,
                "Travessa do assento (flexão)": r.fs_travessa,
                "Pernas (flambagem)": r.fs_flambagem}
    r.elemento_critico = min(criticos, key=criticos.get)

    r.memorial = _montar_memorial(r)
    return r


# --------------------------------------------------------------------------- #
#  Memorial de cálculo (passo a passo)
# --------------------------------------------------------------------------- #
def _montar_memorial(r: Resultados) -> list[tuple[str, list[Passo]]]:
    ent, mat, sec, sec_t = r.entradas, r.material, r.secao, r.secao_travessa
    H = ent.altura_mm / 1000
    P = ent.profundidade_mm / 1000
    e = ent.excentricidade_mm / 1000
    E = mat.E
    mpa = lambda pa: _f(pa / 1e6, 2)  # noqa: E731
    mm = lambda m: _f(m * 1000, 3)    # noqa: E731
    memorial = []

    # 1. Dados ----------------------------------------------------------------
    memorial.append(("1. Dados de entrada", [
        Passo("Massa do usuário", "m", "", f"{_f(ent.massa_kg, 1)} kg"),
        Passo("Altura do assento (comprimento das pernas)", "H", "", f"{_f(ent.altura_mm, 0)} mm"),
        Passo("Largura do assento", "L", "", f"{_f(ent.largura_mm, 0)} mm"),
        Passo("Profundidade do assento (vão da travessa)", "P", "", f"{_f(ent.profundidade_mm, 0)} mm"),
        Passo("Material", "", "", mat.nome),
        Passo("Seção das pernas", "", "", sec.descricao()),
        Passo("Seção das travessas do assento", "", "",
              "igual à das pernas" if ent.travessa_igual_perna else sec_t.descricao()),
        Passo("Fator dinâmico (impacto ao sentar)", "φ", "", _f(ent.fator_dinamico, 2)),
        Passo("Coeficiente de força horizontal", "μ", "", _f(ent.coef_horizontal, 2)),
        Passo("Excentricidade da carga (+ frente)", "e", "", f"{_f(ent.excentricidade_mm, 0)} mm"),
        Passo("Fator de segurança requerido", "FS", "", _f(ent.fator_seguranca, 2)),
        Passo("Coeficiente de comprimento de flambagem", "K", "", _f(ent.k_flambagem, 2)),
    ]))

    # 2. Material ---------------------------------------------------------------
    memorial.append(("2. Propriedades do material", [
        Passo(f"Tensão limite ({mat.criterio})", "σ_lim", "", f"{_f(mat.tensao_limite_mpa, 1)} MPa"),
        Passo("Módulo de elasticidade", "E", "", f"{_f(mat.modulo_elasticidade_gpa, 1)} GPa"),
        Passo("Tensão admissível", "σ_adm = σ_lim / FS",
              f"{_f(mat.tensao_limite_mpa, 1)} / {_f(ent.fator_seguranca, 2)}",
              f"{mpa(r.sigma_adm)} MPa"),
    ]))

    # 3. Seções -------------------------------------------------------------------
    def _passos_secao(sx: Secao, nome: str) -> list[Passo]:
        f = sx.formulas()
        passos = [
            Passo(f"Seção da {nome}", "", "", sx.descricao()),
            Passo("Área da seção", f[0], "", f"{_f(sx.A * 1e6, 2)} mm²"),
            Passo("Momento de inércia (eixo de flexão)", f[1], "", f"{_f(sx.I * 1e12, 1)} mm⁴"),
        ]
        if abs(sx.I_min - sx.I) > 1e-18:
            passos.append(Passo("Menor momento de inércia (flambagem)", "I_mín", "",
                                f"{_f(sx.I_min * 1e12, 1)} mm⁴"))
        passos += [
            Passo("Distância à fibra extrema", f[2], "", f"{_f(sx.c * 1000, 2)} mm"),
            Passo("Módulo de resistência à flexão", f[3], "", f"{_f(sx.W * 1e9, 1)} mm³"),
            Passo("Raio de giração mínimo", "r = √(I_mín / A)", "", f"{_f(sx.r * 1000, 2)} mm"),
        ]
        return passos

    passos_sec = _passos_secao(sec, "perna")
    if ent.travessa_igual_perna:
        passos_sec.append(Passo("Seção da travessa", "", "", "igual à seção da perna"))
    else:
        passos_sec += _passos_secao(sec_t, "travessa")
    memorial.append(("3. Características geométricas das seções", passos_sec))

    # 4. Cargas ---------------------------------------------------------------------
    memorial.append(("4. Carregamento", [
        Passo("Peso estático do usuário", "P₀ = m · g",
              f"{_f(ent.massa_kg, 1)} · 9,81", f"{_f(r.peso_estatico, 1)} N"),
        Passo("Carga de projeto (com efeito dinâmico)", "W = P₀ · φ",
              f"{_f(r.peso_estatico, 1)} · {_f(ent.fator_dinamico, 2)}", f"{_f(r.W, 1)} N"),
        Passo("Força horizontal no assento", "F_H = μ · W",
              f"{_f(ent.coef_horizontal, 2)} · {_f(r.W, 1)}", f"{_f(r.F_H, 1)} N"),
        Passo("Força horizontal em cada pé", "h = F_H / 4",
              f"{_f(r.F_H, 1)} / 4", f"{_f(r.h_perna, 2)} N"),
    ]))

    # 5. Reações ----------------------------------------------------------------------
    memorial.append(("5. Reações vinculares (equilíbrio global)", [
        Passo("ΣM nos pés traseiros = 0 → reação total dianteira",
              "R_D,tot = [W·(P/2 + e) + F_H·H] / P",
              f"[{_f(r.W, 1)}·({_f(P / 2, 3)} + {_f(e, 3)}) + {_f(r.F_H, 1)}·{_f(H, 3)}] / {_f(P, 3)}",
              f"{_f(r.R_D_total, 1)} N"),
        Passo("ΣFy = 0 → reação total traseira", "R_T,tot = W − R_D,tot",
              f"{_f(r.W, 1)} − {_f(r.R_D_total, 1)}", f"{_f(r.R_T_total, 1)} N"),
        Passo("Reação em cada perna dianteira", "R_D = R_D,tot / 2",
              f"{_f(r.R_D_total, 1)} / 2", f"{_f(r.R_D, 1)} N"),
        Passo("Reação em cada perna traseira", "R_T = R_T,tot / 2",
              f"{_f(r.R_T_total, 1)} / 2", f"{_f(r.R_T, 1)} N"),
        Passo("ΣFx = 0 → reação horizontal total no piso", "ΣH = 4·h = F_H",
              f"4 · {_f(r.h_perna, 2)}", f"{_f(r.F_H, 1)} N"),
        Passo("Verificação de tombamento", "R_T,tot ≥ 0",
              f"{_f(r.R_T_total, 1)} N",
              "TOMBA" if r.tomba else "OK — não tomba"),
    ]))

    # 6. Perna ---------------------------------------------------------------------
    memorial.append(("6. Esforços e tensões na perna mais carregada", [
        Passo("Esforço normal (compressão)", "N = máx(R_D, R_T)",
              "", f"{_f(r.N_perna, 1)} N"),
        Passo("Esforço cortante", "V = h", "", f"{_f(r.h_perna, 2)} N"),
        Passo("Momento fletor máximo (no engaste com o assento)", "M = h · H",
              f"{_f(r.h_perna, 2)} · {_f(H, 3)}", f"{_f(r.M_perna, 2)} N·m"),
        Passo("Tensão normal devida ao esforço axial", "σ_N = N / A",
              f"{_f(r.N_perna, 1)} / {_e(sec.A)}", f"{mpa(r.sigma_axial)} MPa"),
        Passo("Tensão normal devida ao momento fletor", "σ_M = M / W",
              f"{_f(r.M_perna, 2)} / {_e(sec.W)}", f"{mpa(r.sigma_flexao_perna)} MPa"),
        Passo("Tensão normal máxima (flexo-compressão)", "σ_máx = σ_N + σ_M",
              f"{mpa(r.sigma_axial)} + {mpa(r.sigma_flexao_perna)}",
              f"{mpa(r.sigma_max_perna)} MPa"),
        Passo("Deformação específica", "ε = σ_máx / E",
              f"{_e(r.sigma_max_perna)} / {_e(E)}", f"{_e(r.deformacao_perna)} ({_f(r.deformacao_perna * 1e6, 1)} με)"),
        Passo("Encurtamento axial", "δ_N = N·H / (E·A)",
              f"{_f(r.N_perna, 1)}·{_f(H, 3)} / ({_e(E)}·{_e(sec.A)})", f"{mm(r.delta_axial)} mm"),
        Passo("Deslocamento lateral do pé", "δ_H = h·H³ / (3·E·I)",
              f"{_f(r.h_perna, 2)}·{_f(H, 3)}³ / (3·{_e(E)}·{_e(sec.I)})", f"{mm(r.delta_lateral)} mm"),
    ]))

    # 7. Flambagem -------------------------------------------------------------------
    memorial.append(("7. Flambagem das pernas (Euler)", [
        Passo("Comprimento de flambagem", "L_e = K · H",
              f"{_f(ent.k_flambagem, 2)} · {_f(H, 3)}", f"{_f(ent.k_flambagem * H, 3)} m"),
        Passo("Índice de esbeltez", "λ = L_e / r", "", _f(r.esbeltez, 1)),
        Passo("Carga crítica de Euler", "P_cr = π²·E·I_mín / L_e²",
              f"π²·{_e(E)}·{_e(sec.I_min)} / {_f(ent.k_flambagem * H, 3)}²", f"{_f(r.P_cr, 0)} N"),
        Passo("Fator de segurança à flambagem", "n_fl = P_cr / N",
              f"{_f(r.P_cr, 0)} / {_f(r.N_perna, 1)}", _f(r.fs_flambagem, 2)),
    ]))

    # 8. Travessa ---------------------------------------------------------------------
    b = P - r.a_carga
    memorial.append(("8. Travessa lateral do assento (viga bi-apoiada)", [
        Passo("Carga em cada travessa", "Q = W / 2", f"{_f(r.W, 1)} / 2", f"{_f(r.Q_travessa, 1)} N"),
        Passo("Posição da carga (a partir do apoio traseiro)", "a = P/2 + e",
              f"{_f(P / 2, 3)} + {_f(e, 3)}", f"{_f(r.a_carga, 3)} m"),
        Passo("Reação no apoio traseiro (ΣM_B = 0)", "R_A = Q·(P − a) / P",
              f"{_f(r.Q_travessa, 1)}·{_f(b, 3)} / {_f(P, 3)}", f"{_f(r.R_A, 1)} N"),
        Passo("Reação no apoio dianteiro (ΣFy = 0)", "R_B = Q − R_A",
              f"{_f(r.Q_travessa, 1)} − {_f(r.R_A, 1)}", f"{_f(r.R_B, 1)} N"),
        Passo("Momento fletor máximo (sob a carga)", "M_máx = Q·a·b / P",
              f"{_f(r.Q_travessa, 1)}·{_f(r.a_carga, 3)}·{_f(b, 3)} / {_f(P, 3)}",
              f"{_f(r.M_travessa, 2)} N·m"),
        Passo("Tensão normal de flexão", "σ = M_máx / W",
              f"{_f(r.M_travessa, 2)} / {_e(sec_t.W)}", f"{mpa(r.sigma_travessa)} MPa"),
        Passo("Deformação específica", "ε = σ / E", "", f"{_e(r.deformacao_travessa)}"),
        Passo("Flecha máxima", "δ = Q·b·(P² − b²)^1,5 / (9·√3·P·E·I)",
              "b = menor distância da carga ao apoio", f"{mm(r.delta_travessa)} mm"),
    ]))

    # 9. Verificação ---------------------------------------------------------------------
    ok = lambda c: "ATENDE" if c else "NÃO ATENDE"  # noqa: E731
    memorial.append(("9. Verificação de segurança", [
        Passo("Pernas: σ_máx ≤ σ_adm", f"{mpa(r.sigma_max_perna)} ≤ {mpa(r.sigma_adm)} MPa",
              f"FS real = σ_lim/σ_máx = {_f(r.fs_perna, 2)}", ok(r.ok_perna)),
        Passo("Travessa: σ ≤ σ_adm", f"{mpa(r.sigma_travessa)} ≤ {mpa(r.sigma_adm)} MPa",
              f"FS real = {_f(r.fs_travessa, 2)}", ok(r.ok_travessa)),
        Passo("Flambagem: n_fl ≥ FS", f"{_f(r.fs_flambagem, 2)} ≥ {_f(ent.fator_seguranca, 2)}",
              "", ok(r.ok_flambagem)),
        Passo("Tombamento: R_T,tot ≥ 0", f"{_f(r.R_T_total, 1)} N ≥ 0", "", ok(not r.tomba)),
        Passo("Massa máxima admissível do usuário", "m_máx = m · FS_real,mín / FS",
              f"elemento crítico: {r.elemento_critico}", f"{_f(r.massa_maxima, 1)} kg"),
        Passo("RESULTADO", "", "", "CADEIRA SEGURA" if r.segura else "CADEIRA NÃO SEGURA"),
    ]))
    return memorial
