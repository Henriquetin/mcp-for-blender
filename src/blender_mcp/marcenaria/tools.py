"""Ferramentas MCP de marcenaria (móveis planejados em MDF -> Blender -> CorteCloud)."""

from __future__ import annotations

import json
from collections.abc import Callable
from importlib import resources
from pathlib import Path
from typing import Any

from mcp.types import ToolAnnotations

from .. import blender_scripts
from . import blender as bl
from . import cortecloud, motor, parametros, validacao

_LEITURA = ToolAnnotations(readOnlyHint=True)


def _params(params: Any) -> dict:
    if isinstance(params, str):
        params = json.loads(params)
    if not isinstance(params, dict):
        raise ValueError("params deve ser um objeto JSON")
    return params


def _calcular(params):
    """(pecas, None) ou (None, mensagem de erro para o modelo repassar)."""
    try:
        return motor.calcular(params), None
    except parametros.ParametrosFaltando as e:
        return None, ("PARE e pergunte ao usuário (não invente): faltam " + ", ".join(e.faltando)
                      + ". Use marcenaria_modelo para ver o formato.")
    except (motor.ErroProjeto, ValueError, KeyError, TypeError) as e:
        return None, f"Projeto não fecha: {e}"


def tabela(pecas, movel) -> str:
    linhas = ["| Qtd | Função | C (mm) | L (mm) | Espessura | Material | Fitas C1/C2/L1/L2 | Nº de furações |",
              "|---|---|---|---|---|---|---|---|"]
    for g in cortecloud.agrupar_para_tabela(pecas, movel):
        fitas = " / ".join(f or "-" for f in g["fitas"])
        funcoes = ", ".join(g["funcoes"])
        linhas.append(f"| {g['qtd']} | {funcoes} | {g['c']} | {g['l']} | {g['espessura']} | {g['material']} "
                      f"| {fitas} | {g['furacoes']} |")
    return "\n".join(linhas)


def _guia() -> str:
    return resources.files("blender_mcp.marcenaria").joinpath("guia.md").read_text(encoding="utf-8")


