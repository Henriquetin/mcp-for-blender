"""Armário em módulos: laterais, base, tampo, rodapé, testeira, divisórias,
prateleiras por vão, gavetas internas e portas de correr.

Diferente do motor de caixa simples, aqui cada peça ganha o referencial a
partir da caixa no mundo e da direção da face interna (peca_auto), e as uniões
saem sozinhas: onde a borda de uma peça encosta na face de outra, entram
cavilhas (unir_por_contato).

Alturas dos vãos são as VISÍVEIS (como no desenho): o vão mais alto de cada
módulo continua atrás da testeira até o tampo.
"""

from __future__ import annotations

import math

from .modelo import Furo, Peca, Rasgo
from .parametros import exigir, numero_positivo
from .visual import caixa as vcaixa
from .visual import cilindro as vcil

TOL = 0.01
EIXOS = {"X": 0, "Y": 1, "Z": 2}
NOMES_DIR = {(0, -1): "esquerda", (0, 1): "direita", (1, -1): "frente", (1, 1): "tras",
             (2, -1): "baixo", (2, 1): "cima"}


class ErroArmario(ValueError):
    pass


# ------------------------------------------------------------ vetores simples

def _vet(eixo, sinal):
    v = [0, 0, 0]
    v[eixo] = sinal
    return tuple(v)


def _cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _eixo_sinal(v):
    for i in range(3):
        if v[i]:
            return i, (1 if v[i] > 0 else -1)
    raise ValueError(v)


def _cantos(caixa):
    x0, y0, z0, x1, y1, z1 = caixa
    return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]


def _parse_normal(s):
    sinal = -1 if s[0] == "-" else 1
    return _vet(EIXOS[s[-1].upper()], sinal)


# ------------------------------------------------------------ peça automática

def local(p: Peca, ponto):
    """Coordenadas (u, v) de um ponto do mundo no referencial da peça."""
    cu = min(_dot(c, p.eixo_u) for c in _cantos(p.caixa))
    cv = min(_dot(c, p.eixo_v) for c in _cantos(p.caixa))
    return _dot(ponto, p.eixo_u) - cu, _dot(ponto, p.eixo_v) - cv


def lado_para(p: Peca, eixo, sinal):
    """Lado local (u0/u1/v0/v1) cuja borda aponta para a direção do mundo (eixo, sinal)."""
    for nome, vetor, s in (("u0", p.eixo_u, -1), ("u1", p.eixo_u, 1), ("v0", p.eixo_v, -1), ("v1", p.eixo_v, 1)):
        e, sg = _eixo_sinal(vetor)
        if e == eixo and sg * s == sinal:
            return nome
    raise ValueError("lado não encontrado")


def peca_auto(funcao, funcao_cc, grupo, mat, espessura, caixa, normal_i, veio, fita=None, juntas=True,
              rasgo=None):
    """Monta a peça a partir da caixa no mundo.

    normal_i: direção da face interna, ex. "+X". veio: eixo do mundo ("X", "Y", "Z").
    fita: nome da fita para as 4 bordas (None = sem fita).
    rasgo: dict(lado=<"tras"|"baixo"|...>, largura, profundidade, distancia).
    """
    n = _parse_normal(normal_i)
    t, _ = _eixo_sinal(n)
    ext = [caixa[i + 3] - caixa[i] for i in range(3)]
    if abs(ext[t] - espessura) > TOL:
        raise ErroArmario(f"{funcao}: espessura {espessura} não bate com a caixa {ext}")
    v = _vet(2, 1) if t != 2 else _vet(1, 1)
    u = _cruz(tuple(-a for a in n), v)
    eu, _ = _eixo_sinal(u)
    ev, _ = _eixo_sinal(v)
    bordas = {}
    for nome, vetor, s in (("u0", u, -1), ("u1", u, 1), ("v0", v, -1), ("v1", v, 1)):
        e, sg = _eixo_sinal(vetor)
        bordas[nome] = NOMES_DIR[(e, sg * s)]
    eixo_veio = "u" if EIXOS[veio] == eu else "v"
    p = Peca(funcao, funcao_cc, grupo, mat["material"], mat["padrao"], espessura, ext[eu], ext[ev], eixo_veio,
             tuple(float(a) for a in caixa), bordas,
             {lado: fita for lado in bordas} if fita else {},
             eixo_u=u, eixo_v=v, normal_i=n, juntas=juntas)
    if rasgo:
        lado = next(k for k, val in bordas.items() if val == rasgo["lado"])
        p.rasgo = Rasgo(lado, rasgo["largura"], rasgo["profundidade"], rasgo["distancia"])
        p.vazios.append(_vazio_rasgo(p, lado))
    return p


