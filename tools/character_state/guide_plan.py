"""Calculate the remaining route from one decoded save and its installed game data."""
from collections import defaultdict
from dataclasses import dataclass
from math import ceil, floor, isfinite

NS = "MelvorBase:"


def chance(value):
    return min(1, max(0, value))


def expected_hits(health, double, weak=0, instant=0):
    if health < 1:
        raise ValueError("Action health or step count must be positive.")
    weak_damage = 3 + health // 10
    hits = [0, 1]
    for remaining in range(2, health + 1):
        rest = sum(
            damage_chance * multiplier_chance * hits[max(0, remaining - damage * multiplier)]
            for damage, damage_chance in ((1, 1 - weak), (weak_damage, weak))
            for multiplier, multiplier_chance in ((1, 1 - double), (2, double))
        )
        hits.append(1 + (1 - instant) * rest)
    return hits[health]


def modifiers(snapshot, skill, stats_type, recipe, product, applied):
    """Read covered contributions once, with exact recipe/category/product matching."""
    skill_stats = snapshot["skills"][skill]["modifiers"]
    context = {"Recipe": NS + recipe["Id"], "Category": recipe["Category"], "Item": product}

    def stat(name, unit, *, experience=False, product_context=False):
        component, kind = ("Experience", "Experience") if experience else ("Action", stats_type)
        node = skill_stats.get(component, {}).get(kind, {}).get(name)
        if node is None:
            return 0.0  # Use the base model when there is no supported contribution.
        if node["unit"] != unit:
            raise ValueError(f"Unexpected unit for {skill}.{name}: {node['unit']}")
        rows = list((node["confirmed_general"] or {}).get("contributions", []))
        for row in node["contextual"]:
            local = row.get("context")
            if (local and not experience
                    and not any(row.get(key) for key in ("condition", "scaling", "from_context"))
                    and (product_context or "Item" not in local)
                    and all(key in context and context[key] == value for key, value in local.items())):
                rows.append(row)
        rows = [
            row for row in rows
            if snapshot["sources"][row["source"]]["type"] not in {"FiremakingBonfire", "RareBonusesEvent"}
            and not snapshot["sources"][row["source"]]["via"].endswith("Potion")
        ]
        if rows:
            value = round(sum(row["value"] for row in rows), 12)
            applied[name] = {"value": value, "unit": unit, "contributions": rows}
            return value
        return 0.0

    return stat


@dataclass(frozen=True)
class Action:
    id: str
    name: str
    kind: str
    skill: str
    level: int
    product: str
    output: float
    inputs: dict
    seconds: float
    xp: float
    preservation: float
    modifiers: dict


def item_quantities(items):
    return {row["Item"]: row["Quantity"] for row in items}


