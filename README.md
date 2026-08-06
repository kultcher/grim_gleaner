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

## Run the profile editor UI

```powershell
.\.venv\Scripts\grim-gleaner-ui.exe
```

The current UI provides the data-driven profile editor with 0–4 star weights,
discoverable package accordions, placeholder Pets and Skills tabs, and reserved
top-level navigation for the future Top Matches benchmark. Profile persistence
and generated Rainbow output are not connected yet.

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

## Rank affixes against the mock profile

```powershell
.\.venv\Scripts\python.exe -m gd_affix_relevance.cli rank `
  --data-root game_data `
  --localization-root game_data\rainbow_examples `
  --game-localization-root game_data\gdx3\text_en `
  --game-localization-root game_data\gdx2\text_en `
  --game-localization-root game_data\gdx1\text_en `
  --game-localization-root game_data\base\text_en `
  --profile bleed-melee `
  --limit 20 `
  --output artifacts\rankings\bleed-melee-top20.txt
```

The mock `bleed-melee` profile assigns fixed weights to Bleeding Damage,
Physical Resistance, Health, Defensive Ability, Attack Speed, Offensive
Ability, and Movement Speed. Flat and percentage forms of the same concept are
collapsed into one scored category. The command grades every reachable
tag/gear-slot/stat-layout variant, then prints only the requested highest-ranked
variants with their matched categories, coverage, full stat list, and source
record.

This is deliberately a category-presence relevance grade. It ignores numeric
roll magnitude and does not estimate whether an item is an upgrade.
