"""Regenerate the public money-making guide from the verified Steam package."""
import argparse
import json

from extract import ROOT, atomic_text, game_data, paths
from money_making import compare
from render_money_making import ASSUMPTIONS, SOURCES, SOURCE_BUILDS, render_public

GUIDE_ID = "money-making-1-40"
GUIDE_DIR = ROOT / "guides" / "money-making" / "1-40"
REFERENCE_BUILD = {
    "channel": "Steam public Early Access (Windows)",
    "version": "0.11.7-alpha",
    "steam_build": 26886380,
    "package_sha256": "9f9af1e006bc26c66a3e07dbaf93c72b5ff95e7622435a12f4223855e0ec0e04",
    "accessed_on": "2026-11-28",
}


def reference_fields(guide_id, reference_build, benchmark):
    return {
        "schema_version": 1,
        "guide_id": guide_id,
        "reference_build": reference_build,
        "benchmark_gp_per_hour": benchmark,
        "assumptions": ASSUMPTIONS,
        "formulas": {
            "gathering_or_artisan": "3600 * (final output sale GP - shop input GP) / expected total chain seconds",
            "mining_break": "interval * (1 - (1 - p)^n) / p, n = ceil(0.9999 / p) in the base case",
            "fishing_cast": "mean(min interval, max interval); GP = fish chance * weighted fish sale GP + junk chance * junk sale GP",
            "thieving_success": "min(1, (100 + stealth) / (100 + perception)); base stealth equals Thieving level",
            "thieving_rate": "3600 * (success * (mean currency + mean common sales per success) - lockpick sale value per attempt) / expected seconds per attempt including stuns",
            "combat_break_even": "3600 * (direct GP + weighted loot sale GP) / reference GP per hour, before supplies",
            "measured_gp_per_hour": "60 * (direct GP + loot sale GP - GP costs) / elapsed minutes",
            "banked_inputs": "expected product GP minus expected consumed ingredient sale GP",
        },
        "sources_used": [
            {"name": name, "url": url, "steam_build": SOURCE_BUILDS.get(name),
             "channel": "Community Early Access reference" if "melvor2.com" in url else "Steam Early Access"}
            for name, url in SOURCES.items()
        ],
    }


def audit_json(report):
    return json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", help="Game executable or directory, defaults to the Steam installation.")
    parser.add_argument("--check", action="store_true", help="Check the generated files without writing them.")
    args = parser.parse_args()
    try:
        data, origin = game_data(paths.find_exe(args.exe))
        if origin["sha256"] != REFERENCE_BUILD["package_sha256"]:
            raise ValueError("The installed package differs from the guide's reference build. Verify its changes before updating the reference.")
        report = {
            **reference_fields(GUIDE_ID, REFERENCE_BUILD, 10000),
            "personalization": {"model": "money_making"},
            **compare(data),
        }
        files = {"guide.html": render_public(report), "calculations.json": audit_json(report)}
        for name, content in files.items():
            path = GUIDE_DIR / name
            if args.check:
                if path.read_text(encoding="utf-8") != content:
                    raise ValueError(f"Generated file is out of date: {path}")
            else:
                atomic_text(path, content)
        print("Money-making guide is up to date." if args.check else "Built the public money-making guide.")
    except (OSError, ValueError, LookupError) as exc:
        parser.exit(1, f"Money-making guide build stopped: {exc}\n")


if __name__ == "__main__":
    main()