def build_action(snapshot, recipe, kind, target_skill):
    requirement, = recipe["Requirements"]
    data = requirement["Data"]
    if (requirement["Type"] != NS + "Level" or data["Component"]["Component"] != "Experience"
            or data.get("IsOr")):
        raise ValueError(f"Unsupported requirements for {recipe['Id']}.")
    skill = data["Component"]["Entity"].removeprefix(NS)
    applied = {}
    artisan = kind == "Artisan"
    if artisan:
        product, = recipe["Products"]
        if product["Chance"] != 1 or recipe["Ingredients"]["Currencies"]:
            raise ValueError(f"Unsupported products or costs for {recipe['Id']}.")
    else:
        product = recipe["Product"]
    stat = modifiers(snapshot, skill, kind + "Action", recipe, product["Item"], applied)

    def percent(name, **context):
        return stat(name, "percentage_fraction", **context)

    def roll(name):
        return chance(percent(name))

    flat_interval = stat("FlatInterval", "ms")
    interval_factor = 1 + percent("PercentInterval")
    flat_output = stat("FlatProductQuantity", "game_value", product_context=artisan)
    output = product["Quantity"] + int(flat_output)
    inputs, preservation, xp = {}, 0, 0
    if artisan:
        interval = floor(recipe["BaseInterval"] * interval_factor + flat_interval)
        steps = max(1, int(recipe["Steps"] + stat("FlatSteps", "game_value")))
        hits = expected_hits(steps, roll("SkipStepChance"))
        preservation = roll("PreservationChance")
        cost_factor = 1 + percent("PercentIngredientCost")
        inputs = {
            item: max(1, int(quantity * cost_factor))
            for item, quantity in item_quantities(recipe["Ingredients"]["Items"]).items()
        }
        output = max(1, int((product["Quantity"] + flat_output) *
                            (1 + percent("PercentProductQuantity", product_context=True))))
        if skill == target_skill:
            xp = (recipe["BaseExperience"] + stat("FlatXPGained", "game_value", experience=True)) * (
                1 + percent("PercentXPGained", experience=True)
            )
    else:
        interval = floor((recipe["BaseInterval"] + flat_interval) * interval_factor)
        if kind == "Woodcutting":
            health = ceil((recipe["BaseMaxHealth"] + stat("FlatMaxHealth", "game_value")) *
                          (1 + percent("PercentMaxHealth")))
            hits = expected_hits(health, roll("DoubleDamageChance"), roll("WeakSpotChance"), roll("InstantCutChance"))
        else:
            probability = chance(recipe["BaseProductChance"] * (1 + percent("PercentIncreaseRockBreakChance")))
            if probability <= 0:
                raise ValueError(f"No progress in the mining model for {recipe['Id']}.")
            # The game forces a break when accumulated prospecting reaches 0.9999.
            progress = percent("FlatMinimumProspecting")
            maximum_hits = max(1, ceil((0.9999 - progress) / probability - 1e-10))
            hits = (1 - (1 - probability) ** maximum_hits) / probability
            output = (output + roll("AdditionalProductQuantityChance")) * (1 + 2 * roll("ShatterChance"))

    output *= 1 + roll("DoublingChance")
    if interval <= 0 or output <= 0 or (skill == target_skill and xp <= 0):
        raise ValueError(f"Invalid modeled rate for {recipe['Id']}.")
    return Action(recipe["Id"], recipe["DisplayName"], kind, skill, data["Level"], product["Item"],
                  output, inputs, interval * hits / 1000, xp, preservation, applied)


def bowstring_exchange(purchase, decoded):
    requirement, = purchase["Requirements"]
    rule = requirement["Data"]
    if (requirement["Type"] != NS + "MasteryGuildRank" or rule["Component"]["Component"] != "MasteryGuild"
            or rule.get("IsOr") or purchase["DefaultBuyLimit"] != 0
            or purchase["Costs"]["Currencies"] or purchase["Provides"]["Currencies"]):
        raise ValueError("Unsupported Bowstring exchange rules.")
    rank = decoded["mastery_ranks"].get(rule["Component"]["Entity"].removeprefix(NS))
    if not rank or rank["rank_pct"][rank["rank_min"]] < rank["rank_pct"][rule["Rank"]]:
        return None
    (product, quantity), = item_quantities(purchase["Provides"]["Items"]).items()
    if product != NS + "Bowstring":
        raise ValueError("Unexpected Bowstring exchange product.")
    return Action("BowstringExchange", "Bowstring exchange", "Shop", "Crafting", 0, product, quantity,
                  item_quantities(purchase["Costs"]["Items"]), 0, 0, 0, {})


