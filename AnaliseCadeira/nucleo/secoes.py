"""Características geométricas das seções transversais das pernas e travessas.

O software trabalha com QUATRO seções transversais:

* Quadrada maciça            — lado ``a``
* Circular maciça            — diâmetro ``d``
* Circular vazada (tubo)     — diâmetro externo ``D`` e diâmetro interno ``d``
* Quadrada vazada (tubo)     — lado externo ``B`` e lado interno ``b`` (concêntricos)

As dimensões são recebidas em milímetros e as grandezas devolvidas em SI
(m, m², m³, m⁴).  Todas as seções são duplamente simétricas, portanto o momento de
inércia é o mesmo para flexão em qualquer direção principal, e a fibra extrema fica
a meia dimensão externa da linha neutra (c = a/2, d/2, D/2 ou B/2).

    Quadrada maciça:  A = a²            I = a⁴/12            W = a³/6
    Circular maciça:  A = π·d²/4        I = π·d⁴/64          W = π·d³/32
    Circular vazada:  A = π(D² − d²)/4  I = π(D⁴ − d⁴)/64    W = π(D⁴ − d⁴)/(32·D)
    Quadrada vazada:  A = B² − b²       I = (B⁴ − b⁴)/12     W = (B⁴ − b⁴)/(6·B)
"""
from __future__ import annotations

from dataclasses import dataclass
import math

QUADRADA = "Quadrada maciça"
CIRCULAR = "Circular maciça"
CIRCULAR_VAZADA = "Circular vazada"
QUADRADA_VAZADA = "Quadrada vazada"

TIPOS_SECAO = [QUADRADA, CIRCULAR, CIRCULAR_VAZADA, QUADRADA_VAZADA]
VAZADAS = {CIRCULAR_VAZADA, QUADRADA_VAZADA}

# rótulos das dimensões de cada seção: externa (nome, símbolo) e interna (ou None)
DIMENSAO = {
    QUADRADA: (("Lado", "a"), None),
    CIRCULAR: (("Diâmetro", "d"), None),
    CIRCULAR_VAZADA: (("Diâmetro externo", "D"), ("Diâmetro interno", "d")),
    QUADRADA_VAZADA: (("Lado externo", "B"), ("Lado interno", "b")),
}


def _n(v: float) -> str:
    return f"{v:g}".replace(".", ",")