def _vazio_rasgo(p: Peca, lado):
    """Caixa no mundo ocupada pelo rasgo (pode receber o fundo)."""
    r = p.rasgo
    t, sn = _eixo_sinal(p.normal_i)
    vetor = p.eixo_u if lado[0] == "u" else p.eixo_v
    e, sg = _eixo_sinal(vetor)
    sinal_borda = sg * (-1 if lado[1] == "0" else 1)  # direção para fora da borda
    lo, hi = list(p.caixa[:3]), list(p.caixa[3:])
    # na espessura: da face interna para dentro
    if sn > 0:
        lo[t] = hi[t] - r.profundidade
    else:
        hi[t] = lo[t] + r.profundidade
    # perpendicular à borda: de distancia até distancia + largura
    if sinal_borda > 0:
        borda = hi[e]
        lo[e], hi[e] = borda - r.distancia - r.largura, borda - r.distancia
    else:
        borda = lo[e]
        lo[e], hi[e] = borda + r.distancia, borda + r.distancia + r.largura
    return (*lo, *hi)


# --------------------------------------------------------------- uniões

def _posicoes(a, b, d, passo_max):
    if b - a <= 2 * d:
        return [(a + b) / 2]
    n = max(2, math.ceil((b - a - 2 * d) / passo_max) + 1)
    return [a + d + i * (b - a - 2 * d) / (n - 1) for i in range(n)]


def unir_por_contato(pecas, uniao):
    """Cavilha onde a borda de A encosta na face de B. Devolve a lista de juntas (para conferência)."""
    if uniao["tipo"] == "nenhuma":
        return []
    cav = uniao["cavilha"]
    d, passo = uniao["distancia_borda"], uniao["espacamento_max"]
    juntas = []
    for a in pecas:
        if not a.juntas or a.normal_i is None:
            continue
        ta, _ = _eixo_sinal(a.normal_i)
        for b in pecas:
            if b is a or not b.juntas or b.normal_i is None:
                continue
            k, sn_b = _eixo_sinal(b.normal_i)
            if k == ta:
                continue
            if abs(a.caixa[k] - b.caixa[k + 3]) < TOL:
                plano, dir_a = a.caixa[k], -1   # A está acima de B no eixo k
            elif abs(a.caixa[k + 3] - b.caixa[k]) < TOL:
                plano, dir_a = a.caixa[k + 3], 1
            else:
                continue
            m = 3 - k - ta
            lo_t, hi_t = max(a.caixa[ta], b.caixa[ta]), min(a.caixa[ta + 3], b.caixa[ta + 3])
            lo_m, hi_m = max(a.caixa[m], b.caixa[m]), min(a.caixa[m + 3], b.caixa[m + 3])
            if hi_t - lo_t < a.espessura - TOL or hi_m - lo_m <= TOL:
                continue
            lado_a = lado_para(a, k, dir_a)
            # face de B tocada: +k se A está acima (dir_a=-1)
            face_b = "i" if (-dir_a) == sn_b else "e"
            meio_t = (a.caixa[ta] + a.caixa[ta + 3]) / 2
            for pos in _posicoes(lo_m, hi_m, d, passo):
                ponto = [0, 0, 0]
                ponto[k], ponto[ta], ponto[m] = plano, meio_t, pos
                ua, va = local(a, ponto)
                ub, vb = local(b, ponto)
                a.furos.append(Furo("topo", cav["diametro"], cav["profundidade_topo"], lado=lado_a,
                                    pos=round(ua if lado_a[0] == "v" else va, 1),
                                    z=round(a.espessura / 2, 1), origem="cavilha"))
                b.furos.append(Furo("face", cav["diametro"], cav["profundidade_face"], u=round(ub, 1),
                                    v=round(vb, 1), face=face_b, origem="cavilha"))
            juntas.append((a.funcao, b.funcao))
    return juntas


