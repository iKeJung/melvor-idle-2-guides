---
name: rota
description: "Pesquise rotas de evolução de habilidades de Melvor Idle 2, considerando a cadeia de materiais, e gere guias locais de consulta por habilidade e intervalo de níveis. Use ao criar ou revisar um guia de level up neste projeto."
---

# Rota

Crie um guia pesquisado e um artefato HTML de consulta na biblioteca deste projeto. Considere o tempo de obter os ingredientes, além da fabricação final. Responda em português e preserve os nomes dos itens do jogo em inglês.

## Entrada

- Identifique a habilidade e os níveis inicial e final no pedido e no contexto atual.
- Se faltar qualquer um desses dados, pergunte em uma única mensagem: **“Qual habilidade você quer analisar e de qual nível até qual nível?”** Peça apenas os campos que faltam. Não repita perguntas já respondidas.
- Aguarde os dados obrigatórios antes de escolher a rota. Investigue fontes e a biblioteca existente enquanto isso, se útil.
- Valide que os níveis são inteiros, que o inicial é menor que o final e que a faixa existe na versão pesquisada. Não presuma que todas as habilidades ou versões tenham o mesmo limite.
- A interpretação padrão é minimizar o tempo total até o nível final, partindo do início exato do nível informado, sem estoque e com as habilidades auxiliares já nos níveis necessários. Use modificadores base como referência. Não interprete nível auxiliar suficiente como equipamentos, ranks, missões ou melhorias já desbloqueados.
- Se o usuário fornecer estoque, XP atual, equipamentos, bônus ou outro objetivo, incorpore-os. Pergunte por outras condições somente quando indispensáveis; para as demais, registre hipóteses e cenários condicionais.

## Pesquisa e cálculo

1. Confirme o jogo e a versão. O contexto padrão deste projeto é **Melvor Idle 2**; não misture receitas ou bônus do primeiro Melvor Idle. Consulte fontes atuais na web, priorizando dados extraídos do jogo, documentação de mecânicas e bases que identifiquem o build. Registre data, URLs e builds conhecidos; exponha discrepâncias relevantes.
2. Compare as opções desbloqueadas dentro da faixa e suas dependências: coleta, processamento, intermediários e ação final. Considere rendimentos por lote, chances, falhas, limites que garantem sucesso, respawn e consumíveis. Não trate o intervalo de um golpe ou de uma subetapa como o ciclo completo.
3. Calcule **XP efetivo/h = 3.600 × XP da habilidade-alvo em toda a cadeia ÷ segundos totais da cadeia**. Conte XP dos intermediários quando eles também treinarem a habilidade-alvo. XP das habilidades auxiliares é um benefício separado. Evite contar duas vezes tempo, produtos compartilhados ou XP já ganho.
4. Examine fontes alternativas relevantes: loja, combate, Thieving e produção paralela. Para compras, inclua o tempo de gerar dinheiro ou insumos quando necessário. Diferencie desbloqueio de nível de desbloqueio por guilda ou missão. Para Farming/Ranching, distinga tempo ativo e espera que realmente bloqueia a rota. Não atribua um custo independente integral a cada coproduto da mesma ação.
5. Se uma taxa depender do personagem e não puder ser medida, use uma hipótese explícita e compare limites ou cenários. Não apresente uma velocidade de combate inventada como taxa observada. Não anuncie uma rota universalmente ótima quando a análise só cobre o cenário base.
6. Calcule quantidades por etapa a partir da curva de XP verificada, arredondando lotes inteiros e carregando o XP e as sobras entre etapas. Use scripts ou cálculos executados para validar as contas. Separe tempo para desbloquear melhorias do tempo economizado por elas.

## Artefato e armazenamento

Use esta estrutura, relativa à raiz do projeto:

```text
guias/
  index.html                          # índice offline gerado
  catalogo.json                       # catálogo gerado; não editar à mão
  <habilidade-em-slug>/
    <inicio>-<fim>/
      guia.html                       # guia completo, independente e imprimível
      metadados.json                  # registro usado para gerar o índice
      calculos.json                   # premissas, entradas e resultados auditáveis
```

- Use o nome inglês da habilidade em slug minúsculo com hífens: `fletching`, `woodcutting`, `firemaking`. Não crie aliases diferentes para a mesma habilidade.
- Antes de escrever, confira o catálogo e o diretório da faixa. Se a mesma habilidade e faixa já existirem, revise o guia e preserve material útil; não crie cópias com sufixos de data ou `final-2`. Uma faixa diferente recebe outro diretório.
- `guia.html` deve abrir por `file://`, sem servidor, bibliotecas remotas ou dependência de `fetch`. Inclua índice interno, layout legível em celular, tabelas responsivas e impressão. Use o guia existente de Fletching como referência visual, sem copiar suas receitas, hipóteses ou conclusão para outra habilidade.
- O conteúdo deve permitir consulta prática: recomendação e condições, rota por faixa, materiais, tempo de cada etapa e total, comparação de alternativas, cálculo de pelo menos uma cadeia, ajustes por bônus/estoque e fontes ligadas aos fatos relevantes. Identifique o que é observado, publicado ou calculado.
- `calculos.json` deve ser um objeto JSON com `guide_id` igual ao `id` dos metadados, unidades, hipóteses, receitas/entradas utilizadas e resultados por etapa. Registre taxas não verificadas como cenários, com sua origem. Use uma organização adequada à habilidade; o HTML e os números desse arquivo devem concordar.
- Crie `metadados.json` conforme este exemplo de formato (substitua valores pelos dados da nova análise):

```json
{
  "schema_version": 1,
  "id": "fletching-1-50",
  "game": "Melvor Idle 2",
  "skill": "Fletching",
  "slug": "fletching",
  "level_start": 1,
  "level_end": 50,
  "title": "Fletching do 1 ao 50",
  "summary": "Rota com coleta e fabricação de todos os materiais.",
  "updated_on": "2026-11-27",
  "status": "referencia",
  "artifact": "guia.html",
  "calculations": "calculos.json",
  "tags": ["coleta incluída", "taxas base"]
}
```

`status`: `referencia` para uma rota calculada com hipóteses; `validado` quando também verificada no personagem/configuração descritos; `parcial` quando restarem dados relevantes indisponíveis, explicitados no guia. A data é a da criação ou revisão efetiva da análise, não a data de uma simples reconstrução do índice.

## Fechamento obrigatório

1. Verifique HTML, links internos, arquivos relativos e consistência de materiais/tempos. Não substitua pesquisa por um template preenchido com números não verificados.
2. Na raiz do projeto, execute:

   ```powershell
   python -X utf8 .agents/skills/rota/scripts/atualizar_indice.py
   python -X utf8 .agents/skills/rota/scripts/atualizar_indice.py --check
   ```

   O script valida os registros antes de gerar `guias/catalogo.json` e `guias/index.html`. A opção `--check` só verifica integridade e sincronização. Corrija falhas antes de entregar.
3. Confirme que o índice contém o novo guia e que os caminhos apontam para arquivos existentes.
4. Entregue links absolutos para **o guia final e o índice da biblioteca**. Informe brevemente a hipótese que mais afeta a recomendação. A entrega do arquivo faz parte da tarefa; não termine apenas com a pesquisa no chat.
