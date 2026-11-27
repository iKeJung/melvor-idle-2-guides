"""Consulta compacta em JSON; por padrão atualiza o save antes de responder."""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from formato_agentes import query


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", "--habilidade", required=True)
    parser.add_argument("--stat")
    parser.add_argument("--componente")
    parser.add_argument("--tipo")
    parser.add_argument("--cache", action="store_true", help="Consulta o snapshot existente sem reler o save")
    parser.add_argument("--save")
    parser.add_argument("--exe")
    parser.add_argument("--saida", type=Path, default=HERE.parents[1] / "dados" / "personagem")
    args = parser.parse_args(argv)
    try:
        if args.cache and (args.save or args.exe):
            raise ValueError("--save/--exe não podem ser usados com --cache.")
        if not args.cache:
            # Imported lazily: cached consultations need only the standard library.
            with redirect_stdout(sys.stderr):
                import extrair
                extrair.extract(extrair.paths.find_save(args.save), extrair.paths.find_exe(args.exe), args.saida)
        document = json.loads((args.saida / "agentes.json").read_text(encoding="utf-8"))
        response = query(document, args.skill, args.stat, args.componente, args.tipo, cached=args.cache)
    except (OSError, ValueError, LookupError, EOFError, SystemExit) as exc:
        print(json.dumps({"status": "erro", "erro": str(exc), "cache_usado_como_fallback": False}, ensure_ascii=False))
        return 1
    print(json.dumps(response, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
