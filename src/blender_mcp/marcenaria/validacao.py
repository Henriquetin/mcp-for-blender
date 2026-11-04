"""Checklist de validação antes de exportar.

Cada item volta como {"item", "status", "detalhes"}; status é "ok", "aviso",
"erro" ou "pendente" (não deu para conferir, ex.: sem catálogo).
"""

from __future__ import annotations

import difflib
import itertools
import json
import math
import os
from pathlib import Path

from . import cortecloud
from .modelo import Peca

TOL = 0.01  # mm

CATALOGO_ENV = "MARCENARIA_CATALOGO"


def carregar_catalogo(catalogo=None):
    """Aceita dict, caminho de arquivo JSON, ou usa a variável MARCENARIA_CATALOGO."""
    if isinstance(catalogo, dict):
        return catalogo
    caminho = catalogo or os.environ.get(CATALOGO_ENV)
    if not caminho:
        return None
    return json.loads(Path(caminho).expanduser().read_text(encoding="utf-8"))


def _item(nome, status, detalhes=None):
    return {"item": nome, "status": status, "detalhes": detalhes or []}


def _intersecao(a, b):
    lo = [max(a[i], b[i]) for i in range(3)]
    hi = [min(a[i + 3], b[i + 3]) for i in range(3)]
    if all(hi[i] - lo[i] > TOL for i in range(3)):
        return (*lo, *hi)
    return None


def _contida(inter, caixa):
    return all(inter[i] >= caixa[i] - TOL and inter[i + 3] <= caixa[i + 3] + TOL for i in range(3))


def sobreposicoes(pecas: list[Peca]):
    """Pares de peças cujo volume se cruza fora de um rasgo previsto."""
    problemas = []
    for a, b in itertools.combinations(pecas, 2):
        inter = _intersecao(a.caixa, b.caixa)
        if inter is None:
            continue
        if any(_contida(inter, v) for v in a.vazios + b.vazios):
            continue
        dims = " x ".join(f"{inter[i + 3] - inter[i]:.1f}" for i in range(3))
        problemas.append(f"{a.funcao} x {b.funcao}: {dims} mm")
    return problemas


def _furos_fora(p: Peca):
    erros = []
    for f in p.furos:
        r = f.diametro / 2
        if f.tipo == "face":
            if f.u - r < -TOL or f.u + r > p.U + TOL or f.v - r < -TOL or f.v + r > p.V + TOL:
                erros.append(f"{p.funcao}: furo Ø{f.diametro:g} ({f.origem}) em u={f.u:g}, v={f.v:g} sai da peça")
            if not f.passante and f.profundidade >= p.espessura - TOL:
                erros.append(f"{p.funcao}: furo Ø{f.diametro:g} ({f.origem}) com {f.profundidade:g} mm "
                             f"atravessa a chapa de {p.espessura:g} mm")
        else:
            comprimento = p.U if f.lado in ("v0", "v1") else p.V
            alcance = p.V if f.lado in ("v0", "v1") else p.U
            if f.pos - r < -TOL or f.pos + r > comprimento + TOL:
                erros.append(f"{p.funcao}: furo de topo ({f.origem}) em {f.pos:g} mm sai da borda")
            if f.z - r < -TOL or f.z + r > p.espessura + TOL:
                erros.append(f"{p.funcao}: furo de topo Ø{f.diametro:g} não cabe na espessura {p.espessura:g}")
            if f.profundidade > alcance + TOL:
                erros.append(f"{p.funcao}: furo de topo com {f.profundidade:g} mm atravessa a peça")
    faces = [f for f in p.furos if f.tipo == "face" and not f.passante]
    for a, b in itertools.combinations(faces, 2):
        if a.face != b.face and math.hypot(a.u - b.u, a.v - b.v) < (a.diametro + b.diametro) / 2 \
                and a.profundidade + b.profundidade >= p.espessura - TOL:
            erros.append(f"{p.funcao}: furos das duas faces se encontram em u={a.u:g}, v={a.v:g} "
                         f"({a.origem} x {b.origem})")
    if p.rasgo:
        alcance = p.V if p.rasgo.lado in ("v0", "v1") else p.U
        if p.rasgo.distancia + p.rasgo.largura > alcance + TOL:
            erros.append(f"{p.funcao}: rasgo sai da peça")
        if p.rasgo.profundidade >= p.espessura:
            erros.append(f"{p.funcao}: rasgo atravessa a chapa")
    return erros


