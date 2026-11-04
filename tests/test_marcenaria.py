"""Marcenaria: parâmetros -> peças -> validação -> JSON do CorteCloud.

Roda sem Blender: o motor é Python puro. Os scripts que vão para o Blender são
só compilados aqui (foram testados à mão com o bpy 5.0).
"""
import asyncio
import copy
import json

import pytest

from blender_mcp import blender_scripts, server
from blender_mcp.marcenaria import blender as bl
from blender_mcp.marcenaria import cortecloud, motor, parametros, validacao
from blender_mcp.marcenaria.modelo import Peca, caixa_mundo

CATALOGO = {
    "chapa": {"c": 2750, "l": 1840, "refilo": 0},
    "materiais": [
        {"nome": "Branco TX 15", "espessura": 15, "padrao": "unicolor"},
        {"nome": "Branco TX 6", "espessura": 6, "padrao": "unicolor"},
    ],
    "fitas": ["Branco TX 0.45"],
}


def nicho(**extra):
    p = parametros.modelo("caixa")["parametros"]
    p.update(extra)
    return p


def call(name, **kw):
    r = asyncio.run(server.mcp.call_tool(name, kw))
    content = r[0] if isinstance(r, tuple) else r
    return content[0].text


def test_ferramentas_registradas():
    nomes = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert {"marcenaria_guia", "marcenaria_modelo", "marcenaria_calcular", "marcenaria_modelar",
            "marcenaria_validar", "marcenaria_exportar_cortecloud", "marcenaria_ler_projeto"} <= nomes


def test_nicho_pecas_e_medidas():
    pecas = {p.funcao: p for p in motor.calcular(nicho())}
    assert set(pecas) == {"Lateral Esquerda", "Lateral Direita", "Base", "Tampo", "Fundo", "Prateleira"}
    assert (pecas["Lateral Esquerda"].U, pecas["Lateral Esquerda"].V) == (300, 400)
    assert (pecas["Base"].U, pecas["Base"].V) == (570, 300)
    # fundo: vão 570 x 370 + 2 x (rasgo 8 - folga 1)
    assert (pecas["Fundo"].U, pecas["Fundo"].V) == (584, 384)


def test_laterais_espelhadas_viram_uma_linha_com_quantity_2():
    dados, _ = cortecloud.montar(motor.calcular(nicho()), "Nicho_Piloto")
    laterais = [p for p in dados["parts"] if p["function"] == "Lateral"]
    assert len(laterais) == 1 and laterais[0]["quantity"] == 2


def test_formato_json_cortecloud():
    dados, _ = cortecloud.montar(motor.calcular(nicho()), "Nicho_Piloto")
    for parte in dados["parts"]:
        assert {"quantity", "c", "l", "function", "complement", "c1", "c2", "l1", "l2", "material",
                "machining"} <= set(parte)
        m = parte["machining"]
        assert (m["x"], m["y"]) == (parte["c"], parte["l"])
        assert isinstance(parte["c"], int) and isinstance(parte["l"], int)
        assert m["startSide"] == 0 and m["furrowMachiningPair"] is None
        assert all(f["face"] == "i" for f in m["horizontalDrills"] + m["verticalDrills"])
        assert all(f["direction"] in ("XP", "YP") for f in m["horizontalDrills"])
    fundo = next(p for p in dados["parts"] if p["function"] == "Fundo")
    assert fundo["machining"]["horizontalDrills"] == [] and fundo["machining"]["verticalDrills"] == []
    assert fundo["machining"]["furrowMachining"] is None


def test_rasgo_sempre_em_c2_e_fita_na_frente():
    for p in motor.calcular(nicho()):
        if p.rasgo:
            rot, _, _ = cortecloud.orientar(p)
            assert cortecloud._ROTACOES[rot][p.rasgo.lado] == "C2"
    dados, _ = cortecloud.montar(motor.calcular(nicho()), "N")
    base = next(p for p in dados["parts"] if p["function"] == "Base")
    assert base["c1"] == "Branco TX 0.45" and base["c2"] is None
    assert base["machining"]["furrowMachining"] == {"face": "i", "depth": 8, "width": 6.7, "distance": 15}


