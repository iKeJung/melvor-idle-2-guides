# Guias de Melvor Idle 2

Este projeto mantém uma biblioteca de rotas de evolução. Para criar ou revisar um guia de habilidade, leia e siga a skill [rota](.agents/skills/rota/SKILL.md).

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
