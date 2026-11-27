# melvor-idle-2-guides

Biblioteca local de [guias de evolução](guias/index.html).

Para consultar o personagem pelo último save local, sem controlar o jogo,
execute no PowerShell:

```powershell
.\extrair-personagem.ps1
```

O relatório é gerado em `dados/personagem/relatorio.html`, acompanhado de
`estado.json` e `bonus.json`. A saída pessoal e os dados extraídos do jogo
ficam fora do Git. Veja [instalação, cobertura e limites](ferramentas/estado_personagem/README.md).

Agentes podem consultar um atributo diretamente, com atualização automática:

```powershell
.\consultar-personagem.ps1 -Habilidade Smithing -Stat SkipStepChance
```

A saída é JSON, com unidade, subtotal identificado, fontes e limites. Para
consultas em lote, use `dados/personagem/agentes.json` conforme o
[contrato do formato](ferramentas/estado_personagem/FORMATO-AGENTES.md).