def register(mcp, get_connection: Callable, pasta_padrao: Path | None = None) -> None:
    def rodar(script: str, args: dict, leitura: bool) -> dict:
        result = get_connection().send_command(
            "execute_code", {"code": blender_scripts.build(script, args)}, read_only=leitura)
        if not isinstance(result, dict) or "result" not in result:
            raise RuntimeError("Addon do Blender antigo demais: atualize com `uvx mcp-for-blender install-addon`.")
        return blender_scripts.parse_result(result["result"])

    @mcp.tool(annotations=_LEITURA)
    def marcenaria_guia() -> str:
        """Fluxo de trabalho e regras para projetar móveis planejados em MDF e exportar ao CorteCloud.
        Leia antes de usar as outras ferramentas marcenaria_*."""
        return _guia()

    @mcp.tool(annotations=_LEITURA)
    def marcenaria_modelo(tipo: str = "caixa") -> str:
        """Modelo de parâmetros para o briefing. tipo: 'caixa' (nicho/armário, com prateleiras e portas
        opcionais) ou 'gaveteiro'. Os valores são sugestões: confirme cada item de `confirmar` com o usuário."""
        try:
            return json.dumps(parametros.modelo(tipo), ensure_ascii=False, indent=2)
        except ValueError as e:
            return str(e)

    @mcp.tool(annotations=_LEITURA)
    def marcenaria_calcular(params: dict | str, catalogo: str | None = None) -> str:
        """Calcula as peças do móvel SEM o Blender: tabela de peças e checklist de validação.
        params: dicionário no formato de marcenaria_modelo. catalogo: caminho do JSON do catálogo da
        central (ou variável MARCENARIA_CATALOGO)."""
        try:
            p = _params(params)
        except ValueError as e:
            return str(e)
        pecas, erro = _calcular(p)
        if erro:
            return erro
        itens = validacao.validar(pecas, p, catalogo)
        return (f"{p['movel']}: {len(pecas)} peças\n\n{tabela(pecas, p['movel'])}\n\n"
                f"Validação:\n{validacao.resumo(itens)}")

    @mcp.tool()
    def marcenaria_modelar(params: dict | str, salvar_como: str | None = None) -> str:
        """Gera (ou regenera) o móvel no Blender a partir dos parâmetros: uma coleção por móvel, uma caixa
        por peça em mm, com custom properties (funcao, material, espessura, fitas, sentido_veio, furacoes).
        Salva o .blend ANTES de alterar a cena; se o arquivo nunca foi salvo, passe salvar_como.
        Só substitui objetos que ele mesmo criou. Depois use look para mostrar ao usuário."""
        try:
            p = _params(params)
        except ValueError as e:
            return str(e)
        pecas, erro = _calcular(p)
        if erro:
            return erro
        try:
            r = rodar(bl.MODELAR, bl.argumentos_modelar(pecas, p, salvar_como), leitura=False)
        except Exception as e:  # conexão, addon antigo, erro no Blender
            return f"Não consegui gerar no Blender: {e}"
        if r.get("erro"):
            return r["erro"]
        itens = validacao.validar(pecas, p)
        return (f"Coleção '{r['colecao']}' gerada com {len(r['criados'])} peças (.blend salvo antes: "
                f"{r['salvo_em']}).\n\n{tabela(pecas, p['movel'])}\n\nValidação prévia:\n{validacao.resumo(itens)}\n\n"
                "Mostre com look (frente, lateral, perspectiva) e PARE até o usuário escrever 'aprovado'.")

    @mcp.tool(annotations=_LEITURA)
    def marcenaria_validar(params: dict | str, catalogo: str | None = None, conferir_blender: bool = True) -> str:
        """Checklist da etapa de validação: round() para inteiro, espessuras do catálogo, peça x chapa,
        sobreposição de volumes, nomes exatos de materiais/fitas, furações dentro da peça. Com
        conferir_blender, também compara a coleção do Blender com o cálculo (pega edição manual)."""
        try:
            p = _params(params)
        except ValueError as e:
            return str(e)
        pecas, erro = _calcular(p)
        if erro:
            return erro
        try:
            itens = validacao.validar(pecas, p, catalogo)
        except (OSError, ValueError) as e:
            return f"Não consegui ler o catálogo: {e}"
        if conferir_blender:
            try:
                cena = rodar(bl.LER_COLECAO, {"movel": p["movel"], "marca": bl.MARCA}, leitura=True)
                if cena.get("erro"):
                    itens.append({"item": "Blender igual ao cálculo", "status": "pendente", "detalhes": [cena["erro"]]})
                else:
                    difs = bl.comparar_com_cena(pecas, p["movel"], cena)
                    itens.append({"item": "Blender igual ao cálculo", "status": "erro" if difs else "ok",
                                  "detalhes": difs})
            except Exception as e:
                itens.append({"item": "Blender igual ao cálculo", "status": "pendente",
                              "detalhes": [f"Blender indisponível: {e}"]})
        return validacao.resumo(itens)

    @mcp.tool()
    def marcenaria_exportar_cortecloud(params: dict | str, aprovado: bool = False, pasta: str | None = None,
                                       catalogo: str | None = None, aceitar_pendentes: bool = False) -> str:
        """Gera '<movel>_cortecloud.json' no formato de importação do CorteCloud. aprovado=True só depois de o
        usuário escrever 'aprovado'. Recusa se a validação tiver erro; itens pendentes (ex.: sem catálogo)
        só passam com aceitar_pendentes=True, autorizado pelo usuário. Não envia nada ao CorteCloud."""
        if not aprovado:
            return "Exportação bloqueada: o usuário ainda não aprovou o modelo e a tabela de peças."
        try:
            p = _params(params)
        except ValueError as e:
            return str(e)
        pecas, erro = _calcular(p)
        if erro:
            return erro
        try:
            itens = validacao.validar(pecas, p, catalogo)
        except (OSError, ValueError) as e:
            return f"Não consegui ler o catálogo: {e}"
        bloq = validacao.bloqueios(itens, aceitar_pendentes)
        if bloq:
            return "Exportação bloqueada pela validação:\n" + validacao.resumo(bloq)
        dados, _ = cortecloud.montar(pecas, p["movel"])
        destino_dir = Path(pasta).expanduser() if pasta else (pasta_padrao or Path.home() / "marcenaria")
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / f"{p['movel']}_cortecloud.json"
        destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        total = sum(x["quantity"] for x in dados["parts"])
        return (f"Arquivo gerado: {destino}\n{len(dados['parts'])} linhas, {total} peças.\n\n"
                f"Validação:\n{validacao.resumo(itens)}\n\n"
                "Roteiro para o usuário: CorteCloud -> novo 'Serviço Completo' -> 'Carregar arquivo Cortecloud' -> "
                "vincular materiais -> conferir cotas de furação -> o usuário aprova e paga. "
                "Você não aprova, não paga e não envia pedido.")

    @mcp.tool(annotations=_LEITURA)
    def marcenaria_ler_projeto(movel: str) -> str:
        """Recupera do Blender os parâmetros usados para gerar a coleção `movel` (para alterar e regenerar)."""
        try:
            cena = rodar(bl.LER_COLECAO, {"movel": movel, "marca": bl.MARCA}, leitura=True)
        except Exception as e:
            return f"Blender indisponível: {e}"
        if cena.get("erro"):
            return cena["erro"]
        if not cena.get("params_json"):
            return f"A coleção {movel} não foi criada por marcenaria_modelar."
        return cena["params_json"]
