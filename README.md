# Grim Gleaner

Grim Gleaner analyzes Grim Dawn item properties and proposes build-relevance
annotations for their localization tags. Its first scoring catalog covers magic
and rare affixes; its compiled item data also covers base items, Monster
Infrequents, epics, legendaries, components, augments, relics, runes, and
consumables. The current UI scores affixes, unique equipment, components, and
augments; it does not attempt to determine whether an entire dropped item is an
upgrade over the player's current equipment.

## Development setup

The project currently targets Python 3.14 on Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest
```

Extracted proprietary game data belongs under `game_data/` and is intentionally
ignored by Git.

Compiled development catalogs belong under `artifacts/`, which is also ignored
until redistribution terms and the release packaging policy are settled.

## Run the profile editor UI

```powershell
.\.venv\Scripts\grim-gleaner-ui.exe
```

The current UI provides the data-driven profile editor with 0–4 star weights,
package-wide weight controls, discoverable package accordions, three pet-stat
packages, and a two-mastery Skills editor. It remembers the last saved or loaded
profile, supports a fully blank New Profile action, and provides a direct View
Matches button. Its Top Matches view ranks both affixes and fixed unique-item
stats against the active profile for every atomic gear slot. Affixes use paired
prefix/suffix tables; Monster Infrequents, epics, and legendaries use a single
minimum-grade-filtered table per slot with basic acquisition-source labels.
Add-ons use paired component/augment tables per slot, including component
acquisition and localized augment-faction columns.
Their fold-down Resistance Cap Mode can temporarily override resistance weights
for add-on ranking without changing the saved profile or the Affixes/Uniques
results.
Build profiles can be saved to and loaded from user-selected JSON files.
The Generate Output page creates a complete, graded Rainbow `text_en` staging
folder for manual installation.

Profile files are versioned, human-readable JSON. Ordinary stats with weight 0
are omitted, while selected build-relevant skills are retained even at weight 0
so adding a skill and weighting it remain separate choices. Conversion sources,
including the future-facing `Specific Skill` selector, default to enabled;
profiles store only sources the user explicitly unchecks.
For example:

```json
{
  "masteries": [
    "playerclass06",
    "playerclass04"
  ],
  "name": "Bleed Werewolf",
  "schema_version": 3,
  "excluded_conversion_sources": {
    "fire": [
      "aether",
      "chaos"
    ]
  },
  "skill_weights": {
    "records/skills/playerclass06/savagery1.dbr": 4
  },
  "weights": {
    "bleeding_damage_percent": 4,
    "health": 2
  }
}
```

## Generate the normalization inventory

```powershell
.\.venv\Scripts\python.exe -m gd_affix_relevance.cli inventory `
  --data-root game_data `
  --localization-root game_data\rainbow_examples `
  --game-localization-root game_data\official_text_en\gdx3 `
  --game-localization-root game_data\official_text_en\gdx2 `
  --game-localization-root game_data\official_text_en\gdx1 `
  --game-localization-root game_data\official_text_en\base `
  --output-dir artifacts\normalization
```

The generated reports are local review artifacts, not accepted normalization
rules:

- `field_inventory.csv`: every active raw field, counts, proposed mapping, and
  representative affixes.
- `mapping_proposals.csv`: all mapped, structured-reference, and ignored
  proposals.
- `bundle_relationships.csv`: raw fields grouped into semantic properties with
  core and optional component roles.
- `affix_reference_status.csv`: informational structural reachability from
  retained item loot tables; distinguishes reachable definitions, definitions
  referenced only by unreachable intermediate tables, and definitions with no
  incoming item reference. It does not assert exact drop availability.
- `inferred_mappings.csv`: systematic mappings that still need spot checks.
- `review_needed.csv`: ambiguous or composite mappings requiring deliberate
  confirmation.
- `unmapped_fields.csv`: active fields with no proposal.
- `unresolved_localization_tags.csv`: tags missing from the supplied Rainbow
  localization files.
- `proposed_normalization_rules.json`: machine-readable proposal ledger.
- `summary.json`: scan and coverage totals.

The normalizer is intentionally independent of affix discovery so Monster
Infrequent base-item records can be added as a separate input source later.

## Generate a random manual-validation sample

```powershell
.\.venv\Scripts\python.exe -m gd_affix_relevance.cli sample `
  --data-root game_data `
  --localization-root game_data\rainbow_examples `
  --count 10 `
  --seed 12345 `
  --output artifacts\samples\sample-12345.txt
```

The sampler includes only affix records structurally reachable from a recognized
gear loot table. It groups leveled records by localization tag, inferred gear
slot, and number-free stat fingerprint. Omitting `--seed` generates and prints a
seed so a sample can still be reproduced.

The repeatable `--game-localization-root` option should point to extracted
official text files containing mastery and item-skill tags. Pass expansion roots
from newest to oldest because the first definition wins. Rainbow entries are
loaded before them, so Rainbow remains authoritative for affix names while
official localization fills in missing skill strings. Without those directories,
skill bonuses resolve to `skillDisplayName` but appear as localization tags.

Each sampled stat fingerprint also reports the level requirements on which that
layout occurs and the number of distinct layouts found for the same affix and
gear slot. This makes tier-dependent stat additions visible without forcing the
sampler to assume a character level or always select the maximum tier.

## Audit fixed item stat packages

```powershell
.\.venv\Scripts\python.exe -m gd_affix_relevance.cli audit-items `
  --data-root game_data `
  --source base `
  --item-directory gearhead `
  --localization-root game_data\base\text_en `
  --catalog-root artifacts\catalog `
  --output artifacts\item-audit\base-gearhead.md