class Stage:
    def __init__(self, stock, bank):
        self.stock = dict(stock)
        self.bank = dict(bank)
        self.bank_used = defaultdict(float)
        self.seconds = self.xp = 0
        self.actions = []

    def prepare(self, action, count, suppliers):
        for item, quantity in action.inputs.items():
            consumed = count * quantity * (1 - action.preservation)
            # Each craft must still have its full input on hand before the preservation roll.
            needed = max(quantity, consumed + quantity * action.preservation)
            available = self.stock.get(item, 0)
            if available + 1e-9 < needed:
                supplier = suppliers[item]
                batches = ceil((needed - available) / supplier.output - 1e-10)
                self.run(supplier, batches, suppliers)

    def finish(self, action, count):
        if not count:
            return
        for item, quantity in action.inputs.items():
            consumed = count * quantity * (1 - action.preservation)
            bank_used = min(consumed, self.bank.get(item, 0))
            self.bank_used[item] += bank_used
            self.bank[item] = self.bank.get(item, 0) - bank_used
            self.stock[item] = self.stock.get(item, 0) - consumed
        self.stock[action.product] = self.stock.get(action.product, 0) + count * action.output
        self.actions.append({"id": action.id, "count": count})
        self.xp += count * action.xp
        self.seconds += count * action.seconds

    def run(self, action, count, suppliers):
        self.prepare(action, count, suppliers)
        self.finish(action, count)


def train(action, suppliers, stock, bank, xp_needed):
    def trial(count):
        stage = Stage(stock, bank)
        stage.run(action, count, suppliers)
        return stage

    # Extra Fletching XP from shafts and headless arrows changes the number of final crafts.
    low = 1
    high = ceil(xp_needed / action.xp)
    while low < high:
        midpoint = (low + high) // 2
        if trial(midpoint).xp + 1e-9 >= xp_needed:
            high = midpoint
        else:
            low = midpoint + 1
    stage = Stage(stock, bank)
    stage.prepare(action, low, suppliers)
    if stage.xp + low * action.xp - action.xp + 1e-9 >= xp_needed:
        # The final craft can be omitted if preparing its supplies already reaches the cutoff.
        low = max(0, ceil((xp_needed - stage.xp - 1e-9) / action.xp))
    stage.finish(action, low)
    return stage


def available_plans(bands, recipes, suppliers, stock, bank, level, xp, xp_table):
    if not bands:
        yield ()
        return
    (target, options), *remaining = bands
    if xp + 1e-9 >= xp_table[target - 1]:
        yield from available_plans(remaining, recipes, suppliers, stock, bank, max(level, target), xp, xp_table)
        return
    for recipe in options:
        action = recipes[recipe]
        if action.level > level:
            raise ValueError(f"{action.name} now requires level {action.level}. Review the guide's recipe bands.")
        attempt = train(action, suppliers, stock, bank, xp_table[target - 1] - xp)
        end_xp = xp + attempt.xp
        result = {"level_start": level, "level_target": target, "recipe": recipe,
                  "xp_after": end_xp, "xp_gained": attempt.xp, "seconds": attempt.seconds,
                  "actions": attempt.actions, "bank_used": dict(attempt.bank_used)}
        for later in available_plans(remaining, recipes, suppliers, attempt.stock, attempt.bank,
                                     target, end_xp, xp_table):
            yield (result, *later)


