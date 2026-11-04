# Marcenaria: MDF → Blender → CorteCloud

Extensão do MCP for Blender para móveis planejados em MDF. A partir de um dicionário de
parâmetros, ela gera:

1. o modelo 3D no Blender (uma coleção por móvel, uma caixa por peça, em mm);
2. a lista de peças conferível;
3. o arquivo `<movel>_cortecloud.json`, no formato de importação do CorteCloud, com cortes, fitas e furações.

As regras construtivas ficam em código (`src/blender_mcp/marcenaria/`), não no prompt. O mesmo
`params` sempre gera as mesmas peças. O cálculo, a validação e a exportação **funcionam com o
Blender fechado**.

## Ferramentas

| Ferramenta | O que faz | Precisa do Blender? |
|---|---|---|
| `marcenaria_guia` | Fluxo de 6 etapas e regras | não |
| `marcenaria_modelo(tipo)` | Parâmetros sugeridos para o briefing (`caixa` ou `gaveteiro`) e o que confirmar | não |
| `marcenaria_calcular(params, catalogo)` | Tabela de peças + checklist | não |
| `marcenaria_modelar(params, salvar_como)` | Salva o .blend e (re)gera o móvel | sim |
| `marcenaria_validar(params, catalogo)` | Checklist + compara a cena com o cálculo | opcional |
| `marcenaria_exportar_cortecloud(params, aprovado, ...)` | Grava o JSON | não |
| `marcenaria_ler_projeto(movel)` | Lê de volta os params guardados na coleção | sim |

Continuam disponíveis as ferramentas do MCP for Blender: `execute_blender_code`, `look`, `get_scene_info` etc.
Para esconder as de marcenaria, use `BLENDER_MCP_MARCENARIA=0`.

## Travas de segurança (em código)

- `marcenaria_modelar` **salva o .blend antes** de mexer na cena. Se o arquivo nunca foi salvo, ela recusa e pede `salvar_como`.
- Só apaga objetos que ela mesma criou (marcados com `marcenaria_gerado`). Se houver objeto de terceiros na coleção, ela recusa.
- Se faltar parâmetro que muda a medida de corte, a resposta é "PARE e pergunte ao usuário". Não existe valor escondido.
- A exportação exige `aprovado=True` e não passa com erro de validação. Itens pendentes (ex.: sem catálogo) só passam com `aceitar_pendentes=True`.
- Nada é enviado ao CorteCloud. Quem aprova e paga é sempre você.

## Validação (checklist)

- Medidas com `round()` para inteiro (nunca ceil), aplicado já na criação da peça. Assim, furos medidos a partir da borda oposta usam a medida real de corte.
- Espessuras que existem no catálogo.
- Nenhuma peça maior que a chapa (com refilo; peça amadeirada não gira).
- Nenhuma sobreposição de volume. O encaixe do fundo no rasgo é permitido.
- Nomes de materiais e fitas exatamente iguais aos do catálogo. Se houver erro de digitação, sugere o nome certo.
- Furações dentro da peça e sem atravessar a chapa.
- Extras: folgas reais de portas e frentes depois do arredondamento; veio x rasgo em C2.

## Instalação

1. Instale o addon no Blender (o mesmo do projeto original):
   ```bash
   uvx mcp-for-blender install-addon
   ```
   No Blender, abra a barra lateral (N), aba "MCP for Blender", e clique em "Connect".
2. Aponte o seu cliente MCP para esta versão. Exemplo para Claude Desktop/Claude Code, já apontando para o fork:
   ```json
   {
     "mcpServers": {
       "blender": {
         "command": "uvx",
         "args": ["--from", "git+https://github.com/Henriquetin/mcp-for-blender@marcenaria", "mcp-for-blender"],
         "env": { "MARCENARIA_CATALOGO": "C:/marcenaria/catalogo.json" }
       }
     }
   }
   ```
3. Copie `src/blender_mcp/marcenaria/catalogo_exemplo.json` e troque pelos nomes **exatos** do catálogo da sua central.

## Montagem que o gerador faz

- Laterais inteiras. Base, tampo e prateleiras entre as laterais. Fundo em rasgo.
- Eixos: X = largura, Y = profundidade (frente em y=0), Z = altura. Portas e frentes de gaveta ficam sobrepostas, em y < 0.
- União: `cavilha`, `minifix` (minifix nas pontas, cavilha no meio se houver ficha de cavilha) ou `nenhuma`.
- Portas (1 ou 2): caneco conforme a ficha da dobradiça; a quantidade sai da tabela `regra_quantidade`.
- Gaveteiro: frentes sobrepostas, caixa de gaveta com fundo em rasgo, largura = vão − desconto da corrediça.
- Unicolor: c = maior lado. Amadeirado: c = veio. Rasgo sempre em C2. Peças idênticas viram `quantity`.

## Piloto: o que conferir na primeira importação

O referencial de cantos foi montado a partir do resumo do formato. Confirme no CorteCloud:

1. Furos de topo da **Base**: devem aparecer nas duas pontas (L1 e L2), a 37 mm da frente e do fundo.
2. Rasgo das **Laterais**: no lado oposto à fita (C2), a 15 mm da borda.
3. Furos de face das **Laterais**: a 7,5 mm de baixo e de cima (centro da base e do tampo).

Se algo sair espelhado ou no lado errado, o ajuste é só na tabela `CANTO_TOPO` / `_ROTACOES` em
`src/blender_mcp/marcenaria/cortecloud.py`.

## Ainda não gera

Furação de corrediça, de puxador e de calço de dobradiça na lateral; fundo sobreposto; portas de correr; móveis com divisória vertical.

## Testes

```bash
uv run pytest tests/test_marcenaria.py
```

O script de modelagem também foi rodado no Blender 5.0.1 (`pip install bpy`). Nicho e gaveteiro foram gerados e lidos de volta com 0 diferença em relação ao cálculo.