# ---------------------------------------------------------------- motor

CAMPOS = ["movel", "largura", "altura", "profundidade", "espessura", "profundidade_interna",
          "materiais.externo.material", "materiais.externo.padrao", "materiais.interno.material",
          "materiais.interno.padrao", "fitas", "rodape.altura", "rodape.profundidade", "rodape.recuo_frontal",
          "testeira.altura", "fundo.material", "fundo.padrao", "fundo.espessura", "fundo.rasgo_largura",
          "fundo.rasgo_profundidade", "fundo.rasgo_distancia", "fundo.folga", "fundo.divisoes", "modulos",
          "portas_correr.quantidade", "portas_correr.transpasse", "portas_correr.folga_inferior",
          "portas_correr.folga_superior", "portas_correr.posicoes_y", "portas_correr.espessura",
          "uniao.tipo", "uniao.distancia_borda", "uniao.espacamento_max", "uniao.cavilha.diametro",
          "uniao.cavilha.profundidade_face", "uniao.cavilha.profundidade_topo"]


def _fita(params, mat):
    if params.get("fita_padrao", "todas") == "nenhuma":
        return None
    nome = params["fitas"].get(mat["material"])
    if not nome:
        raise ErroArmario(f"Sem fita definida para o material {mat['material']} (params.fitas).")
    return nome


