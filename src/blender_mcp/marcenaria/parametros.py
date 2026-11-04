"""Parâmetros dos móveis: modelos para o briefing e checagem do que falta.

Regra: nada que muda medida de corte tem valor escondido. Os modelos trazem
valores sugeridos só para o briefing, marcados em `confirmar`; o cálculo exige
que cada campo esteja presente em params.
"""

from __future__ import annotations

import copy

TIPOS = ("caixa", "gaveteiro", "armario")

_FUNDO = {
    "tipo": "rasgo",
    "material": "Branco TX 6",
    "padrao": "unicolor",
    "espessura": 6,
    "rasgo_largura": 6.7,
    "rasgo_profundidade": 8,
    "rasgo_distancia": 15,
    "folga": 1,
}

_UNIAO = {
    "tipo": "cavilha",
    "distancia_borda": 37,
    "espacamento_max": 300,
    "cavilha": {"diametro": 8, "profundidade_face": 12, "profundidade_topo": 22},
    "minifix": None,
}

_EXEMPLO_MINIFIX = {
    "tambor_diametro": 15,
    "tambor_profundidade": 12.5,
    "tambor_distancia_borda": 34,
    "furo_topo_diametro": 8,
    "furo_topo_profundidade": 34,
    "pino_face_diametro": 5,
    "pino_face_profundidade": 11,
}

MODELOS = {
    "caixa": {
        "movel": "Nicho_Piloto",
        "tipo": "caixa",
        "largura": 600,
        "altura": 400,
        "profundidade": 300,
        "caixa": {"material": "Branco TX 15", "padrao": "unicolor", "espessura": 15},
        "fundo": _FUNDO,
        "fita": {"nome": "Branco TX 0.45", "padrao": "frente"},
        "uniao": _UNIAO,
        "prateleiras": {"quantidade": 1, "recuo_frontal": 0},
        "portas": None,
        "chapa": {"c": 2750, "l": 1840, "refilo": 0},
    },
    "gaveteiro": {
        "movel": "Gaveteiro_Piloto",
        "tipo": "gaveteiro",
        "largura": 450,
        "altura": 600,
        "profundidade": 450,
        "caixa": {"material": "Branco TX 15", "padrao": "unicolor", "espessura": 15},
        "fundo": _FUNDO,
        "fita": {"nome": "Branco TX 0.45", "padrao": "frente"},
        "uniao": _UNIAO,
        "gavetas": {
            "quantidade": 3,
            "frente": {"material": "Branco TX 15", "padrao": "unicolor", "espessura": 15},
            "folga_perimetro": 2,
            "folga_entre": 3,
            "corredica": {"comprimento": 400, "desconto_largura_total": 25},
            "caixa": {"material": "Branco TX 15", "padrao": "unicolor", "espessura": 15, "desconto_altura": 40},
            "fundo": {**_FUNDO, "rasgo_distancia": 10},
            "fita_caixa": False,
        },
        "chapa": {"c": 2750, "l": 1840, "refilo": 0},
    },
}

MODELOS["armario"] = {
    "movel": "Guarda_Roupa",
    "tipo": "armario",
    "largura": 2750,
    "altura": 2400,
    "profundidade": 500,
    "espessura": 18,
    "profundidade_interna": 420,
    "materiais": {
        "externo": {"material": "Freijó 18", "padrao": "amadeirado"},
        "interno": {"material": "Branco TX 18", "padrao": "unicolor"},
    },
    "fitas": {"Freijó 18": "Freijó 0.45", "Branco TX 18": "Branco TX 0.45"},
    "fita_padrao": "todas",
    "rodape": {"altura": 100, "profundidade": 400, "recuo_frontal": 50},
    "testeira": {"altura": 100},
    "fundo": {**_FUNDO, "divisoes": 2},
    "modulos": [
        {"vaos": [{"tipo": "sapateira", "altura": 185}, {"tipo": "gavetas", "quantidade": 4, "altura": 622},
                  {"tipo": "cabideiro", "altura": 905}, {"tipo": "maleiro", "altura": "resto"}]},
        {"vaos": [{"tipo": "cabideiro", "altura": "resto"}, {"tipo": "nicho", "altura": 295},
                  {"tipo": "nicho", "altura": 295}, {"tipo": "nicho", "altura": 295}, {"tipo": "nicho", "altura": 335}]},
        {"vaos": [{"tipo": "cabideiro", "altura": "resto"}, {"tipo": "maleiro", "altura": 365}]},
        {"vaos": [{"tipo": "sapateira", "altura": 185}, {"tipo": "gavetas", "quantidade": 4, "altura": 622},
                  {"tipo": "cabideiro", "altura": 905}, {"tipo": "maleiro", "altura": "resto"}]},
    ],
    "gavetas": {
        "material": "interno",
        "espessura_caixa": 18,
        "folga": 3,
        "desconto_altura": 40,
        "corredica": {"comprimento": 380, "desconto_largura_total": 25},
        "fundo": {**_FUNDO, "rasgo_distancia": 10},
    },
    "portas_correr": {
        "quantidade": 4,
        "espessura": 18,
        "transpasse": 20,
        "folga_inferior": 20,
        "folga_superior": 20,
        "posicoes_y": [5, 30],
    },
    "uniao": {"tipo": "cavilha", "distancia_borda": 37, "espacamento_max": 300,
              "cavilha": {"diametro": 8, "profundidade_face": 12, "profundidade_topo": 22}},
    "chapa": {"c": 2750, "l": 1840, "refilo": 0},
}

