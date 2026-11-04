"""Conversão das peças para o JSON de importação do CorteCloud.

Referência: https://cortecloud.com/api-docs/guias/json_import

Referencial adotado (CONFIRMAR NO PILOTO):
- Peça vista pela face interna "i"; X ao longo de c, Y ao longo de l.
- Canto 0 = (0, 0). Canto 1 = (c, 0). Canto 2 = (c, l). Canto 3 = (0, l).
- C1 é o lado y=0, C2 o lado y=l, L1 o lado x=0, L2 o lado x=c.
- Furos de face: sempre canto 0, x/y absolutos.
- Furos de topo: canto do lado furado (tabela CANTO_TOPO), x=0 em L1/L2, y=0 em C1/C2.
- Rasgo: sempre em C2; `distance` = da borda C2 até a borda mais próxima do rasgo.
Se a importação mostrar furos espelhados ou no lado errado, ajuste só as
tabelas abaixo; o resto do código não muda.
"""

from __future__ import annotations

import json

from .modelo import Peca

# lado do CorteCloud -> (canto, direção) para furos horizontais (de topo)
CANTO_TOPO = {
    "L1": (0, "XP"),
    "L2": (1, "XP"),
    "C1": (0, "YP"),
    "C2": (3, "YP"),
}

# rotação -> (lado local que vira C1, C2, L1, L2)
_ROTACOES = {
    0: {"v0": "C1", "v1": "C2", "u0": "L1", "u1": "L2"},
    180: {"v1": "C1", "v0": "C2", "u1": "L1", "u0": "L2"},
    90: {"u1": "C1", "u0": "C2", "v0": "L1", "v1": "L2"},
    270: {"u0": "C1", "u1": "C2", "v1": "L1", "v0": "L2"},
}


def _xy(rot, p: Peca, u, v):
    U, V = p.U, p.V
    return {0: (u, v), 180: (U - u, V - v), 90: (v, U - u), 270: (V - v, u)}[rot]


def orientar(p: Peca):
    """Escolhe a rotação: rasgo sempre em C2; c = veio (amadeirado) ou maior lado (unicolor).

    Devolve (rotacao, avisos, erros).
    """
    avisos, erros = [], []
    if p.padrao == "amadeirado":
        eixo_c = p.eixo_veio
    else:
        eixo_c = "u" if p.U >= p.V else "v"
    if p.rasgo:
        eixo_rasgo = "u" if p.rasgo.lado in ("v0", "v1") else "v"
        if eixo_rasgo != eixo_c:
            if p.padrao == "amadeirado":
                erros.append(f"{p.funcao}: o rasgo do fundo cai no lado L com o veio no comprimento. "
                             "Confirme com a central (startSide=1?) antes de enviar.")
            else:
                avisos.append(f"{p.funcao}: c ficou no lado menor para o rasgo ficar em C2.")
            eixo_c = eixo_rasgo
        if eixo_c == "u":
            rot = 0 if p.rasgo.lado == "v1" else 180
        else:
            rot = 90 if p.rasgo.lado == "u0" else 270
    else:
        rot = 0 if eixo_c == "u" else 90
    return rot, avisos, erros


def _num(x):
    x = round(float(x), 1)
    return int(x) if x == int(x) else x


