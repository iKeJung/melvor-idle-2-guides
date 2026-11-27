# Contrato de consulta para agentes — v1

`agentes.json` é uma projeção indexada de `estado.json`, gerada pela mesma
extração. O formato detalhado anterior permanece disponível. Identificação:

```json
{"formato": "melvor2-personagem-agentes", "schema_version": 1}
```

Alterações incompatíveis exigem outra `schema_version`; consumidores devem
recusar versões desconhecidas. IDs de habilidade, componente, tipo e atributo
são os IDs ingleses do jogo. Consultas aceitam diferenças de caixa, sem
adivinhar aliases ou confundir atributos de componentes diferentes.

## Consulta recomendada

```powershell
.\consultar-personagem.ps1 -Habilidade Smithing -Stat SkipStepChance
.\consultar-personagem.ps1 -Habilidade Smithing
.\consultar-personagem.ps1 -Habilidade Smithing -Stat SkipStepChance -Componente Action -Tipo ArtisanAction
```

Equivalente direto, inclusive para chamadas por subprocessos:

```powershell
.\.venv\Scripts\python.exe -X utf8 -I ferramentas\estado_personagem\consultar.py --skill Smithing --stat SkipStepChance
```

Por padrão, a consulta relê o save, regenera os snapshots e só então retorna
o resultado em JSON UTF-8. Mensagens de extração vão para stderr. Código de
saída `0` significa consulta executada, mas o agente ainda deve verificar
`status`: `encontrado` ou `nao_identificado`. Código não zero indica erro.
Não há fallback automático para arquivo antigo. Argumentos inválidos podem
ser reportados pelo argparse/PowerShell em stderr.

Com `-Cache` / `--cache`, lê apenas `agentes.json`; não relê o jogo nem valida
que o save permaneça igual. A resposta marca `leitura: cache`. A data de
extração pode ser recente e o save antigo: confira **ambas as datas**, a idade
do save e o personagem. `-Save`, `-Exe` e `-Saida` correspondem aos argumentos
da extração; `-Save`/`-Exe` não são aceitos com `-Cache`.

## Estrutura indexada

O caminho de um atributo é:

```text
habilidades.Smithing.modificadores.Action.ArtisanAction.SkipStepChance
```

Exemplo de nó (valores ilustrativos):

```json
{
  "unidade": "fracao_percentual",
  "geral_confirmado": {
    "valor": 0.06,
    "percentual": 6,
    "contribuicoes": [
      {"fonte": "f_exemplo_luvas", "valor": 0.01},
      {"fonte": "f_exemplo_bigorna", "valor": 0.05}
    ]
  },
  "contextuais": [],
  "incertos": [],
  "valor_final": null,
  "completo": false
}
```

`fontes` resolve as referências em uma única tabela, com `tipo`, `id`, `nome`
e `via`. As chaves reais são determinísticas, derivadas de tipo, ID e via;
não são números de posição. Contribuições contextuais/incertas preservam
`contexto`, `condicao`, `escala`, `from_context` e `nota` quando presentes.
O valor de uma contribuição escalada é o coeficiente registrado, não o
resultado de uma escala que ainda não foi avaliada.

Cada habilidade também tem `nivel` e `xp`. O documento contém `nivel_total`,
`atividade`, `snapshot`, `cobertura` e `outros_bonus_e_globais`. O snapshot
identifica personagem/UUID, modo, versão do save, SHA-256 do save e do pacote
do jogo, horário do save e horário da extração, ambos ISO 8601 com fuso.

## Resposta de uma consulta

A resposta usa `formato: melvor2-personagem-agentes-consulta`, versão `1`,
com `status`, `leitura`, `snapshot`, `habilidade`, `nivel`, `xp`, `cobertura`,
`modificador` e somente as `fontes` referenciadas. Sem `--stat`, retorna
`modificadores` para a habilidade inteira. `snapshot.idade_save_segundos`
é calculada no momento da consulta.

`outros_bonus_e_globais` inclui os candidatos de outros componentes para o
mesmo atributo e **todos os grupos globais**, pois nomes de grupos podem
ser diferentes do atributo. A presença de um candidato não confirma que ele
se aplique à habilidade consultada. A expansão de grupos globais não é feita.

## Regras numéricas

- `fracao_percentual`: `valor * 100` para exibição; `0.06` representa `6%`.
  `percentual` é somente uma conversão de unidade, não outra contribuição.
- `ms`: valor em milissegundos, com sinal preservado.
- `valor_do_jogo`: unidade não inferida; mantenha o valor bruto e confira a
  descrição/mecânica antes de usá-lo em cálculos.
- `geral_confirmado` soma apenas modificadores gerais confirmados pelas
  fontes cobertas. As parcelas em `contribuicoes` **já estão incluídas**.
- `valor_final: null` e `completo: false` impedem confundir o subtotal com o
  valor final do jogo. Bases, limites, multiplicadores e fontes ainda não
  interpretadas não são modelados por esta interface.
- Bônus contextuais/incertos e globais não entram no subtotal. Não os aplique
  sem verificar contexto, condições, escala e regras de combinação.
- Atributo ausente retorna `status: nao_identificado` e `modificador: null`.
  Atributo apenas contextual/incerto tem `geral_confirmado: null`. **Nenhum
  desses casos significa zero.** Um `valor: 0` explícito é um subtotal conhecido.
- Múltiplas correspondências de atributo causam erro; selecione componente
  e tipo. Habilidade inexistente ou versão incompatível também causam erro.

Cobertura permanece parcial e é declarada em cada resposta. Este formato
organiza o conhecimento disponível; não amplia as fontes interpretadas pelo
leitor. Use `estado.json`, `bonus.json` e `estado_decodificado.json` para uma
auditoria mais detalhada.
