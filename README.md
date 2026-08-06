# Grim Gleaner

Grim Gleaner analyzes extracted Grim Dawn magic and rare affixes and proposes
build-relevance annotations for their localization tags. It does not estimate
whether an item is an upgrade.

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
discoverable package accordions, and placeholder Pets and Skills tabs. Its Top
Matches view ranks the compiled affix catalog against the active profile and
shows the facts behind each result. Build profiles can be saved to and loaded
from user-selected JSON files. The Generate Output page creates a complete,
graded Rainbow `text_en` staging folder for manual installation.

Profile files are versioned, human-readable JSON. Only nonzero weights are
stored; omitted stats load as weight 0. For example:

```json
{
  "name": "Bleed Werewolf",
  "schema_version": 1,
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
list, and source record.

This is deliberately a category-presence relevance grade. It ignores numeric
roll magnitude and does not estimate whether an item is an upgrade.

## Generate Rainbow staging output

```powershell
.\.venv\Scripts\python.exe -m gd_affix_relevance.cli generate-output `
  --catalog-root artifacts\catalog `
  --profile-file Lightning.json `
  --source-root artifacts\text_en `
  --output-dir artifacts\generated\lightning\text_en
```

The source must be a complete Rainbow `text_en` folder: Grim Dawn displays
`Tag not found` for omitted entries once an override file is present. The
generator copies every source file, changes only exact catalog affix tags, and
never writes to the source or live game directory.

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
  --game-version unknown `
  --output-dir artifacts\catalog
```

Pass official English localization roots from newest expansion to base because
the first definition wins. The compiler applies DBR sources in the opposite
direction (base through the newest expansion), so newer records replace older
records at the same logical path.

The deterministic bundle contains all structurally reachable magic/rare affix
variants plus named player/mastery, pet, and item-granted skill DBRs. Monster,
quest, devotion, default, and template branches are excluded. Only the English
name strings those records require are retained. The application can load these
small JSON files without requiring end users to extract game archives. See
[`docs/catalog-schema.md`](docs/catalog-schema.md) for scope and extension
points.
