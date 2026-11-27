"""Verify the agent contract, ambiguous queries, and failures without implicit caching."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_format import build_agent_state, query


def example_state():
    def row(value, **extra):
        return {"source_type": "Item", "source_id": "MelvorBase:Test", "source_name": "Test",
                "via": "toolbelt:Smithing/Test", "effective_value": value, **extra}
    return {"character": "Synthetic character", "mode": "Test", "total_level": 31,
            "activity": {"skill": "Smithing", "action": "Test"},
            "origin": {"character_id": "test-uuid", "save_modified_local": datetime.now(timezone.utc).isoformat(),
                       "extracted_at": datetime.now(timezone.utc).isoformat(), "save_sha256": "test-save-hash",
                       "save_version": 32, "game_package": {"sha256": "test-game-hash"}},
            "warnings": [], "limits": ["Partial coverage."], "other_and_global_bonuses": [],
            "skills": {"Smithing": {"level": 31, "xp": 16000, "general_bonuses": [
                {"component": "Action", "type": "ArtisanAction", "stat": "SkipStepChance",
                 "unit": "percentage", "value": 0.06, "sources": [row(0.06)]},
                {"component": "Action", "type": "ArtisanAction", "stat": "FlatInterval",
                 "unit": "ms", "value": -100, "sources": [row(-100)]},
                {"component": "Action", "type": "ArtisanAction", "stat": "FlatTest",
                 "unit": "value", "value": 0, "sources": [row(0)]}],
                "contextual_bonuses": [row(0.5, component="Action", stats_type="ArtisanAction", stat="ContextOnly",
                                           unit="percentage", context={"Recipe": "MelvorBase:Test"}, scaling={"Type": "Test"})],
                "uncertain_bonuses": [row(0.2, component="Action", stats_type="ArtisanAction", stat="UncertainOnly",
                                        unit="percentage", note="UNCERTAIN: rank")]}}}


class AgentContractTests(unittest.TestCase):
    def setUp(self):
        self.state = example_state()
        self.document = build_agent_state(self.state)

    def test_units_provenance_and_final_unknown(self):
        response = query(self.document, "smithing", "skipstepchance")
        bonus = response["modifier"]
        self.assertEqual(bonus["confirmed_general"]["value"], 0.06)
        self.assertEqual(bonus["confirmed_general"]["percentage"], 6)
        self.assertEqual(bonus["unit"], "percentage_fraction")
        self.assertIsNone(bonus["final_value"])
        self.assertFalse(bonus["complete"])
        self.assertEqual(len(response["sources"]), 1)
        self.assertGreaterEqual(response["snapshot"]["save_age_seconds"], 0)
        self.assertEqual(query(self.document, "Smithing", "FlatInterval")["modifier"]["confirmed_general"]["value"], -100)

    def test_absence_context_uncertainty_and_zero_differ(self):
        missing = query(self.document, "Smithing", "DoesNotExist")
        self.assertEqual(missing["status"], "unidentified")
        self.assertIsNone(missing["modifier"])
        zero = query(self.document, "Smithing", "FlatTest")["modifier"]
        self.assertEqual(zero["confirmed_general"]["value"], 0)
        contextual = query(self.document, "Smithing", "ContextOnly")["modifier"]
        self.assertIsNone(contextual["confirmed_general"])
        self.assertEqual(contextual["contextual"][0]["context"]["Recipe"], "MelvorBase:Test")
        self.assertEqual(contextual["contextual"][0]["scaling"], {"Type": "Test"})
        uncertain = query(self.document, "Smithing", "UncertainOnly")["modifier"]
        self.assertIsNone(uncertain["confirmed_general"])
        self.assertEqual(len(uncertain["uncertain"]), 1)

    def test_ambiguous_stats_require_component_or_type(self):
        components = self.document["skills"]["Smithing"]["modifiers"]
        components["Other"] = deepcopy(components["Action"])
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            query(self.document, "Smithing", "SkipStepChance")
        self.assertEqual(query(self.document, "Smithing", "SkipStepChance", component="action")["modifier"]["component"], "Action")
        components["Action"]["OtherType"] = deepcopy(components["Action"]["ArtisanAction"])
        with self.assertRaises(ValueError):
            query(self.document, "Smithing", "SkipStepChance", component="Action")
        self.assertEqual(query(self.document, "Smithing", "SkipStepChance", "Action", "ArtisanAction")["modifier"]["type"], "ArtisanAction")

    def test_global_candidates_are_retained_but_not_added(self):
        self.state["other_and_global_bonuses"] = [{"source_type": "FiremakingBonfire", "source_id": "MelvorBase:Normal",
            "source_name": "Normal", "via": "bonfire", "effective_value": 0.01, "entity": None, "component": None,
            "stats_type": None, "stat": "GlobalPercentXpGained", "unit": "percentage", "classification": "general"}]
        response = query(build_agent_state(self.state), "Smithing", "SkipStepChance")
        self.assertEqual(response["modifier"]["confirmed_general"]["value"], 0.06)
        self.assertEqual(response["other_and_global_bonuses"][0]["stat"], "GlobalPercentXpGained")
        self.assertEqual(len(response["sources"]), 2)

    def test_source_ids_stable_and_response_does_not_mutate_snapshot(self):
        reordered = deepcopy(self.state)
        reordered["skills"]["Smithing"]["general_bonuses"].reverse()
        self.assertEqual(build_agent_state(reordered)["sources"], self.document["sources"])
        before = deepcopy(self.document)
        response = query(self.document, "Smithing", cached=True)
        response["modifiers"].clear()
        self.assertEqual(self.document, before)

    def test_bad_version_unknown_skill_and_naive_timestamp_fail(self):
        document = deepcopy(self.document)
        document["schema_version"] = 99
        with self.assertRaises(ValueError):
            query(document, "Smithing")
        with self.assertRaises(LookupError):
            query(self.document, "UnknownSkill")
        document = deepcopy(self.document)
        document["snapshot"]["save_modified_at"] = "2026-01-01T12:00:00"
        with self.assertRaises(ValueError):
            query(document, "Smithing")

    def test_legacy_snapshot_is_rejected_before_reading_english_fields(self):
        # Historical keys are intentional input data for backward-version rejection.
        legacy = {"formato": "melvor2-personagem-agentes", "schema_version": 1,
                  "habilidades": {"Smithing": {"nivel": 31}}}
        with self.assertRaisesRegex(ValueError, "regenerate the snapshot"):
            query(legacy, "Smithing", cached=True)
        old_version = deepcopy(self.document)
        old_version["schema_version"] = 1
        with self.assertRaisesRegex(ValueError, "regenerate the snapshot"):
            query(old_version, "Smithing", cached=True)

    def test_cli_json_cache_and_failed_refresh_never_falls_back(self):
        script = Path(__file__).with_name("query.py")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot = root / "agents.json"
            original = json.dumps(self.document)
            snapshot.write_text(original, encoding="utf-8")
            command = [sys.executable, "-X", "utf8", "-I", str(script), "--skill", "Smithing", "--stat", "SkipStepChance", "--output", folder]
            cached = subprocess.run(command + ["--cache", "--component", "action", "--type", "artisanaction"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(cached.returncode, 0, cached.stderr)
            self.assertEqual(json.loads(cached.stdout)["read_mode"], "cache")
            self.assertEqual(json.loads(cached.stdout)["schema_version"], 2)
            self.assertEqual(json.loads(cached.stdout)["modifier"]["component"], "Action")
            failure = subprocess.run(command + ["--save", str(root / "missing.sav")], capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(failure.returncode, 0)
            response = json.loads(failure.stdout)
            self.assertEqual(response["status"], "error")
            self.assertFalse(response["cache_used_as_fallback"])
            self.assertEqual(snapshot.read_text(encoding="utf-8"), original)
            wrong_selection = subprocess.run(command + ["--cache", "--save", "other.sav"], capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(wrong_selection.returncode, 0)


if __name__ == "__main__":
    unittest.main()