def peca_para_cortecloud(p: Peca, complemento: str) -> tuple[dict, dict]:
    """Uma peça -> (parte do JSON sem quantity, info para conferência)."""
    rot, avisos, erros = orientar(p)
    mapa = _ROTACOES[rot]
    c_bruto, l_bruto = (p.U_bruto, p.V_bruto) if rot in (0, 180) else (p.V_bruto, p.U_bruto)
    c, l = (p.U, p.V) if rot in (0, 180) else (p.V, p.U)

    fitas = {"c1": None, "c2": None, "l1": None, "l2": None}
    for lado_local, nome in p.fitas.items():
        fitas[mapa[lado_local].lower()] = nome

    horizontais, verticais = [], []
    for f in p.furos:
        if f.tipo == "face":
            x, y = _xy(rot, p, f.u, f.v)
            verticais.append({"corner": 0, "bolthole": bool(f.passante), "x": _num(x), "y": _num(y),
                              "depth": _num(p.espessura if f.passante else f.profundidade),
                              "diameter": _num(f.diametro), "face": f.face})
        else:
            lado_cc = mapa[f.lado]
            # ponto na borda, em u/v locais
            if f.lado in ("v0", "v1"):
                u, v = f.pos, (0 if f.lado == "v0" else p.V)
            else:
                u, v = (0 if f.lado == "u0" else p.U), f.pos
            x, y = _xy(rot, p, u, v)
            canto, direcao = CANTO_TOPO[lado_cc]
            if lado_cc in ("L1", "L2"):
                cx, cy = 0, y
            else:
                cx, cy = x, 0
            horizontais.append({"corner": canto, "direction": direcao, "x": _num(cx), "y": _num(cy),
                                "z": _num(f.z), "depth": _num(f.profundidade), "diameter": _num(f.diametro),
                                "face": "i"})
    horizontais.sort(key=lambda d: (d["corner"], d["direction"], d["x"], d["y"]))
    verticais.sort(key=lambda d: (d["x"], d["y"], d["diameter"]))

    rasgo = None
    if p.rasgo:
        rasgo = {"face": "i", "depth": _num(p.rasgo.profundidade), "width": _num(p.rasgo.largura),
                 "distance": _num(p.rasgo.distancia)}

    parte = {
        "c": c, "l": l,
        "function": p.funcao_cc, "complement": complemento,
        **fitas,
        "material": p.material,
        "machining": {
            "x": c, "y": l, "z": _num(p.espessura), "startSide": 0,
            "horizontalDrills": horizontais,
            "verticalDrills": verticais,
            "furrowMachining": rasgo,
            "furrowMachiningPair": None,
        },
    }
    info = {
        "funcao": p.funcao, "rotacao": rot, "c_bruto": c_bruto, "l_bruto": l_bruto,
        "lado_c": "u" if rot in (0, 180) else "v",
        "sentido_veio": "c" if p.padrao == "amadeirado" else "livre",
        "avisos": avisos, "erros": erros,
    }
    return parte, info


def montar(pecas: list[Peca], movel: str) -> tuple[dict, list[dict]]:
    """JSON completo, com peças idênticas agrupadas em quantity."""
    grupos: dict[str, dict] = {}
    ordem = []
    infos = []
    for p in pecas:
        parte, info = peca_para_cortecloud(p, movel)
        infos.append(info)
        chave = json.dumps(parte, sort_keys=True, ensure_ascii=False)
        if chave not in grupos:
            grupos[chave] = {"quantity": 0, **parte, "_funcoes": []}
            ordem.append(chave)
        grupos[chave]["quantity"] += 1
        grupos[chave]["_funcoes"].append(p.funcao)
    parts = []
    for chave in ordem:
        g = dict(grupos[chave])
        g.pop("_funcoes")
        parts.append(g)
    return {"parts": parts}, infos


def agrupar_para_tabela(pecas: list[Peca], movel: str) -> list[dict]:
    """Mesma agregação do JSON, com as funções completas, para a tabela de conferência."""
    linhas: dict[str, dict] = {}
    ordem = []
    for p in pecas:
        parte, _info = peca_para_cortecloud(p, movel)
        chave = json.dumps(parte, sort_keys=True, ensure_ascii=False)
        if chave not in linhas:
            m = parte["machining"]
            n_fur = len(m["horizontalDrills"]) + len(m["verticalDrills"]) + (1 if m["furrowMachining"] else 0)
            linhas[chave] = {"qtd": 0, "funcoes": [], "c": parte["c"], "l": parte["l"], "espessura": m["z"],
                             "material": parte["material"],
                             "fitas": [parte["c1"], parte["c2"], parte["l1"], parte["l2"]], "furacoes": n_fur}
            ordem.append(chave)
        linhas[chave]["qtd"] += 1
        linhas[chave]["funcoes"].append(p.funcao)
    return [linhas[k] for k in ordem]
