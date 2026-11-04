"""Geometria só para visualização: furos, rasgos e ferragens.

Nada daqui entra na tabela de peças nem no JSON do CorteCloud. Cada item é
{"grupo", "material", "forma": "caixa", "caixa": [...]} ou
{"grupo", "material", "forma": "cilindro", "centro": [...], "eixo": 0|1|2, "raio", "comprimento"}.
O Blender junta cada grupo num objeto só, na subcoleção "Ferragens e Furos".
"""

from __future__ import annotations

from .modelo import Peca

SALIENCIA = 0.4  # mm para fora da face, para o furo aparecer como disco escuro


def caixa(grupo, material, caixa_mundo):
    return {"grupo": grupo, "material": material, "forma": "caixa", "caixa": [float(a) for a in caixa_mundo]}


def cilindro(grupo, material, centro, eixo, raio, comprimento):
    return {"grupo": grupo, "material": material, "forma": "cilindro", "centro": [float(a) for a in centro],
            "eixo": eixo, "raio": float(raio), "comprimento": float(comprimento)}


def _eixo(v):
    for i in range(3):
        if v[i]:
            return i, (1 if v[i] > 0 else -1)
    raise ValueError(v)


def _coord(p: Peca, vetor, valor):
    """Coordenada do mundo, no eixo de `vetor`, de uma posição local (u ou v)."""
    e, s = _eixo(vetor)
    return e, (p.caixa[e] + valor) if s > 0 else (p.caixa[e + 3] - valor)


def furos(p: Peca, movel: str = "") -> list[dict]:
    """Furos e rasgos da peça, num grupo próprio ("Furos - <função>") preso à peça no Blender."""
    itens = _furos(p)
    for it in itens:
        it["grupo"] = f"Furos - {p.funcao}"
        it["pai"] = f"{p.funcao} - {movel}"
    return itens


def _furos(p: Peca) -> list[dict]:
    if p.normal_i is None:
        return []  # peças do motor de caixa simples não guardam o referencial no mundo
    t, sn = _eixo(p.normal_i)
    face_i = p.caixa[t + 3] if sn > 0 else p.caixa[t]
    face_e = p.caixa[t] if sn > 0 else p.caixa[t + 3]
    saida = []
    for f in p.furos:
        r = f.diametro / 2
        centro = [0.0, 0.0, 0.0]
        if f.tipo == "face":
            eu, cu = _coord(p, p.eixo_u, f.u)
            ev, cv = _coord(p, p.eixo_v, f.v)
            centro[eu], centro[ev] = cu, cv
            plano = face_i if f.face == "i" else face_e
            para_dentro = -sn if f.face == "i" else sn
            prof = p.espessura if f.passante else f.profundidade
            centro[t] = plano + para_dentro * (prof - SALIENCIA) / 2
            saida.append(cilindro("Furos", "furo", centro, t, r, prof + SALIENCIA))
        else:
            vetor_borda = p.eixo_u if f.lado[0] == "u" else p.eixo_v
            vetor_ao_longo = p.eixo_v if f.lado[0] == "u" else p.eixo_u
            eb, sb = _eixo(vetor_borda)
            noze = f.lado[1] == "0"
            borda = (p.caixa[eb] if sb > 0 else p.caixa[eb + 3]) if noze else \
                    (p.caixa[eb + 3] if sb > 0 else p.caixa[eb])
            para_dentro = (sb if noze else -sb)
            ea, ca = _coord(p, vetor_ao_longo, f.pos)
            centro[ea] = ca
            centro[t] = face_i - sn * f.z
            centro[eb] = borda + para_dentro * (f.profundidade - SALIENCIA) / 2
            saida.append(cilindro("Furos", "furo", centro, eb, r, f.profundidade + SALIENCIA))
    for v in p.vazios:
        saida.append(caixa("Rasgos", "furo", v))
    return saida


def todos(pecas: list[Peca], ferragens: list[dict] | None = None, movel: str = "") -> list[dict]:
    itens = [i for p in pecas for i in furos(p, movel)]
    return itens + list(ferragens or [])
