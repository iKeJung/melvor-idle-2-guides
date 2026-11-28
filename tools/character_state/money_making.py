"""Compare selected repeatable GP methods using Melvor Idle 2 game data."""
from dataclasses import asdict, replace
from math import ceil, floor

from guide_plan import NS, build_action, chance, modifiers, require_bank_inventory

SCOPE = {"combat": 30, "non_combat": 40}
GATHERING = {
    "Woodcutting": ("NormalTree", "FlaxBush", "OakTree", "AmbervineBush", "WillowTree", "TeakTree"),
    "Mining": ("Stone", "Clay", "CopperOre", "RuneEssence", "Topaz", "IronOre", "SilverOre", "Coal",
               "Sapphire", "GoldOre", "MithrilOre"),
    "Fishing": ("ShallowPools", "CalmShallows", "QuietBend", "DockWaters", "PebbleBank",
                "WindsweptShores", "PierWalk", "RapidRuns"),
}
ARTISAN = (
    "StoneSword", "StonePlatebody", "CopperBar", "CopperPlatebody", "IronBar", "IronPlatelegs",
    "IronPlatebody", "SilverBar", "SteelBar", "SteelDagger", "SteelShield", "SteelPlatebody",
    "MithrilBar", "MithrilDagger", "GoldBar", "NormalBow", "OakBow", "WillowBow",
    "Topaz", "Sapphire", "SilverTopazRing", "SilverTopazAmulet", "SilverSapphireRing",
    "AirWand", "WaterWand", "EarthWand", "FireWand", "FireStaff",
)
INTERMEDIATES = (
    "Bowstring", "MoltenGlass", "UnpoweredOrb", "AirRune", "MindRune", "WaterRune", "EarthRune", "FireRune",
)
THIEVING = (
    "Citizen", "Thug", "LockedThugChest", "CookingStall", "ThugChief", "Craftsman", "Fisherman",
    "Farmer", "Chef", "Bandit", "LockedRanchersChest", "MarketSeedStall", "Herbalist",
)
COMBAT = {
    "GolbinForest": {"Golbin": 1, "GolbinScout": 1, "GolbinAmbusher": 4, "Hobgolbin": 12},
    "CorruptedFarmlands": {"EvilPlant": 5, "GiantChicken": 7, "MagicCow": 9, "Scarecrow": 15, "JackOLantern": 21},
    "GreenMangroves": {"MangroveStrider": 26},
}
QUESTS = ("MQ1", "MQ2", "MQ3")
SHOP = ("CopperFishingRod", "BankSpaceFishing1")


def indexes(data):
    return {kind: {row["Id"]: row for row in rows} for kind, rows in data["Objects"].items()}


def mean_range(record):
    return (record["MinQuantity"] + record["MaxQuantity"]) / 2


def weighted_value(rows, value, quantity=mean_range):
    weight = sum(row["Weight"] for row in rows)
    return sum(value(row["Item"]) * quantity(row) * row["Weight"] for row in rows) / weight if weight else 0


def requirements(*records):
    result = {}
    for record in records:
        for req in record.get("Requirements") or ():
            rule = req["Data"]
            if (req["Type"] != NS + "Level" or rule["IsOr"]
                    or rule["Component"]["Component"] != "Experience"):
                raise ValueError(f"Unsupported requirement for {record['Id']}.")
            skill = rule["Component"]["Entity"].removeprefix(NS)
            result[skill] = max(result.get(skill, 1), rule["Level"])
    if any(level > SCOPE["non_combat"] for level in result.values()):
        raise ValueError(f"Method exceeds the non-combat scope: {result}.")
    return result


