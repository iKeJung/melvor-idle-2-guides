"""Render the public and local money-making guides as standalone HTML."""
from datetime import datetime
from html import escape
from pathlib import Path
from string import Template

HERE = Path(__file__).resolve().parent

SOURCES = {
    "Steam public branch history": "https://steamdb.info/app/3218350/depots/#branches",
    "Official Steam patch notes": "https://steamcommunity.com/app/3218350/allnews/",
    "Mining calculator": "https://melvor2.com/calculators/mining/",
    "Fishing calculator": "https://melvor2.com/calculators/fishing/",
    "Smithing calculator": "https://melvor2.com/calculators/smithing/",
    "Crafting calculator": "https://melvor2.com/calculators/crafting/",
    "Thieving calculator": "https://melvor2.com/calculators/thieving/",
    "Lockpick sources": "https://melvor2.com/items/lockpick/",
    "Giant Chicken's drops": "https://melvor2.com/monsters/giant-chicken/",
    "Mangrove Strider's drops": "https://melvor2.com/monsters/mangrove-strider/",
    "Combat monster directory": "https://melvor2.com/monsters/",
    "Quest guide": "https://melvor2.com/guides/melvor-idle-2-quests-guide/",
    "Shop and sales overview": "https://melvor2.com/guides/melvor-idle-2-early-game-money-making/",
}

SOURCE_BUILDS = {
    "Steam public branch history": 26886380,
    "Mining calculator": 26724394,
    "Fishing calculator": 26724394,
    "Smithing calculator": 26886380,
    "Crafting calculator": 26886380,
    "Thieving calculator": 26724394,
    "Lockpick sources": 26724394,
    "Giant Chicken's drops": 26886380,
    "Mangrove Strider's drops": 26724394,
    "Combat monster directory": 26886380,
    "Quest guide": 26886380,
    "Shop and sales overview": 26724394,
}

ASSUMPTIONS = [
    "Gathering and crafting use expected yields across long runs and sell the listed output at the in-game GP price.",
    "Chains start with empty stock, and their GP/h includes all listed gathering and processing plus shop input costs. Skill training, shopping clicks, menus, and sale time are outside the estimate.",
    "Fishing uses the ordinary catch and Junk rolls. The scenario omits bait, priority fish, and special catches. Mining and Woodcutting omit extra drops such as Geodes and Bird Nests.",
    "Thieving models direct GP and common loot. It includes normal failed attempts and stuns. Rare loot, extra pickpockets, food, and lockpick replenishment time are outside the estimate.",
    "Combat values use published base drops and assume all listed loot can be collected for sale. GP/h requires a timed session with the chosen gear and supplies.",
]


def num(value, digits=0):
    return f"{value:,.{digits}f}"


def levels_text(levels):
    return ", ".join(f"{skill} {level}" for skill, level in sorted(levels.items()))


def table(headers, rows):
    headings = "".join(f'<th scope="col">{escape(header)}</th>' for header in headers)
    body = []
    for row in rows:
        cells = "".join(f'<td class="num">{cell}</td>' if isinstance(cell, (float, int))
                        else f"<td>{escape(cell)}</td>" for cell in row)
        body.append(f"<tr>{cells}</tr>")
    return f'<div class="table"><table><thead><tr>{headings}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def detail(title, content, expanded=False):
    return f'<details{" open" if expanded else ""}><summary>{escape(title)}</summary>{content}</details>'


def group_methods(methods):
    groups = {
        "Woodcutting": [], "Mining": [], "Fishing": [], "Crafting and processing": [], "Thieving": [],
    }
    for row in methods:
        group = "Crafting and processing" if row["kind"] == "Artisan" else row["kind"]
        groups[group].append(row)
    return groups


def status(row):
    problems = []
    if row["missing_levels"]:
        problems.append("Reach " + levels_text(row["missing_levels"]))
    if not row.get("tool_ready", True):
        problems.append("Equip " + " or ".join(row["access_items"]))
    if not row.get("cash_ready", True):
        problems.append(f"Budget {num(row['cash_for_base_batch'])} GP for one batch from scratch")
    return ". ".join(problems) or "Prerequisites met"


