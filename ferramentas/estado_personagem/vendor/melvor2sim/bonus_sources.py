"""Extracted from build_tables.py; see LICENSE and ORIGEM.md."""
NS = "MelvorBase:"

def short(i):
    return i[len(NS):] if isinstance(i,str) and i.startswith(NS) else i

def name_of(v):
    return v.get("Singular") if isinstance(v, dict) else v

def collect_bonuses(objects):
    """Flatten every modifier ({Stat, Value, LocalContext...}) found in any object."""
    rows = []

    def walk(node, path, src_type, src):
        if isinstance(node, dict):
            stat = node.get("Stat")
            if "Value" in node and (isinstance(stat, dict) or "StatGroup" in node):
                ctx = node.get("LocalContext") or {}
                comp = ctx.get("Component") or {}
                rows.append({
                    "source_type": src_type, "source_id": NS + src["Id"],
                    "source_name": name_of(src.get("DisplayName")), "path": path,
                    "stats_type": short(stat.get("StatsType")) if stat else None,
                    "stat": stat.get("Name") if stat else node.get("StatGroup"),
                    "value": node["Value"],
                    "entity": short(comp.get("Entity")), "component": comp.get("Component"),
                    "context": {k: v for k, v in ctx.items() if k != "Component" and v is not None},
                    "from_context": node.get("FromContext"), "condition": node.get("Condition"),
                    "scaling": node.get("Scaling"),
                })
                return
            for k, v in node.items():
                walk(v, f"{path}.{short(k)}" if path else short(k), src_type, src)
        elif isinstance(node, list):
            for v in node:
                walk(v, path, src_type, src)

    for otype, recs in objects.items():
        for rec in recs:
            if isinstance(rec, dict) and "Id" in rec:
                walk(rec, "", otype, rec)
    return rows