def fishing(row, location, snapshot, value):
    applied = {}
    stat = modifiers(snapshot, "Fishing", "FishingAction", row, None, applied,
                     context={"Recipe": NS + row["Id"], "Location": row["Location"]},
                     excluded_via=("fishing_bait",))

    def percent(name):
        return stat(name, "percentage_fraction")

    def interval(bound):
        return floor((row[f"Base{bound}Interval"] + stat(f"Flat{bound}Interval", "ms"))
                     * (1 + percent(f"Percent{bound}Interval")))

    minimum = interval("Min")
    seconds = (minimum + max(minimum, interval("Max"))) / 2000
    fish = chance((row["FishChance"] + percent("FlatFishChance")) * (1 + percent("IncreasedFishChance")))
    fish += (1 - fish) * chance(percent("JunkRerollChance"))
    doubling = chance(percent("DoublingChance"))
    gp = (fish * weighted_value(row["RandomProducts"], value) + (1 - fish) * value(row["JunkItem"]))
    gp *= 1 + doubling
    if seconds <= 0:
        raise ValueError(f"Invalid fishing interval for {row['Id']}.")
    return {
        "id": row["Id"], "name": row["DisplayName"], "skill": "Fishing", "kind": "Fishing",
        "requirements": requirements(row, location), "location": location["DisplayName"],
        "seconds": seconds, "gp_per_cycle": gp, "gp_per_hour": gp * 3600 / seconds,
        "fish_chance": fish, "modifiers": applied,
    }


def shop_supply(record):
    item, = record["Provides"]["Items"]
    cost, = record["Costs"]["Currencies"]
    if (cost["Currency"] != NS + "GoldPieces" or record["Costs"]["Items"]
            or record["Requirements"] or record["DisplayRequirements"] or record["DefaultBuyLimit"]):
        raise ValueError(f"Unsupported shop supply: {record['Id']}.")
    return item["Item"], cost["Quantity"] / item["Quantity"]


def chain(action, suppliers, shop):
    """Return expected cycles for one finished batch, including all upstream actions."""
    steps = {action.id: 1.0}
    gp = 0.0
    for item, count in action.inputs.items():
        used = count * (1 - action.preservation)
        if item in shop:
            gp += used * shop[item]
            continue
        source = suppliers[item]
        upstream, cost = chain(source, suppliers, shop)
        batches = used / source.output
        gp += cost * batches
        for recipe_id, cycles in upstream.items():
            steps[recipe_id] = steps.get(recipe_id, 0) + cycles * batches
    return steps, gp


def sale_method(action, actions, suppliers, shop, value):
    steps, cost = chain(action, suppliers, shop)
    levels = {}
    seconds = 0.0
    for recipe_id, cycles in steps.items():
        stage = actions[recipe_id]
        levels[stage.skill] = max(levels.get(stage.skill, 1), stage.level)
        seconds += cycles * stage.seconds
    sale = action.output * value(action.product)
    return {
        "id": action.id, "name": action.name, "skill": action.skill, "kind": action.kind,
        "requirements": levels, "steps": steps, "seconds": seconds, "sale_gp": sale, "input_gp": cost,
        "gp_per_cycle": sale - cost, "gp_per_hour": 3600 * (sale - cost) / seconds,
    }


