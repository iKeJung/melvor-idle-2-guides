"""Testes sintéticos; nenhum save pessoal é distribuído."""
from html.parser import HTMLParser
import json
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extrair

d = extrair.decoder


def string(value):
    blob = value.encode()
    assert len(blob) < 128
    return bytes([len(blob)]) + blob


def row(**changes):
    result = {"entity": "Fletching", "component": "Action", "stats_type": "ArtisanAction",
              "stat": "DoublingChance", "context": {}, "condition": None, "scaling": None,
              "from_context": None, "value": 0.02, "effective_value": 0.02,
              "source_name": "<Teste>", "source_id": "MelvorBase:Test", "source_type": "Item", "via": "toolbelt"}
    return dict(result, **changes)


class ExtractionTests(unittest.TestCase):
    def test_bank_v32_tab_icon_does_not_desync_next_tab(self):
        def tab(label, icon):
            # StackableInventory, empty, followed by label, tags and v32 icon.
            return struct.pack("<iii??i", 20, 1, 100, True, False, 0) + string(label) + struct.pack("<i?", 0, bool(icon)) + (string(icon) if icon else b"")
        blob = struct.pack("<ii", 0, 2) + tab("Materiais", "MelvorBase:OakLog") + tab("Outros", None)
        reader = d.Reader(blob, version=32)
        tabs = d.d_bank(reader)
        self.assertEqual([t["label"] for t in tabs], ["Materiais", "Outros"])
        self.assertEqual(tabs[0]["icon"], "MelvorBase:OakLog")
        self.assertEqual(reader.left, 0)

    def test_bank_v31_has_no_tab_icon(self):
        blob = struct.pack("<iiiii??i", 0, 1, 20, 1, 100, True, False, 0) + string("Itens") + struct.pack("<i", 0)
        reader = d.Reader(blob, version=31)
        self.assertEqual(d.d_bank(reader)[0]["label"], "Itens")
        self.assertEqual(reader.left, 0)

    def test_invalid_regions_fail(self):
        for count in (-1, 100):
            with self.assertRaises((ValueError, EOFError)):
                d.Reader(struct.pack("<i", count)).region()

    def test_two_handed_equipment_not_counted_twice(self):
        def slot(occupied):
            body = struct.pack("<i??", 1, occupied, True) + string("MelvorBase:Staff")
            return struct.pack("<i", len(body)) + body
        blob = struct.pack("<i", 2) + string("Weapon") + slot(False) + string("Offhand") + slot(True)
        self.assertEqual(list(d.d_slots(d.Reader(blob), True)), ["Weapon"])

    def test_xp_level_boundaries(self):
        self.assertEqual(d.level_from_xp(0), 1)
        self.assertEqual(d.level_from_xp(82), 1)
        self.assertEqual(d.level_from_xp(83), 2)
        self.assertEqual(d.level_from_xp(7398), 24)

    def test_conditional_uncertain_and_global_not_summed(self):
        data = {"ComponentModifierDescriptions": [{"Key": {"Stat": {"Name": "DoublingChance", "StatsType": "MelvorBase:ArtisanAction"}}, "TemplateString": "{Value:0%}"}], "GlobalModifierDescriptions": []}
        state = {"skills": {"Fletching": {"level": 24, "xp": 7398}}, "toolbelts": {},
                 "header": {"character": "<Miouky>", "gamemode": "Test", "total_level": 24, "active_entity": "Fletching", "active_action": "Oak"}, "warnings": []}
        rows = [row(), row(effective_value=0.03), row(context={"Recipe": "MelvorBase:Oak"}, effective_value=0.2),
                row(note="UNCERTAIN: rank", effective_value=0.4), row(entity=None, stat="GlobalPercentXpGained", stats_type=None)]
        result = extrair.summarize(state, rows, data, {"save_modificado_local": "agora", "extraido_em": "agora"})
        skill = result["habilidades"]["Fletching"]
        self.assertEqual(skill["bonus_gerais"][0]["valor"], 0.05)
        self.assertEqual(len(skill["bonus_contextuais"]), 1)
        self.assertEqual(len(skill["bonus_incertos"]), 1)
        self.assertEqual(len(result["outros_bonus_e_globais"]), 1)
        report = extrair.report_html(result)
        self.assertNotIn("<Miouky>", report)
        self.assertIn("&lt;Miouky&gt;", report)
        self.assertIn("+5%", report)
        HTMLParser().feed(report)
        json.dumps(result, allow_nan=False)

    def test_bonfire_only_with_enabled_and_remaining_ticks(self):
        def entities(left, enabled):
            return {"Firemaking": {"Bonfire": d.Reader(struct.pack("<ii?", 100, left, False) + b"\x01" + string("MelvorBase:Normal") + struct.pack("?", enabled))}}
        self.assertFalse(extrair.read_temporary(entities(0, True))[0]["applies"])
        self.assertFalse(extrair.read_temporary(entities(10, False))[0]["applies"])
        self.assertTrue(extrair.read_temporary(entities(10, True))[0]["applies"])

    def test_set_thresholds_are_applied_per_tier(self):
        modifier = {"Stat": {"StatsType": "MelvorBase:ArtisanAction", "Name": "DoublingChance"},
                    "Value": 0.1, "LocalContext": {"Component": {"Entity": "MelvorBase:Fletching", "Component": "Action"}}}
        data = {"Objects": {"EquipmentSetBonus": [{"Id": "TestSet", "DisplayName": "Test Set", "Items": ["A", "B", "C"],
                    "Bonuses": [{"ItemCount": 2, "Modifiers": {"Component": [modifier]}}, {"ItemCount": 3, "Modifiers": {"Component": [dict(modifier, Value=0.2)]}}]}]}}
        state = {"equipment": {}, "toolbelts": {"Fletching": {"one": {"item": "A", "qty": 1}, "two": {"item": "B", "qty": 1}}}, "prayers": {}, "warnings": []}
        rows = extrair.augment_bonuses(state, data, [], None, [])
        self.assertEqual([r["effective_value"] for r in rows], [0.1])
        self.assertEqual(state["warnings"], [])


if __name__ == "__main__":
    unittest.main()
