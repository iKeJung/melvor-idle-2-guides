"""Refresh offline personalized guides from the latest local save."""
import argparse
from base64 import b64encode
from datetime import datetime
from html import escape
import json
from math import isfinite
from pathlib import Path
from string import Template
import sys
from time import sleep
import webbrowser

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from agent_format import build_agent_state
from extract import ROOT, atomic_text, decoder, paths, read_character
from guide_plan import calculate_guide


def number(value, digits=2):
    return f"{value:,.{digits}f}".rstrip("0").rstrip(".") if digits else f"{value:,.0f}"


def duration(seconds):
    if seconds < 60:
        return f"{round(seconds)} s"
    hours, minutes = divmod(round(seconds / 60), 60)
    return f"{hours} h {minutes:02d} min" if hours else f"{minutes} min"


def render(guide, report):
    snapshot = report["snapshot"]
    actions = report["action_models"]
    current, target = report["current"], report["target"]
    assumptions = report["assumptions"]
    stages = []
    for stage in report["stages"]:
        rate = stage["xp_gained"] * 3600 / stage["seconds"]
        steps = "".join(f"<li>{count:,} × {escape(actions[key]['name'])}</li>"
                        for key, count in ((step["id"], step["count"]) for step in stage["actions"]))
        stages.append(f'''<tr>
          <td>{stage['level_start']} → {stage['level_target']}</td>
          <td><ol>{steps}</ol></td>
          <td class="num">{number(rate, 0)}</td>
          <td class="num">{duration(stage['seconds'])}</td>
        </tr>''')

    def items(quantities):
        names = report["item_names"]
        entries = sorted(quantities.items(), key=lambda entry: names[entry[0]].casefold())
        return "".join(f"<li>{number(quantity)} {escape(names[item])}</li>" for item, quantity in entries)

    modifiers = []
    sources = report["sources"]
    for action in actions.values():
        for stat, modifier in action["modifiers"].items():
            value, unit = modifier["value"], modifier["unit"]
            display = f"{value * 100:+.2f}%" if unit == "percentage_fraction" else f"{value:+g}"
            if unit == "ms":
                display += " ms"
            source_names = sorted({
                sources[row["source"]]["name"] or sources[row["source"]]["id"]
                for row in modifier["contributions"]
            })
            modifiers.append(f"<tr><td>{escape(action['name'])}</td><td>{escape(stat)}</td>"
                             f"<td class='num'>{display}</td><td>{escape(', '.join(source_names))}</td></tr>")
    modifiers_html = "".join(modifiers) or '<tr><td colspan="4">No supported modifier contributed to the estimate.</td></tr>'

    missing = assumptions["missing_auxiliary_levels"]
    prerequisite = ""
    if missing:
        requirement = ", ".join(f"{skill} {level}" for skill, level in sorted(missing.items()))
        prerequisite = f'<p class="note">Reach {escape(requirement)} to follow this plan. The estimate excludes that training.</p>'
    feather_assumption = ""
    if "GiantChicken" in actions:
        feather_assumption = (f"<li>Giant Chicken averages {number(assumptions['expected_feathers_per_kill'])} feathers per kill. "
                              f"The model uses {number(assumptions['chicken_cycle_seconds'])} s per kill "
                              f"({escape(assumptions['chicken_cycle_source'])}), including respawn and replenishing supplies.</li>")
    save_time = datetime.fromisoformat(snapshot["save_modified_at"])
    generated = datetime.fromisoformat(snapshot["extracted_at"])
    age = max(0, (generated - save_time).total_seconds())
    audit = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    return Template((HERE / "personal-guide.html").read_text(encoding="utf-8")).substitute(
        skill=escape(report["skill"]), character=escape(snapshot["character"]), level=current["level"], xp=number(current["xp"]),
        target=target["level"], target_xp=number(target["xp"]), remaining=duration(report["seconds"]),
        xp_remaining=number(max(0, target["xp"] - current["xp"])),
        save_time=escape(save_time.isoformat(sep=" ", timespec="seconds")), save_age=duration(age),
        generated=escape(generated.isoformat(sep=" ", timespec="seconds")), save_sha=escape(snapshot["save_sha256"]),
        stages="".join(stages) or '<tr><td colspan="4">You have reached the target level.</td></tr>',
        bank_items=items(report["bank_used"]) or "<li>No banked materials used.</li>",
        gather_items=items(report["to_gather"]) or "<li>No gathering required.</li>",
        modifiers=modifiers_html, prerequisite=prerequisite, feather_assumption=feather_assumption,
        guide_path=escape(guide["artifact"], quote=True), guide_id=escape(guide["id"], quote=True),
        audit_data=b64encode(audit.encode("utf-8")).decode("ascii"),
    )


def refresh(save, exe, chicken_seconds):
    summary, decoded, data, *_ = read_character(save, exe)
    snapshot = build_agent_state(summary)
    library = ROOT / "guides"
    output = ROOT / "data" / "character" / "guides"
    catalog = json.loads((library / "catalog.json").read_text(encoding="utf-8"))
    results = []
    for guide in catalog["guides"]:
        reference = json.loads((library / guide["calculations"]).read_text(encoding="utf-8"))
        if "personalization" not in reference:
            continue
        report = calculate_guide(guide, reference, snapshot, decoded, data, decoder.XP_TABLE, chicken_seconds)
        results.append((guide["id"], render(guide, report)))
    if not results:
        raise ValueError("The library contains no guides that support character data.")
    output.mkdir(parents=True, exist_ok=True)
    for guide_id, html in results:
        guide_path = output / f"{guide_id}.html"
        atomic_text(guide_path, html)
        yield guide_path


def save_signature(save):
    stat = save.stat()
    return stat.st_mtime_ns, stat.st_size


def watch(save, exe, seconds, signature):
    print("Updating when the selected save changes. Press Ctrl+C to stop.", flush=True)
    last_error = None
    while True:
        sleep(3)
        try:
            changed = save_signature(save)
            if changed != signature:
                for report in refresh(save, exe, seconds):
                    print(f"Updated: {report}", flush=True)
                signature = changed
            last_error = None
        except (OSError, ValueError, LookupError, EOFError) as exc:
            if str(exc) != last_error:
                print(f"Guide refresh failed; retrying: {exc}", file=sys.stderr, flush=True)
                last_error = str(exc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", help="Save file or directory, defaults to the newest local save.")
    parser.add_argument("--exe", help="Game executable or directory, defaults to the Steam installation.")
    parser.add_argument("--chicken-cycle-seconds", type=float, help="Full time per Giant Chicken kill in the feather scenario.")
    parser.add_argument("--open", action="store_true", help="Open the updated guides in the default browser.")
    parser.add_argument("--watch", action="store_true", help="Keep updating when the selected save file changes.")
    args = parser.parse_args()
    seconds = args.chicken_cycle_seconds
    if seconds is not None and (not isfinite(seconds) or seconds <= 0):
        parser.error("--chicken-cycle-seconds must be positive and finite.")
    try:
        save = paths.find_save(args.save)
        exe = paths.find_exe(args.exe)
        signature = save_signature(save) if args.watch else None
        reports = list(refresh(save, exe, seconds))
    except (OSError, ValueError, LookupError, EOFError) as exc:
        parser.exit(1, f"Guide refresh stopped: {exc}\n")
    for report in reports:
        print(f"Personalized guide: {report}")
        if args.open and not webbrowser.open(report.as_uri()):
            print("Open the guide with the path above.")
    if args.watch:
        try:
            watch(save, exe, seconds, signature)
        except KeyboardInterrupt:
            print("Stopped watching the save.")


if __name__ == "__main__":
    main()