def method_tables(methods, personal=False):
    result = []
    for group, rows in group_methods(methods).items():
        headers = ["Method", "Requirements", "Seconds per cycle", "GP per cycle", "GP/h"]
        if group == "Thieving":
            headers[2:2] = ["Success at level", "Max damage"]
        if personal:
            headers.insert(2, "Save status")
            rows = sorted(rows, key=lambda row: not row["available"])
        cells = []
        for row in rows:
            name = row["name"] + (" · " + row["location"] if "location" in row else " · " + row["skill"])
            reqs = levels_text(row["requirements"])
            if row.get("access_items"):
                reqs += " + " + " or ".join(row["access_items"]) + " equipped"
            if row.get("cash_for_base_batch"):
                reqs += f" + {num(row['cash_for_base_batch'])} GP per base batch"
            fields = [name, reqs]
            if personal:
                current = status(row)
                if row.get("tool_quantity") is not None and row["lockpick_gp_per_attempt"]:
                    current += f" · {row['tool_quantity']:,} lockpicks equipped"
                fields.append(current)
            if group == "Thieving":
                fields.extend([f"{row['success']:.1%} at {row['assumed_level']}", row["max_damage"]])
            fields.extend(num(row[key], 0 if key == "gp_per_hour" else 2)
                          for key in ("seconds", "gp_per_cycle", "gp_per_hour"))
            cells.append(fields)
        result.append(detail(group, table(headers, cells), expanded=group == "Crafting and processing" and personal))
    return "".join(result)


def combat_section(report, benchmark):
    rows = []
    for row in sorted(report["combat"], key=lambda target: target["level"]):
        gp = row["total_gp_per_kill"]
        rows.append((row["name"], row["area"], row["level"], num(row["direct_gp_per_kill"], 2),
                     num(row["loot_gp_per_kill"], 2), num(gp, 2), num(gp * 3600 / benchmark, 1)))
    return f'''<section id="combat">
      <h2>Combat through level {report["scope"]["combat"]}</h2>
      <p>Start with Golbin Forest to check your damage and food use. Test Giant Chicken in Corrupted Farmlands next, then compare stronger targets as your gear improves. Try Mangrove Strider only when a supervised run shows the setup can sustain it. Check enemy attacks, loadout, healing and loot collection before leaving a fight unattended.</p>
      <p>The last column gives the longest average kill cycle that can match {num(benchmark)} GP/h before supply costs. Include the respawn and all downtime. Start with direct GP if you are keeping the loot. Use the measured session below for net GP/h with your equipment.</p>
      {table(("Enemy", "Area", "Enemy level", "Direct GP/kill", "Loot GP/kill", "Total GP/kill", "Break-even s/kill"), rows)}
    </section>'''


def assumptions(report):
    return "<ul>" + "".join(f"<li>{escape(line)}</li>" for line in report["assumptions"]) + "</ul>"


def sources(report):
    reference = report["reference_build"]
    links = []
    for source in report["sources_used"]:
        build = f' · build {source["steam_build"]}' if source["steam_build"] else ""
        links.append(f'<li>{source["channel"]}{build} · <a href="{source["url"]}">{escape(source["name"])}</a></li>')
    return f'''<section id="sources">
      <h2>Data and sources</h2>
      <p>Base values and action logic checked against the installed Windows Steam Early Access package and game assembly, version {reference["version"]}, public build {reference["steam_build"]}. The community pages cross-check selected values and identify actions. The installed build provides the calculation inputs.</p>
      <p>Sources accessed {reference["accessed_on"]}. The first Early Access patch fixed bait preservation. Both guide views use a bait-free Fishing baseline.</p>
      <ul>{"".join(links)}</ul>
    </section>'''


def page(title, eyebrow, intro, links, content, benchmark, footer):
    nav = "".join(f'<a href="#{anchor}">{escape(label)}</a>' for anchor, label in links)
    template = Template((HERE / "money-making.html").read_text(encoding="utf-8"))
    return template.substitute(title=escape(title), eyebrow=escape(eyebrow), intro=intro, navigation=nav,
                               content=content, benchmark=benchmark, footer=footer)