def stock_job(action, bank, value):
    if not action.inputs:
        return None
    batches = min(bank.get(item, 0) // quantity for item, quantity in action.inputs.items())
    if batches < 1:
        return None
    gain = batches * (action.output * value(action.product)
                      - sum(quantity * (1 - action.preservation) * value(item)
                            for item, quantity in action.inputs.items()))
    if gain <= 0:
        return None
    return {
        "id": action.id, "name": action.name, "batches": batches,
        "inputs": {item: quantity * batches for item, quantity in action.inputs.items()},
        "seconds": action.seconds * batches, "extra_gp": gain, "extra_gp_per_hour": gain * 3600 / (action.seconds * batches),
    }


def thieving(row, location, snapshot, decoded, value, items):
    levels = requirements(row, location)
    if row["Stages"] != 1 or row["CompletionDropTable"] or row["HeistBonuses"]:
        raise ValueError(f"Unsupported Thieving method: {row['Id']}.")
    access = row.get("AccessRequirements") or []
    access_items = []
    for req in access:
        rule = req["Data"]
        if (req["Type"] != NS + "ToolbeltItemEquipped" or rule["Quantity"] != 1
                or rule["IsOr"] != bool(access_items)
                or rule["Component"] != {"Entity": NS + "Thieving", "Component": "Toolbelt"}):
            raise ValueError(f"Unsupported access rule for {row['Id']}.")
        access_items.append(rule["Item"])
    tool = decoded.get("toolbelts", {}).get("Thieving", {}).get("ThievingTool", {})
    equipped = tool.get("item")
    base = "snapshot" not in snapshot
    eligible_tool = not access_items or equipped in access_items
    # Show the lockpick case for the public guide and for missing or mismatched equipment.
    assumed_tool = equipped if eligible_tool else access_items[0]
    used_per_attempt = bool(access_items and assumed_tool == NS + "Lockpick")
    applied = {}
    skill_level = snapshot["skills"]["Thieving"]["level"]
    stat = modifiers(snapshot, "Thieving", "ThievingAction", row, None, applied, context={
        "Recipe": NS + row["Id"], "Category": row["Category"], "RecipeType": row["RecipeType"],
    })

    def percent(name):
        return stat(name, "percentage_fraction")

    def modified(value, field, unit="game_value"):
        return max(0, floor((value + stat("Flat" + field, unit)) * (1 + percent("Percent" + field))))

    stealth = modified(max(skill_level, levels["Thieving"]), "Stealth")
    perception = modified(row["Perception"], "Perception")
    success = min(1, (100 + stealth) / (100 + perception))
    interval = modified(row["BaseInterval"], "Interval", "ms")
    stun = modified(2000, "StunInterval", "ms")
    seconds = (interval + (1 - success) * (1 - chance(percent("StunAvoidanceChance"))) * stun) / 1000
    if interval <= 0:
        raise ValueError(f"Invalid Thieving interval for {row['Id']}.")
    reward = row["CurrencyReward"]
    currency = 0
    if reward["Currency"] == NS + "GoldPieces":
        currency = (modified(reward["MinQuantity"], "CurrencyReward")
                    + modified(reward["MaxQuantity"], "CurrencyReward")) / 2
        currency *= chance(row["BaseCurrencyLootChance"] * (1 + percent("PercentCurrencyLootChance")))
    fortune = stat("FlatFortune", "game_value")
    if success < 1:
        fortune += stat("FlatFortuneUnderSuccess", "game_value")

    def loot_quantity(drop):
        quantities = range(drop["MinQuantity"], drop["MaxQuantity"] + 1)
        return sum(floor(n * (1 + fortune / 100)) for n in quantities) / len(quantities)

    common = weighted_value(row["CommonDropTable"], value, loot_quantity)
    common *= chance(row["BaseCommonLootChance"] * (1 + percent("PercentCommonLootChance")))
    common *= 1 + chance(percent("DoublingChance"))
    lockpick_cost = value(NS + "Lockpick") if used_per_attempt else 0
    gp = success * (currency + common) - lockpick_cost
    return {
        "id": row["Id"], "name": row["DisplayName"], "skill": "Thieving", "location": location["DisplayName"],
        "kind": "Thieving", "requirements": levels, "assumed_level": max(skill_level, levels["Thieving"]),
        "access_items": [items[item.removeprefix(NS)]["DisplayName"]["Singular"] for item in access_items],
        "tool": assumed_tool if access_items else None,
        "tool_quantity": tool.get("qty") if access_items and eligible_tool and not base else None,
        "tool_ready": eligible_tool,
        "success": success, "max_damage": row["Damage"], "seconds": seconds,
        "direct_gp_per_success": currency, "common_gp_per_success": common, "lockpick_gp_per_attempt": lockpick_cost,
        "gp_per_cycle": gp, "gp_per_hour": gp * 3600 / seconds, "modifiers": applied,
    }


def combat(entries, value):
    for area_id, enemies in COMBAT.items():
        area = entries["CombatArea"][area_id]
        if area["UnlockRequirements"] or area["DisplayRequirements"]:
            raise ValueError(f"Unsupported combat access rule for {area_id}.")
        for enemy_id, level in enemies.items():
            if level > SCOPE["combat"]:
                raise ValueError(f"Enemy exceeds the combat scope: {enemy_id}.")
            row = entries["Enemy"][enemy_id]
            if row["Requirements"] or row["DisplayRequirements"] or NS + enemy_id not in area["Enemies"]:
                raise ValueError(f"Unsupported combat access rule for {enemy_id}.")
            drops = row["Drops"]
            gp = sum(mean_range(reward) for reward in drops["FixedCurrencies"]
                     if reward["Currency"] == NS + "GoldPieces")
            items = sum(mean_range(drop) * value(drop["Item"]) for drop in drops["FixedItems"])
            items += sum(table["Chance"] * weighted_value(table["Table"], value) for table in drops["ItemTables"])
            yield {"id": enemy_id, "name": row["DisplayName"], "level": level, "area": area["DisplayName"],
                   "direct_gp_per_kill": gp, "loot_gp_per_kill": items, "total_gp_per_kill": gp + items}


def compare(data, snapshot=None, decoded=None):
    personal = snapshot is not None
    if personal:
        require_bank_inventory(decoded)
    entries = indexes(data)
    items = entries["Item"]
    snapshot = snapshot if personal else {"skills": {
        skill: {"level": 1, "modifiers": {}} for skill in (*GATHERING, "Smithing", "Crafting", "Fletching",
                                                         "Runecrafting", "Thieving")
    }, "sources": {}}
    decoded = decoded if personal else {}
    levels = {skill: detail["level"] for skill, detail in snapshot["skills"].items()}

    def value(item):
        sale = items[item.removeprefix(NS)]["SellsFor"]
        return sale["Quantity"] if sale and sale["Currency"] == NS + "GoldPieces" else 0

    actions, methods, inputs, artisan_rows = {}, [], {}, {}
    for skill, recipes in GATHERING.items():
        table = entries[skill + "Recipe"]
        for key in recipes:
            row = table[key]
            if skill == "Fishing":
                location = entries["FishingLocation"][row["Location"].removeprefix(NS)]
                methods.append(fishing(row, location, snapshot, value))
                fields = ("Location", "BaseMinInterval", "BaseMaxInterval", "FishChance", "RandomProducts",
                          "JunkItem", "Requirements")
            else:
                requirements(row)
                action = build_action(snapshot, row, skill, None)
                key = f"{skill}/{key}" if key in ARTISAN else key
                actions[key] = replace(action, id=key)
                fields = ("BaseInterval", "BaseMaxHealth", "BaseProductChance", "Product", "Requirements")
            inputs[key] = {field: row[field] for field in fields if field in row}
            if skill == "Fishing":
                inputs[key]["RandomProducts"] = [
                    {field: product[field] for field in ("Item", "MinQuantity", "MaxQuantity", "Weight")}
                    for product in row["RandomProducts"]
                ]
    for key in (*ARTISAN, *INTERMEDIATES):
        row = entries["ArtisanRecipe"][key]
        requirements(row)
        actions[key] = build_action(snapshot, row, "Artisan", None)
        artisan_rows[key] = row
        inputs[key] = {field: row[field] for field in ("BaseInterval", "Steps", "Ingredients", "Products", "Requirements")}
    suppliers = {action.product: action for action in actions.values()}
    sand, price = shop_supply(entries["ShopPurchase"]["BucketofSand"])
    shop = {sand: price}
    methods.extend(sale_method(action, actions, suppliers, shop, value) for action in actions.values()
                   if action.id not in INTERMEDIATES)
    for key in THIEVING:
        row = entries["ThievingRecipe"][key]
        location = entries["ThievingLocation"][row["Category"].removeprefix(NS)]
        methods.append(thieving(row, location, snapshot, decoded, value, items))
        inputs[key] = {field: row[field] for field in ("BaseInterval", "Perception", "Damage",
                                                     "BaseCurrencyLootChance", "CurrencyReward", "BaseCommonLootChance",
                                                     "CommonDropTable", "Requirements", "AccessRequirements")}
    targets = list(combat(entries, value))
    for target in targets:
        inputs[target["id"]] = entries["Enemy"][target["id"]]["Drops"]

    def unlocked(requirements):
        return all(levels.get(skill, 0) >= level for skill, level in requirements.items())

    gold = decoded.get("currencies", {}).get("GoldPieces")
    # Use unmodified artisan batches to budget the first shop purchase.
    unmodified = {key: build_action({"skills": {actions[key].skill: {"modifiers": {}}}}, row, "Artisan", None)
                  for key, row in artisan_rows.items()}
    base_suppliers = {**suppliers, **{action.product: action for action in unmodified.values()}}
    for method in methods:
        method["missing_levels"] = {skill: level for skill, level in method["requirements"].items()
                                    if levels.get(skill, 0) < level} if personal else {}
        if method["kind"] == "Artisan":
            _, cash = chain(unmodified[method["id"]], base_suppliers, shop)
            if cash:
                method["cash_for_base_batch"] = ceil(cash)
                method["cash_ready"] = not personal or (gold is not None and gold >= ceil(cash))
        method["available"] = (not method["missing_levels"] and method.get("tool_ready", True)
                               and method.get("cash_ready", True)) if personal else None

    bank = {}
    for tab in decoded.get("bank_tabs", []):
        for stack in tab["stacks"]:
            if not stack["locked"] and not stack["placeholder"]:
                bank[stack["item"]] = bank.get(stack["item"], 0) + stack["qty"]
    jobs = [job for action in actions.values() if unlocked({action.skill: action.level})
            if (job := stock_job(action, bank, value))]
    prices = {
        item: value(item) for item in sorted({action.product for action in actions.values()}
                                           | set(shop) | {NS + "Lockpick"}
                                           | {i for table in inputs.values() for i in referenced_items(table)})
    }
    result = {
        "scope": SCOPE, "units": {"currency": "GP", "duration": "seconds", "rate": "GP/hour"},
        "methods": sorted(methods, key=lambda row: -row["gp_per_hour"]),
        "combat": targets, "action_models": {key: asdict(action) for key, action in actions.items()},
        "inputs": inputs, "sale_prices": prices, "shop_supply_gp": shop,
        "quests": [{"id": key, "name": entries["Quest"][key]["DisplayName"],
                    "gp": sum(c["Quantity"] for c in entries["Quest"][key]["Rewards"]["Currency"]
                              if c["Currency"] == NS + "GoldPieces")} for key in QUESTS],
        "shop_examples": {key: {field: entries["ShopPurchase"][key][field] for field in
                                ("DisplayName", "Costs", "Requirements")} for key in SHOP},
    }
    if personal:
        result.update(snapshot=snapshot["snapshot"], coverage=snapshot["coverage"], sources=snapshot["sources"],
                      levels=levels, gold=gold, bank_jobs=sorted(jobs, key=lambda row: -row["extra_gp_per_hour"]),
                      bank_item_names={item: items[item.removeprefix(NS)]["DisplayName"]["Singular"]
                                       for job in jobs for item in job["inputs"]})
    return result


def referenced_items(value):
    if isinstance(value, dict):
        for key, entry in value.items():
            if key in {"Item", "JunkItem"}:
                yield entry
            else:
                yield from referenced_items(entry)
    elif isinstance(value, list):
        for entry in value:
            yield from referenced_items(entry)