def calculate_guide(guide, reference, snapshot, decoded, data, xp_table, chicken_seconds=None):
    if ("Inventory" not in decoded["components_present"].get("Bank", {})
            or any("Bank/Inventory:" in warning for warning in decoded["warnings"])):
        raise ValueError("The bank could not be decoded. Refreshing the personalized guide stopped.")
    skill = guide["skill"]
    current = snapshot["skills"][skill]
    xp, level = current["xp"], current["level"]
    target = guide["level_end"]
    if not isfinite(xp) or xp < 0:
        raise ValueError("The saved skill XP is invalid.")
    settings = reference["personalization"]
    bands = settings["stages"]
    boundaries = [band["start"] for band in bands] + [target]
    if (not bands or boundaries[0] != guide["level_start"] or sorted(set(boundaries)) != boundaries
            or target > len(xp_table) or any(not band["recipes"] for band in bands)):
        raise ValueError("The personalized guide has invalid level bands.")
    if level < guide["level_start"]:
        raise ValueError(f"The saved {skill} level is below this guide's start.")

    recipes = {}
    suppliers = {}
    objects = data["Objects"]
    stage_recipes = {recipe for band in bands for recipe in band["recipes"]}
    component_recipes = settings["component_recipes"]
    for kind, ids in (
        ("Artisan", stage_recipes | set(component_recipes)),
        ("Woodcutting", settings["woodcutting_recipes"]),
        ("Mining", settings["mining_recipes"]),
    ):
        records = {record["Id"]: record for record in objects[kind + "Recipe"]}
        for recipe in sorted(ids):
            action = build_action(snapshot, records[recipe], kind, skill)
            if recipe in stage_recipes and action.skill != skill:
                raise ValueError(f"{action.name} no longer trains {skill}.")
            recipes[recipe] = action
            if kind != "Artisan" or recipe in component_recipes:
                suppliers[action.product] = action

    assumptions = reference["assumptions"]
    cycle_source = "user supplied" if chicken_seconds is not None else "reference scenario"
    if chicken_seconds is None:
        chicken_seconds = assumptions["giant_chicken_cycle_seconds"]
    feather_yield = assumptions["expected_feathers_per_kill"]
    feathers = Action("GiantChicken", "Giant Chicken", "Combat", "Combat", 0, NS + "Feathers",
                      feather_yield, {}, chicken_seconds, 0, 0, {})
    recipes[feathers.id] = suppliers[feathers.product] = feathers
    purchases = {record["Id"]: record for record in objects["ShopPurchase"]}
    purchase = purchases["Bowstring"]
    exchange = bowstring_exchange(purchase, decoded)
    supplier_options = [suppliers]
    if exchange:
        recipes[exchange.id] = exchange
        supplier_options.append({**suppliers, exchange.product: exchange})

    stock = decoded["bank"]
    pending = [(end, band["recipes"]) for end, band in zip(boundaries[1:], bands) if level < end]
    stages = min(
        (plan for option in supplier_options
         for plan in available_plans(pending, recipes, option, stock, stock, level, xp, xp_table)),
        key=lambda plan: sum(stage["seconds"] for stage in plan),
    )
    actions = {entry["id"]: recipes[entry["id"]] for stage in stages for entry in stage["actions"]}
    required = {}
    bank_used, to_gather = defaultdict(float), defaultdict(float)
    for stage in stages:
        for item, quantity in stage["bank_used"].items():
            bank_used[item] += quantity
        for entry in stage["actions"]:
            action = actions[entry["id"]]
            if action.skill not in {skill, "Combat"} and action.level > snapshot["skills"][action.skill]["level"]:
                required[action.skill] = max(required.get(action.skill, 0), action.level)
            if action.kind in {"Woodcutting", "Mining", "Combat"}:
                to_gather[action.product] += entry["count"] * action.output
    stock_used = {item: quantity for item, quantity in bank_used.items() if quantity > 1e-9}
    source_ids = {row["source"] for action in actions.values() for modifier in action.modifiers.values()
                  for row in modifier["contributions"]}
    names = {NS + item["Id"]: item["DisplayName"]["Singular"] for item in objects["Item"]
             if NS + item["Id"] in stock_used or NS + item["Id"] in to_gather}
    return {
        "schema_version": 1, "guide_id": guide["id"], "skill": skill, "snapshot": snapshot["snapshot"],
        "coverage": snapshot["coverage"], "current": {"level": level, "xp": xp},
        "target": {"level": target, "xp": xp_table[target - 1]},
        "assumptions": {"chicken_cycle_seconds": chicken_seconds, "expected_feathers_per_kill": feather_yield,
                        "chicken_cycle_source": cycle_source,
                        "bowstring_exchange_confirmed": exchange is not None, "missing_auxiliary_levels": required},
        "stages": stages, "seconds": sum(stage["seconds"] for stage in stages),
        "action_models": {key: vars(action) for key, action in actions.items()}, "item_names": names,
        "bank_used": stock_used, "to_gather": dict(to_gather),
        "sources": {key: snapshot["sources"][key] for key in sorted(source_ids)},
    }