def test_medidas_com_round_nunca_ceil():
    p = nicho(portas=copy.deepcopy(parametros.EXEMPLO_PORTAS))  # portas de 296,5 mm
    portas = [x for x in motor.calcular(p) if x.funcao_cc == "Porta"]
    assert all(x.U == round(296.5) == 296 for x in portas)


def test_caneco_a_distancia_certa_da_borda_da_dobradica_apos_arredondar():
    p = nicho(portas=copy.deepcopy(parametros.EXEMPLO_PORTAS))
    dados, _ = cortecloud.montar(motor.calcular(p), "N")
    portas = [x for x in dados["parts"] if x["function"] == "Porta"]
    ys = sorted({f["y"] for x in portas for f in x["machining"]["verticalDrills"]})
    largura = portas[0]["l"]
    assert ys == [22.5, largura - 22.5]


def test_parametro_faltando_manda_perguntar():
    p = nicho()
    del p["uniao"]["cavilha"]
    texto = call("marcenaria_calcular", params=p)
    assert "pergunte ao usuário" in texto and "uniao.cavilha.diametro" in texto


def test_portas_sem_ficha_da_dobradica_param():
    p = nicho(portas={"quantidade": 2, "material": "Branco TX 15", "padrao": "unicolor", "espessura": 15,
                      "folga_perimetro": 2, "folga_entre": 3})
    with pytest.raises(parametros.ParametrosFaltando) as e:
        motor.calcular(p)
    assert "portas.dobradica.caneco_diametro" in e.value.faltando


def test_gaveteiro_corredica_maior_que_a_caixa():
    g = parametros.modelo("gaveteiro")["parametros"]
    g["gavetas"]["corredica"]["comprimento"] = 450
    with pytest.raises(motor.ErroProjeto):
        motor.calcular(g)


def test_gaveteiro_sem_sobreposicao():
    g = parametros.modelo("gaveteiro")["parametros"]
    assert validacao.sobreposicoes(motor.calcular(g)) == []


def test_sobreposicao_detectada():
    pecas = motor.calcular(nicho())
    pecas.append(Peca("Intrusa", "Intrusa", "caixa", "Branco TX 15", "unicolor", 15, 100, 100, "u",
                      caixa_mundo(0, 0, 100, 100, 100, 115), {}))
    assert any("Intrusa" in s for s in validacao.sobreposicoes(pecas))


def test_validacao_completa_com_catalogo():
    itens = validacao.validar(motor.calcular(nicho()), nicho(), CATALOGO)
    status = {i["item"]: i["status"] for i in itens}
    assert "erro" not in status.values() and "pendente" not in status.values()


def test_nome_errado_no_catalogo_sugere_o_certo():
    p = nicho()
    p["caixa"]["material"] = "Branco Tx 15"
    itens = validacao.validar(motor.calcular(p), p, CATALOGO)
    nomes = next(i for i in itens if i["item"].startswith("Materiais"))
    assert nomes["status"] == "erro" and "Branco TX 15" in nomes["detalhes"][0]


def test_peca_maior_que_a_chapa():
    p = nicho(largura=3000)
    itens = validacao.validar(motor.calcular(p), p, CATALOGO)
    assert next(i for i in itens if "chapa" in i["item"])["status"] == "erro"


def test_exportar_exige_aprovacao(tmp_path):
    texto = call("marcenaria_exportar_cortecloud", params=nicho(), pasta=str(tmp_path))
    assert "bloqueada" in texto and not list(tmp_path.iterdir())


def test_exportar_bloqueia_pendencias_sem_catalogo(tmp_path, monkeypatch):
    monkeypatch.delenv(validacao.CATALOGO_ENV, raising=False)
    texto = call("marcenaria_exportar_cortecloud", params=nicho(), aprovado=True, pasta=str(tmp_path))
    assert "bloqueada" in texto


def test_exportar_gera_arquivo(tmp_path):
    cat = tmp_path / "cat.json"
    cat.write_text(json.dumps(CATALOGO), encoding="utf-8")
    texto = call("marcenaria_exportar_cortecloud", params=nicho(), aprovado=True, pasta=str(tmp_path),
                 catalogo=str(cat))
    arquivo = tmp_path / "Nicho_Piloto_cortecloud.json"
    assert arquivo.exists(), texto
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    assert sum(p["quantity"] for p in dados["parts"]) == 6
    assert "Carregar arquivo Cortecloud" in texto


