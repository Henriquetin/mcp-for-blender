"""Peças de um móvel em MDF, descritas sem depender do Blender.

Cada peça é uma caixa alinhada aos eixos do mundo (mm):
- X: largura, da esquerda para a direita
- Y: profundidade, da frente (y=0) para o fundo (+Y)
- Z: altura, do chão para cima

Furos e rasgos ficam no referencial próprio da peça (u, v), visto pela face
interna ("i"): u para a direita, v para cima. Os lados da peça são u0 (u=0),
u1 (u=U), v0 (v=0) e v1 (v=V). A conversão para C1/C2/L1/L2 do CorteCloud
acontece em cortecloud.py, que escolhe a rotação conforme o veio e o rasgo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LADOS = ("u0", "u1", "v0", "v1")


@dataclass
class Furo:
    """Furo na face interna (tipo "face") ou no topo/borda da peça (tipo "topo").

    face: centro em (u, v).
    topo: `lado` é a borda furada; `pos` é a posição ao longo dessa borda (em u
    para v0/v1, em v para u0/u1); `z` é a posição na espessura a partir da face
    interna.
    """

    tipo: str
    diametro: float
    profundidade: float
    u: float = 0.0
    v: float = 0.0
    lado: str | None = None
    pos: float = 0.0
    z: float = 0.0
    passante: bool = False
    face: str = "i"  # "i" (interna) ou "e" (externa; só furos de face)
    origem: str = ""  # "cavilha", "minifix-tambor", "caneco"... só para conferência


@dataclass
class Rasgo:
    lado: str
    largura: float
    profundidade: float
    distancia: float  # da borda `lado` até a borda mais próxima do rasgo


@dataclass
class Peca:
    funcao: str          # nome completo, ex.: "Lateral Esquerda"
    funcao_cc: str       # nome enviado ao CorteCloud, ex.: "Lateral"
    grupo_material: str  # chave em params ("caixa", "fundo", "portas"...)
    material: str
    padrao: str          # "unicolor" ou "amadeirado"
    espessura: float
    U: float
    V: float
    eixo_veio: str       # "u" ou "v": direção do veio desejada na peça
    caixa: tuple         # (x0, y0, z0, x1, y1, z1) em mm, no mundo
    bordas: dict         # lado -> descrição ("frente", "tras", "cima"...)
    fitas: dict = field(default_factory=dict)  # lado -> nome da fita
    furos: list = field(default_factory=list)
    rasgo: Rasgo | None = None
    vazios: list = field(default_factory=list)  # caixas do rasgo no mundo (podem receber outra peça)

    U_bruto: float = 0.0
    V_bruto: float = 0.0
    # Referencial no mundo (preenchido por armario.peca_auto); None nas peças do motor antigo.
    eixo_u: tuple | None = None
    eixo_v: tuple | None = None
    normal_i: tuple | None = None
    juntas: bool = True  # recebe/dá cavilhas quando encosta em outra peça

    def __post_init__(self):
        """Arredonda c/l com round() (nunca ceil) já na criação.

        Assim furos medidos a partir da borda oposta usam a medida que vai ser
        cortada. A caixa no mundo mantém o canto mínimo e passa a ter a medida
        arredondada.
        """
        self.U_bruto, self.V_bruto = float(self.U), float(self.V)
        U, V = round(self.U), round(self.V)
        ext = [self.caixa[i + 3] - self.caixa[i] for i in range(3)]
        eixo_esp = min(range(3), key=lambda i: abs(ext[i] - self.espessura))
        outros = [i for i in range(3) if i != eixo_esp]
        a, b = outros
        if abs(ext[a] - self.U_bruto) + abs(ext[b] - self.V_bruto) > abs(ext[b] - self.U_bruto) + abs(ext[a] - self.V_bruto):
            a, b = b, a
        nova = list(self.caixa)
        nova[a + 3] = nova[a] + U
        nova[b + 3] = nova[b] + V
        self.caixa = tuple(nova)
        self.U, self.V = U, V

    @property
    def nome_lado(self):
        return {v: k for k, v in self.bordas.items()}


def caixa_mundo(x0, y0, z0, x1, y1, z1):
    return tuple(float(a) for a in (min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1)))
