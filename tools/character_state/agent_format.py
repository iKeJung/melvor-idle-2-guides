"""Query contract v2: stable indexes and subtotals with provenance."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

FORMAT = "melvor2-character-agents"
VERSION = 2
UNITS = {"percentage": "percentage_fraction", "ms": "ms", "value": "game_value"}


def build_agent_state(state):
    sources = {}

    def contribution(row):
        identity = {k: row[k] for k in ("source_type", "source_id", "via")}
        key = "s_" + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
        source = {"type": identity["source_type"], "id": identity["source_id"],
                  "name": row.get("source_name"), "via": identity["via"]}
        if key in sources and sources[key] != source:
            raise ValueError("Conflicting source identifier.")
        sources[key] = source
        result = {"source": key, "value": row["effective_value"]}
        for key_name in ("context", "condition", "scaling", "from_context", "note"):
            if row.get(key_name):
                result[key_name] = deepcopy(row[key_name])
        return result

    def node(index, component, kind, stat, unit):
        stats = index.setdefault(component, {}).setdefault(kind, {})
        target = stats.setdefault(stat, {"unit": UNITS[unit], "confirmed_general": None,
                                        "contextual": [], "uncertain": [],
                                        "final_value": None, "complete": False})
        if target["unit"] != UNITS[unit]:
            raise ValueError(f"Mismatched units for {component}.{kind}.{stat}.")
        return target

    skills = {}
    for name, skill in state["skills"].items():
        index = {}
        for total in skill["general_bonuses"]:
            target = node(index, total["component"], total["type"], total["stat"], total["unit"])
            if target["confirmed_general"] is not None:
                raise ValueError("Duplicate subtotal in source state.")
            target["confirmed_general"] = {"value": total["value"],
                                          "contributions": [contribution(r) for r in total["sources"]]}
            if total["unit"] == "percentage":
                target["confirmed_general"]["percentage"] = round(total["value"] * 100, 8)
        for group, source_group in (("contextual", "contextual_bonuses"), ("uncertain", "uncertain_bonuses")):
            for row in skill[source_group]:
                target = node(index, row["component"], row["stats_type"], row["stat"], row["unit"])
                target[group].append(contribution(row))
        skills[name] = {"level": skill["level"], "xp": skill["xp"], "modifiers": index}

    other = []
    for row in state["other_and_global_bonuses"]:
        other.append({"entity": row["entity"], "component": row["component"], "type": row["stats_type"],
                      "stat": row["stat"], "unit": UNITS[row["unit"]],
                      "classification": row["classification"], **contribution(row)})
    origin = state["origin"]
    return {"format": FORMAT, "schema_version": VERSION,
            "snapshot": {"character": state["character"], "mode": state["mode"],
                         "character_id": origin.get("character_id"),
                         "save_modified_at": origin["save_modified_local"],
                         "extracted_at": origin["extracted_at"], "save_sha256": origin["save_sha256"],
                         "save_version": origin["save_version"],
                         "game_package_sha256": origin["game_package"]["sha256"]},
            "coverage": {"complete": False, "value_type": "confirmed_general_modifier_subtotal",
                          "globals_included_in_subtotals": False, "absence_means_zero": False,
                          "limits": list(state["limits"]), "warnings": list(state["warnings"])},
            "total_level": state["total_level"], "activity": deepcopy(state["activity"]),
            "skills": skills, "other_and_global_bonuses": other, "sources": sources}


def validate_version(document):
    if document.get("format") != FORMAT or document.get("schema_version") != VERSION:
        raise ValueError("Incompatible query format; regenerate the snapshot.")


def _resolve(mapping, name, label):
    matches = [key for key in mapping if key.casefold() == name.casefold()]
    if not matches:
        raise LookupError(f"{label} '{name}' not found. Available: {', '.join(mapping)}")
    return matches[0]


def query(document, skill, stat=None, component=None, kind=None, *, cached=False):
    validate_version(document)
    name = _resolve(document["skills"], skill, "Skill")
    data = document["skills"][name]
    snapshot = deepcopy(document["snapshot"])
    modified = datetime.fromisoformat(snapshot["save_modified_at"])
    if modified.tzinfo is None:
        raise ValueError("Snapshot has no time zone.")
    snapshot["save_age_seconds"] = round((datetime.now(timezone.utc) - modified).total_seconds(), 1)
    response = {"format": FORMAT + "-query", "schema_version": VERSION,
                "status": "found", "read_mode": "cache" if cached else "refreshed_save",
                "snapshot": snapshot, "skill": name, "level": data["level"], "xp": data["xp"],
                "coverage": deepcopy(document["coverage"])}
    if stat is None:
        if component or kind:
            raise ValueError("Use --stat to filter component/type.")
        response["modifiers"] = deepcopy(data["modifiers"])
    else:
        matches = []
        for comp, kinds in data["modifiers"].items():
            if component and component.casefold() != comp.casefold():
                continue
            for stats_type, values in kinds.items():
                if kind and kind.casefold() != stats_type.casefold():
                    continue
                for key, value in values.items():
                    if key.casefold() == stat.casefold():
                        matches.append({"component": comp, "type": stats_type, "stat": key, **deepcopy(value)})
        if len(matches) > 1:
            choices = ", ".join(f"{m['component']}.{m['type']}.{m['stat']}" for m in matches)
            raise ValueError(f"Ambiguous query; specify --component and/or --type: {choices}")
        response["modifier"] = matches[0] if matches else None
        if not matches:
            response["status"] = "unidentified"
            response["query"] = {"stat": stat, "component": component, "type": kind}

    # Return other/global candidates for this stat; never apply them implicitly.
    response["other_and_global_bonuses"] = deepcopy([r for r in document["other_and_global_bonuses"]
                                                   if stat is None or r["stat"].casefold() == stat.casefold()
                                                   or r["entity"] is None])
    refs = set()
    def walk(value):
        if isinstance(value, dict):
            if "source" in value:
                refs.add(value["source"])
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(response)
    response["sources"] = {key: deepcopy(document["sources"][key]) for key in sorted(refs)}
    return response
