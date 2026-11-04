"""Motor paramétrico: dicionário de parâmetros -> lista de peças.

Mudou a medida? Rode de novo. Nada aqui depende do Blender, então o cálculo,
a validação e a exportação funcionam mesmo com o Blender fechado.

Montagem adotada (a mesma para caixa e gaveteiro):
- laterais inteiras (altura total); base e tampo entre as laterais;
- fundo em rasgo nas laterais, base e tampo;
- prateleiras fixas entre as laterais, terminando antes do fundo;
- portas e frentes de gaveta sobrepostas, na frente da caixa (y < 0).
"""

from __future__ import annotations

import math

from .modelo import Furo, Peca, Rasgo, caixa_mundo
from .parametros import TIPOS, exigir, numero_positivo


class ErroProjeto(ValueError):
    """Medidas que não fecham (ex.: corrediça maior que a caixa)."""


# ---------------------------------------------------------------- utilidades

def _fitas_para(bordas: dict, lados_semanticos, nome_fita):
    if not nome_fita:
        return {}
    return {lado: nome_fita for lado, sentido in bordas.items() if sentido in lados_semanticos}


def _regras_fita(params):
    fita = params.get("fita") or {}
    padrao = fita.get("padrao", "frente")
    nome = fita.get("nome")
    if padrao not in ("frente", "frente_e_topo", "nenhuma"):
        raise ValueError("fita.padrao deve ser 'frente', 'frente_e_topo' ou 'nenhuma'")
    if padrao == "nenhuma":
        nome = None
    return nome, padrao


def _posicoes(inicio, fim, distancia, espacamento_max):
    primeiro, ultimo = inicio + distancia, fim - distancia
    vao = ultimo - primeiro
    if vao <= 0:
        raise ErroProjeto(
            f"Peça com {fim - inicio:g} mm não comporta furação a {distancia:g} mm de cada borda.")
    n = max(2, math.ceil(vao / espacamento_max) + 1)
    passo = vao / (n - 1)
    return [primeiro + i * passo for i in range(n)]


def _r1(x):
    return round(float(x), 1)


# ------------------------------------------------------------------- uniões

def _validar_uniao(params):
    uniao = params.get("uniao")
    exigir(params, ["uniao.tipo"])
    tipo = uniao["tipo"]
    if tipo == "nenhuma":
        return
    if tipo not in ("cavilha", "minifix"):
        raise ValueError("uniao.tipo deve ser 'cavilha', 'minifix' ou 'nenhuma'")
    exigir(params, ["uniao.distancia_borda", "uniao.espacamento_max"])
    if tipo == "cavilha":
        campos = ["uniao.cavilha.diametro", "uniao.cavilha.profundidade_face", "uniao.cavilha.profundidade_topo"]
    else:
        campos = [f"uniao.minifix.{c}" for c in (
            "tambor_diametro", "tambor_profundidade", "tambor_distancia_borda", "furo_topo_diametro",
            "furo_topo_profundidade", "pino_face_diametro", "pino_face_profundidade")]
    exigir(params, campos)
    numero_positivo(params, campos + ["uniao.distancia_borda", "uniao.espacamento_max"])