def calcular(params: dict) -> tuple[list[Peca], dict]:
    exigir(params, CAMPOS)
    numero_positivo(params, ["largura", "altura", "profundidade", "espessura", "profundidade_interna"])
    if params["uniao"]["tipo"] not in ("cavilha", "nenhuma"):
        raise ErroArmario("No armário em módulos, uniao.tipo deve ser 'cavilha' ou 'nenhuma'.")
    L, A, P, e = params["largura"], params["altura"], params["profundidade"], params["espessura"]
    ext, intr = params["materiais"]["externo"], params["materiais"]["interno"]
    fext, fint = _fita(params, ext), _fita(params, intr)
    fu = params["fundo"]
    w, rp, d, fo, ef = (fu["rasgo_largura"], fu["rasgo_profundidade"], fu["rasgo_distancia"], fu["folga"],
                        fu["espessura"])
    rasgo = {"lado": "tras", "largura": w, "profundidade": rp, "distancia": d}
    hr, pr, rf = params["rodape"]["altura"], params["rodape"]["profundidade"], params["rodape"]["recuo_frontal"]
    T = params["testeira"]["altura"]
    if rf + pr > P:
        raise ErroArmario("Rodapé mais fundo que o armário.")

    pecas: list[Peca] = []
    ferragens: list[str] = []
    visuais: list[dict] = []
    z_base, z_tampo = hr, A - e          # base: z_base..z_base+e ; tampo: z_tampo..A
    z_int0, z_int1 = z_base + e, z_tampo  # vão interno total
    z_vis = z_tampo - T                   # topo visível (abaixo da testeira)
    y_fundo = P - d - w                   # frente do rasgo do fundo
    y_div0 = y_fundo - params["profundidade_interna"]
    if y_div0 < 0:
        raise ErroArmario("profundidade_interna maior que o espaço até o fundo.")

    # Caixa externa
    pecas.append(peca_auto("Lateral Esquerda", "Lateral", "externo", ext, e, (0, 0, 0, e, P, A), "+X", "Z",
                           fext, rasgo=rasgo))
    pecas.append(peca_auto("Lateral Direita", "Lateral", "externo", ext, e, (L - e, 0, 0, L, P, A), "-X", "Z",
                           fext, rasgo=rasgo))
    pecas.append(peca_auto("Base", "Base", "interno", intr, e, (e, 0, z_base, L - e, P, z_base + e), "+Z", "X",
                           fint, rasgo=rasgo))
    pecas.append(peca_auto("Tampo", "Tampo", "externo", ext, e, (e, 0, z_tampo, L - e, P, A), "-Z", "X",
                           fext, rasgo=rasgo))

    # Testeira e travessa do trilho superior
    pecas.append(peca_auto("Testeira", "Testeira", "externo", ext, e, (e, 0, z_vis, L - e, e, z_tampo), "+Y", "X",
                           fext))
    z_trav = z_vis - e
    pecas.append(peca_auto("Travessa Trilho Superior", "Travessa", "interno", intr, e,
                           (e, 0, z_trav, L - e, math.floor(y_div0), z_vis), "-Z", "X", fint))

    # Rodapé
    pecas.append(peca_auto("Rodape Frontal", "Rodape", "externo", ext, e, (e, rf, 0, L - e, rf + e, hr), "+Y", "X",
                           fext))
    pecas.append(peca_auto("Rodape Traseiro", "Rodape", "interno", intr, e,
                           (e, rf + pr - e, 0, L - e, rf + pr, hr), "-Y", "X", fint))

    # Módulos e divisórias
    mods = params["modulos"]
    n = len(mods)
    Wm = (L - 2 * e - (n - 1) * e) / n
    xs = [e + i * (Wm + e) for i in range(n)]
    for i in range(n - 1):
        x0 = xs[i] + Wm
        pecas.append(peca_auto(f"Divisoria {i + 1}", "Divisoria", "interno", intr, e,
                               (x0, y_div0, z_int0, x0 + e, y_fundo, z_int1), "+X", "Z", fint))
    for i in range(n):
        xc = xs[i] + Wm / 2
        pecas.append(peca_auto(f"Travessa Rodape {i + 1}", "Travessa Rodape", "interno", intr, e,
                               (xc - e / 2, rf + e, 0, xc + e / 2, rf + pr - e, hr), "+X", "Y", fint))

    gav = params.get("gavetas")
    for i, mod in enumerate(mods):
        x0, x1 = xs[i], xs[i] + Wm
        vaos = mod["vaos"]
        livres = [v for v in vaos if v.get("altura") in (None, "resto")]
        fixos = sum(v["altura"] for v in vaos if v not in livres)
        disponivel = (z_vis - z_int0) - (len(vaos) - 1) * e
        if len(livres) > 1:
            raise ErroArmario(f"Módulo {i + 1}: só um vão pode ter altura 'resto'.")
        resto = disponivel - fixos
        if livres:
            if resto < 100:
                raise ErroArmario(f"Módulo {i + 1}: vãos somam mais que a altura disponível ({disponivel:g} mm).")
        elif abs(resto) > 1:
            raise ErroArmario(f"Módulo {i + 1}: vãos somam {fixos:g} mm, disponível {disponivel:g} mm.")
        z = z_int0
        nome_mod = f"Modulo {i + 1}"
        for j, vao in enumerate(vaos):
            h = resto if vao in livres else vao["altura"]
            topo = z_int1 if j == len(vaos) - 1 else z + h
            tipo = vao["tipo"]
            if tipo == "cabideiro":
                ferragens.append(f"{nome_mod}: cabideiro (tubo) de {Wm:.0f} mm + 2 suportes")
                z_tubo = min(topo, z_vis) - 60 if j == len(vaos) - 1 else topo - 60
                yc = (y_div0 + y_fundo) / 2
                visuais.append(vcil("Cabideiros", "metal", (x0 + Wm / 2, yc, z_tubo), 0, 12.5, Wm))
                for xs_ in (x0, x1 - 25):
                    visuais.append(vcaixa("Cabideiros", "metal", (xs_, yc - 15, z_tubo - 15, xs_ + 25, yc + 15, z_tubo + 25)))
            if tipo == "gavetas":
                _gavetas(pecas, ferragens, params, gav, nome_mod, x0, x1, z, z + h, y_div0, y_fundo, vao["quantidade"],
                         visuais)
            if j < len(vaos) - 1:
                pecas.append(peca_auto(f"Prateleira {nome_mod} {j + 1}", "Prateleira", "interno", intr, e,
                                       (x0, y_div0, topo, x1, y_fundo, topo + e), "+Z", "X", fint))
                z = topo + e

    # Fundo em rasgo, dividido atrás das divisórias
    ndiv = int(fu["divisoes"])
    xs_corte = [0.0]
    for k in range(1, ndiv):
        alvo = L * k / ndiv
        dv = min(range(n - 1), key=lambda i: abs(xs[i] + Wm + e / 2 - alvo))
        xs_corte.append(xs[dv] + Wm + e / 2)
    xs_corte.append(float(L))
    exte = rp - fo
    fy0 = P - d - w / 2 - ef / 2
    for k in range(ndiv):
        a = e - exte if k == 0 else xs_corte[k] + 0.5
        b = L - e + exte if k == ndiv - 1 else xs_corte[k + 1] - 0.5
        pecas.append(peca_auto(f"Fundo {k + 1}" if ndiv > 1 else "Fundo", "Fundo", "fundo", fu, ef,
                               (a, fy0, z_int0 - exte, b, fy0 + ef, z_int1 + exte), "-Y", "Z", None, juntas=False))

    # Portas de correr (entre as laterais, abaixo da travessa)
    pc = params["portas_correr"]
    np_, tr, ep = int(pc["quantidade"]), pc["transpasse"], pc["espessura"]
    vao_l = L - 2 * e
    Wp = round((vao_l + (np_ - 1) * tr) / np_)
    zp0, zp1 = z_int0 + pc["folga_inferior"], z_trav - pc["folga_superior"]
    planos = pc["posicoes_y"]
    for k in range(np_):
        xp = e + k * (vao_l - Wp) / (np_ - 1) if np_ > 1 else e
        y0 = planos[k % len(planos)]
        if y0 + ep > y_div0:
            raise ErroArmario("Portas de correr batem nas divisórias: revise posicoes_y ou profundidade_interna.")
        pecas.append(peca_auto(f"Porta Correr {k + 1}", "Porta Correr", "externo", ext, ep,
                               (xp, y0, zp0, xp + Wp, y0 + ep, zp1), "+Y", "Z", fext, juntas=False))
    yt0, yt1 = min(planos) - 3, max(planos) + ep + 3
    visuais.append(vcaixa("Trilhos", "aluminio", (e, yt0, zp1 + 2, L - e, yt1, z_trav)))      # superior
    visuais.append(vcaixa("Trilhos", "aluminio", (e, yt0, z_int0, L - e, yt1, z_int0 + 6)))   # inferior
    for k in range(np_):
        xp = e + k * (vao_l - Wp) / (np_ - 1) if np_ > 1 else e
        yc = planos[k % len(planos)] + ep / 2
        for xr in (xp + 70, xp + Wp - 70):
            raio = (zp0 - z_int0 - 6) / 2
            visuais.append(vcil("Roldanas e Guias", "roldana", (xr, yc, z_int0 + 6 + raio), 1, raio, 10))
            visuais.append(vcaixa("Roldanas e Guias", "roldana", (xr - 15, yc - 5, zp1, xr + 15, yc + 5, zp1 + 14)))
    ferragens.append(f"Kit porta de correr: {np_} portas, 2 trilhos de {vao_l:g} mm (superior e inferior), "
                     f"transpasse real {(np_ * Wp - vao_l) / max(np_ - 1, 1):.1f} mm")

    juntas = unir_por_contato(pecas, params["uniao"])
    n_cav = sum(1 for p in pecas for f in p.furos if f.origem == "cavilha" and f.tipo == "topo")
    ferragens.append(f"Cavilhas Ø{params['uniao']['cavilha']['diametro']}: {n_cav} un.")
    return pecas, {"ferragens": ferragens, "juntas": len(juntas), "visuais": visuais}


