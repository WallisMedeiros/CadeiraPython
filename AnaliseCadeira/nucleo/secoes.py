"""Características geométricas das seções transversais das pernas/travessas.

As dimensões são recebidas em milímetros e as grandezas devolvidas em SI
(m, m², m³, m⁴).

Convenção: o plano de flexão é o plano vertical da vista lateral da cadeira.
`h` é a dimensão da seção nesse plano (altura) e `b` a dimensão perpendicular.
`I` é o momento de inércia em relação ao eixo de flexão e `I_min` o menor
momento de inércia (usado na flambagem).
"""
from dataclasses import dataclass
import math

TIPOS_SECAO = [
    "Quadrada maciça",
    "Retangular maciça",
    "Circular maciça",
    "Tubo quadrado",
    "Tubo retangular",
    "Tubo circular",
]

TUBOS = {"Tubo quadrado", "Tubo retangular", "Tubo circular"}
COM_ALTURA = {"Retangular maciça", "Tubo retangular"}


@dataclass(frozen=True)
class Secao:
    tipo: str
    b_mm: float             # lado/largura ou diâmetro externo
    h_mm: float             # altura no plano de flexão
    t_mm: float             # parede (tubos)
    A: float                # área [m²]
    I: float                # inércia em relação ao eixo de flexão [m⁴]
    I_min: float            # menor inércia [m⁴]
    c: float                # distância da linha neutra à fibra extrema [m]

    @property
    def W(self) -> float:   # módulo de resistência à flexão [m³]
        return self.I / self.c

    @property
    def r(self) -> float:   # raio de giração mínimo [m]
        return math.sqrt(self.I_min / self.A)

    def descricao(self) -> str:
        b, h, t = (f"{v:g}".replace(".", ",") for v in (self.b_mm, self.h_mm, self.t_mm))
        return {
            "Quadrada maciça": f"Quadrada maciça {b} × {b} mm",
            "Retangular maciça": f"Retangular maciça {b} × {h} mm (b × h)",
            "Circular maciça": f"Circular maciça Ø{b} mm",
            "Tubo quadrado": f"Tubo quadrado {b} × {b} × {t} mm",
            "Tubo retangular": f"Tubo retangular {b} × {h} × {t} mm",
            "Tubo circular": f"Tubo circular Ø{b} × {t} mm",
        }[self.tipo]

    def formulas(self) -> list[str]:
        """[área, inércia, c, W] em texto para o memorial."""
        return {
            "Quadrada maciça": ["A = a²", "I = a⁴ / 12", "c = a / 2", "W = I / c = a³ / 6"],
            "Retangular maciça": ["A = b·h", "I = b·h³ / 12", "c = h / 2", "W = I / c = b·h² / 6"],
            "Circular maciça": ["A = π·d² / 4", "I = π·d⁴ / 64", "c = d / 2", "W = I / c = π·d³ / 32"],
            "Tubo quadrado": ["A = a² − (a − 2t)²", "I = [a⁴ − (a − 2t)⁴] / 12", "c = a / 2", "W = I / c"],
            "Tubo retangular": ["A = b·h − (b − 2t)(h − 2t)", "I = [b·h³ − (b − 2t)(h − 2t)³] / 12",
                                "c = h / 2", "W = I / c"],
            "Tubo circular": ["A = π·(D² − d²) / 4,  d = D − 2t", "I = π·(D⁴ − d⁴) / 64",
                              "c = D / 2", "W = I / c"],
        }[self.tipo]


def criar_secao(tipo: str, b_mm: float, t_mm: float = 0.0, h_mm: float | None = None) -> Secao:
    """Cria a seção.  `b_mm` = lado/diâmetro/largura; `h_mm` = altura (retangulares)."""
    if tipo not in TIPOS_SECAO:
        raise ValueError(f"Tipo de seção desconhecido: {tipo}")
    if b_mm <= 0:
        raise ValueError("A espessura/diâmetro da seção deve ser maior que zero.")
    if tipo in COM_ALTURA:
        if h_mm is None or h_mm <= 0:
            raise ValueError("Informe a altura h da seção retangular (maior que zero).")
    else:
        h_mm = b_mm
    if tipo not in TUBOS:
        t_mm = 0.0
    else:
        if t_mm <= 0:
            raise ValueError("Informe a espessura da parede do tubo (maior que zero).")
        if 2 * t_mm >= min(b_mm, h_mm):
            raise ValueError("A parede do tubo deve ser menor que metade da menor dimensão externa.")

    b, h, t = b_mm / 1000, h_mm / 1000, t_mm / 1000

    if tipo == "Quadrada maciça":
        I = b ** 4 / 12
        return Secao(tipo, b_mm, h_mm, 0, b ** 2, I, I, b / 2)
    if tipo == "Retangular maciça":
        return Secao(tipo, b_mm, h_mm, 0, b * h, b * h ** 3 / 12,
                     min(b * h ** 3, h * b ** 3) / 12, h / 2)
    if tipo == "Circular maciça":
        I = math.pi * b ** 4 / 64
        return Secao(tipo, b_mm, h_mm, 0, math.pi * b ** 2 / 4, I, I, b / 2)

    bi, hi = b - 2 * t, h - 2 * t
    if tipo == "Tubo quadrado":
        I = (b ** 4 - bi ** 4) / 12
        return Secao(tipo, b_mm, h_mm, t_mm, b ** 2 - bi ** 2, I, I, b / 2)
    if tipo == "Tubo retangular":
        I = (b * h ** 3 - bi * hi ** 3) / 12
        I2 = (h * b ** 3 - hi * bi ** 3) / 12
        return Secao(tipo, b_mm, h_mm, t_mm, b * h - bi * hi, I, min(I, I2), h / 2)
    # Tubo circular
    I = math.pi * (b ** 4 - bi ** 4) / 64
    return Secao(tipo, b_mm, h_mm, t_mm, math.pi * (b ** 2 - bi ** 2) / 4, I, I, b / 2)
