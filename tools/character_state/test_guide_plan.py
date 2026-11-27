import unittest

from guide_plan import Action, NS, available_plans, expected_hits, modifiers, train


def action(key, seconds, xp, *, output=1, inputs=None, preservation=0):
    return Action(key, key, "Artisan", "Fletching", 1, NS + key, output,
                  inputs or {}, seconds, xp, preservation, {})


class GuidePlanTests(unittest.TestCase):
    def test_context_and_source_filters(self):
        recipe = {"Id": "Bowstring", "Category": NS + "Resources"}
        sources = {
            "station": {"type": "ShopPurchase", "via": "shop"},
            "potion": {"type": "Item", "via": "toolbelt:Crafting/CraftingPotion"},
        }
        def row(value, **context):
            return {"source": "station", "value": value, **context}

        interval = {
            "unit": "ms",
            "confirmed_general": {"value": -200, "contributions": [
                row(-100), {"source": "potion", "value": -100},
            ]},
            "contextual": [
                row(-100, context={"Category": NS + "Resources"}),
                row(-500, context={"Recipe": NS + "Armour"}),
                row(-500, context={"Recipe": NS + "Bowstring"}, condition={"Season": "Summer"}),
                row(-500, context={"Item": NS + "Bowstring"}),
            ],
            "uncertain": [row(-500)],
        }
        snapshot = {
            "skills": {"Crafting": {"modifiers": {"Action": {"ArtisanAction": {"FlatInterval": interval}}}}},
            "sources": sources,
        }
        applied = {}
        stat = modifiers(snapshot, "Crafting", "ArtisanAction", recipe, NS + "Bowstring", applied)
        self.assertEqual(stat("FlatInterval", "ms"), -200)
        self.assertEqual(len(applied["FlatInterval"]["contributions"]), 2)
        self.assertEqual(stat("SkipStepChance", "percentage_fraction"), 0)
        self.assertNotIn("SkipStepChance", applied)

    def test_one_step_cannot_be_skipped(self):
        self.assertEqual(expected_hits(1, 0.45), 1)
        self.assertAlmostEqual(expected_hits(2, 0.03), 1.97)
        self.assertAlmostEqual(expected_hits(3, 0.03), 2.9409)

    def test_preparation_xp_can_reach_target_without_crafting_final_recipe(self):
        shaft = action("Shaft", 2, 2, output=20)
        arrow = action("Arrow", 2, 3, inputs={shaft.product: 10})
        stage = train(arrow, {shaft.product: shaft}, {}, {}, 2)
        self.assertEqual(stage.actions, [{"id": "Shaft", "count": 1}])
        self.assertEqual(stage.stock[shaft.product], 20)
        self.assertEqual(stage.xp, 2)

    def test_preparation_reaches_cutoff_before_gathering_other_ingredients(self):
        tips = action("Tips", 30, 0, output=10)
        headless = action("Headless", 2, 3, output=10)
        arrow = action("Arrow", 4, 7, inputs={tips.product: 4, headless.product: 4})
        suppliers = {supply.product: supply for supply in (tips, headless)}
        stage = train(arrow, suppliers, {}, {}, 3)
        self.assertEqual(stage.actions, [{"id": "Headless", "count": 1}])
        self.assertEqual(stage.seconds, 2)

    def test_preparation_caps_input_for_xp_earning_batches(self):
        log = action("Log", 3, 0)
        shaft = action("Shaft", 2, 2, inputs={log.product: 1})
        arrow = action("Arrow", 4, 7, inputs={shaft.product: 10})
        suppliers = {supply.product: supply for supply in (log, shaft)}
        stage = train(arrow, suppliers, {}, {}, 3)
        self.assertEqual(stage.actions, [{"id": "Log", "count": 2}, {"id": "Shaft", "count": 2}])
        self.assertEqual(stage.xp, 4)

    def test_preservation_requires_first_batch_and_carries_expected_surplus(self):
        source = action("Supply", 1, 0, output=2)
        recipe = action("Arrow", 2, 5, inputs={source.product: 2}, preservation=0.5)
        stage = train(recipe, {source.product: source}, {source.product: 1}, {source.product: 1}, 5)
        self.assertEqual(stage.actions, [{"id": "Supply", "count": 1}, {"id": "Arrow", "count": 1}])
        self.assertEqual(stage.bank_used[source.product], 1)
        self.assertEqual(stage.stock[source.product], 2)
        next_stage = train(recipe, {source.product: source}, stage.stock, stage.bank, 5)
        self.assertEqual(next_stage.actions, [{"id": "Arrow", "count": 1}])
        self.assertEqual(next_stage.bank_used[source.product], 0)

    def test_alternatives_can_save_banked_material_for_later(self):
        supply = action("Supply", 30, 0)
        quick = action("Quick", 1, 5, inputs={supply.product: 1})
        slower = action("Slower", 2, 5)
        recipes = {recipe.id: recipe for recipe in (quick, slower)}
        bands = [(2, ["Quick", "Slower"]), (3, ["Quick"])]
        stock = {supply.product: 1}
        plans = available_plans(bands, recipes, {supply.product: supply}, stock, stock, 1, 0, [0, 5, 10])
        fastest = min(plans, key=lambda plan: sum(stage["seconds"] for stage in plan))
        self.assertEqual([stage["recipe"] for stage in fastest], ["Slower", "Quick"])


if __name__ == "__main__":
    unittest.main()