def render_public(report):
    methods = {row["id"]: row for row in report["methods"]}
    actions = report["action_models"]
    route = [
        ("Starting from level 1", "NormalTree", "Sell spare logs. Use Shallow Pools to build a food reserve."),
        ("First manufacturing", "CopperPlatebody", "Keep enough Copper Bars for your next tool or quest."),
        ("Iron gear", "IronPlatelegs", "Mine, smelt and smith. Compare the entire chain with raw ore sales."),
        ("Jewellery", "SilverTopazAmulet", "Mine Topaz and Silver Ore, cut the gems, smelt the silver and craft."),
        ("Steel alternative", "SteelPlatebody", "Use Coal and Iron Ore. Try the Steel Dagger when Smithing reaches 25."),
        ("Simple later option", "TeakTree", "Sell spare Teak Logs. Try Rapid Runs when you also want fish."),
    ]
    rows = [(stage, methods[key]["name"], levels_text(methods[key]["requirements"]),
             num(methods[key]["gp_per_hour"]), advice) for stage, key, advice in route]
    fishing = []
    best_rate = 0
    for row in sorted(group_methods(report["methods"])["Fishing"], key=lambda option: option["requirements"]["Fishing"]):
        if row["gp_per_hour"] > best_rate:
            fishing.append(f'{row["name"]} ({row["requirements"]["Fishing"]})')
            best_rate = row["gp_per_hour"]
    worked = methods["IronPlatelegs"]
    gp_sale = report["sale_prices"]["MelvorBase:IronPlatelegs"]
    shop = report["shop_examples"]
    rod = shop["CopperFishingRod"]
    bank = shop["BankSpaceFishing1"]
    quest_goals = {
        "MQ1": "Hand in 24 Stone Arrows and defeat 3 Archery Targets with Ranged. Keep the reward arrows and Shrimp for combat.",
        "MQ2": "Hand in 3 Copper Swords, catch 15 Raw Sardine and defeat 5 Golbin Ambushers. Save the 100 Copper Bars for tools or craft with the surplus.",
        "MQ3": "Clear Wood and Stone Debris, hand in 50 Mackerel Bait, catch 15 Raw Trout and defeat the Enraged Boar.",
    }
    quests = table(("Main quest", "One-time GP", "Preparation"),
                   ((row["name"], num(row["gp"]), quest_goals[row["id"]]) for row in report["quests"]))
    content = rf'''<section id="route">
      <h2>What to do next</h2>
      <p>Start with surplus logs or fish and collect quest rewards when their goals overlap your training. Iron Platelegs are an early option once Mining 10 and Smithing 18 are ready. Silver Topaz Amulets give the highest base GP/h among the gathering and crafting chains compared here. Use a simpler gathering action if its rate with your tools beats the chain or if you want the materials for another skill.</p>
      {table(("Milestone", "Method", "Required levels", "Base GP/h", "How to use it"), rows)}
      <p>For bait-free fish sales, upgrade your spot along this base GP/h sequence as the levels become available. {escape(" → ".join(fishing))}. Keep raw fish you intend to cook for combat or Thieving.</p>
      <p>For early Thieving, try Citizen or Thug first and check your food use. Locked Thug Chest at Thieving 10 takes either a Lockpick or a Thug Chest Key in the toolbelt. Thug can drop Lockpicks. Each chest attempt spends a pick regardless of success. The reusable key gives +500 Stealth and +50 Fortune on that chest. Compare chest runs with your actual food and pick supply, then try Fisherman at 20 or Bandit and Chef later in the range.</p>
    </section>
    <section id="rates">
      <h2>Compare repeatable methods</h2>
      <p>Expand a method group to see the levels and rates. Gathering uses one full cut, break or cast. Artisan rows use one full finished batch. Thieving uses one attempted action at the required skill level. Thieving rates include direct GP and common sales after any lockpick sale value. Check the actual net rate after food and replenishment before choosing it.</p>
      {method_tables(report["methods"])}
      <h3>Worked chain for Iron Platelegs</h3>
      <p>Mine 4 Iron Ore at {num(actions["IronOre"]["seconds"], 3)} s each. Smelt 4 Iron Bars at {num(actions["IronBar"]["seconds"], 1)} s each. Finish one pair of Iron Platelegs in {num(actions["IronPlatelegs"]["seconds"], 1)} s and sell for {num(gp_sale)} GP. The chain takes {num(worked["seconds"], 2)} s on average, or <strong>{num(worked["gp_per_hour"])} GP/h</strong>. With four bars already in the bank, the same craft adds {num(gp_sale - 4 * report["sale_prices"]["MelvorBase:IronBar"])} GP over selling the bars immediately.</p>
      <p>Fire Wand is another chain to compare. Buy Bucket of Sand for {num(report["shop_supply_gp"]["MelvorBase:BucketofSand"])} GP each, smelt Molten Glass and craft an Unpowered Orb. Mine Rune Essence for Fire and Mind Runes. The model subtracts the cost of the sand.</p>
      {detail("Calculation assumptions", assumptions(report))}
    </section>
    {combat_section(report, report["benchmark_gp_per_hour"])}
    <section id="quests">
      <h2>Quests and first purchases</h2>
      {quests}
      <p>Check what an upgrade will save over the hours you intend to use it. Copper Fishing Rod opens at Fishing {rod["Requirements"][0]["Data"]["Level"]} and costs {num(rod["Costs"]["Currencies"][0]["Quantity"])} GP plus {rod["Costs"]["Items"][0]["Quantity"]} Copper Bars. Fishing's first +20 bank slots unlock at level {bank["Requirements"][0]["Data"]["Level"]} for {num(bank["Costs"]["Currencies"][0]["Quantity"])} GP. Buy slots when space is cutting sessions short. Keep quest items, spares for upgrades, and at least the food, ammo, runes and bones you plan to use.</p>
      <p>Estimate payback as the cost in GP and materials divided by the extra GP/h. For example, a 2,000 GP upgrade that adds 500 GP/h takes 4 hours to recover its cash cost. Add any required farming or training time if you are starting from scratch.</p>
    </section>
    <section id="personalize">
      <h2>Use your own character</h2>
      <p>Set up the local character reader. From the repository root in PowerShell, run <code>.\update-guides.ps1 -Open</code>. Open the Money-making result to compare currently available routes, missing requirements, equipped chest tools and profitable uses for unlocked bank stacks. Use <code>-Save</code> to choose a save or <code>-Watch</code> to update while you play.</p>
      <p><a href="../../../tools/character_state/README.md">Set up the character reader</a> · <a href="calculations.json">Open the public calculation data</a></p>
    </section>
    <section id="continue">
      <h2>Continue past Combat 30 or non-combat 40</h2>
      <ol>
        <li>Keep your current reliable method as a benchmark. Note your next cash goal and skills close to a new unlock. Check the current public build and patch notes before copying sale prices, recipes or loot tables.</li>
        <li>When Fishing reaches 44, test Rocky Shores. Compare it with the current spot using your rod, catch mix and bait costs. For Mining and Smithing, check Adamantite Ore at Mining 45 and verify the full new bar recipe before switching. In combat, test a single newly unlocked target and record net GP/h, including respawn, food, ammunition and runes.</li>
        <li>Compare passive Farming and Ranching income on their calendar time and count the active time to plant, feed or harvest. Price seed, food and other inputs. Add the net passive income to the active method only if both can operate together.</li>
        <li>For another published range, follow the extension instructions in the repository. Add only verified IDs and requirements, recalculate both views, and rebuild the library index.</li>
      </ol>
      <p><a href="../../../README.md#update-or-extend-the-money-making-guide">Update or extend this guide</a></p>
    </section>'''
    intro = '<p>Repeatable gold through non-combat level 40 and selected fights through Combat 30. Use the quest cash to get started, then choose using GP per hour, available supplies and the skills you want to train.</p>'
    footer = sources(report) + '<p><a href="../../index.html">Back to the guide library</a></p>'
    return page("Early money-making", "Melvor Idle 2 · Steam Early Access", intro, (
        ("route", "Start here"), ("rates", "GP rates"), ("combat", "Combat"), ("quests", "Quests and shop"),
        ("personalize", "Personal guide"), ("continue", "Continue past the caps"), ("measure", "GP/h calculator"),
        ("sources", "Sources")), content, report["benchmark_gp_per_hour"], footer)


