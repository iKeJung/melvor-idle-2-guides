"""Extract the latest saved character state without opening or controlling the game."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import struct
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from agent_format import build_agent_state
sys.path.insert(0, str(HERE / "vendor" / "melvor2sim"))
try:
    import read_save as decoder
except ModuleNotFoundError as exc:
    if exc.name != "brotli":
        raise
    raise SystemExit("Install the dependency: python -m pip install -r tools/character_state/requirements.txt")
import paths
import unpack_melvor
from bonus_sources import collect_bonuses

UPSTREAM = "091ae1a0adbc5d886d73d9e517b9054e47e2879e"
CACHE = ROOT / ".cache" / "character-state"
LIMITATIONS = [
    "Snapshot of the latest autosave on disk. Does not simulate offline progress or read game memory.",
    "Totals sum confirmed general modifiers; they are not final XP, production, or combat rates.",
    "Recipe, category, item, conditional, and scaled bonuses remain separate and are excluded from general totals.",
    "Masteries with an uncertain rank are excluded from confirmed totals.",
    "Global bonus groups are listed separately and are not automatically included in skill totals.",
    "Does not yet interpret Ranching animal/enclosure bonuses, internal Astrology events, "
    "Thieving distractions/heists, Agility techniques, environmental conditions, or combat effects/passives/stances/prayers. "
    "An empty list does not prove these sources provide no bonuses.",
]


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def atomic_text(path, value):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name, suffix=".tmp", delete=False) as handle:
        temp = Path(handle.name)
        handle.write(value)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def game_data(exe):
    """Read only the PCK JSON package, validating its checksum before use."""
    cache_dir = CACHE / "game"
    signature = {"exe": str(exe), "size": exe.stat().st_size, "mtime_ns": exe.stat().st_mtime_ns}
    cached = cache_dir / "MelvorBase.json"
    manifest = cache_dir / "origin.json"
    if cached.exists() and manifest.exists():
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        if previous["signature"] == signature:
            blob = cached.read_bytes()
            if hashlib.sha256(blob).hexdigest() == previous["sha256"]:
                return json.loads(blob.decode("utf-8-sig")), previous
    with exe.open("rb") as stream:
        base, entries = unpack_melvor.read_directory(stream)
        entry = next((e for e in entries if e[0].removeprefix("res://") == "Data/Packages/MelvorBase.json"), None)
        if entry is None:
            raise ValueError("MelvorBase.json package not found in the executable.")
        _, offset, size, checksum = entry
        stream.seek(base + offset)
        blob = stream.read(size)
    if hashlib.md5(blob).digest() != checksum:
        raise ValueError("Invalid game package checksum.")
    data = json.loads(blob.decode("utf-8-sig"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(blob)
    origin = {"signature": signature, "sha256": hashlib.sha256(blob).hexdigest()}
    dump(manifest, origin)
    return data, origin


def stable_save(path):
    for attempt in range(4):
        before = path.stat()
        try:
            blob = path.read_bytes()
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns) and len(blob) == after.st_size:
                return blob, after
        except PermissionError:
            pass
        if attempt < 3:
            time.sleep(0.15)
    raise ValueError("The save changed during reading. Run again after the autosave.")


def extra_components(blob):
    r = decoder.Reader(blob)
    header = decoder.read_header(r)
    r.version = header["version"]
    return decoder.read_entities(r)


def read_temporary(entities):
    bonfire = None
    events = []
    r = entities.get("Firemaking", {}).get("Bonfire")
    if r:
        maximum, left, paused = r.i32(), r.i32(), r.bool()
        bid, enabled = decoder.opt_str(r), r.bool()
        bonfire = {"id": bid, "max_ticks": maximum, "ticks_left": left,
                   "paused": paused, "enabled": enabled, "applies": bool(bid and enabled and left > 0)}
        if r.left:
            raise ValueError("Bonfire layout has changed.")
    for skill, components in entities.items():
        r = components.get("RareEvents")
        if r is None:
            continue
        r.bytes(13)  # TickTimer: bool + state + wait_ticks + ticks_left
        if r.bool():
            event_id = r.str()
            body = r.region()
            active, charges = body.bool(), body.i32()
            if body.left:
                raise ValueError("RareEvents layout has changed.")
            events.append({"skill": skill, "id": event_id, "active": active, "charges": charges})
        if r.left:
            raise ValueError("RareEvents layout has changed.")
    return bonfire, events


def augment_bonuses(state, data, active, bonfire, events):
    objects = data["Objects"]
    all_rows = collect_bonuses(objects)

    def add(kind, sid, via):
        for row in all_rows:
            if row["source_type"] == kind and row["source_id"] == sid:
                active.append(dict(row, via=via, multiplier=1, effective_value=row["value"]))

    if bonfire and bonfire["applies"]:
        add("FiremakingBonfire", bonfire["id"], "bonfire")
    for event in events:
        if event["active"]:
            add("RareBonusesEvent", event["id"], "rare_event:" + event["skill"])
    for slot in state["prayers"].get("slots", {}).values():
        prayer = slot.get("active")
        # Unknown activation states are deliberately not treated as active.
        if prayer:
            state["warnings"].append("A prayer is selected/activated in the save: prayer bonuses are not totaled.")

    groups = {"equipment": state["equipment"], **{"toolbelt:" + k: v for k, v in state["toolbelts"].items()}}
    for via, slots in groups.items():
        equipped = {s["item"] for s in slots.values() if s["qty"] > 0}
        for item_set in objects.get("EquipmentSetBonus", []):
            count = len(equipped.intersection(item_set["Items"]))
            for index, tier in enumerate(item_set["Bonuses"]):
                if count < tier["ItemCount"]:
                    continue
                selected = {"Id": item_set["Id"], "DisplayName": item_set["DisplayName"], "Modifiers": tier["Modifiers"]}
                for row in collect_bonuses({"EquipmentSetBonus": [selected]}):
                    active.append(dict(row, via=f"set:{via}:{index}", multiplier=1, effective_value=row["value"]))
    return active


def bonus_unit(row, data):
    descriptions = data["ComponentModifierDescriptions"]
    matches = [d for d in descriptions if (d["Key"].get("Stat") or {}).get("Name") == row["stat"]
               and decoder.short((d["Key"].get("Stat") or {}).get("StatsType")) == row["stats_type"]]
    if row["stats_type"] is None:
        matches = [d for d in data["GlobalModifierDescriptions"] if d.get("StatGroup") == row["stat"]]
    templates = [m["TemplateString"] for m in matches]
    if any(re.search(r"\{Value:[^{}]*%", t) for t in templates):
        return "percentage"
    if any("{Value:intervaltime:" in t for t in templates):
        return "ms"
    return "value"


def classify(row):
    if "UNCERTAIN" in row.get("note", ""):
        return "uncertain"
    if any(row.get(k) for k in ("context", "condition", "scaling", "from_context")):
        return "contextual"
    return "general"


def summarize(state, rows, data, origin):
    by_skill = {}
    for skill, xp in state["skills"].items():
        by_skill[skill] = {"level": xp["level"], "xp": xp["xp"], "general_bonuses": [],
                          "contextual_bonuses": [], "uncertain_bonuses": [],
                          "tools": state["toolbelts"].get(skill, {}),
                          "mastery": state.get("mastery_ranks", {}).get(skill)}
    other, totals = [], defaultdict(lambda: {"value": 0.0, "sources": []})
    for b in rows:
        b = dict(b, classification=classify(b), unit=bonus_unit(b, data))
        skill = b["entity"]
        if skill not in by_skill:
            other.append(b)
            continue
        if b["classification"] == "general":
            key = (skill, b["component"], b["stats_type"], b["stat"], b["unit"])
            totals[key]["value"] += b["effective_value"]
            totals[key]["sources"].append(b)
        else:
            by_skill[skill]["uncertain_bonuses" if b["classification"] == "uncertain" else "contextual_bonuses"].append(b)
    for (skill, component, stats_type, stat, unit), total in totals.items():
        by_skill[skill]["general_bonuses"].append({"component": component, "type": stats_type, "stat": stat,
                                              "unit": unit, "value": round(total["value"], 8), "sources": total["sources"]})
    # Global groups are retained explicitly: expanding them requires the actual
    # group's component membership, not a guess based on the stat name.
    return {"schema_version": 2, "character": state["header"]["character"],
            "mode": state["header"]["gamemode"], "total_level": sum(s["level"] for s in by_skill.values()),
            "header_total_level": state["header"]["total_level"],
            "activity": {"skill": state["header"]["active_entity"], "action": state["header"]["active_action"]},
            "origin": origin, "coverage": "partial; see limitations and contextual/uncertain bonuses",
            "limits": LIMITATIONS, "warnings": state["warnings"], "skills": by_skill,
            "other_and_global_bonuses": other}


LABELS = {"PercentXPGained": "XP", "DoublingChance": "Doubling chance",
          "PreservationChance": "Material preservation", "SkipStepChance": "Step skipping chance",
          "FlatInterval": "Interval", "PercentInterval": "Interval", "DoubleDamageChance": "Double damage chance",
          "FlatStealth": "Stealth", "FlatProficiency": "Proficiency"}


def format_value(value, unit):
    return f"{value * 100:+g}%" if unit == "percentage" else f"{value:+g}" + (" ms" if unit == "ms" else "")


def report_html(result):
    esc = lambda v: html.escape(str(v), quote=True)
    def bonus_line(b, aggregate=False):
        value = b["value"] if aggregate else b["effective_value"]
        sources = b["sources"] if aggregate else [b]
        names = "; ".join((x.get("source_name") or x["source_id"]) + " (" + x["via"] + ")" for x in sources)
        suffix = ""
        if not aggregate:
            scope = {k: b[k] for k in ("context", "condition", "scaling", "from_context", "note") if b.get(k)}
            if scope:
                suffix = "<pre>" + esc(json.dumps(scope, ensure_ascii=False, indent=2)) + "</pre>"
        return "<li><b>" + esc(LABELS.get(b["stat"], b["stat"])) + ": " + esc(format_value(value, b["unit"])) + "</b><br><small>" + esc(names) + "</small>" + suffix + "</li>"
    overview, details = [], []
    for skill, s in result["skills"].items():
        summary = "; ".join(LABELS.get(b["stat"], b["stat"]) + " " + format_value(b["value"], b["unit"]) for b in s["general_bonuses"]) or "No confirmed general modifiers"
        overview.append(f'<tr><td><a href="#{esc(skill)}">{esc(skill)}</a></td><td>{s["level"]}</td><td>{s["xp"]:,.2f}</td><td>{esc(summary)}</td></tr>')
        sections = []
        for key, title, aggregated in (("general_bonuses", "Confirmed general modifiers", True), ("contextual_bonuses", "By context / condition", False), ("uncertain_bonuses", "Unconfirmed — excluded from totals", False)):
            if s[key]:
                sections.append(f"<h3>{title}</h3><ul>" + "".join(bonus_line(b, aggregated) for b in s[key]) + "</ul>")
        if s["tools"]:
            sections.append("<h3>Toolbelt / equipped potions</h3><pre>" + esc(json.dumps(s["tools"], ensure_ascii=False, indent=2)) + "</pre>")
        details.append(f'<details id="{esc(skill)}"><summary>{esc(skill)} · level {s["level"]}</summary>' + ("".join(sections) or "<p>No bonuses identified by the covered sources.</p>") + "</details>")
    activity = result["activity"]
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Character state · Melvor Idle 2</title><style>
:root{color-scheme:dark}body{font:16px/1.5 system-ui;background:#101820;color:#eaf1f8;max-width:1150px;margin:auto;padding:28px}a{color:#7fd9bd}h1{font-size:30px}small{color:#aabaca}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #35424e}thead{background:#1b2a36}details{background:#182632;border:1px solid #35424e;border-radius:8px;margin:12px 0;padding:16px}summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;color:#b9d0dc}li{margin:12px 0}.notice{background:#302b1c;border-left:4px solid #e0b85e;padding:14px}.scroll{overflow:auto}
</style><h1>''' + esc(result["character"]) + f''' · total level {result["total_level"]}</h1><p>''' + esc(activity["skill"]) + " · " + esc(activity["action"]) + "</p><p>Latest save: " + esc(result["origin"]["save_modified_local"]) + "<br>Extracted at: " + esc(result["origin"]["extracted_at"]) + "</p><div class=notice><b>Partial coverage</b><ul>" + "".join("<li>" + esc(v) + "</li>" for v in result["limits"] + result["warnings"]) + "</ul></div><p><a href=state.json>JSON for queries and calculations</a> · <a href=bonus.json>Bonuses by source</a></p><h2>Skills</h2><div class=scroll><table><thead><tr><th>Skill</th><th>Level</th><th>Saved XP</th><th>Confirmed general modifiers</th></tr></thead><tbody>" + "".join(overview) + "</tbody></table></div><h2>Bonus sources and conditions</h2>" + "".join(details) + "<h2>Other components / unexpanded globals</h2><ul>" + "".join(bonus_line(b) for b in result["other_and_global_bonuses"]) + '</ul><p><small>Reader based on <a href="https://github.com/jtwilli/melvor2sim">melvor2sim</a> (MIT), with local adaptations. No data sent over the network.</small></p></html>'


def read_character(save, exe):
    """Return the summary, decoded save, and game data from the same extraction."""
    save, exe = save.resolve(), exe.resolve()
    data, game_origin = game_data(exe)
    tables = CACHE / "tables"
    for kind, records in data["Objects"].items():
        dump(tables / "objects" / (kind + ".json"), records)
    decoder.TABLES = tables
    blob, stat = stable_save(save)
    CACHE.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=CACHE, suffix=".sav", delete=False) as handle:
        snapshot = Path(handle.name)
        handle.write(blob)
    try:
        state = decoder.parse_save(snapshot)
        entities = extra_components(decoder.decompress(snapshot))
    except (decoder.brotli.error, struct.error) as exc:
        raise ValueError(f"Could not decode save {save.name}: {exc}") from exc
    finally:
        snapshot.unlink(missing_ok=True)
    state["save_file"] = save.name
    if not state["skills"] or any("Experience" in w for w in state["warnings"]):
        raise ValueError("Could not read all skill levels.")
    state["mastery_ranks"] = decoder.mastery_ranks(state, tables / "objects", data["EntityConfig"])
    active = decoder.active_bonuses(state, collect_bonuses(data["Objects"]), state["mastery_ranks"], tables / "objects")["active"]
    bonfire, events = read_temporary(entities)
    active = augment_bonuses(state, data, active, bonfire, events)
    for skill, rank in state["mastery_ranks"].items():
        if rank["rank_min"] != rank["rank_max"]:
            state["warnings"].append(f"{skill}: mastery rank between {decoder.short(rank['rank_min'])} and {decoder.short(rank['rank_max'])}; uncertain bonuses kept separate.")
    origin = {"save": str(save), "save_sha256": hashlib.sha256(blob).hexdigest(), "save_version": state["header"]["version"],
              "character_id": state["header"]["uuid"],
              "save_modified_local": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
              "extracted_at": datetime.now(timezone.utc).astimezone().isoformat(), "game_package": game_origin,
              "upstream_commit": UPSTREAM}
    result = summarize(state, active, data, origin)
    if result["total_level"] != result["header_total_level"]:
        result["warnings"].append("The sum of skill levels differs from the save header; inspect individual skills.")
    return result, state, data, active, bonfire, events


def extract(save, exe, output):
    save, exe, output = save.resolve(), exe.resolve(), output.resolve()
    if output.is_relative_to(save.parent) or output.is_relative_to(exe.parent):
        raise ValueError("Output must be outside the save and game directories.")
    result, state, _, active, bonfire, events = read_character(save, exe)
    output.mkdir(parents=True, exist_ok=True)
    dump(output / "state.json", result)
    dump(output / "bonus.json", {"origin": result["origin"], "bonus": active, "bonfire": bonfire, "rare_events": events, "limits": LIMITATIONS})
    dump(output / "decoded_state.json", state)
    atomic_text(output / "report.html", report_html(result))
    dump(output / "agents.json", build_agent_state(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", help=".sav file or directory; default: latest save in AppData")
    parser.add_argument("--exe", help="Melvor2.exe or directory; default: detected in Steam libraries")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "character")
    args = parser.parse_args()
    try:
        result = extract(paths.find_save(args.save), paths.find_exe(args.exe), args.output)
    except (OSError, ValueError, EOFError, KeyError) as exc:
        parser.exit(1, f"Extraction stopped: {exc}\n")
    print(f"{result['character']} | total level {result['total_level']} | save v{result['origin']['save_version']}")
    print(", ".join(f"{k} {s['level']}" for k, s in result["skills"].items()))
    for warning in result["warnings"]:
        print("WARNING:", warning)
    print("Report:", (args.output / "report.html").resolve())
    print("JSON:", (args.output / "state.json").resolve())


if __name__ == "__main__":
    main()
