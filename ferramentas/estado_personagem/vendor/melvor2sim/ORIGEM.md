# Código de terceiros

Origem: https://github.com/jtwilli/melvor2sim
Commit: `091ae1a0adbc5d886d73d9e517b9054e47e2879e`
Licença: MIT, preservada em `LICENSE`.

`paths.py` e `unpack_melvor.py` são cópias do upstream. `bonus_sources.py`
contém `name_of` e `collect_bonuses` de `build_tables.py`, com os auxiliares
necessários. `read_save.py` recebeu adaptações locais:

- aceita somente saves v31/v32;
- v32 lê o ícone opcional de cada aba do banco;
- propaga a versão aos leitores de regiões e valida seus limites;
- ignora slots de equipamentos ocupados por outro slot (armas de duas mãos)
  e itens sem quantidade, evitando bônus duplicados.

O formato v32 e as regras de Bonfire, RareEvents e EquipmentSetBonus foram
conferidos por inspeção local de `GamesByMalcs.Melvor2.dll`, build Steam
26886380. Nenhum arquivo proprietário do jogo é distribuído neste projeto.
