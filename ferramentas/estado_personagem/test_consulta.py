"""Verifica o contrato para agentes, ambiguidades e falhas sem cache implícito."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from formato_agentes import build_agent_state, query


def example_state():
    def row(value, **extra):
        return {"source_type": "Item", "source_id": "MelvorBase:Test", "source_name": "Test",
                "via": "toolbelt:Smithing/Test", "effective_value": value, **extra}
    return {"personagem": "Personagem sintético", "modo": "Test", "nivel_total": 31,
            "atividade": {"habilidade": "Smithing", "acao": "Test"},
            "origem": {"personagem_id": "test-uuid", "save_modificado_local": datetime.now(timezone.utc).isoformat(),
                       "extraido_em": datetime.now(timezone.utc).isoformat(), "save_sha256": "test-save-hash",
                       "versao_save": 32, "pacote_jogo": {"sha256": "test-game-hash"}},
            "avisos": [], "limites": ["Cobertura parcial."], "outros_bonus_e_globais": [],
            "habilidades": {"Smithing": {"nivel": 31, "xp": 16000, "bonus_gerais": [
                {"componente": "Action", "tipo": "ArtisanAction", "stat": "SkipStepChance",
                 "unidade": "percentual", "valor": 0.06, "fontes": [row(0.06)]},
                {"componente": "Action", "tipo": "ArtisanAction", "stat": "FlatInterval",
                 "unidade": "ms", "valor": -100, "fontes": [row(-100)]},
                {"componente": "Action", "tipo": "ArtisanAction", "stat": "FlatTest",
                 "unidade": "valor", "valor": 0, "fontes": [row(0)]}],
                "bonus_contextuais": [row(0.5, component="Action", stats_type="ArtisanAction", stat="ContextOnly",
                                           unidade="percentual", context={"Recipe": "MelvorBase:Test"}, scaling={"Type": "Test"})],
                "bonus_incertos": [row(0.2, component="Action", stats_type="ArtisanAction", stat="UncertainOnly",
                                        unidade="percentual", note="UNCERTAIN: rank")]}}}


class AgentContractTests(unittest.TestCase):
    def setUp(self):
        self.state = example_state()
        self.document = build_agent_state(self.state)

    def test_units_provenance_and_final_unknown(self):
        response = query(self.document, "smithing", "skipstepchance")
        bonus = response["modificador"]
        self.assertEqual(bonus["geral_confirmado"]["valor"], 0.06)
        self.assertEqual(bonus["geral_confirmado"]["percentual"], 6)
        self.assertEqual(bonus["unidade"], "fracao_percentual")
        self.assertIsNone(bonus["valor_final"])
        self.assertFalse(bonus["completo"])
        self.assertEqual(len(response["fontes"]), 1)
        self.assertGreaterEqual(response["snapshot"]["idade_save_segundos"], 0)
        self.assertEqual(query(self.document, "Smithing", "FlatInterval")["modificador"]["geral_confirmado"]["valor"], -100)

    def test_absence_context_uncertainty_and_zero_differ(self):
        missing = query(self.document, "Smithing", "DoesNotExist")
        self.assertEqual(missing["status"], "nao_identificado")
        self.assertIsNone(missing["modificador"])
        zero = query(self.document, "Smithing", "FlatTest")["modificador"]
        self.assertEqual(zero["geral_confirmado"]["valor"], 0)
        contextual = query(self.document, "Smithing", "ContextOnly")["modificador"]
        self.assertIsNone(contextual["geral_confirmado"])
        self.assertEqual(contextual["contextuais"][0]["contexto"]["Recipe"], "MelvorBase:Test")
        self.assertEqual(contextual["contextuais"][0]["escala"], {"Type": "Test"})
        uncertain = query(self.document, "Smithing", "UncertainOnly")["modificador"]
        self.assertIsNone(uncertain["geral_confirmado"])
        self.assertEqual(len(uncertain["incertos"]), 1)

    def test_ambiguous_stats_require_component_or_type(self):
        components = self.document["habilidades"]["Smithing"]["modificadores"]
        components["Other"] = deepcopy(components["Action"])
        with self.assertRaisesRegex(ValueError, "ambígua"):
            query(self.document, "Smithing", "SkipStepChance")
        self.assertEqual(query(self.document, "Smithing", "SkipStepChance", component="action")["modificador"]["componente"], "Action")
        components["Action"]["OtherType"] = deepcopy(components["Action"]["ArtisanAction"])
        with self.assertRaises(ValueError):
            query(self.document, "Smithing", "SkipStepChance", component="Action")
        self.assertEqual(query(self.document, "Smithing", "SkipStepChance", "Action", "ArtisanAction")["modificador"]["tipo"], "ArtisanAction")

    def test_global_candidates_are_retained_but_not_added(self):
        self.state["outros_bonus_e_globais"] = [{"source_type": "FiremakingBonfire", "source_id": "MelvorBase:Normal",
            "source_name": "Normal", "via": "bonfire", "effective_value": 0.01, "entity": None, "component": None,
            "stats_type": None, "stat": "GlobalPercentXpGained", "unidade": "percentual", "classificacao": "geral"}]
        response = query(build_agent_state(self.state), "Smithing", "SkipStepChance")
        self.assertEqual(response["modificador"]["geral_confirmado"]["valor"], 0.06)
        self.assertEqual(response["outros_bonus_e_globais"][0]["stat"], "GlobalPercentXpGained")
        self.assertEqual(len(response["fontes"]), 2)

    def test_source_ids_stable_and_response_does_not_mutate_snapshot(self):
        reordered = deepcopy(self.state)
        reordered["habilidades"]["Smithing"]["bonus_gerais"].reverse()
        self.assertEqual(build_agent_state(reordered)["fontes"], self.document["fontes"])
        before = deepcopy(self.document)
        response = query(self.document, "Smithing", cached=True)
        response["modificadores"].clear()
        self.assertEqual(self.document, before)

    def test_bad_version_unknown_skill_and_naive_timestamp_fail(self):
        document = deepcopy(self.document)
        document["schema_version"] = 99
        with self.assertRaises(ValueError):
            query(document, "Smithing")
        with self.assertRaises(LookupError):
            query(self.document, "UnknownSkill")
        document = deepcopy(self.document)
        document["snapshot"]["save_modificado_em"] = "2026-01-01T12:00:00"
        with self.assertRaises(ValueError):
            query(document, "Smithing")

    def test_cli_json_cache_and_failed_refresh_never_falls_back(self):
        script = Path(__file__).with_name("consultar.py")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot = root / "agentes.json"
            original = json.dumps(self.document)
            snapshot.write_text(original, encoding="utf-8")
            command = [sys.executable, "-X", "utf8", "-I", str(script), "--skill", "Smithing", "--stat", "SkipStepChance", "--saida", folder]
            cached = subprocess.run(command + ["--cache"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(cached.returncode, 0, cached.stderr)
            self.assertEqual(json.loads(cached.stdout)["leitura"], "cache")
            failure = subprocess.run(command + ["--save", str(root / "missing.sav")], capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(failure.returncode, 0)
            response = json.loads(failure.stdout)
            self.assertEqual(response["status"], "erro")
            self.assertFalse(response["cache_usado_como_fallback"])
            self.assertEqual(snapshot.read_text(encoding="utf-8"), original)
            wrong_selection = subprocess.run(command + ["--cache", "--save", "other.sav"], capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(wrong_selection.returncode, 0)


if __name__ == "__main__":
    unittest.main()
