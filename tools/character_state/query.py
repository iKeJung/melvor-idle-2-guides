"""Compact JSON query; refreshes the save snapshot by default."""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from agent_format import query


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--stat")
    parser.add_argument("--component")
    parser.add_argument("--type")
    parser.add_argument("--cache", action="store_true", help="Query the existing snapshot without rereading the save")
    parser.add_argument("--save")
    parser.add_argument("--exe")
    parser.add_argument("--output", type=Path, default=HERE.parents[1] / "data" / "character")
    args = parser.parse_args(argv)
    try:
        if args.cache and (args.save or args.exe):
            raise ValueError("--save/--exe cannot be used with --cache.")
        if not args.cache:
            # Imported lazily: cached consultations need only the standard library.
            with redirect_stdout(sys.stderr):
                import extract
                extract.extract(extract.paths.find_save(args.save), extract.paths.find_exe(args.exe), args.output)
        document = json.loads((args.output / "agents.json").read_text(encoding="utf-8"))
        response = query(document, args.skill, args.stat, args.component, args.type, cached=args.cache)
    except (OSError, ValueError, LookupError, EOFError, SystemExit) as exc:
        print(json.dumps({"status": "error", "error": str(exc), "cache_used_as_fallback": False}, ensure_ascii=False))
        return 1
    print(json.dumps(response, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
