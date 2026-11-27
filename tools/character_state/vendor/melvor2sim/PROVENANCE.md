# Third-party code

Source: https://github.com/jtwilli/melvor2sim
Commit: `091ae1a0adbc5d886d73d9e517b9054e47e2879e`
License: MIT, preserved in `LICENSE`.

`paths.py` and `unpack_melvor.py` are unchanged upstream copies. `bonus_sources.py` contains `name_of` and `collect_bonuses` from `build_tables.py`, together with their helpers. Local adaptations to `read_save.py`:

- Accept only saves v31/v32.
- Read each bank tab's optional icon in v32.
- Propagate the version to region readers and validate region boundaries.
- Ignore equipment slots occupied by another slot (two-handed weapons) and items without quantity, preventing duplicate bonuses.

The v32 format and Bonfire, RareEvents, and EquipmentSetBonus rules were checked by locally inspecting `GamesByMalcs.Melvor2.dll`, Steam build 26886380. No proprietary game files are distributed in this project.