def _unir(params, painel: Peca, lado_painel: str, lateral: Peca, u_lateral, v_lateral):
    """Fura a junção painel (base/tampo/prateleira) -> lateral.

    `lado_painel` é a borda u0/u1 do painel encostada na lateral; a borda corre
    em v (profundidade). u_lateral(pos_v) dá o u da lateral para cada posição;
    v_lateral é a altura do centro do painel na lateral.
    """
    uniao = params["uniao"]
    tipo = uniao["tipo"]
    if tipo == "nenhuma":
        return
    posicoes = _posicoes(0, painel.V, uniao["distancia_borda"], uniao["espacamento_max"])
    meio = painel.espessura / 2
    cav = uniao.get("cavilha")
    mf = uniao.get("minifix")
    for i, pos in enumerate(posicoes):
        nas_pontas = i in (0, len(posicoes) - 1)
        usa_minifix = tipo == "minifix" and (nas_pontas or not cav)
        if usa_minifix:
            painel.furos.append(Furo("topo", mf["furo_topo_diametro"], mf["furo_topo_profundidade"],
                                     lado=lado_painel, pos=_r1(pos), z=_r1(meio), origem="minifix-haste"))
            dist = mf["tambor_distancia_borda"]
            u = dist if lado_painel == "u0" else painel.U - dist
            painel.furos.append(Furo("face", mf["tambor_diametro"], mf["tambor_profundidade"],
                                     u=_r1(u), v=_r1(pos), origem="minifix-tambor"))
            lateral.furos.append(Furo("face", mf["pino_face_diametro"], mf["pino_face_profundidade"],
                                      u=_r1(u_lateral(pos)), v=_r1(v_lateral), origem="minifix-pino"))
        else:
            painel.furos.append(Furo("topo", cav["diametro"], cav["profundidade_topo"],
                                     lado=lado_painel, pos=_r1(pos), z=_r1(meio), origem="cavilha"))
            lateral.furos.append(Furo("face", cav["diametro"], cav["profundidade_face"],
                                      u=_r1(u_lateral(pos)), v=_r1(v_lateral), origem="cavilha"))


# -------------------------------------------------------------------- caixa

