# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Melvor Idle 2 players planning their progression. They use the public guides to choose a leveling route or a way to earn GP. Players with a supported Steam save on Windows can also use local tools to see which options fit their character and bank.

## Product Purpose

Help players decide what to train or do next and understand how much time and preparation it will take. A player can find a guide for a skill and level range, compare the relevant options, and check the assumptions behind the recommendation.

## Positioning

The guides account for gathering and processing materials when estimating a leveling route. Each route includes sources, assumptions, and downloadable calculations so players can see what drives the result. Supported guides can be recalculated locally using a player's saved progress, materials, and identified modifiers.

## Operating Context

- Search or filter the [route library](guides/index.html) by skill. The HTML guides work offline, and the public library is also available on GitHub Pages. External references require a connection.
- Use the public Fletching route for a baseline plan or the early money-making guide to compare GP methods and starter quest rewards. The money-making guide includes a calculator for measured sessions.
- On Windows, use the PowerShell tools with a local Steam save to inspect character state or generate personalized Fletching and money-making guides. Local estimates identify the save timestamp and SHA-256 so players can tell which snapshot they used.

## Capabilities and Constraints

- Use Melvor Idle 2 data. Identify the source and target game build, and disclose assumptions and unresolved differences that affect a recommendation.
- Keep public guides independent of personal data. The character tools read saves locally, and personal snapshots and generated guides stay outside Git and the public build.
- Treat personalized results as estimates with documented coverage. Apply only supported modifiers and carry uncertainty through to the result. Some methods rely on a player's measured session data.
- Keep repository content in English and preserve official game names and identifiers.

## Evidence on Hand

- [Fletching levels 1–50](guides/fletching/1-50/guide.html) and its [calculations](guides/fletching/1-50/calculations.json).
- [Early money-making through Combat 30 and non-combat 40](guides/money-making/1-40/guide.html) and its [calculations](guides/money-making/1-40/calculations.json).
- [Character reader setup and coverage](tools/character_state/README.md) and the [character query format](tools/character_state/AGENT-FORMAT.md).

## Product Principles

1. Make the next action clear. Name the route or method, its requirements, and the work it takes to get started.
2. Compare the full workflow. Include gathering and processing where they affect time or GP, and state when a scenario assumes materials are already banked.
3. Make estimates auditable. Keep the game build, sources, inputs, and assumptions available alongside the results.
4. Keep personalization local. Let players use public guides without a save and generate private estimates when they choose to use one.
