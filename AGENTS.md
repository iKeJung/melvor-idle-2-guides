# Guias de Melvor Idle 2

Este projeto mantém uma biblioteca de rotas de evolução. Para criar ou revisar um guia de habilidade, leia e siga a skill [rota](.agents/skills/rota/SKILL.md).

## Consulta do personagem por agentes

Quando o usuário perguntar sobre **seu personagem** (nível, XP, bônus,
equipamentos ou melhorias), consulte os saves locais por comando. O fluxo
não exige controle da interface, screenshots, exportação manual ou envio do
save para sites.

Na raiz do projeto, prefira uma consulta específica:

```powershell
.\consultar-personagem.ps1 -Habilidade Smithing -Stat SkipStepChance
```

- A consulta **atualiza a leitura do save por padrão** e retorna JSON em stdout.
  Verifique o código de saída e `status`; em erro, não trate a saída anterior
  como atual. `-Cache` é uma opção explícita para consultar um snapshot sem
  atualizá-lo; informe sua data e essa limitação ao responder.
- Sem `-Stat`, retorna nível, XP e todos os modificadores identificados para
  a habilidade. Preserve os IDs ingleses do jogo, por exemplo `Smithing`,
  `SkipStepChance`, `DoublingChance` e `PercentXPGained`. A busca ignora caixa.
  Para atributo ambíguo, adicione `-Componente Action -Tipo ArtisanAction`.
- Para equipamentos/toolbelts e maestrias, atualize a leitura e consulte
  `estado.json` em `habilidades.<Skill>.ferramentas` / `maestria`;
  equipamento de combate e inventário ficam em `estado_decodificado.json`.
- Confirme `snapshot.personagem`, `snapshot.personagem_id`, data do save e
  `snapshot.idade_save_segundos`. O padrão escolhe o `.sav` mais recente;
  use `-Save 'caminho\save_personagem.sav'` se houver um personagem específico.
- Leia `modificador.geral_confirmado.valor` junto com `unidade`. A unidade
  `fracao_percentual` usa `0.06 = 6%`; o campo `percentual` já contém `6`.
  `ms` significa milissegundos. Não converta `valor_do_jogo` sem verificar
  sua mecânica.
- **É um subtotal de modificadores identificados, não uma chance/taxa final.**
  `completo: false` e `valor_final: null` são intencionais. Contextuais,
  incertos e grupos globais não entram no subtotal. Só aplique condicionais
  quando o contexto da ação corresponder e a condição puder ser verificada;
  não some grupos globais ou fontes novamente ao subtotal.
- `status: nao_identificado`, `modificador: null` ou `geral_confirmado: null`
  significam valor desconhecido, **nunca zero**. Um subtotal numérico `0` é
  diferente de ausência. Consulte sempre `cobertura`, `contextuais`,
  `incertos`, `outros_bonus_e_globais` e `fontes` antes de concluir.
- Ao responder, priorize valor identificado e fontes; mencione limitações
  que afetem a conclusão. Em cálculos personalizados, registre o SHA-256 do
  snapshot e os modificadores usados como premissas. Não substitua as
  hipóteses de uma rota genérica por dados pessoais sem pedido/contexto para isso.

O arquivo gerado `dados/personagem/agentes.json` é a interface de consulta
em lote, indexada por
`habilidades.<Skill>.modificadores.<Componente>.<Tipo>.<Stat>`.
Para atualizar todos os arquivos, execute `.\extrair-personagem.ps1`.
Formato, exemplos e limites: [FORMATO-AGENTES.md](ferramentas/estado_personagem/FORMATO-AGENTES.md).
Instalação e interpretação detalhada: [README da ferramenta](ferramentas/estado_personagem/README.md).
Os saves e snapshots pessoais permanecem ignorados pelo Git.

## Skill disponível no projeto

- **rota** — Pesquisa a habilidade e o intervalo de níveis, calcula a cadeia de materiais e entrega um artefato de consulta. Entrada: [.agents/skills/rota/SKILL.md](.agents/skills/rota/SKILL.md).

## Fluxo para cada novo guia

1. Obtenha a habilidade e os níveis inicial/final; pergunte somente pelos dados ausentes.
2. Pesquise Melvor Idle 2 e registre fontes, versão e hipóteses. Considere as habilidades auxiliares já nos níveis necessários, incluindo o tempo de obter e processar os materiais.
3. Salve `guia.html`, `metadados.json` e `calculos.json` em `guias/<habilidade>/<inicio>-<fim>/`.
4. Atualize o guia existente quando a habilidade e a faixa coincidirem. Use outro diretório para outra faixa. Não espalhe novos guias na raiz.
5. Execute o gerador do índice e seu `--check`, conforme a skill. `guias/index.html` e `guias/catalogo.json` são gerados a partir dos metadados.
6. Entregue links para o guia e para a biblioteca. A tarefa só está concluída com o artefato salvo e incluído no índice.

Exemplos de uso: `Use $rota` ou `Crie uma rota de Woodcutting do 10 ao 50`. No primeiro caso, a skill deve perguntar a habilidade e a faixa; no segundo, já pode começar a pesquisa.