def _caixa(params, pecas):
    """Laterais, base, tampo e fundo. Devolve dados para prateleiras/portas/gavetas."""
    L, A, P = params["largura"], params["altura"], params["profundidade"]
    cx = params["caixa"]
    e = cx["espessura"]
    mat, pad = cx["material"], cx["padrao"]
    fita_nome, fita_padrao = _regras_fita(params)
    frente = {"frente"} | ({"cima"} if fita_padrao == "frente_e_topo" else set())

    fundo = params["fundo"]
    tem_rasgo = fundo["tipo"] == "rasgo"
    if fundo["tipo"] not in ("rasgo", "nenhum"):
        raise ValueError("fundo.tipo deve ser 'rasgo' ou 'nenhum' (sobreposto ainda não suportado)")
    if tem_rasgo:
        w, rp, d, f, ef = (fundo["rasgo_largura"], fundo["rasgo_profundidade"], fundo["rasgo_distancia"],
                           fundo["folga"], fundo["espessura"])
        if ef > w:
            raise ErroProjeto(f"Fundo de {ef} mm não entra no rasgo de {w} mm.")
        if rp >= e:
            raise ErroProjeto(f"Rasgo de {rp} mm de profundidade atravessa a chapa de {e} mm.")
        if f >= rp:
            raise ErroProjeto("fundo.folga tem de ser menor que a profundidade do rasgo.")
        rasgo = lambda lado: Rasgo(lado, w, rp, d)
        y_rasgo = (P - d - w, P - d)
        limite_y = P - d - w  # até onde peças internas podem ir sem bater no fundo
    else:
        rasgo = lambda lado: None
        limite_y = P

    def lateral(lado_mundo):
        esquerda = lado_mundo == "Esquerda"
        x0, x1 = (0, e) if esquerda else (L - e, L)
        bordas = ({"u0": "frente", "u1": "tras"} if esquerda else {"u0": "tras", "u1": "frente"})
        bordas.update({"v0": "baixo", "v1": "cima"})
        p = Peca(f"Lateral {lado_mundo}", "Lateral", "caixa", mat, pad, e, P, A, "v",
                 caixa_mundo(x0, 0, 0, x1, P, A), bordas, _fitas_para(bordas, frente, fita_nome))
        if tem_rasgo:
            p.rasgo = rasgo("u1" if esquerda else "u0")
            vx = (e - rp, e) if esquerda else (L - e, L - e + rp)
            p.vazios.append(caixa_mundo(vx[0], y_rasgo[0], 0, vx[1], y_rasgo[1], A))
        return p

    lat_e, lat_d = lateral("Esquerda"), lateral("Direita")
    pecas += [lat_e, lat_d]

    def horizontal(funcao, z0, y1, face_i_em_cima):
        """Base (face interna para cima) ou tampo/prateleira (face interna para baixo)."""
        bordas = ({"u0": "esquerda", "u1": "direita"} if face_i_em_cima else {"u0": "direita", "u1": "esquerda"})
        bordas.update({"v0": "frente", "v1": "tras"})
        y0 = 0 if funcao in ("Base", "Tampo") else params["prateleiras"]["recuo_frontal"]
        nome_cc = funcao.split(" ")[0]
        p = Peca(funcao, nome_cc, "caixa", mat, pad, e, L - 2 * e, y1 - y0, "u",
                 caixa_mundo(e, y0, z0, L - e, y1, z0 + e), bordas, _fitas_para(bordas, {"frente"}, fita_nome))
        return p

    base = horizontal("Base", 0, P, True)
    tampo = horizontal("Tampo", A - e, P, False)
    if tem_rasgo:
        base.rasgo = rasgo("v1")
        base.vazios.append(caixa_mundo(e, y_rasgo[0], e - rp, L - e, y_rasgo[1], e))
        tampo.rasgo = rasgo("v1")
        tampo.vazios.append(caixa_mundo(e, y_rasgo[0], A - e, L - e, y_rasgo[1], A - e + rp))
    pecas += [base, tampo]

    # base: u=x-e (u0 encosta na esquerda). tampo/prateleiras: u=(L-e)-x (u0 encosta na direita).
    # Lateral esquerda: u=y. Lateral direita: u=P-y. Painel: v=y-y0.
    def unir_horizontal(painel, face_i_em_cima, z_centro):
        y0 = painel.caixa[1]
        lado_esq, lado_dir = ("u0", "u1") if face_i_em_cima else ("u1", "u0")
        _unir(params, painel, lado_esq, lat_e, lambda pos: y0 + pos, z_centro)
        _unir(params, painel, lado_dir, lat_d, lambda pos: P - (y0 + pos), z_centro)

    unir_horizontal(base, True, e / 2)
    unir_horizontal(tampo, False, A - e / 2)

    if tem_rasgo:
        ext = rp - f
        fx0, fx1 = e - ext, L - e + ext
        fz0, fz1 = e - ext, A - e + ext
        fy0 = P - d - w / 2 - ef / 2
        bordas = {"u0": "esquerda", "u1": "direita", "v0": "baixo", "v1": "cima"}
        pecas.append(Peca("Fundo", "Fundo", "fundo", fundo["material"], fundo["padrao"], ef,
                          fx1 - fx0, fz1 - fz0, "v", caixa_mundo(fx0, fy0, fz0, fx1, fy0 + ef, fz1), bordas))

    return {"lat_e": lat_e, "lat_d": lat_d, "limite_y": limite_y, "unir_horizontal": unir_horizontal}


def _prateleiras(params, pecas, ctx):
    prat = params.get("prateleiras") or {"quantidade": 0}
    n = int(prat.get("quantidade") or 0)
    if n <= 0:
        return
    exigir(params, ["prateleiras.recuo_frontal"])
    L, A = params["largura"], params["altura"]
    cx = params["caixa"]
    e = cx["espessura"]
    fita_nome, _ = _regras_fita(params)
    y0, y1 = prat["recuo_frontal"], ctx["limite_y"]
    if y1 - y0 <= 50:
        raise ErroProjeto("Prateleira ficaria com menos de 50 mm de profundidade.")
    vao = (A - 2 * e - n * e) / (n + 1)
    if vao <= 0:
        raise ErroProjeto("Prateleiras demais para essa altura.")
    for k in range(1, n + 1):
        z0 = e + k * vao + (k - 1) * e
        nome = "Prateleira" if n == 1 else f"Prateleira {k}"
        bordas = {"u0": "direita", "u1": "esquerda", "v0": "frente", "v1": "tras"}
        p = Peca(nome, "Prateleira", "caixa", cx["material"], cx["padrao"], e, L - 2 * e, y1 - y0, "u",
                 caixa_mundo(e, y0, z0, L - e, y1, z0 + e), bordas, _fitas_para(bordas, {"frente"}, fita_nome))
        pecas.append(p)
        ctx["unir_horizontal"](p, False, z0 + e / 2)