def folgas_reais(pecas: list[Peca], params: dict):
    """Folgas medidas nas caixas já arredondadas, comparadas com as nominais."""
    frentes = [p for p in pecas if p.grupo_material in ("portas", "gavetas.frente")]
    if not frentes:
        return None
    cfg = params.get("portas") if frentes[0].grupo_material == "portas" else params.get("gavetas")
    fp, fe = cfg["folga_perimetro"], cfg["folga_entre"]
    L, A = params["largura"], params["altura"]
    eixo = 0 if frentes[0].grupo_material == "portas" else 2
    frentes.sort(key=lambda p: p.caixa[eixo])
    medidas = []  # (descrição, real, nominal)
    for p in frentes:
        medidas += [(f"{p.funcao} esquerda", p.caixa[0], fp) if eixo == 2 or p is frentes[0] else None,
                    (f"{p.funcao} direita", L - p.caixa[3], fp) if eixo == 2 or p is frentes[-1] else None,
                    (f"{p.funcao} embaixo", p.caixa[2], fp) if eixo == 0 or p is frentes[0] else None,
                    (f"{p.funcao} em cima", A - p.caixa[5], fp) if eixo == 0 or p is frentes[-1] else None]
    for a, b in itertools.pairwise(frentes):
        medidas.append((f"entre {a.funcao} e {b.funcao}", b.caixa[eixo] - a.caixa[eixo + 3], fe))
    det, status = [], "ok"
    for m in medidas:
        if m is None:
            continue
        nome, real, nominal = m
        if real < -TOL:
            det.append(f"{nome}: invade {abs(real):.2f} mm")
            status = "erro"
        elif abs(real - nominal) > 0.1:
            det.append(f"{nome}: {real:.2f} mm (nominal {nominal:g})")
            if status == "ok":
                status = "aviso"
    return det, status


def _sugestao(nome, opcoes):
    perto = difflib.get_close_matches(nome, opcoes, n=1, cutoff=0.5)
    return f" (você quis dizer '{perto[0]}'?)" if perto else ""