def _gavetas(pecas, ferragens, params, gav, nome_mod, x0, x1, z0, z1, y_frente, y_fundo, n, visuais):
    exigir(params, ["gavetas.corredica.comprimento", "gavetas.corredica.desconto_largura_total", "gavetas.folga",
                    "gavetas.desconto_altura", "gavetas.material", "gavetas.espessura_caixa",
                    "gavetas.fundo.material", "gavetas.fundo.padrao", "gavetas.fundo.espessura",
                    "gavetas.fundo.rasgo_largura", "gavetas.fundo.rasgo_profundidade",
                    "gavetas.fundo.rasgo_distancia", "gavetas.fundo.folga"])
    e = params["espessura"]
    mat = params["materiais"][gav["material"]]
    fita = _fita(params, mat)
    f = gav["folga"]
    W = x1 - x0
    H = z1 - z0
    h = (H - (n + 1) * f) / n
    eg = gav["espessura_caixa"]
    Db = gav["corredica"]["comprimento"]
    Wb = W - gav["corredica"]["desconto_largura_total"]
    Hb = h - gav["desconto_altura"]
    gf = gav["fundo"]
    w, rp, d, fo, ef = gf["rasgo_largura"], gf["rasgo_profundidade"], gf["rasgo_distancia"], gf["folga"], gf["espessura"]
    yb0 = y_frente + e
    if yb0 + Db > y_fundo:
        raise ErroArmario(f"{nome_mod}: corrediça de {Db:g} mm não cabe (livre {y_fundo - yb0:.0f} mm).")
    rg = {"lado": "baixo", "largura": w, "profundidade": rp, "distancia": d}
    xb0 = x0 + (W - Wb) / 2
    xb1 = xb0 + Wb
    for k in range(n):
        num = n - k
        zf = z0 + f + k * (h + f)
        tag = f"{nome_mod} Gaveta {num}"
        pecas.append(peca_auto(f"Frente {tag}", "Frente Gaveta", "gavetas", mat, e,
                               (x0 + f, y_frente, zf, x1 - f, y_frente + e, zf + h), "+Y", "X", fita, juntas=False))
        zb = zf + gav["desconto_altura"] / 2
        yb1 = yb0 + Db
        # corrediças: entre a lateral da gaveta e a divisória, no meio da altura da caixa
        zc = zb + Hb / 2
        for xa, xb in ((x0, xb0), (xb1, x1)):
            visuais.append(vcaixa("Corrediças", "metal", (xa + 0.5, yb0, zc - 22.5, xb - 0.5, yb1, zc + 22.5)))
        pecas.append(peca_auto(f"Lateral Esquerda {tag}", "Lateral Gaveta", "gavetas", mat, eg,
                               (xb0, yb0, zb, xb0 + eg, yb1, zb + Hb), "+X", "Y", fita, rasgo=rg))
        pecas.append(peca_auto(f"Lateral Direita {tag}", "Lateral Gaveta", "gavetas", mat, eg,
                               (xb1 - eg, yb0, zb, xb1, yb1, zb + Hb), "-X", "Y", fita, rasgo=rg))
        pecas.append(peca_auto(f"Contra-frente {tag}", "Contra-frente Gaveta", "gavetas", mat, eg,
                               (xb0 + eg, yb0, zb, xb1 - eg, yb0 + eg, zb + Hb), "+Y", "X", fita, rasgo=rg))
        pecas.append(peca_auto(f"Traseira {tag}", "Traseira Gaveta", "gavetas", mat, eg,
                               (xb0 + eg, yb1 - eg, zb, xb1 - eg, yb1, zb + Hb), "-Y", "X", fita, rasgo=rg))
        ex = rp - fo
        zf0 = zb + d + (w - ef) / 2
        pecas.append(peca_auto(f"Fundo {tag}", "Fundo Gaveta", "gavetas.fundo", gf, ef,
                               (xb0 + eg - ex, yb0 + eg - ex, zf0, xb1 - eg + ex, yb1 - eg + ex, zf0 + ef), "+Z", "X",
                               None, juntas=False))
    ferragens.append(f"{nome_mod}: {n} pares de corrediça {Db:g} mm")
