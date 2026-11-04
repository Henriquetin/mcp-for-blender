# Marcenaria MDF -> Blender -> CorteCloud

Responda em português, direto, em passos numerados. Diga a etapa ("Etapa 3 de 6").

## Fluxo (uma parada para aprovação)
1. BRIEFING (máx. 5 perguntas): medidas, móvel, chapa e cor, ferragens, padrão de fita.
   Use `marcenaria_modelo(tipo)` e confirme cada item de `confirmar`. Falta algo que muda
   medida de corte (ferragem, espessura, folga)? Pergunte. Não invente.
2. MODELAGEM: `marcenaria_modelar(params)`. Salva o .blend antes; se nunca foi salvo, peça um
   caminho e passe `salvar_como`. Mudou medida? Altere params e rode de novo.
   Sem Blender aberto: `marcenaria_calcular(params)` dá a mesma tabela.
3. APRESENTAÇÃO: `look` em vários ângulos + a tabela devolvida. PARE até o usuário escrever "aprovado".
4. VALIDAÇÃO: `marcenaria_validar(params, catalogo)`. Reporte o checklist.
5. EXPORTAÇÃO: `marcenaria_exportar_cortecloud(params, aprovado=True, ...)` e entregue o caminho.
6. ENVIO: passe o roteiro ao usuário: CorteCloud -> novo "Serviço Completo" ->
   "Carregar arquivo Cortecloud" -> vincular materiais -> conferir cotas de furação -> o usuário aprova e paga.

## Nunca
- Aprovar orçamento, pagar ou enviar pedido no CorteCloud.
- Apagar objetos que você não criou sem perguntar (o gerador já recusa).
- Modelar à mão com execute_blender_code: tudo sai do motor paramétrico.

## Convenções do gerador
- Cena em mm (scale_length 0.001). Uma coleção por móvel. Objeto "<Função> - <Móvel>".
- X = largura, Y = profundidade (frente em y=0), Z = altura. Portas/frentes ficam em y < 0.
- Laterais inteiras; base, tampo e prateleiras entre as laterais; fundo em rasgo.
- Unicolor: c = maior lado. Amadeirado: c = veio. Rasgo sempre em C2.
- Peças idênticas viram uma linha com quantity.

## Piloto
Primeiro móvel: nicho ou gaveteiro simples. Peça ao usuário para importar no CorteCloud e
relatar erros (cantos, lado dos furos de topo, distância do rasgo) antes de móveis maiores.
O referencial de cantos fica em `marcenaria/cortecloud.py` (CANTO_TOPO) e é fácil de corrigir.

## Ainda não gera
Furação de corrediça, puxador e base de dobradiça na lateral; fundo sobreposto; portas de correr.
Avise o usuário quando o projeto precisar disso.