def validar(pecas: list[Peca], params: dict, catalogo=None) -> list[dict]:
    cat = carregar_catalogo(catalogo if catalogo is not None else params.get("catalogo"))
    movel = params.get("movel", "")
    convertidas = [cortecloud.peca_para_cortecloud(p, movel) for p in pecas]
    itens = []

    # 1. Arredondamento
    contagem: dict = {}
    for (parte, info) in convertidas:
        for eixo, bruto, final in (("c", info["c_bruto"], parte["c"]), ("l", info["l_bruto"], parte["l"])):
            if abs(bruto - round(bruto)) > 1e-9:
                chave = (parte["function"], eixo, round(bruto, 2), final)
                contagem[chave] = contagem.get(chave, 0) + 1
    arred = [f"{n}x {func}: {eixo} {bruto:.2f} -> {final}" for (func, eixo, bruto, final), n in contagem.items()]
    itens.append(_item("Medidas inteiras com round() (nunca ceil)", "aviso" if arred else "ok", arred))

    # 2. Espessuras do catálogo
    espessuras = sorted({p.espessura for p in pecas})
    if cat:
        validas = set(cat.get("espessuras") or []) | {m["espessura"] for m in cat.get("materiais", [])}
        fora = [f"{e:g} mm" for e in espessuras if e not in validas]
        itens.append(_item("Espessuras existentes no catálogo", "erro" if fora else "ok",
                           [f"Fora do catálogo: {', '.join(fora)}"] if fora else []))
    else:
        itens.append(_item("Espessuras existentes no catálogo", "pendente",
                           [f"Sem catálogo. Espessuras usadas: {', '.join(f'{e:g}' for e in espessuras)} mm"]))

    # 3. Peça x chapa
    chapa = dict((cat or {}).get("chapa") or {})
    chapa.update({k: v for k, v in (params.get("chapa") or {}).items() if v is not None})
    if chapa.get("c") and chapa.get("l"):
        refilo = chapa.get("refilo") or 0
        C, Lc = chapa["c"] - 2 * refilo, chapa["l"] - 2 * refilo
        grandes = []
        for p, (parte, _) in zip(pecas, convertidas):
            c, l = parte["c"], parte["l"]
            cabe = (c <= C and l <= Lc) or (p.padrao != "amadeirado" and l <= C and c <= Lc)
            if not cabe:
                grandes.append(f"{p.funcao}: {c} x {l} (chapa útil {C:g} x {Lc:g})")
        itens.append(_item(f"Nenhuma peça maior que a chapa {chapa['c']} x {chapa['l']}",
                           "erro" if grandes else "ok", grandes))
    else:
        itens.append(_item("Nenhuma peça maior que a chapa", "pendente", ["Informe chapa.c e chapa.l"]))

    # 4. Sobreposição
    sob = sobreposicoes(pecas)
    itens.append(_item("Nenhuma sobreposição de volume entre peças", "erro" if sob else "ok", sob))

    # 5. Nomes de materiais e fitas
    materiais = sorted({(p.material, p.espessura) for p in pecas})
    fitas = sorted({n for p in pecas for n in p.fitas.values()})
    if cat:
        nomes_mat = {m["nome"]: m for m in cat.get("materiais", [])}
        nomes_fita = list(cat.get("fitas", []))
        det, status = [], "ok"
        for nome, esp in materiais:
            m = nomes_mat.get(nome)
            if not m:
                det.append(f"Material '{nome}' não está no catálogo{_sugestao(nome, list(nomes_mat))}")
                status = "erro"
            elif m.get("espessura") is not None and m["espessura"] != esp:
                det.append(f"Material '{nome}' é {m['espessura']} mm no catálogo, mas a peça usa {esp:g} mm")
                status = "erro"
        for nome in fitas:
            if nome not in nomes_fita:
                det.append(f"Fita '{nome}' não está no catálogo{_sugestao(nome, nomes_fita)}")
                status = "erro"
        for p in pecas:
            m = nomes_mat.get(p.material)
            if m and m.get("padrao") and m["padrao"] != p.padrao:
                det.append(f"{p.funcao}: catálogo diz '{m['padrao']}', params dizem '{p.padrao}'")
                status = "erro"
        itens.append(_item("Materiais e fitas com nomes exatos do catálogo", status, det))
    else:
        itens.append(_item("Materiais e fitas com nomes exatos do catálogo", "pendente",
                           ["Sem catálogo. Usados: " + "; ".join(n for n, _ in materiais) +
                            (" | fitas: " + "; ".join(fitas) if fitas else "")]))

    # 6. Furações dentro da peça
    fora = [e for p in pecas for e in _furos_fora(p)]
    itens.append(_item("Furações dentro dos limites da peça", "erro" if fora else "ok", fora))

    # Extra: folgas reais de portas e frentes depois do arredondamento
    folgas = folgas_reais(pecas, params)
    if folgas is not None:
        det, status = folgas
        itens.append(_item("Folgas reais de portas/frentes após arredondamento", status, det))

    # Extra: veio e rasgo no C2
    av = [a for _, info in convertidas for a in info["avisos"]]
    er = [e for _, info in convertidas for e in info["erros"]]
    itens.append(_item("Veio e rasgo em C2", "erro" if er else ("aviso" if av else "ok"), er + av))
    return itens


def resumo(itens) -> str:
    simbolo = {"ok": "[x]", "aviso": "[!]", "erro": "[ERRO]", "pendente": "[?]"}
    linhas = []
    for it in itens:
        linhas.append(f"{simbolo[it['status']]} {it['item']}")
        linhas += [f"    - {d}" for d in it["detalhes"]]
    return "\n".join(linhas)


def bloqueios(itens, aceitar_pendentes=False):
    ruins = {"erro"} | (set() if aceitar_pendentes else {"pendente"})
    return [it for it in itens if it["status"] in ruins]