def test_scripts_do_blender_compilam():
    p = nicho(portas=copy.deepcopy(parametros.EXEMPLO_PORTAS))
    args = bl.argumentos_modelar(motor.calcular(p), p, "/tmp/x.blend")
    compile(blender_scripts.build(bl.MODELAR, args), "modelar", "exec")
    compile(blender_scripts.build(bl.LER_COLECAO, {"movel": "x", "marca": bl.MARCA}), "ler", "exec")
    nomes = [x["nome"] for x in args["pecas"]]
    assert "Lateral Esquerda - Nicho_Piloto" in nomes
    props = args["pecas"][0]["props"]
    assert {"funcao", "material", "espessura", "fita_c1", "fita_c2", "fita_l1", "fita_l2", "sentido_veio",
            "furacoes"} <= set(props)


def test_modelar_salva_antes_de_alterar():
    # O script só altera a cena depois de salvar (ou devolve erro pedindo salvar_como).
    script = bl.MODELAR
    assert script.index("save_mainfile") < script.index("unit_settings")
    assert script.index("save_mainfile") < script.index("objects.remove")


# ------------------------------------------------------------ armário em módulos

def armario():
    return parametros.modelo("armario")["parametros"]


def test_armario_valida_sem_erros():
    cat = dict(CATALOGO, materiais=CATALOGO["materiais"] + [
        {"nome": "Branco TX 18", "espessura": 18, "padrao": "unicolor"},
        {"nome": "Freijó 18", "espessura": 18, "padrao": "amadeirado"}], fitas=["Branco TX 0.45", "Freijó 0.45"])
    pecas = motor.calcular(armario())
    assert len(pecas) == 80
    itens = validacao.validar(pecas, armario(), cat)
    assert [i["item"] for i in itens if i["status"] in ("erro", "pendente")] == []


def test_armario_vaos_fecham_com_a_imagem():
    pecas = {p.funcao: p for p in motor.calcular(armario())}
    # maleiro do módulo 1 = resto = 398 (imagem: 397)
    prat_cab = pecas["Prateleira Modulo 1 3"]
    assert 2282 - prat_cab.caixa[5] == 398
    portas = [p for p in pecas.values() if p.funcao_cc == "Porta Correr"]
    assert len(portas) == 4 and all((p.U, p.V) == (694, 2106) for p in portas)


def test_armario_corredica_grande_demais():
    p = armario()
    p["gavetas"]["corredica"]["comprimento"] = 420
    with pytest.raises(ValueError):
        motor.calcular(p)


def test_armario_vaos_que_nao_fecham():
    p = armario()
    p["modulos"][2]["vaos"][0]["altura"] = 1700  # sem 'resto'
    with pytest.raises(ValueError, match="Módulo 3"):
        motor.calcular(p)


def test_armario_cavilhas_nas_duas_faces_da_divisoria():
    pecas = {p.funcao: p for p in motor.calcular(armario())}
    faces = {f.face for f in pecas["Divisoria 1"].furos if f.tipo == "face"}
    assert faces == {"i", "e"}


def test_furos_das_duas_faces_que_se_encontram_viram_erro():
    from blender_mcp.marcenaria.modelo import Furo
    p = motor.calcular(armario())[0]
    p.furos += [Furo("face", 8, 12, u=200, v=200, face="i"), Furo("face", 8, 12, u=200, v=200, face="e")]
    assert any("duas faces" in e for e in validacao._furos_fora(p))


def test_furos_visuais_ficam_dentro_da_peca():
    from blender_mcp.marcenaria import visual
    for p in motor.calcular(armario()):
        for it in visual.furos(p, "X"):
            if it["forma"] != "cilindro":
                continue
            c, e, r, h = it["centro"], it["eixo"], it["raio"], it["comprimento"]
            for i in range(3):
                meia = h / 2 if i == e else r
                folga = visual.SALIENCIA + 0.01 if i == e else 0.01
                assert c[i] - meia >= p.caixa[i] - folga, (p.funcao, it)
                assert c[i] + meia <= p.caixa[i + 3] + folga, (p.funcao, it)


def test_armario_tem_ferragens_visuais():
    _, info = motor.calcular_com_info(armario())
    grupos = {v["grupo"] for v in info["visuais"]}
    assert {"Corrediças", "Trilhos", "Roldanas e Guias", "Cabideiros"} <= grupos