def _portas(params, pecas):
    portas = params.get("portas")
    if not portas:
        return
    campos = ["portas.quantidade", "portas.material", "portas.padrao", "portas.espessura",
              "portas.folga_perimetro", "portas.folga_entre", "portas.dobradica.caneco_diametro",
              "portas.dobradica.caneco_profundidade", "portas.dobradica.distancia_centro_borda",
              "portas.dobradica.distancia_extremidade", "portas.dobradica.regra_quantidade"]
    exigir(params, campos)
    n = int(portas["quantidade"])
    if n not in (1, 2):
        raise ValueError("portas.quantidade deve ser 1 ou 2")
    if n == 1:
        exigir(params, ["portas.lado_dobradica"])
        if portas["lado_dobradica"] not in ("esquerda", "direita"):
            raise ValueError("portas.lado_dobradica deve ser 'esquerda' ou 'direita'")
    L, A = params["largura"], params["altura"]
    fp, fe, ep = portas["folga_perimetro"], portas["folga_entre"], portas["espessura"]
    fita_nome, _ = _regras_fita(params)
    W = (L - 2 * fp - (n - 1) * fe) / n
    H = A - 2 * fp
    dob = portas["dobradica"]
    qtd = None
    for limite, q in sorted(dob["regra_quantidade"]):
        if H <= limite:
            qtd = int(q)
            break
    if qtd is None:
        raise ErroProjeto(f"Porta de {H:g} mm é mais alta que a regra de dobradiças informada.")
    ext = dob["distancia_extremidade"]
    for k in range(n):
        x0 = fp + k * (W + fe)
        if n == 2:
            nome, lado_dob = ("Porta Esquerda", "esquerda") if k == 0 else ("Porta Direita", "direita")
        else:
            nome, lado_dob = "Porta", portas["lado_dobradica"]
        bordas = {"u0": "direita", "u1": "esquerda", "v0": "baixo", "v1": "cima"}
        p = Peca(nome, "Porta", "portas", portas["material"], portas["padrao"], ep, W, H, "v",
                 caixa_mundo(x0, -ep, fp, x0 + W, 0, fp + H), bordas,
                 {lado: fita_nome for lado in bordas} if fita_nome else {})
        Hr = p.V
        vs = [ext + i * (Hr - 2 * ext) / (qtd - 1) for i in range(qtd)] if qtd > 1 else [Hr / 2]
        dc = dob["distancia_centro_borda"]
        u = dc if lado_dob == "direita" else p.U - dc
        for v in vs:
            p.furos.append(Furo("face", dob["caneco_diametro"], dob["caneco_profundidade"],
                                u=_r1(u), v=_r1(v), origem="caneco"))
        pecas.append(p)


