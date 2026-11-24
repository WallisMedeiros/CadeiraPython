"""Motor de cálculo da análise estrutural simplificada da cadeira.

PREMISSAS DO MODELO
-------------------
* Carregamento ESTÁTICO e exclusivamente VERTICAL: o peso do usuário
      P = m · g
  sem fator dinâmico e sem força horizontal (atrito não considerado).
* Excentricidade FIXA e = 0: a carga atua no centro do assento.
* 4 pernas verticais de comprimento H nos cantos de um retângulo L (largura) × ℓ
  (profundidade).  Por simetria, cada lado (perna dianteira + perna traseira +
  travessa lateral) recebe metade da carga; a análise é feita na vista lateral.

REAÇÕES VINCULARES (equilíbrio global, ΣM nos pés traseiros):
      R_D,tot · ℓ = P · (ℓ/2 + e)      com e = 0  →  R_D,tot = P/2
      R_T,tot     = P − R_D,tot = P/2
  Cada perna: R = P/4.  Não há reações horizontais (ΣFx = 0 sem forças horizontais).

PERNA (barra engastada no quadro do assento, livre no piso):
      N = −R (compressão)    V = 0    M = 0
  Com carga somente vertical e centrada, a perna trabalha em compressão simples:
      σ = N/A + M/W = N/A         δ_N = N·H/(E·A)

TRAVESSA LATERAL DO ASSENTO (viga bi-apoiada nas pernas, vão ℓ):
  carga concentrada Q = P/2 no meio do vão (a = ℓ/2 + e = ℓ/2)
      R_A = R_B = Q/2      M_máx = Q·ℓ/4      σ = M_máx/W      δ_máx = Q·ℓ³/(48·E·I)

VERIFICAÇÃO:  σ_adm = σ_lim / FS ;  segura se σ ≤ σ_adm nas pernas e na travessa.

Sistema de unidades do memorial: N, mm e MPa (1 MPa = 1 N/mm²).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math

import numpy as np

from .materiais import MATERIAIS, Material
from .secoes import TIPOS_SECAO, Secao, criar_secao, validar_dimensoes

G = 10.00                  # m/s² (valor adotado no projeto para a aceleração da gravidade)
EXCENTRICIDADE_MM = 0.0    # premissa fixa do modelo: carga centrada no assento


# --------------------------------------------------------------------------- #
#  Entradas
# --------------------------------------------------------------------------- #
@dataclass
class Entradas:
    massa_kg: float = 100.0
    altura_mm: float = 450.0            # altura do assento ao piso = comprimento das pernas
    largura_mm: float = 400.0           # largura do assento (entre pernas, esquerda-direita)
    profundidade_mm: float = 400.0      # profundidade do assento ℓ (vão da travessa lateral)
    material: str = "Madeira - Eucalipto (C40)"
    tipo_secao: str = "Quadrada maciça"
    espessura_perna_mm: float = 40.0    # dimensão externa: a, d, D ou B
    interna_perna_mm: float = 0.0       # dimensão interna (só seções vazadas): d ou b
    # travessa lateral do assento
    travessa_igual_perna: bool = True
    tipo_secao_travessa: str = "Quadrada maciça"
    dimensao_travessa_mm: float = 40.0  # dimensão externa da travessa
    interna_travessa_mm: float = 0.0    # dimensão interna da travessa (só vazadas)
    fator_seguranca: float = 2.0        # FS requerido

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
        erros += validar_dimensoes(self.tipo_secao, self.espessura_perna_mm,
                                   self.interna_perna_mm, "perna")
        if (self.espessura_perna_mm > 0
                and self.espessura_perna_mm >= min(self.largura_mm, self.profundidade_mm) / 2):
            erros.append("A espessura das pernas é incompatível com as dimensões do assento.")
        if not self.travessa_igual_perna:
            erros += validar_dimensoes(self.tipo_secao_travessa, self.dimensao_travessa_mm,
                                       self.interna_travessa_mm, "travessa")
        if self.fator_seguranca < 1:
            erros.append("O fator de segurança deve ser ≥ 1,0.")
        if self.material not in MATERIAIS:
            erros.append(f"Material não disponível: {self.material}. "
                         f"Opções: {', '.join(MATERIAIS)}.")
        if erros:
            raise ValueError("\n".join(erros))

    def obter_material(self) -> Material:
        return MATERIAIS[self.material]


# --------------------------------------------------------------------------- #
#  Memorial de cálculo
# --------------------------------------------------------------------------- #
@dataclass
class Passo:
    """Uma etapa do memorial de cálculo.

    descricao      o que está sendo calculado
    formula        fórmula em texto simples (interfaces)
    substituicao   fórmula com os valores numéricos
    resultado      valor final com unidade
    latex          fórmula em mathtext (relatório PDF)
    explicacao     por que o cálculo é feito e qual conceito de RM é aplicado
    variaveis      [(símbolo, significado)] das variáveis da fórmula
    desenvolvimento passos intermediários da conta
    interpretacao  leitura técnica do resultado
    """
    descricao: str
    formula: str = ""
    substituicao: str = ""
    resultado: str = ""
    latex: str = ""
    explicacao: str = ""
    variaveis: list[tuple[str, str]] = field(default_factory=list)
    desenvolvimento: str = ""
    interpretacao: str = ""


@dataclass
class EtapaMemorial:
    chave: str
    titulo: str
    introducao: str
    passos: list[Passo]


# --------------------------------------------------------------------------- #
#  Resultados
# --------------------------------------------------------------------------- #
@dataclass
class Resultados:
    entradas: Entradas
    material: Material
    secao: Secao
    secao_travessa: Secao
    # carga
    P: float = 0.0                      # peso do usuário (carga estática) [N]
    # reações
    R_D_total: float = 0.0
    R_T_total: float = 0.0
    R_D: float = 0.0
    R_T: float = 0.0
    # perna
    N_perna: float = 0.0
    V_perna: float = 0.0
    M_perna: float = 0.0
    sigma_axial: float = 0.0
    sigma_flexao_perna: float = 0.0
    sigma_max_perna: float = 0.0
    delta_axial: float = 0.0
    deformacao_perna: float = 0.0
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
    ok_perna: bool = False
    ok_travessa: bool = False
    segura: bool = False
    massa_maxima: float = 0.0
    elemento_critico: str = ""
    memorial: list[EtapaMemorial] = field(default_factory=list)

    @property
    def excentricidade_mm(self) -> float:
        return EXCENTRICIDADE_MM

    # ----------------------------------------------------------------- #
    #  Diagramas de esforços internos (arrays para plotagem)
    # ----------------------------------------------------------------- #
    def diagramas_perna(self, n: int = 101):
        """y [m] a partir do pé; N [N], V [N], M [N·m] da perna (compressão simples)."""
        H = self.entradas.altura_mm / 1000
        y = np.linspace(0, H, n)
        N = np.full_like(y, -self.N_perna)
        V = np.full_like(y, self.V_perna)
        M = np.full_like(y, self.M_perna)
        return y, N, V, M

    def diagramas_travessa(self, n: int = 401):
        """x [m] a partir do apoio traseiro; V [N], M [N·m], deflexão v [m] (para baixo +)."""
        L = self.entradas.profundidade_mm / 1000
        a, Q = self.a_carga, self.Q_travessa
        b = L - a
        x = np.linspace(0, L, n)
        V = np.where(x < a, self.R_A, self.R_A - Q)
        M = np.where(x <= a, self.R_A * x, self.R_A * x - Q * (x - a))
        EI = self.material.E * self.secao_travessa.I
        # linha elástica de viga bi-apoiada com carga concentrada (positivo = para baixo)
        v = np.where(
            x <= a,
            Q * b * x * (L ** 2 - b ** 2 - x ** 2) / (6 * L * EI),
            Q * a * (L - x) * (L ** 2 - a ** 2 - (L - x) ** 2) / (6 * L * EI),
        )
        return x, V, M, v

    def etapa(self, chave: str) -> EtapaMemorial:
        return next(e for e in self.memorial if e.chave == chave)


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
    sec = criar_secao(ent.tipo_secao, ent.espessura_perna_mm, ent.interna_perna_mm)
    if ent.travessa_igual_perna:
        sec_t = sec
    else:
        sec_t = criar_secao(ent.tipo_secao_travessa, ent.dimensao_travessa_mm,
                            ent.interna_travessa_mm)
    r = Resultados(ent, mat, sec, sec_t)

    H = ent.altura_mm / 1000
    L = ent.profundidade_mm / 1000
    e = EXCENTRICIDADE_MM / 1000
    E = mat.E

    # 1) Carga estática ------------------------------------------------------
    r.P = ent.massa_kg * G

    # 2) Reações de apoio (equilíbrio global) ---------------------------------
    r.R_D_total = r.P * (L / 2 + e) / L
    r.R_T_total = r.P - r.R_D_total
    r.R_D = r.R_D_total / 2
    r.R_T = r.R_T_total / 2

    # 3) Perna: compressão simples ---------------------------------------------
    r.N_perna = max(r.R_D, r.R_T)
    r.V_perna = 0.0          # não há força transversal na perna
    r.M_perna = 0.0          # sem força transversal nem excentricidade -> sem momento
    r.sigma_axial = r.N_perna / sec.A
    r.sigma_flexao_perna = r.M_perna / sec.W
    r.sigma_max_perna = r.sigma_axial + r.sigma_flexao_perna
    r.delta_axial = r.N_perna * H / (E * sec.A)
    r.deformacao_perna = r.sigma_max_perna / E

    # 4) Travessa lateral (viga bi-apoiada) -----------------------------------
    r.Q_travessa = r.P / 2
    r.a_carga = L / 2 + e
    b = L - r.a_carga
    r.R_A = r.Q_travessa * b / L
    r.R_B = r.Q_travessa - r.R_A
    r.M_travessa = r.Q_travessa * r.a_carga * b / L
    r.sigma_travessa = r.M_travessa / sec_t.W
    r.delta_travessa = r.Q_travessa * L ** 3 / (48 * E * sec_t.I)
    r.deformacao_travessa = r.sigma_travessa / E

    # 5) Verificação --------------------------------------------------------
    r.sigma_adm = mat.tensao_limite / ent.fator_seguranca
    r.fs_perna = mat.tensao_limite / r.sigma_max_perna if r.sigma_max_perna > 0 else math.inf
    r.fs_travessa = mat.tensao_limite / r.sigma_travessa if r.sigma_travessa > 0 else math.inf
    r.ok_perna = r.sigma_max_perna <= r.sigma_adm
    r.ok_travessa = r.sigma_travessa <= r.sigma_adm
    r.segura = r.ok_perna and r.ok_travessa

    # todas as solicitações são proporcionais a P -> massa máxima admissível
    fs_min = min(r.fs_perna, r.fs_travessa)
    r.massa_maxima = ent.massa_kg * fs_min / ent.fator_seguranca
    criticos = {"Pernas (compressão)": r.fs_perna, "Travessa do assento (flexão)": r.fs_travessa}
    r.elemento_critico = min(criticos, key=criticos.get)

    r.memorial = _montar_memorial(r)
    return r


# --------------------------------------------------------------------------- #
#  Memorial de cálculo (passo a passo, com explicações)
# --------------------------------------------------------------------------- #
def _montar_memorial(r: Resultados) -> list[EtapaMemorial]:
    ent, mat, sec, sec_t = r.entradas, r.material, r.secao, r.secao_travessa
    H_mm, L_mm, e_mm = ent.altura_mm, ent.profundidade_mm, EXCENTRICIDADE_MM
    H, L, e = H_mm / 1000, L_mm / 1000, e_mm / 1000
    E_mpa = mat.E / 1e6
    mpa = lambda pa: _f(pa / 1e6, 3)  # noqa: E731
    A_mm2 = sec.A * 1e6
    It_mm4, Wt_mm3 = sec_t.I * 1e12, sec_t.W * 1e9
    b = L - r.a_carga
    memorial: list[EtapaMemorial] = []

    def _dim(sx: Secao) -> str:
        return sx.descricao() + f" ({sx.dimensoes()})"

    # ------------------------------------------------------------------ 1. Dados
    memorial.append(EtapaMemorial("dados", "1. Dados de entrada e premissas fixas", (
        "Valores informados pelo usuário na interface do software e premissas fixas do modelo. "
        "Todos os resultados seguintes são obtidos a partir deles."), [
        Passo("Massa do usuário", "m", resultado=f"{_f(ent.massa_kg, 1)} kg"),
        Passo("Altura do assento ao piso (comprimento das pernas)", "H", resultado=f"{_f(H_mm, 0)} mm"),
        Passo("Largura do assento (distância entre pernas, lateral)", "L", resultado=f"{_f(ent.largura_mm, 0)} mm"),
        Passo("Profundidade do assento (vão da travessa lateral)", "ℓ", resultado=f"{_f(L_mm, 0)} mm"),
        Passo("Material da estrutura", resultado=mat.nome),
        Passo("Seção transversal das pernas", resultado=_dim(sec)),
        Passo("Seção transversal das travessas do assento",
              resultado="igual à das pernas" if ent.travessa_igual_perna else _dim(sec_t)),
        Passo("Fator de segurança requerido", "FS", resultado=_f(ent.fator_seguranca, 2)),
        Passo("Aceleração da gravidade adotada (premissa fixa)", "g", resultado=f"{_f(G, 2)} m/s²"),
        Passo("Excentricidade adotada (premissa fixa)", "e", resultado=f"{_f(e_mm, 0)} mm"),
    ]))

    # ------------------------------------------------------------------ 2. Material
    memorial.append(EtapaMemorial("material", "2. Propriedades do material e tensão admissível", (
        "As propriedades mecânicas do material definem quanto a estrutura pode ser solicitada "
        "(tensão limite) e quanto ela se deforma sob carga (módulo de elasticidade)."), [
        Passo("Tensão limite do material", "σ_lim", resultado=f"{_f(mat.tensao_limite_mpa, 1)} MPa",
              explicacao=(f"Para o material selecionado ({mat.condicao}), a tensão limite "
                          f"corresponde ao {mat.criterio}. Fonte: {mat.fonte}.")),
        Passo("Módulo de elasticidade", "E",
              resultado=f"{_f(mat.modulo_elasticidade_gpa, 1)} GPa = {_f(E_mpa, 0)} MPa",
              explicacao="Constante de proporcionalidade entre tensão e deformação no regime "
                         "elástico (Lei de Hooke, σ = E·ε)."),
        Passo("Tensão admissível", "σ_adm = σ_lim / FS",
              f"{_f(mat.tensao_limite_mpa, 1)} MPa / {_f(ent.fator_seguranca, 2)}",
              f"{_f(r.sigma_adm / 1e6, 2)} MPa",
              latex=r"\sigma_{\mathrm{adm}} = \dfrac{\sigma_{\mathrm{lim}}}{FS}",
              explicacao=("A estrutura não deve trabalhar no limite de resistência do material, "
                          "pois existem incertezas nas cargas, nas dimensões e nas propriedades. "
                          "Divide-se a tensão limite pelo fator de segurança para obter a maior "
                          "tensão que se aceita nas peças."),
              variaveis=[("σ_adm", "tensão admissível [MPa]"),
                         ("σ_lim", "tensão limite do material [MPa]"),
                         ("FS", "fator de segurança requerido [adimensional]")],
              interpretacao=(f"Nenhuma tensão normal calculada nas pernas ou na travessa poderá "
                             f"superar {_f(r.sigma_adm / 1e6, 2)} MPa para que a cadeira seja "
                             f"considerada segura.")),
    ]))

    # ------------------------------------------------------------------ 3. Geometria
    def _passos_secao(sx: Secao, nome: str) -> list[Passo]:
        f, sub = sx.formulas(), sx.substituicoes()
        vdim = sx.variaveis()
        A2, I4, W3 = sx.A * 1e6, sx.I * 1e12, sx.W * 1e9
        vazio = (" Na seção vazada, a área do furo interno é descontada da área externa."
                 if sx.vazada else "")
        return [
            Passo(f"Área da seção da {nome}", f["A"][0], sub["A"], f"{_f(A2, 2)} mm²",
                  latex=f["A"][1],
                  explicacao=("A área resiste ao esforço normal: quanto maior a área, menor a "
                              "tensão produzida pela compressão (σ = N/A)." + vazio),
                  variaveis=[("A", "área da seção transversal [mm²]")] + vdim,
                  interpretacao=f"Usada no cálculo da tensão axial e do encurtamento da {nome}."),
            Passo(f"Momento de inércia da {nome}", f["I"][0], sub["I"], f"{_f(I4, 0)} mm⁴",
                  latex=f["I"][1],
                  explicacao=("O momento de inércia mede a distribuição da área em torno da linha "
                              "neutra e governa a rigidez à flexão (deslocamentos inversamente "
                              "proporcionais a E·I)."
                              + (" Nas seções vazadas, subtrai-se a inércia do furo, que está "
                                 "concentrado perto da linha neutra e contribui pouco."
                                 if sx.vazada else "")),
                  variaveis=[("I", "momento de inércia em relação à linha neutra [mm⁴]")] + vdim,
                  interpretacao=("Por ser uma seção duplamente simétrica, o valor é o mesmo em "
                                 "qualquer direção principal de flexão.")),
            Passo(f"Distância da linha neutra à fibra extrema ({nome})", f["c"][0], sub["c"],
                  f"{_f(sx.c * 1000, 2)} mm", latex=f["c"][1],
                  explicacao="Na flexão, a tensão é máxima nas fibras mais afastadas da linha neutra.",
                  variaveis=[("c", "distância da linha neutra à fibra mais afastada [mm]")] + vdim[:1]),
            Passo(f"Módulo resistente à flexão da {nome}", f["W"][0], sub["W"], f"{_f(W3, 1)} mm³",
                  latex=f["W"][1],
                  explicacao=("O módulo resistente W = I/c relaciona diretamente o momento fletor "
                              "com a tensão máxima de flexão (σ = M/W)."),
                  variaveis=[("W", "módulo resistente à flexão [mm³]"),
                             ("I", "momento de inércia [mm⁴]"), ("c", "distância à fibra extrema [mm]")],
                  interpretacao="Quanto maior W, menor a tensão de flexão para o mesmo momento."),
        ]

    passos_sec = _passos_secao(sec, "perna")
    if ent.travessa_igual_perna:
        passos_sec.append(Passo("Seção da travessa", resultado="igual à seção da perna (mesmos A, I, c e W)"))
    else:
        passos_sec += _passos_secao(sec_t, "travessa")
    memorial.append(EtapaMemorial("geometria", "3. Características geométricas das seções", (
        f"Seção das pernas: {_dim(sec)}. As propriedades geométricas são calculadas em relação ao "
        f"centroide da seção, em milímetros."), passos_sec))

    # ------------------------------------------------------------------ 4. Carregamento
    memorial.append(EtapaMemorial("carregamento", "4. Carregamento", (
        "A única ação considerada é o peso do usuário, aplicado de forma estática e vertical no "
        "centro do assento. Não se aplicam fator dinâmico, força horizontal nem excentricidade."), [
        Passo("Peso do usuário (carga estática)", "P = m · g", f"{_f(ent.massa_kg, 1)} kg · {_f(G, 2)} m/s²",
              f"{_f(r.P, 1)} N", latex=r"P = m \cdot g",
              explicacao=("A massa (kg) é convertida em força peso (N) pela 2ª Lei de Newton. O "
                          "valor é usado diretamente como carregamento estático, sem "
                          "multiplicadores."),
              variaveis=[("P", "peso aplicado pelo usuário [N]"), ("m", "massa do usuário [kg]"),
                         ("g", "aceleração da gravidade [m/s²]")],
              interpretacao="É esta força que percorre a estrutura: assento → travessas → pernas → piso."),
    ]))

    # ------------------------------------------------------------------ 5. Reações
    memorial.append(EtapaMemorial("reacoes", "5. Reações vinculares (equilíbrio global)", (
        "A cadeira inteira é tratada como um corpo rígido em equilíbrio estático, apoiado no piso "
        "pelos quatro pés. Aplicando as equações de equilíbrio do plano (ΣFx = 0, ΣFy = 0 e "
        "ΣM = 0) na vista lateral, obtêm-se as forças que o piso exerce sobre as pernas."), [
        Passo("Reação vertical total nas pernas dianteiras (ΣM nos pés traseiros = 0)",
              "R_D,tot = P·(ℓ/2 + e) / ℓ",
              f"{_f(r.P, 1)} · ({_f(L_mm / 2, 1)} + {_f(e_mm, 0)}) / {_f(L_mm, 0)}",
              f"{_f(r.R_D_total, 1)} N",
              latex=r"R_{D,\mathrm{tot}} = \dfrac{P\,(\ell/2 + e)}{\ell}",
              explicacao=("Somando os momentos em torno dos pés traseiros, as reações traseiras não "
                          "geram momento e a única incógnita é a reação dianteira. Como a "
                          "excentricidade é fixa em e = 0, a carga atua no meio da profundidade."),
              variaveis=[("R_D,tot", "soma das reações verticais nas duas pernas dianteiras [N]"),
                         ("P", "peso do usuário [N]"), ("ℓ", "profundidade (distância entre pernas) [mm]"),
                         ("e", "excentricidade (premissa fixa = 0) [mm]")],
              interpretacao="Com a carga centrada, a frente recebe exatamente metade do peso."),
        Passo("Reação vertical total nas pernas traseiras (ΣFy = 0)", "R_T,tot = P − R_D,tot",
              f"{_f(r.P, 1)} − {_f(r.R_D_total, 1)}", f"{_f(r.R_T_total, 1)} N",
              latex=r"R_{T,\mathrm{tot}} = P - R_{D,\mathrm{tot}}",
              explicacao="A soma das forças verticais deve ser nula: o piso devolve toda a carga P.",
              variaveis=[("R_T,tot", "soma das reações verticais nas duas pernas traseiras [N]")]),
        Passo("Reação em cada perna dianteira", "R_D = R_D,tot / 2", f"{_f(r.R_D_total, 1)} / 2",
              f"{_f(r.R_D, 1)} N", latex=r"R_D = \dfrac{R_{D,\mathrm{tot}}}{2}",
              explicacao="Por simetria lateral, as duas pernas dianteiras dividem igualmente a reação."),
        Passo("Reação em cada perna traseira", "R_T = R_T,tot / 2", f"{_f(r.R_T_total, 1)} / 2",
              f"{_f(r.R_T, 1)} N", latex=r"R_T = \dfrac{R_{T,\mathrm{tot}}}{2}",
              interpretacao=("As quatro pernas recebem a mesma reação, P/4. Todas as reações são "
                             "positivas (de compressão): os quatro pés permanecem apoiados.")),
        Passo("Reações horizontais no piso (ΣFx = 0)", "ΣH = 0", "sem forças horizontais aplicadas",
              "0 N", latex=r"\Sigma F_x = 0 \;\Rightarrow\; H = 0",
              explicacao=("Como o modelo não considera força horizontal no assento (atrito "
                          "desconsiderado), o piso não precisa exercer reações horizontais.")),
    ]))

    # ------------------------------------------------------------------ 6. Esforços internos
    memorial.append(EtapaMemorial("esforcos", "6. Esforços internos solicitantes", (
        "Esforços internos são as forças e momentos que uma parte da peça transmite à outra em "
        "uma seção qualquer. São obtidos pelo método das seções: corta-se a peça e aplica-se o "
        "equilíbrio ao trecho isolado."), [
        Passo("Perna — esforço normal (compressão)", "N = máx(R_D, R_T)",
              f"máx({_f(r.R_D, 1)}; {_f(r.R_T, 1)})", f"{_f(r.N_perna, 1)} N (compressão)",
              latex=r"N = \max(R_D,\; R_T)",
              explicacao=("Cortando a perna em qualquer altura, a parte inferior só está sujeita à "
                          "reação vertical do piso; logo o esforço normal é constante e de "
                          "compressão."),
              variaveis=[("N", "esforço normal na perna [N]"),
                         ("R_D, R_T", "reações em cada perna dianteira e traseira [N]")]),
        Passo("Perna — esforço cortante e momento fletor", "V = 0 ;  M = 0", "",
              "V = 0 N ; M = 0 N·m", latex=r"V = 0 \qquad M = 0",
              explicacao=("A perna não recebe nenhuma força transversal: a reação do piso é "
                          "vertical e alinhada com o eixo da perna, e a travessa bi-apoiada "
                          "transmite à perna apenas a reação vertical do apoio. Sem força "
                          "transversal e sem excentricidade, não há cortante nem momento."),
              interpretacao=("Excentricidade nula não elimina os momentos da estrutura: eles "
                             "continuam existindo na travessa (a seguir), onde a carga atua "
                             "transversalmente ao eixo da peça.")),
        Passo("Travessa — carga concentrada em cada travessa lateral", "Q = P / 2",
              f"{_f(r.P, 1)} / 2", f"{_f(r.Q_travessa, 1)} N", latex=r"Q = \dfrac{P}{2}",
              explicacao=("Cada uma das duas travessas laterais recebe metade da carga do usuário. "
                          "Concentrar a carga em um ponto é conservador: gera momento maior do que "
                          "uma carga distribuída de mesma resultante."),
              variaveis=[("Q", "carga em cada travessa [N]")]),
        Passo("Travessa — posição da carga (a partir do apoio traseiro)", "a = ℓ/2 + e",
              f"{_f(L_mm / 2, 1)} + {_f(e_mm, 0)} mm", f"{_f(r.a_carga * 1000, 1)} mm",
              latex=r"a = \dfrac{\ell}{2} + e",
              variaveis=[("a", "distância da carga ao apoio traseiro [mm]"),
                         ("b = ℓ − a", f"distância ao apoio dianteiro = {_f(b * 1000, 1)} mm")],
              interpretacao="Com e = 0 a carga fica exatamente no meio do vão."),
        Passo("Travessa — reações nos apoios (ΣM = 0 e ΣFy = 0)", "R_A = Q·(ℓ − a) / ℓ ;  R_B = Q − R_A",
              f"{_f(r.Q_travessa, 1)} · {_f(b * 1000, 1)} / {_f(L_mm, 0)}",
              f"R_A = {_f(r.R_A, 1)} N ; R_B = {_f(r.R_B, 1)} N",
              latex=r"R_A = \dfrac{Q\,(\ell-a)}{\ell} \qquad R_B = Q - R_A",
              explicacao="A travessa é uma viga bi-apoiada sobre as pernas; as reações saem do equilíbrio da viga.",
              variaveis=[("R_A", "reação no apoio traseiro da travessa [N]"),
                         ("R_B", "reação no apoio dianteiro da travessa [N]")]),
        Passo("Travessa — esforço cortante", "V = R_A (0 ≤ x < a);  V = R_A − Q (a < x ≤ ℓ)",
              f"{_f(r.R_A, 1)} N  |  {_f(r.R_A - r.Q_travessa, 1)} N",
              f"|V|máx = {_f(max(r.R_A, r.R_B), 1)} N",
              latex=r"V(x) = R_A \;\; (x<a) \qquad V(x) = R_A - Q \;\; (x>a)",
              explicacao="O cortante é constante em cada trecho e muda de sinal sob a carga concentrada.",
              interpretacao="O ponto em que o cortante troca de sinal coincide com o momento máximo."),
        Passo("Travessa — momento fletor máximo (sob a carga)", "M_máx = Q·a·b / ℓ = Q·ℓ / 4",
              f"{_f(r.Q_travessa, 1)} · {_f(L_mm, 0)} / 4",
              f"{_f(r.M_travessa, 3)} N·m", latex=r"M_{\mathrm{máx}} = \dfrac{Q\,a\,b}{\ell} = \dfrac{Q\,\ell}{4}",
              explicacao=("O momento é nulo nos apoios e cresce linearmente até o ponto de "
                          "aplicação da carga, onde atinge o valor máximo. Com a carga no meio "
                          "do vão (a = b = ℓ/2), a expressão geral reduz-se a Q·ℓ/4."),
              variaveis=[("M_máx", "momento fletor máximo na travessa [N·m]"),
                         ("a, b", "distâncias da carga aos apoios [mm]"), ("ℓ", "vão da travessa [mm]")],
              desenvolvimento=f"{_f(r.M_travessa * 1000, 1)} N·mm",
              interpretacao="Valor usado no cálculo da tensão de flexão da travessa."),
    ]))

    # ------------------------------------------------------------------ 7. Tensões normais
    memorial.append(EtapaMemorial("tensoes", "7. Tensões normais", (
        "A tensão normal σ é a força por unidade de área perpendicular à seção. Ela provém do "
        "esforço normal (σ = N/A) e do momento fletor (σ = M/W). Na perna atua apenas a "
        "compressão; na travessa atua a flexão."), [
        Passo("Perna — tensão normal devida ao esforço axial", "σ_N = N / A",
              f"{_f(r.N_perna, 1)} N / {_f(A_mm2, 1)} mm²", f"{mpa(r.sigma_axial)} MPa",
              latex=r"\sigma_N = \dfrac{N}{A}",
              explicacao="A compressão se distribui uniformemente na seção.",
              variaveis=[("σ_N", "tensão normal de compressão [MPa = N/mm²]"),
                         ("N", "esforço normal [N]"), ("A", "área da seção [mm²]")]),
        Passo("Perna — tensão normal máxima", "σ_máx = N/A + M/W",
              f"{mpa(r.sigma_axial)} + 0", f"{mpa(r.sigma_max_perna)} MPa",
              latex=r"\sigma_{\mathrm{máx}} = \dfrac{N}{A} + \dfrac{M}{W}",
              explicacao=("Expressão geral da tensão normal com esforço axial e momento fletor. "
                          "Como M = 0 na perna, a parcela de flexão é nula e a perna trabalha em "
                          "compressão simples."),
              variaveis=[("σ_máx", "tensão normal máxima (compressão) na perna [MPa]"),
                         ("M", "momento fletor na perna (= 0) [N·mm]"), ("W", "módulo resistente [mm³]")],
              interpretacao="Esta é a tensão máxima nas pernas exigida como saída pelo edital."),
        Passo("Travessa — tensão normal de flexão", "σ_t = M_máx / W",
              f"{_f(r.M_travessa * 1000, 1)} N·mm / {_f(Wt_mm3, 1)} mm³", f"{mpa(r.sigma_travessa)} MPa",
              latex=r"\sigma_t = \dfrac{M_{\mathrm{máx}}}{W} = \dfrac{M_{\mathrm{máx}}\,c}{I}",
              explicacao=("Pela fórmula da flexão, a tensão varia linearmente com a distância à "
                          "linha neutra: é nula no centro e máxima nas fibras extremas. A fibra "
                          "superior é comprimida e a inferior tracionada, com o mesmo valor."),
              variaveis=[("σ_t", "tensão máxima de flexão na travessa [MPa]"),
                         ("M_máx", "momento máximo na travessa [N·mm]"), ("W", "módulo resistente [mm³]")],
              interpretacao=("A travessa está mais solicitada que a perna."
                             if r.sigma_travessa > r.sigma_max_perna else
                             "A perna está mais solicitada que a travessa.")),
    ]))

    # ------------------------------------------------------------------ 8. Deformações
    razao = f"ℓ/{_f(L / r.delta_travessa, 0)}" if r.delta_travessa > 0 else "—"
    memorial.append(EtapaMemorial("deformacoes", "8. Deformações", (
        "Com o material em regime elástico-linear (Lei de Hooke), calculam-se a deformação "
        "específica (ε) e os deslocamentos das peças, usando o módulo de elasticidade do material "
        "selecionado. Esses valores indicam a rigidez da cadeira."), [
        Passo("Perna — deformação específica", "ε = σ_máx / E",
              f"{mpa(r.sigma_max_perna)} MPa / {_f(E_mpa, 0)} MPa", f"{_e(r.deformacao_perna)} "
              f"({_f(r.deformacao_perna * 1e6, 1)} με)", latex=r"\varepsilon = \dfrac{\sigma_{\mathrm{máx}}}{E}",
              explicacao="Variação relativa de comprimento da perna (adimensional).",
              variaveis=[("ε", "deformação específica [mm/mm]; 1 με = 10⁻⁶"), ("E", "módulo de elasticidade [MPa]")]),
        Passo("Perna — encurtamento axial", "δ_N = N·H / (E·A)",
              f"{_f(r.N_perna, 1)} · {_f(H_mm, 0)} / ({_f(E_mpa, 0)} · {_f(A_mm2, 1)})",
              f"{_f(r.delta_axial * 1000, 4)} mm", latex=r"\delta_N = \dfrac{N\,H}{E\,A}",
              explicacao="Encurtamento da perna provocado pela compressão.",
              variaveis=[("δ_N", "encurtamento da perna [mm]"), ("H", "comprimento da perna [mm]")]),
        Passo("Travessa — deformação específica máxima", "ε_t = σ_t / E",
              f"{mpa(r.sigma_travessa)} / {_f(E_mpa, 0)}",
              f"{_e(r.deformacao_travessa)} ({_f(r.deformacao_travessa * 1e6, 1)} με)",
              latex=r"\varepsilon_t = \dfrac{\sigma_t}{E}"),
        Passo("Travessa — flecha máxima (no meio do vão)", "δ = Q·ℓ³ / (48·E·I)",
              f"{_f(r.Q_travessa, 1)} · {_f(L_mm, 0)}³ / (48 · {_f(E_mpa, 0)} · {_f(It_mm4, 0)})",
              f"{_f(r.delta_travessa * 1000, 4)} mm",
              latex=r"\delta_{\mathrm{máx}} = \dfrac{Q\,\ell^3}{48\,E\,I}",
              explicacao=("Flecha máxima da viga bi-apoiada com carga concentrada no meio do vão, "
                          "obtida pela equação da linha elástica."),
              variaveis=[("δ_máx", "deslocamento vertical máximo da travessa [mm]"),
                         ("I", "momento de inércia da travessa [mm⁴]")],
              interpretacao=f"A flecha corresponde a {razao} do vão."),
    ]))

    # ------------------------------------------------------------------ 9. Verificação
    ok = lambda c: "ATENDE" if c else "NÃO ATENDE"  # noqa: E731
    memorial.append(EtapaMemorial("verificacao", "9. Verificação da resistência", (
        "Compara-se cada tensão atuante com a tensão admissível do material selecionado. A "
        "cadeira é considerada segura somente se as pernas e a travessa atenderem ao critério."), [
        Passo("Pernas: σ_máx ≤ σ_adm", f"{mpa(r.sigma_max_perna)} ≤ {_f(r.sigma_adm / 1e6, 2)} MPa",
              f"FS real = σ_lim / σ_máx = {_f(r.fs_perna, 2)}", ok(r.ok_perna),
              latex=r"\sigma_{\mathrm{máx}} \leq \sigma_{\mathrm{adm}}",
              interpretacao=f"Aproveitamento da tensão admissível: {_f(100 * r.sigma_max_perna / r.sigma_adm, 1)}%."),
        Passo("Travessa: σ_t ≤ σ_adm", f"{mpa(r.sigma_travessa)} ≤ {_f(r.sigma_adm / 1e6, 2)} MPa",
              f"FS real = σ_lim / σ_t = {_f(r.fs_travessa, 2)}", ok(r.ok_travessa),
              latex=r"\sigma_t \leq \sigma_{\mathrm{adm}}",
              interpretacao=f"Aproveitamento da tensão admissível: {_f(100 * r.sigma_travessa / r.sigma_adm, 1)}%."),
        Passo("Massa máxima admissível do usuário", "m_máx = m · FS_real,mín / FS",
              f"{_f(ent.massa_kg, 1)} · {_f(min(r.fs_perna, r.fs_travessa), 2)} / {_f(ent.fator_seguranca, 2)}",
              f"{_f(r.massa_maxima, 1)} kg",
              latex=r"m_{\mathrm{máx}} = m \cdot \dfrac{FS_{\mathrm{real,mín}}}{FS}",
              explicacao=("Como todas as tensões são proporcionais à carga, a massa que leva o "
                          "elemento crítico exatamente à tensão admissível é obtida por "
                          "proporção."),
              interpretacao=f"Elemento crítico: {r.elemento_critico.lower()}."),
        Passo("RESULTADO", resultado="CADEIRA SEGURA" if r.segura else "CADEIRA NÃO SEGURA"),
    ]))
    return memorial