@dataclass(frozen=True)
class Secao:
    tipo: str
    externa_mm: float       # a, d, D ou B
    interna_mm: float       # d ou b (0 nas maciças)
    A: float                # área [m²]
    I: float                # momento de inércia em relação à linha neutra [m⁴]
    c: float                # distância da linha neutra à fibra extrema [m]

    @property
    def W(self) -> float:   # módulo de resistência à flexão [m³]
        return self.I / self.c

    @property
    def vazada(self) -> bool:
        return self.tipo in VAZADAS

    @property
    def simbolo(self) -> str:
        return DIMENSAO[self.tipo][0][1]

    @property
    def simbolo_interno(self) -> str:
        return DIMENSAO[self.tipo][1][1] if self.vazada else ""

    def variaveis(self) -> list[tuple[str, str]]:
        (ne, se), interna = DIMENSAO[self.tipo]
        v = [(se, f"{ne.lower()} da seção [mm]")]
        if interna:
            v.append((interna[1], f"{interna[0].lower()} da seção [mm]"))
        return v

    def descricao(self) -> str:
        e, i = _n(self.externa_mm), _n(self.interna_mm)
        return {
            QUADRADA: f"Quadrada maciça {e} × {e} mm",
            CIRCULAR: f"Circular maciça Ø{e} mm",
            CIRCULAR_VAZADA: f"Circular vazada Ø{e} × Ø{i} mm (ext. × int.)",
            QUADRADA_VAZADA: f"Quadrada vazada {e} × {e} mm, interno {i} × {i} mm",
        }[self.tipo]

    def dimensoes(self) -> str:
        """Dimensões utilizadas, com símbolos (texto para tabelas)."""
        (ne, se), interna = DIMENSAO[self.tipo]
        t = f"{se} = {_n(self.externa_mm)} mm"
        if interna:
            t += f"; {interna[1]} = {_n(self.interna_mm)} mm"
        return t

    def formulas(self) -> dict[str, tuple[str, str]]:
        """Fórmulas de A, I, c e W em texto simples e em mathtext (LaTeX)."""
        return {
            QUADRADA: {
                "A": ("A = a²", r"A = a^2"),
                "I": ("I = a⁴ / 12", r"I = \dfrac{a^4}{12}"),
                "c": ("c = a / 2", r"c = \dfrac{a}{2}"),
                "W": ("W = I / c = a³ / 6", r"W = \dfrac{I}{c} = \dfrac{a^3}{6}"),
            },
            CIRCULAR: {
                "A": ("A = π·d² / 4", r"A = \dfrac{\pi\, d^2}{4}"),
                "I": ("I = π·d⁴ / 64", r"I = \dfrac{\pi\, d^4}{64}"),
                "c": ("c = d / 2", r"c = \dfrac{d}{2}"),
                "W": ("W = I / c = π·d³ / 32", r"W = \dfrac{I}{c} = \dfrac{\pi\, d^3}{32}"),
            },
            CIRCULAR_VAZADA: {
                "A": ("A = π·(D² − d²) / 4", r"A = \dfrac{\pi\,(D^2 - d^2)}{4}"),
                "I": ("I = π·(D⁴ − d⁴) / 64", r"I = \dfrac{\pi\,(D^4 - d^4)}{64}"),
                "c": ("c = D / 2", r"c = \dfrac{D}{2}"),
                "W": ("W = I / c = π·(D⁴ − d⁴) / (32·D)",
                      r"W = \dfrac{I}{c} = \dfrac{\pi\,(D^4 - d^4)}{32\,D}"),
            },
            QUADRADA_VAZADA: {
                "A": ("A = B² − b²", r"A = B^2 - b^2"),
                "I": ("I = (B⁴ − b⁴) / 12", r"I = \dfrac{B^4 - b^4}{12}"),
                "c": ("c = B / 2", r"c = \dfrac{B}{2}"),
                "W": ("W = I / c = (B⁴ − b⁴) / (6·B)", r"W = \dfrac{I}{c} = \dfrac{B^4 - b^4}{6\,B}"),
            },
        }[self.tipo]

    def substituicoes(self) -> dict[str, str]:
        """Substituição numérica (em mm) de cada fórmula, para o memorial."""
        e, i = _n(self.externa_mm), _n(self.interna_mm)
        return {
            QUADRADA: {"A": f"{e}²", "I": f"{e}⁴ / 12", "c": f"{e} / 2", "W": f"{e}³ / 6"},
            CIRCULAR: {"A": f"π · {e}² / 4", "I": f"π · {e}⁴ / 64", "c": f"{e} / 2",
                       "W": f"π · {e}³ / 32"},
            CIRCULAR_VAZADA: {"A": f"π · ({e}² − {i}²) / 4", "I": f"π · ({e}⁴ − {i}⁴) / 64",
                              "c": f"{e} / 2", "W": f"π · ({e}⁴ − {i}⁴) / (32 · {e})"},
            QUADRADA_VAZADA: {"A": f"{e}² − {i}²", "I": f"({e}⁴ − {i}⁴) / 12", "c": f"{e} / 2",
                              "W": f"({e}⁴ − {i}⁴) / (6 · {e})"},
        }[self.tipo]


def validar_dimensoes(tipo: str, externa_mm: float, interna_mm: float, nome: str = "seção") -> list[str]:
    """Lista de erros de dimensão (vazia se válida)."""
    if tipo not in TIPOS_SECAO:
        return [f"Tipo de seção não disponível para a {nome}: {tipo}. Opções: {', '.join(TIPOS_SECAO)}."]
    (ne, _), interna = DIMENSAO[tipo]
    erros = []
    if externa_mm is None or externa_mm <= 0:
        erros.append(f"{ne} da {nome} deve ser maior que zero.")
    if interna:
        if interna_mm is None or interna_mm <= 0:
            erros.append(f"{interna[0]} da {nome} deve ser maior que zero.")
        elif externa_mm is not None and externa_mm > 0 and interna_mm >= externa_mm:
            erros.append(f"{interna[0]} da {nome} deve ser menor que o {ne.lower()}.")
    return erros


def criar_secao(tipo: str, externa_mm: float, interna_mm: float = 0.0) -> Secao:
    """Cria a seção a partir do tipo e das dimensões (mm).  `interna_mm` só nas vazadas."""
    erros = validar_dimensoes(tipo, externa_mm, interna_mm)
    if erros:
        raise ValueError("\n".join(erros))
    E = externa_mm / 1000
    if tipo not in VAZADAS:
        interna_mm = 0.0
    i = interna_mm / 1000
    if tipo == QUADRADA:
        return Secao(tipo, externa_mm, 0.0, A=E ** 2, I=E ** 4 / 12, c=E / 2)
    if tipo == CIRCULAR:
        return Secao(tipo, externa_mm, 0.0, A=math.pi * E ** 2 / 4, I=math.pi * E ** 4 / 64, c=E / 2)
    if tipo == CIRCULAR_VAZADA:
        return Secao(tipo, externa_mm, interna_mm, A=math.pi * (E ** 2 - i ** 2) / 4,
                     I=math.pi * (E ** 4 - i ** 4) / 64, c=E / 2)
    return Secao(tipo, externa_mm, interna_mm, A=E ** 2 - i ** 2, I=(E ** 4 - i ** 4) / 12, c=E / 2)