def _gavetas(params, pecas, ctx):
    g = params["gavetas"]
    campos = ["gavetas.quantidade", "gavetas.frente.material", "gavetas.frente.padrao",
              "gavetas.frente.espessura", "gavetas.folga_perimetro", "gavetas.folga_entre",
              "gavetas.corredica.comprimento", "gavetas.corredica.desconto_largura_total",
              "gavetas.caixa.material", "gavetas.caixa.padrao", "gavetas.caixa.espessura",
              "gavetas.caixa.desconto_altura", "gavetas.fundo.material", "gavetas.fundo.padrao",
              "gavetas.fundo.espessura", "gavetas.fundo.rasgo_largura", "gavetas.fundo.rasgo_profundidade",
              "gavetas.fundo.rasgo_distancia", "gavetas.fundo.folga"]
    exigir(params, campos)
    L, A = params["largura"], params["altura"]
    e = params["caixa"]["espessura"]
    n = int(g["quantidade"])
    if n < 1:
        raise ValueError("gavetas.quantidade deve ser pelo menos 1")
    fp, fe = g["folga_perimetro"], g["folga_entre"]
    fr, gc, gf = g["frente"], g["caixa"], g["fundo"]
    fita_nome, _ = _regras_fita(params)
    fita_caixa = fita_nome if g.get("fita_caixa") else None

    h = (A - 2 * fp - (n - 1) * fe) / n
    W = L - 2 * fp
    eg = gc["espessura"]
    Wb = L - 2 * e - g["corredica"]["desconto_largura_total"]
    Db = g["corredica"]["comprimento"]
    Hb = h - gc["desconto_altura"]
    w, rp, d, f, ef = gf["rasgo_largura"], gf["rasgo_profundidade"], gf["rasgo_distancia"], gf["folga"], gf["espessura"]
    if Db > ctx["limite_y"]:
        raise ErroProjeto(f"Corrediça de {Db:g} mm não cabe: profundidade livre é {ctx['limite_y']:g} mm.")
    if Hb <= d + w + 10:
        raise ErroProjeto(f"Caixa de gaveta com {Hb:g} mm de altura é baixa demais para o fundo em rasgo.")
    if ef > w or rp >= eg or f >= rp:
        raise ErroProjeto("Fundo da gaveta não fecha com o rasgo (espessura, profundidade ou folga).")

    x0b, x1b = e + (L - 2 * e - Wb) / 2, e + (L - 2 * e - Wb) / 2 + Wb
    for k in range(n):
        num = n - k  # gaveta 1 = a de cima
        z0 = fp + k * (h + fe)
        sufixo = f" {num}" if n > 1 else ""
        bordas = {"u0": "direita", "u1": "esquerda", "v0": "baixo", "v1": "cima"}
        pecas.append(Peca(f"Frente Gaveta{sufixo}", "Frente Gaveta", "gavetas.frente", fr["material"], fr["padrao"],
                          fr["espessura"], W, h, "u", caixa_mundo(fp, -fr["espessura"], z0, fp + W, 0, z0 + h), bordas,
                          {lado: fita_nome for lado in bordas} if fita_nome else {}))

        zb = z0 + gc["desconto_altura"] / 2
        if zb < e or zb + Hb > A - e:
            raise ErroProjeto(f"Caixa da gaveta{sufixo} sai do vão interno; revise folgas e desconto_altura.")
        y0b, y1b = 0, Db
        zr = (zb + d, zb + d + w)

        for lado_mundo in ("Esquerda", "Direita"):
            esq = lado_mundo == "Esquerda"
            lx0, lx1 = (x0b, x0b + eg) if esq else (x1b - eg, x1b)
            bl = ({"u0": "frente", "u1": "tras"} if esq else {"u0": "tras", "u1": "frente"})
            bl.update({"v0": "baixo", "v1": "cima"})
            p = Peca(f"Lateral Gaveta{sufixo} {lado_mundo}", "Lateral Gaveta", "gavetas.caixa", gc["material"],
                     gc["padrao"], eg, Db, Hb, "u", caixa_mundo(lx0, y0b, zb, lx1, y1b, zb + Hb), bl,
                     _fitas_para(bl, {"cima"}, fita_caixa), rasgo=Rasgo("v0", w, rp, d))
            vx = (x0b + eg - rp, x0b + eg) if esq else (x1b - eg, x1b - eg + rp)
            p.vazios.append(caixa_mundo(vx[0], y0b, zr[0], vx[1], y1b, zr[1]))
            pecas.append(p)

        bi = {"v0": "baixo", "v1": "cima"}
        cf = Peca(f"Contra-frente Gaveta{sufixo}", "Contra-frente Gaveta", "gavetas.caixa", gc["material"],
                  gc["padrao"], eg, Wb - 2 * eg, Hb, "u",
                  caixa_mundo(x0b + eg, y0b, zb, x1b - eg, y0b + eg, zb + Hb),
                  {"u0": "direita", "u1": "esquerda", **bi}, rasgo=Rasgo("v0", w, rp, d))
        cf.fitas = _fitas_para(cf.bordas, {"cima"}, fita_caixa)
        cf.vazios.append(caixa_mundo(x0b + eg, y0b + eg - rp, zr[0], x1b - eg, y0b + eg, zr[1]))
        tr = Peca(f"Traseira Gaveta{sufixo}", "Traseira Gaveta", "gavetas.caixa", gc["material"], gc["padrao"],
                  eg, Wb - 2 * eg, Hb, "u", caixa_mundo(x0b + eg, y1b - eg, zb, x1b - eg, y1b, zb + Hb),
                  {"u0": "esquerda", "u1": "direita", **bi}, rasgo=Rasgo("v0", w, rp, d))
        tr.fitas = _fitas_para(tr.bordas, {"cima"}, fita_caixa)
        tr.vazios.append(caixa_mundo(x0b + eg, y1b - eg, zr[0], x1b - eg, y1b - eg + rp, zr[1]))
        pecas += [cf, tr]

        ext = rp - f
        fx0, fx1 = x0b + eg - ext, x1b - eg + ext
        fy0, fy1 = y0b + eg - ext, y1b - eg + ext
        fz0 = zb + d + (w - ef) / 2
        pecas.append(Peca(f"Fundo Gaveta{sufixo}", "Fundo Gaveta", "gavetas.fundo", gf["material"], gf["padrao"], ef,
                          fx1 - fx0, fy1 - fy0, "u", caixa_mundo(fx0, fy0, fz0, fx1, fy1, fz0 + ef),
                          {"u0": "esquerda", "u1": "direita", "v0": "frente", "v1": "tras"}))