def render_personal(report, reference_path, audit_name):
    snapshot = report["snapshot"]
    save_time = datetime.fromisoformat(snapshot["save_modified_at"])
    generated = datetime.fromisoformat(snapshot["extracted_at"])
    age = max(0, int((generated - save_time).total_seconds()))
    ready = [row for row in report["methods"] if row["available"] and row["kind"] != "Thieving"]
    best = ready[0] if ready else None
    benchmark = max(1, round(best["gp_per_hour"])) if best else report["benchmark_gp_per_hour"]
    gold = "unknown" if report["gold"] is None else f'{num(report["gold"])} GP'
    timing = f'saved {escape(save_time.isoformat(sep=" ", timespec="seconds"))} · {age // 60:,} min old at generation'
    intro = f'<p>{escape(snapshot["character"])} · {gold} in the wallet · {timing}.</p>'
    if best:
        intro += f'<p class="note">Best modelled gathering or crafting option available in this save is <strong>{escape(best["name"])}</strong> at <strong>{num(best["gp_per_hour"])} GP/h</strong> with the full supply chain. Compare it with a measured combat or Thieving run before switching.</p>'
    if snapshot["game_package_sha256"] != report["reference_build"]["package_sha256"]:
        intro += '<p class="note">The installed package differs from the published reference. Rates use the local game data. The action formulas were verified on the reference build.</p>'
    best_thief = next((row for row in report["methods"] if row["available"] and row["kind"] == "Thieving"), None)
    hint = ""
    if best_thief:
        hint = f'<p>First Thieving run to measure by estimated return is <strong>{escape(best_thief["name"])}</strong> at {num(best_thief["gp_per_hour"])} GP/h before food and replenishment time. Check the in-game success chance and survivability.</p>'
    jobs = []
    for row in report["bank_jobs"]:
        materials = ", ".join(f'{count:,} × {report["bank_item_names"][item]}' for item, count in row["inputs"].items())
        jobs.append((row["name"], row["batches"], materials, num(row["seconds"] / 60, 1),
                     num(row["extra_gp"]), num(row["extra_gp_per_hour"])))
    bank_table = table(("Job", "Batches", "Stock to set aside", "Minutes", "Extra GP", "Extra GP/h"), jobs) if jobs else (
        "<p>No profitable immediate jobs were found among the compared recipes.</p>")
    appendix = []
    action_rows = [*report["action_models"].values(), *report["methods"]]
    for row in action_rows:
        for stat, modifier in row.get("modifiers", {}).items():
            scale, suffix = {"percentage_fraction": (100, "%"), "ms": (1, " ms"),
                             "game_value": (1, "")}[modifier["unit"]]
            names = sorted({report["sources"][entry["source"]]["name"] or report["sources"][entry["source"]]["id"]
                            for entry in modifier["contributions"]})
            appendix.append((row["name"], stat, f'{modifier["value"] * scale:+g}{suffix}', ", ".join(names)))
    mods = detail("Applied modifiers and their sources",
                  table(("Action", "Modifier", "Contribution", "Sources"), appendix)) if appendix else (
        "<p>No supported modifiers contributed to these estimates.</p>")
    body = f'''<section id="rates">
      <h2>Repeatable methods for this save</h2>
      <p>Requirements use the saved skill levels and active toolbelt. Locked entries show the estimated method with the indicated prerequisites and supported saved modifiers. The comparison covers the guide's early-game methods even if your skill levels are higher.</p>
      {hint}
      {method_tables(report["methods"], personal=True)}
    </section>
    <section id="stock">
      <h2>Make more from banked materials</h2>
      <p>Each row compares crafting with selling the required ingredients immediately. Use one row at a time since jobs can share the same stock. The suggested batch count uses the unlocked stacks at full ingredient cost. Extra GP can include the expected value of preserved inputs. Set aside anything you need for quests or upgrades before starting.</p>
      {bank_table}
    </section>
    {combat_section(report, benchmark)}
    <section id="assumptions">
      <h2>Assumptions and save details</h2>
      {assumptions(report)}
      <p>Estimates use supported confirmed tool, gear, mastery and action modifiers. Unknown, uncertain, global, temporary and unverified conditional bonuses remain outside the model. Check the in-game stats if an estimate differs from your run.</p>
      {mods}
      <p>Character ID <code>{escape(snapshot["character_id"] or "unknown")}</code><br>Save SHA-256 <code>{escape(snapshot["save_sha256"])}</code></p>
      <p><a href="{escape(audit_name, quote=True)}" download>Download local calculations</a> · <a href="{escape(reference_path, quote=True)}">Read the public guide and sources</a></p>
    </section>'''
    return page("Money-making for your character", "Melvor Idle 2 · Local save", intro, (
        ("rates", "Available routes"), ("stock", "Banked materials"), ("combat", "Combat"), ("measure", "GP/h calculator"),
        ("assumptions", "Assumptions and save")), body, benchmark, "")
