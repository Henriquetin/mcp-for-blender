"""Scripts que rodam dentro do Blender (via execute_code do addon).

Seguem o padrão de blender_scripts: leem ARGS e devolvem um dict.
"""

from __future__ import annotations

import json

from . import cortecloud
from .modelo import Peca

MARCA = "marcenaria_gerado"

# Gera o móvel: salva o .blend, configura mm, recria só os objetos que este
# script criou antes e recusa mexer em objetos de terceiros na coleção.
MODELAR = r'''
import bpy, json

movel = ARGS["movel"]

# 1. Salvar antes de alterar a cena
if bpy.data.filepath:
    bpy.ops.wm.save_mainfile()
elif ARGS.get("salvar_como"):
    bpy.ops.wm.save_as_mainfile(filepath=ARGS["salvar_como"])
else:
    return {"erro": "O .blend ainda não foi salvo. Informe salvar_como (caminho .blend) para salvar antes de modelar."}
salvo_em = bpy.data.filepath

# 2. Unidades em milímetro (1 unidade = 1 mm)
us = bpy.context.scene.unit_settings
us.system = "METRIC"
us.scale_length = 0.001
us.length_unit = "MILLIMETERS"
for tela in bpy.data.screens:
    for area in tela.areas:
        for esp in area.spaces:
            if esp.type == "VIEW_3D":
                esp.clip_start = 1
                esp.clip_end = 100000

# 3. Coleção do móvel
col = bpy.data.collections.get(movel)
if col is None:
    col = bpy.data.collections.new(movel)
    bpy.context.scene.collection.children.link(col)
alheios = [o.name for o in col.objects if not o.get(ARGS["marca"])]
if alheios:
    return {"erro": "A coleção tem objetos que não foram criados pelo gerador: " + ", ".join(alheios)
            + ". Mova ou apague-os você mesmo (ou autorize) antes de gerar de novo."}
for o in list(col.objects):
    malha = o.data
    bpy.data.objects.remove(o, do_unlink=True)
    if malha is not None and malha.users == 0:
        bpy.data.meshes.remove(malha)
col["marcenaria_params"] = ARGS["params_json"]

# 4. Materiais (cor só para visualização)
def material(nome, padrao):
    nm = "MDF - " + nome
    m = bpy.data.materials.get(nm)
    if m is None:
        m = bpy.data.materials.new(nm)
        m.use_nodes = True
    cor = (0.55, 0.38, 0.22, 1.0) if padrao == "amadeirado" else (0.9, 0.9, 0.88, 1.0)
    m.diffuse_color = cor
    bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if m.node_tree else None
    if bsdf is not None:
        bsdf.inputs[0].default_value = cor
    return m

# 5. Uma caixa por peça, origem no centro, sem rotação e escala 1
criados = []
for p in ARGS["pecas"]:
    x0, y0, z0, x1, y1, z1 = p["caixa"]
    hx, hy, hz = (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2
    vs = [(sx * hx, sy * hy, sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    malha = bpy.data.meshes.new(p["nome"])
    malha.from_pydata(vs, [], fs)
    malha.update()
    ob = bpy.data.objects.new(p["nome"], malha)
    ob.location = (x0 + hx, y0 + hy, z0 + hz)
    col.objects.link(ob)
    ob.data.materials.append(material(p["material"], p["padrao"]))
    ob[ARGS["marca"]] = True
    for k, v in p["props"].items():
        ob[k] = v
    criados.append(ob.name)

bpy.context.view_layer.update()
return {"criados": criados, "colecao": col.name, "salvo_em": salvo_em}
'''

# Lê as caixas da coleção para conferir se alguém editou à mão.
LER_COLECAO = r'''
import bpy
col = bpy.data.collections.get(ARGS["movel"])
if col is None:
    return {"erro": "Coleção não encontrada: " + ARGS["movel"]}
bpy.context.view_layer.update()  # matrix_world de objetos recém-criados
saida = []
for o in col.objects:
    if o.type != "MESH":
        continue
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    if not pts:
        continue
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    saida.append({"nome": o.name, "caixa": lo + hi, "gerado": bool(o.get(ARGS["marca"])),
                  "rot": [round(a, 6) for a in o.rotation_euler], "escala": [round(a, 6) for a in o.scale]})
return {"objetos": saida, "params_json": col.get("marcenaria_params")}
'''


def nome_objeto(p: Peca, movel: str) -> str:
    return f"{p.funcao} - {movel}"


def argumentos_modelar(pecas: list[Peca], params: dict, salvar_como=None) -> dict:
    movel = params["movel"]
    lista = []
    for p in pecas:
        parte, _info = cortecloud.peca_para_cortecloud(p, movel)
        m = parte["machining"]
        furacoes = {"horizontalDrills": m["horizontalDrills"], "verticalDrills": m["verticalDrills"],
                    "furrowMachining": m["furrowMachining"]}
        lista.append({
            "nome": nome_objeto(p, movel),
            "caixa": list(p.caixa),
            "material": p.material,
            "padrao": p.padrao,
            "props": {
                "funcao": p.funcao,
                "material": p.material,
                "espessura": float(p.espessura),
                "c": parte["c"], "l": parte["l"],
                "fita_c1": parte["c1"] or "", "fita_c2": parte["c2"] or "",
                "fita_l1": parte["l1"] or "", "fita_l2": parte["l2"] or "",
                "sentido_veio": "comprimento (c)" if p.padrao == "amadeirado" else "livre (c = maior lado)",
                "furacoes": json.dumps(furacoes, ensure_ascii=False),
            },
        })
    return {"movel": movel, "pecas": lista, "marca": MARCA, "salvar_como": salvar_como,
            "params_json": json.dumps(params, ensure_ascii=False)}


def comparar_com_cena(pecas: list[Peca], movel: str, cena: dict) -> list[str]:
    """Diferenças entre o que o motor calcula e o que está no Blender."""
    esperado = {nome_objeto(p, movel): p.caixa for p in pecas}
    achados = {o["nome"]: o for o in cena.get("objetos", [])}
    difs = []
    for nome, caixa in esperado.items():
        o = achados.get(nome)
        if o is None:
            difs.append(f"Falta no Blender: {nome}")
            continue
        if any(abs(a - b) > 0.05 for a, b in zip(o["caixa"], caixa)):
            difs.append(f"Medida/posição diferente no Blender: {nome}")
        if any(abs(a) > 1e-6 for a in o["rot"]) or any(abs(s - 1) > 1e-6 for s in o["escala"]):
            difs.append(f"Rotação/escala não aplicada: {nome}")
    for nome, o in achados.items():
        if nome not in esperado:
            difs.append(f"Objeto a mais na coleção: {nome}" + ("" if o["gerado"] else " (não criado pelo gerador)"))
    return difs