# -------------------------------------------------------------- ponto único

def calcular_com_info(params: dict):
    """(peças, info). info traz ferragens no armário em módulos."""
    if params.get("tipo") == "armario":
        from . import armario
        return armario.calcular(params)
    return calcular(params), {"ferragens": []}


def calcular(params: dict) -> list[Peca]:
    """Gera as peças do móvel. Levanta ParametrosFaltando/ErroProjeto/ValueError."""
    if params.get("tipo") == "armario":
        from . import armario
        return armario.calcular(params)[0]
    exigir(params, ["movel", "tipo", "largura", "altura", "profundidade", "caixa.material", "caixa.padrao",
                    "caixa.espessura", "fundo.tipo", "fita.padrao", "uniao.tipo"])
    if params["tipo"] not in TIPOS:
        raise ValueError(f"tipo deve ser um de {TIPOS}")
    if params["fundo"]["tipo"] == "rasgo":
        exigir(params, [f"fundo.{c}" for c in ("material", "padrao", "espessura", "rasgo_largura",
                                                "rasgo_profundidade", "rasgo_distancia", "folga")])
    if params["fita"]["padrao"] != "nenhuma":
        exigir(params, ["fita.nome"])
    numero_positivo(params, ["largura", "altura", "profundidade", "caixa.espessura"])
    for grupo in ("caixa", "fundo"):
        pad = (params.get(grupo) or {}).get("padrao")
        if pad is not None and pad not in ("unicolor", "amadeirado"):
            raise ValueError(f"{grupo}.padrao deve ser 'unicolor' ou 'amadeirado'")
    _validar_uniao(params)

    pecas: list[Peca] = []
    ctx = _caixa(params, pecas)
    if params["tipo"] == "caixa":
        _prateleiras(params, pecas, ctx)
        _portas(params, pecas)
    else:
        if params.get("portas"):
            raise ValueError("Gaveteiro não leva portas: as frentes das gavetas fecham a caixa.")
        exigir(params, ["gavetas"])
        _gavetas(params, pecas, ctx)
    return pecas