EXEMPLO_PORTAS = {
    "quantidade": 2,
    "material": "Branco TX 15",
    "padrao": "unicolor",
    "espessura": 15,
    "folga_perimetro": 2,
    "folga_entre": 3,
    "lado_dobradica": "esquerda",
    "dobradica": {
        "caneco_diametro": 35,
        "caneco_profundidade": 12,
        "distancia_centro_borda": 22.5,
        "distancia_extremidade": 100,
        "regra_quantidade": [[900, 2], [1600, 3], [2000, 4], [2400, 5]],
    },
}

# O que o briefing tem de confirmar com o usuário (muda medida de corte ou usinagem).
CONFIRMAR = {
    "caixa": [
        "largura/altura/profundidade externas",
        "caixa.material (nome exato do catálogo) e caixa.espessura",
        "fundo: tipo, espessura e rasgo_largura/profundidade/distancia/folga da central",
        "uniao: tipo e medidas da ficha da cavilha/minifix",
        "fita.nome (catálogo) e fita.padrao",
        "portas: folgas e ficha da dobradiça (se houver portas)",
        "chapa: c x l e refilo",
    ],
    "gaveteiro": [
        "largura/altura/profundidade externas",
        "caixa.material e espessura",
        "fundo e rasgo da central",
        "uniao: ficha da cavilha/minifix",
        "gavetas.corredica: comprimento e desconto_largura_total (ficha técnica)",
        "gavetas.caixa.desconto_altura e folgas das frentes",
        "fita.nome e padrao",
        "chapa: c x l e refilo",
    ],
    "armario": [
        "largura/altura/profundidade, espessura e profundidade_interna (divisórias)",
        "materiais externo/interno e fitas (nomes exatos do catálogo)",
        "rodapé (altura, profundidade, recuo) e testeira",
        "módulos: vãos de baixo para cima, altura visível; um vão por módulo pode ser 'resto'",
        "portas_correr: ficha do kit (transpasse, folgas dos trilhos, posições y dos trilhos)",
        "gavetas: corrediça (comprimento, desconto), folga e desconto_altura",
        "fundo em rasgo e em quantas partes",
        "uniao: cavilha (ficha)",
        "chapa: c x l e refilo",
    ],
}


def modelo(tipo: str) -> dict:
    if tipo not in MODELOS:
        raise ValueError(f"tipo deve ser um de {TIPOS}")
    return {
        "parametros": copy.deepcopy(MODELOS[tipo]),
        "confirmar": CONFIRMAR[tipo],
        "exemplo_portas": copy.deepcopy(EXEMPLO_PORTAS) if tipo == "caixa" else None,
        "exemplo_minifix": copy.deepcopy(_EXEMPLO_MINIFIX),
    }


class ParametrosFaltando(ValueError):
    def __init__(self, faltando):
        self.faltando = faltando
        super().__init__("Faltam parâmetros que mudam medida de corte: " + ", ".join(faltando))


def _get(d, caminho):
    atual = d
    for parte in caminho.split("."):
        if not isinstance(atual, dict) or parte not in atual or atual[parte] is None:
            return None
        atual = atual[parte]
    return atual


def exigir(params: dict, caminhos) -> None:
    faltando = [c for c in caminhos if _get(params, c) is None]
    if faltando:
        raise ParametrosFaltando(faltando)


def numero_positivo(params: dict, caminhos) -> None:
    ruins = []
    for c in caminhos:
        v = _get(params, c)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
            ruins.append(c)
    if ruins:
        raise ValueError("Devem ser números positivos (mm): " + ", ".join(ruins))
