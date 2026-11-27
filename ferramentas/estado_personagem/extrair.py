"""Extrai o último estado salvo do personagem sem abrir ou controlar o jogo."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from formato_agentes import build_agent_state
sys.path.insert(0, str(HERE / "vendor" / "melvor2sim"))
try:
    import read_save as decoder
except ModuleNotFoundError as exc:
    if exc.name != "brotli":
        raise
    raise SystemExit("Instale a dependência: python -m pip install -r ferramentas/estado_personagem/requirements.txt")
import paths
import unpack_melvor
from bonus_sources import collect_bonuses

UPSTREAM = "091ae1a0adbc5d886d73d9e517b9054e47e2879e"
CACHE = ROOT / ".cache" / "estado-personagem"
LIMITES = [
    "Retrato do último autosave em disco. Não simula progresso offline nem lê a memória do jogo.",
    "Totais somam modificadores gerais confirmados; não são taxas finais de XP, produção ou combate.",
    "Bônus por receita, categoria, item, condição ou escala ficam separados; não entram nos totais gerais.",
    "Maestrias com rank incerto ficam fora dos totais confirmados.",
    "Grupos de bônus globais são listados separadamente e não entram automaticamente nos totais por habilidade.",
    "Ainda não interpreta bônus de animais/enclosures de Ranching, eventos internos de Astrology, "
    "distrações/heists de Thieving, técnicas de Agility, condições ambientais e efeitos/passivas/stance/orações de combate. "
    "Uma lista vazia não comprova ausência de bônus nessas fontes.",
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
    """Lê apenas o pacote JSON do PCK, validando o checksum antes de usá-lo."""
    cache_dir = CACHE / "jogo"
    signature = {"exe": str(exe), "size": exe.stat().st_size, "mtime_ns": exe.stat().st_mtime_ns}
    cached = cache_dir / "MelvorBase.json"
    manifest = cache_dir / "origem.json"
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
            raise ValueError("Pacote MelvorBase.json não encontrado no executável.")
        _, offset, size, checksum = entry
        stream.seek(base + offset)
        blob = stream.read(size)
    if hashlib.md5(blob).digest() != checksum:
        raise ValueError("Checksum inválido no pacote do jogo.")
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
    raise ValueError("Save mudou durante a leitura. Execute novamente após o autosave.")


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
            raise ValueError("Layout de Bonfire mudou.")
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
                raise ValueError("Layout de RareEvents mudou.")
            events.append({"skill": skill, "id": event_id, "active": active, "charges": charges})
        if r.left:
            raise ValueError("Layout de RareEvents mudou.")
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
            state["warnings"].append("Prayer selecionada/ativada no save: bônus de oração não totalizados.")

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
        return "percentual"
    if any("{Value:intervaltime:" in t for t in templates):
        return "ms"
    return "valor"


def classify(row):
    if "UNCERTAIN" in row.get("note", ""):
        return "incerto"
    if any(row.get(k) for k in ("context", "condition", "scaling", "from_context")):
        return "contextual"
    return "geral"


def summarize(state, rows, data, origin):
    by_skill = {}
    for skill, xp in state["skills"].items():
        by_skill[skill] = {"nivel": xp["level"], "xp": xp["xp"], "bonus_gerais": [],
                          "bonus_contextuais": [], "bonus_incertos": [],
                          "ferramentas": state["toolbelts"].get(skill, {}),
                          "maestria": state.get("mastery_ranks", {}).get(skill)}
    other, totals = [], defaultdict(lambda: {"valor": 0.0, "fontes": []})
    for b in rows:
        b = dict(b, classificacao=classify(b), unidade=bonus_unit(b, data))
        skill = b["entity"]
        if skill not in by_skill:
            other.append(b)
            continue
        if b["classificacao"] == "geral":
            key = (skill, b["component"], b["stats_type"], b["stat"], b["unidade"])
            totals[key]["valor"] += b["effective_value"]
            totals[key]["fontes"].append(b)
        else:
            by_skill[skill]["bonus_incertos" if b["classificacao"] == "incerto" else "bonus_contextuais"].append(b)
    for (skill, component, stats_type, stat, unit), total in totals.items():
        by_skill[skill]["bonus_gerais"].append({"componente": component, "tipo": stats_type, "stat": stat,
                                              "unidade": unit, "valor": round(total["valor"], 8), "fontes": total["fontes"]})
    # Global groups are retained explicitly: expanding them requires the actual
    # group's component membership, not a guess based on the stat name.
    return {"schema_version": 1, "personagem": state["header"]["character"],
            "modo": state["header"]["gamemode"], "nivel_total": sum(s["nivel"] for s in by_skill.values()),
            "nivel_total_cabecalho": state["header"]["total_level"],
            "atividade": {"habilidade": state["header"]["active_entity"], "acao": state["header"]["active_action"]},
            "origem": origin, "cobertura": "parcial; consulte limites e bônus contextuais/incertos",
            "limites": LIMITES, "avisos": state["warnings"], "habilidades": by_skill,
            "outros_bonus_e_globais": other}


LABELS = {"PercentXPGained": "XP", "DoublingChance": "Chance de duplicação",
          "PreservationChance": "Preservação de materiais", "SkipStepChance": "Chance de pular etapa",
          "FlatInterval": "Intervalo", "PercentInterval": "Intervalo", "DoubleDamageChance": "Chance de dano duplo",
          "FlatStealth": "Furtividade", "FlatProficiency": "Proficiência"}


def format_value(value, unit):
    return f"{value * 100:+g}%" if unit == "percentual" else f"{value:+g}" + (" ms" if unit == "ms" else "")


def report_html(result):
    esc = lambda v: html.escape(str(v), quote=True)
    def bonus_line(b, aggregate=False):
        value = b["valor"] if aggregate else b["effective_value"]
        sources = b["fontes"] if aggregate else [b]
        names = "; ".join((x.get("source_name") or x["source_id"]) + " (" + x["via"] + ")" for x in sources)
        suffix = ""
        if not aggregate:
            scope = {k: b[k] for k in ("context", "condition", "scaling", "from_context", "note") if b.get(k)}
            if scope:
                suffix = "<pre>" + esc(json.dumps(scope, ensure_ascii=False, indent=2)) + "</pre>"
        return "<li><b>" + esc(LABELS.get(b["stat"], b["stat"])) + ": " + esc(format_value(value, b["unidade"])) + "</b><br><small>" + esc(names) + "</small>" + suffix + "</li>"
    overview, details = [], []
    for skill, s in result["habilidades"].items():
        summary = "; ".join(LABELS.get(b["stat"], b["stat"]) + " " + format_value(b["valor"], b["unidade"]) for b in s["bonus_gerais"]) or "Nenhum modificador geral confirmado"
        overview.append(f'<tr><td><a href="#{esc(skill)}">{esc(skill)}</a></td><td>{s["nivel"]}</td><td>{s["xp"]:,.2f}</td><td>{esc(summary)}</td></tr>')
        sections = []
        for key, title, aggregated in (("bonus_gerais", "Gerais confirmados", True), ("bonus_contextuais", "Por contexto / condição", False), ("bonus_incertos", "Não confirmados — excluídos dos totais", False)):
            if s[key]:
                sections.append(f"<h3>{title}</h3><ul>" + "".join(bonus_line(b, aggregated) for b in s[key]) + "</ul>")
        if s["ferramentas"]:
            sections.append("<h3>Toolbelt / poções equipadas</h3><pre>" + esc(json.dumps(s["ferramentas"], ensure_ascii=False, indent=2)) + "</pre>")
        details.append(f'<details id="{esc(skill)}"><summary>{esc(skill)} · nível {s["nivel"]}</summary>' + ("".join(sections) or "<p>Nenhum bônus identificado pelas fontes cobertas.</p>") + "</details>")
    activity = result["atividade"]
    return '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Estado do personagem · Melvor Idle 2</title><style>
:root{color-scheme:dark}body{font:16px/1.5 system-ui;background:#101820;color:#eaf1f8;max-width:1150px;margin:auto;padding:28px}a{color:#7fd9bd}h1{font-size:30px}small{color:#aabaca}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #35424e}thead{background:#1b2a36}details{background:#182632;border:1px solid #35424e;border-radius:8px;margin:12px 0;padding:16px}summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;color:#b9d0dc}li{margin:12px 0}.notice{background:#302b1c;border-left:4px solid #e0b85e;padding:14px}.scroll{overflow:auto}
</style><h1>''' + esc(result["personagem"]) + f''' · nível total {result["nivel_total"]}</h1><p>''' + esc(activity["habilidade"]) + " · " + esc(activity["acao"]) + "</p><p>Último save: " + esc(result["origem"]["save_modificado_local"]) + "<br>Extraído em: " + esc(result["origem"]["extraido_em"]) + "</p><div class=notice><b>Cobertura parcial</b><ul>" + "".join("<li>" + esc(v) + "</li>" for v in result["limites"] + result["avisos"]) + "</ul></div><p><a href=estado.json>JSON para consulta e cálculos</a> · <a href=bonus.json>Bônus por fonte</a></p><h2>Habilidades</h2><div class=scroll><table><thead><tr><th>Habilidade</th><th>Nível</th><th>XP salvo</th><th>Modificadores gerais confirmados</th></tr></thead><tbody>" + "".join(overview) + "</tbody></table></div><h2>Origem e condições dos bônus</h2>" + "".join(details) + "<h2>Outros componentes / globais não expandidos</h2><ul>" + "".join(bonus_line(b) for b in result["outros_bonus_e_globais"]) + '</ul><p><small>Leitor baseado em <a href="https://github.com/jtwilli/melvor2sim">melvor2sim</a> (MIT), com adaptações locais. Nenhum dado enviado à rede.</small></p></html>'


def extract(save, exe, output):
    save, exe, output = save.resolve(), exe.resolve(), output.resolve()
    if output.is_relative_to(save.parent) or output.is_relative_to(exe.parent):
        raise ValueError("A saída deve ficar fora das pastas de saves e do jogo.")
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
    finally:
        snapshot.unlink(missing_ok=True)
    state["save_file"] = save.name
    if not state["skills"] or any("Experience" in w for w in state["warnings"]):
        raise ValueError("Não foi possível ler todos os níveis.")
    state["mastery_ranks"] = decoder.mastery_ranks(state, tables / "objects", data["EntityConfig"])
    active = decoder.active_bonuses(state, collect_bonuses(data["Objects"]), state["mastery_ranks"], tables / "objects")["active"]
    bonfire, events = read_temporary(entities)
    active = augment_bonuses(state, data, active, bonfire, events)
    for skill, rank in state["mastery_ranks"].items():
        if rank["rank_min"] != rank["rank_max"]:
            state["warnings"].append(f"{skill}: rank de maestria entre {decoder.short(rank['rank_min'])} e {decoder.short(rank['rank_max'])}; bônus incertos separados.")
    origin = {"save": str(save), "save_sha256": hashlib.sha256(blob).hexdigest(), "versao_save": state["header"]["version"],
              "personagem_id": state["header"]["uuid"],
              "save_modificado_local": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
              "extraido_em": datetime.now(timezone.utc).astimezone().isoformat(), "pacote_jogo": game_origin,
              "upstream_commit": UPSTREAM}
    result = summarize(state, active, data, origin)
    if result["nivel_total"] != result["nivel_total_cabecalho"]:
        result["avisos"].append("Soma dos níveis difere do cabeçalho do save; consulte os valores por habilidade.")
    output.mkdir(parents=True, exist_ok=True)
    dump(output / "estado.json", result)
    dump(output / "bonus.json", {"origem": origin, "bonus": active, "bonfire": bonfire, "eventos_raros": events, "limites": LIMITES})
    dump(output / "estado_decodificado.json", state)
    atomic_text(output / "relatorio.html", report_html(result))
    dump(output / "agentes.json", build_agent_state(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", help="Arquivo .sav ou diretório; padrão: save mais recente no AppData")
    parser.add_argument("--exe", help="Melvor2.exe ou diretório; padrão: detectado nas bibliotecas Steam")
    parser.add_argument("--saida", type=Path, default=ROOT / "dados" / "personagem")
    args = parser.parse_args()
    try:
        result = extract(paths.find_save(args.save), paths.find_exe(args.exe), args.saida)
    except (OSError, ValueError, EOFError, KeyError) as exc:
        parser.exit(1, f"Extração interrompida: {exc}\n")
    print(f"{result['personagem']} | nível total {result['nivel_total']} | save v{result['origem']['versao_save']}")
    print(", ".join(f"{k} {s['nivel']}" for k, s in result["habilidades"].items()))
    for warning in result["avisos"]:
        print("AVISO:", warning)
    print("Relatório:", (args.saida / "relatorio.html").resolve())
    print("JSON:", (args.saida / "estado.json").resolve())


if __name__ == "__main__":
    main()
