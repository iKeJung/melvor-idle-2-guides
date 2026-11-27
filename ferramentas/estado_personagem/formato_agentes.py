"""Contrato de consulta v1: índices estáveis e subtotais com proveniência."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

FORMAT = "melvor2-personagem-agentes"
VERSION = 1
UNITS = {"percentual": "fracao_percentual", "ms": "ms", "valor": "valor_do_jogo"}


def build_agent_state(state):
    sources = {}

    def contribution(row):
        identity = {k: row[k] for k in ("source_type", "source_id", "via")}
        key = "f_" + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
        source = {"tipo": identity["source_type"], "id": identity["source_id"],
                  "nome": row.get("source_name"), "via": identity["via"]}
        if key in sources and sources[key] != source:
            raise ValueError("Identificador de fonte em conflito.")
        sources[key] = source
        result = {"fonte": key, "valor": row["effective_value"]}
        for old, new in (("context", "contexto"), ("condition", "condicao"),
                         ("scaling", "escala"), ("from_context", "from_context"), ("note", "nota")):
            if row.get(old):
                result[new] = deepcopy(row[old])
        return result

    def node(index, component, kind, stat, unit):
        stats = index.setdefault(component, {}).setdefault(kind, {})
        target = stats.setdefault(stat, {"unidade": UNITS[unit], "geral_confirmado": None,
                                        "contextuais": [], "incertos": [],
                                        "valor_final": None, "completo": False})
        if target["unidade"] != UNITS[unit]:
            raise ValueError(f"Unidades divergentes para {component}.{kind}.{stat}.")
        return target

    skills = {}
    for name, skill in state["habilidades"].items():
        index = {}
        for total in skill["bonus_gerais"]:
            target = node(index, total["componente"], total["tipo"], total["stat"], total["unidade"])
            if target["geral_confirmado"] is not None:
                raise ValueError("Subtotal duplicado no estado de origem.")
            target["geral_confirmado"] = {"valor": total["valor"],
                                          "contribuicoes": [contribution(r) for r in total["fontes"]]}
            if total["unidade"] == "percentual":
                target["geral_confirmado"]["percentual"] = round(total["valor"] * 100, 8)
        for group, source_group in (("contextuais", "bonus_contextuais"), ("incertos", "bonus_incertos")):
            for row in skill[source_group]:
                target = node(index, row["component"], row["stats_type"], row["stat"], row["unidade"])
                target[group].append(contribution(row))
        skills[name] = {"nivel": skill["nivel"], "xp": skill["xp"], "modificadores": index}

    other = []
    for row in state["outros_bonus_e_globais"]:
        other.append({"entidade": row["entity"], "componente": row["component"], "tipo": row["stats_type"],
                      "stat": row["stat"], "unidade": UNITS[row["unidade"]],
                      "classificacao": row["classificacao"], **contribution(row)})
    origin = state["origem"]
    return {"formato": FORMAT, "schema_version": VERSION,
            "snapshot": {"personagem": state["personagem"], "modo": state["modo"],
                         "personagem_id": origin.get("personagem_id"),
                         "save_modificado_em": origin["save_modificado_local"],
                         "extraido_em": origin["extraido_em"], "save_sha256": origin["save_sha256"],
                         "versao_save": origin["versao_save"],
                         "pacote_jogo_sha256": origin["pacote_jogo"]["sha256"]},
            "cobertura": {"completa": False, "tipo_valor": "subtotal_de_modificadores_gerais_confirmados",
                          "globais_incluidos_nos_subtotais": False, "ausencia_significa_zero": False,
                          "limites": list(state["limites"]), "avisos": list(state["avisos"])},
            "nivel_total": state["nivel_total"], "atividade": deepcopy(state["atividade"]),
            "habilidades": skills, "outros_bonus_e_globais": other, "fontes": sources}


def validate_version(document):
    if document.get("formato") != FORMAT or document.get("schema_version") != VERSION:
        raise ValueError("Formato de consulta incompatível; gere novamente o snapshot.")


def _resolve(mapping, name, label):
    matches = [key for key in mapping if key.casefold() == name.casefold()]
    if not matches:
        raise LookupError(f"{label} '{name}' não encontrado. Disponíveis: {', '.join(mapping)}")
    return matches[0]


def query(document, skill, stat=None, component=None, kind=None, *, cached=False):
    validate_version(document)
    name = _resolve(document["habilidades"], skill, "Habilidade")
    data = document["habilidades"][name]
    snapshot = deepcopy(document["snapshot"])
    modified = datetime.fromisoformat(snapshot["save_modificado_em"])
    if modified.tzinfo is None:
        raise ValueError("Snapshot sem fuso horário.")
    snapshot["idade_save_segundos"] = round((datetime.now(timezone.utc) - modified).total_seconds(), 1)
    response = {"formato": FORMAT + "-consulta", "schema_version": VERSION,
                "status": "encontrado", "leitura": "cache" if cached else "save_atualizado",
                "snapshot": snapshot, "habilidade": name, "nivel": data["nivel"], "xp": data["xp"],
                "cobertura": deepcopy(document["cobertura"])}
    if stat is None:
        if component or kind:
            raise ValueError("Use --stat para filtrar componente/tipo.")
        response["modificadores"] = deepcopy(data["modificadores"])
    else:
        matches = []
        for comp, kinds in data["modificadores"].items():
            if component and component.casefold() != comp.casefold():
                continue
            for stats_type, values in kinds.items():
                if kind and kind.casefold() != stats_type.casefold():
                    continue
                for key, value in values.items():
                    if key.casefold() == stat.casefold():
                        matches.append({"componente": comp, "tipo": stats_type, "stat": key, **deepcopy(value)})
        if len(matches) > 1:
            choices = ", ".join(f"{m['componente']}.{m['tipo']}.{m['stat']}" for m in matches)
            raise ValueError(f"Consulta ambígua; informe --componente e/ou --tipo: {choices}")
        response["modificador"] = matches[0] if matches else None
        if not matches:
            response["status"] = "nao_identificado"
            response["consulta"] = {"stat": stat, "componente": component, "tipo": kind}

    # Return other/global candidates for this stat; never apply them implicitly.
    response["outros_bonus_e_globais"] = deepcopy([r for r in document["outros_bonus_e_globais"]
                                                   if stat is None or r["stat"].casefold() == stat.casefold()
                                                   or r["entidade"] is None])
    refs = set()
    def walk(value):
        if isinstance(value, dict):
            if "fonte" in value:
                refs.add(value["fonte"])
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(response)
    response["fontes"] = {key: deepcopy(document["fontes"][key]) for key in sorted(refs)}
    return response
