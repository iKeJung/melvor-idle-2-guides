# Estado do personagem

Leitura local do último autosave de **Melvor Idle 2 no Steam/Windows**, sem
abrir janelas ou controlar a interface. Testado no save v32 e build Steam
26886380. O leitor também aceita o formato v31; outras versões são recusadas.

Na raiz do projeto, prepare o ambiente uma vez:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ferramentas\estado_personagem\requirements.txt
```

Depois, atualize por comando:

```powershell
.\extrair-personagem.ps1
```

O script encontra o jogo nas bibliotecas Steam e lê o `.sav` mais recente em
`%APPDATA%\Games By Malcs\Melvor Idle 2`. Com vários personagens, selecione o
arquivo explicitamente para evitar ler outro personagem:

```powershell
.\extrair-personagem.ps1 -Save 'C:\caminho\save_personagem.sav'
```

Também aceita `-Exe 'F:\SteamLibrary\steamapps\common\Melvor Idle 2\Melvor2.exe'`
e `-Saida 'F:\Melvor-idle-2\dados\personagem'`. Funciona a partir de outro
diretório quando o caminho do `.ps1` é absoluto. Não instala mods nem escreve
no save, na pasta do jogo ou no AppData. Após a instalação, roda sem rede.

Saídas em `dados/personagem/`:

- `relatorio.html`: níveis, XP, bônus gerais por habilidade e detalhes das fontes.
- `estado.json`: retrato consolidado para consultas futuras e cálculos de rotas.
- `agentes.json`: índice compacto por habilidade/componente/tipo/atributo,
  com fontes deduplicadas e distinção explícita entre subtotal e valor final.
- `bonus.json`: modificadores por fonte e estado de Bonfire/eventos raros.
- `estado_decodificado.json`: dados intermediários, como toolbelts, compras,
  pets, astrologia, maestrias, equipamento e inventário.

Os arquivos são locais e ignorados pelo Git, assim como `.cache/` (dados
proprietários do jogo) e `.venv/`. O script não transfere seu save para sites.
Não é um monitor contínuo: execute novamente para atualizar. A data do save e
o SHA-256 identificam o retrato lido. Uma gravação concorrente é repetida e a
decodificação ocorre em cópia temporária. Em erro, a última saída bem-sucedida
permanece; confira sempre a data no relatório.

## Consulta por agentes

```powershell
.\consultar-personagem.ps1 -Habilidade Smithing -Stat SkipStepChance
```

A consulta atualiza o save por padrão e retorna somente o resultado pedido em
JSON, com unidade, fontes, data, identidade do personagem e cobertura.
Sem `-Stat`, retorna os modificadores da habilidade. `-Cache` consulta o
snapshot já gerado, marcando que não houve atualização. Falhas não usam cache
automaticamente. Veja o [contrato v1 e exemplos](FORMATO-AGENTES.md); as regras
de uso pelos agentes estão no `AGENTS.md` da raiz.

## Como interpretar os bônus

`habilidades.<nome>.bonus_gerais` soma somente modificadores confirmados e sem
contexto. A origem de cada parcela aparece em `fontes`. `valor` mantém a
unidade original do jogo: `0.03` com `unidade: percentual` aparece como `+3%`;
`-100` com `unidade: ms` corresponde a `-100 ms`. O relatório não calcula a
chance final nem aplica pisos, tetos ou multiplicadores das ações.

`bonus_contextuais` preserva receita/categoria/item, condição e escala. Por
exemplo, a cesta de Flax só modifica a receita Flax Bush. Esses bônus não
devem ser somados indiscriminadamente à habilidade inteira. `bonus_incertos`
contém maestrias cujo rank não pode ser determinado pelo leitor; não entra
nos totais confirmados. Modificadores de outros componentes e grupos globais
ficam em `outros_bonus_e_globais`, sem expansão implícita para cada habilidade.

Cobertura: toolbelts e poções equipadas, equipamento ativo, conjuntos com
quantidade mínima de peças, compras, pets, nós permanentes de Astrology,
maestrias, Hunting Journal, isca de Fishing, Bonfire habilitada com tempo
restante e eventos RareEvents ativados.

Limites: bônus de animais/enclosures de Ranching, eventos internos de
Astrology, distrações/heists de Thieving, técnicas de Agility, condições
ambientais e efeitos/passivas/stances/orações de combate ainda não são
totalizados. O snapshot não avança o progresso offline. **Uma lista vazia não
significa que o personagem não tenha bônus dessas fontes.** A cobertura é
parcial, exposta também no JSON e no relatório.

## Verificação

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s ferramentas\estado_personagem -p 'test_*.py' -v
```

Testes usam dados sintéticos e cobrem o ícone de abas v32, compatibilidade
v31, fronteiras de XP, regiões inválidas, equipamentos de duas mãos,
separação de bônus contextuais/incertos/globais, conjuntos por número de
peças e duração/ativação de Bonfire. A extração real foi validada contra a
soma dos níveis no cabeçalho; não houve conferência visual dentro do jogo.

Leitor adaptado do projeto MIT [melvor2sim](https://github.com/jtwilli/melvor2sim),
com proveniência e alterações em [ORIGEM.md](vendor/melvor2sim/ORIGEM.md).