```

This exploratory audit classifies records using both filename family and the
DBR's actual `itemClassification`, inventories fixed intrinsic stat layouts,
and compares their normalized property IDs with the current affix catalog. For
Monster Infrequent candidates it also follows each
`modifiedSkillName`/`modifierSkillName` pair into the referenced skill-modifier
DBR. Item meshes, sounds, requirements, set references, and other catalog
metadata are retained outside the gameplay-gap count.

## Rank affixes against a saved profile

```powershell
.\.venv\Scripts\python.exe -m gd_affix_relevance.cli rank `
  --catalog-root artifacts\catalog `
  --profile-file profiles\bleed-werewolf.json `
  --limit 20 `
  --output artifacts\rankings\bleed-melee-top20.txt
```

The command loads the same editable JSON profile used by the UI, grades every
compiled tag/gear-slot/stat-layout variant, then prints only the requested
highest-ranked variants with their matched categories, coverage, full stat
list, and source record. Direct bonuses to a selected mastery skill use that
skill's profile weight. Skill-modifier effects remain cataloged but are not yet
part of scoring.

This is deliberately a category-presence relevance grade. Each matched weight
contributes `weight² / 4` points, then receives a soft multiplier from 70% to
100% based on the share of that affix or item's stat categories that matched.
This makes core and emphasized stats increasingly valuable without imposing a
hard core-stat requirement. It ignores numeric roll magnitude and does not
estimate whether an item is an upgrade.

## Generate Rainbow staging output

```powershell
.\.venv\Scripts\python.exe -m gd_affix_relevance.cli generate-output `
  --catalog-root artifacts\catalog `
  --profile-file Lightning.json `
  --source-root artifacts\text_en `
  --output-dir artifacts\generated\lightning\text_en
```

The source must contain complete `tags*_items.txt` files: Grim Dawn displays
`Tag not found` for omitted entries once an override file is present. During
development these can be the extracted official English files or complete
Rainbow files. The generator copies every source file, changes only exact
catalog tags, and never writes to the source or live game directory.

Official files provide a self-contained, uncolored baseline for optional
release output. Rainbow is supported as an alternate source for users who want
to retain its existing colors, but it is not required by catalog compilation or
name resolution. Unannotated equipment, containers, breakables, doors, and
other labels are preserved verbatim from whichever complete source is selected.

Markers use `(S6)`, where the letter is the relevance grade and the number is
the matched profile-stat count. `(S*5)` means variant layouts differ and the
grade conservatively uses only stats shared by every layout. Rerunning replaces
the existing generated marker instead of stacking another one.

## Compile the runtime catalog

```powershell
.\.venv\Scripts\python.exe -m gd_affix_relevance.cli compile-catalog `
  --data-root game_data `
  --localization-root game_data\gdx3\text_en `
  --localization-root game_data\gdx2\text_en `
  --localization-root game_data\gdx1\text_en `
  --localization-root game_data\base\text_en `
  --mastery-tree-root artifacts\mastery-trees `
  --game-version unknown `
  --output-dir artifacts\catalog
```

Pass official English localization roots from newest expansion to base because
the first definition wins. The compiler applies DBR sources in the opposite
direction (base through the newest expansion), so newer records replace older
records at the same logical path.

The deterministic schema-version-5 bundle contains all structurally reachable
magic/rare affix variants; named player/mastery, pet, and item-granted skill
DBRs; and split item catalogs for equipment, components, augments, relics,
runes, and consumables. Equipment includes common/magical bases, Monster
Infrequents, rares, crafted and faction gear, epics, legendaries, awakened
variants, and equippable quest-record exceptions. Enemy-only gear and transmute
proxies are excluded.

Concrete item variants retain normalized fixed stats, levels, applicable slots,
set names, granted or consumable-effect skills, component completion references,
and MI/rune skill modifiers. Only the English strings required by compiled
records are retained. The application can load these JSON files without
requiring end users to extract game archives. See
[`docs/catalog-schema.md`](docs/catalog-schema.md) for scope and extension
points.

Affix definitions retain Magical/Rare classification and discrete skill-rank
values. Mastery skills retain their DBR tier and class-tree order; curated
parent/child links are loaded from `artifacts/mastery-trees` when that optional
compiler argument is supplied.

The item-catalog compiler needs `records/items` plus the player, pet, and
item-granted definitions it follows into `records/skills`. Optional component
faction-vendor and reputation metadata also uses
`records/creatures/npcs/merchants` and referenced faction controllers.
Complete official localization files are separate compilation inputs used to
resolve names and seed safe optional `tags*_items.txt` output. World-data DBRs
outside those branches are not required unless Grim Gleaner later begins
interpreting or annotating doors, map interactables, or quest objects rather
than simply preserving their localization entries.
