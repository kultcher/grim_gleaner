# AGENTS.md

## Project overview

This project is a Windows desktop utility for Grim Dawn that annotates item affix names according to how strongly their properties correspond to a user-defined build profile.

It is not intended to determine whether an item is an upgrade. Its purpose is to reduce visual and cognitive clutter by answering a narrower question:

> How much of this prefix or suffix maps onto the stats this build cares about?

The application will:

1. Read extracted Grim Dawn affix `.dbr` records.
2. Convert raw database fields into player-facing stat categories.
3. Let the user assign importance weights to those categories.
4. Calculate a relevance grade for each affix localization tag.
5. Add compact markers to Rainbow Filter localization text.
6. Preserve Rainbow Filter’s existing colors and formatting.

Say a player is building a melee bleed-focused character, an item drop might display like:
```text
[—] Cabalist's Leather Vestment [B3] of Butchery
```

Here, `B` is a heuristic relevance grade and `3` indicates that the affix contains three selected stat categories (in this case +bleeding damage, health and elemental resistance. The Cabalist's affix gets a blank (or maybe like `F0`) because it has no relevant affixes to our build.

Do not describe this score as an upgrade probability, it's goal is to communicate potential relevance to a player's build.

---

## Current technical findings

### Grim Dawn database extraction

Grim Dawn includes `ArchiveTool.exe`.

An `.arz` database can be extracted with:

```powershell
ArchiveTool.exe "C:\Path\database.arz" -database "C:\Absolute\Output\Directory"
```

Use an absolute output path. Omitting the destination or using an unreliable relative path may produce an empty directory tree.

The result is a directory tree containing readable `.dbr` files. These files do not require further extraction.

The `-extract` command is used for resource archives such as `.arc` files, not for extracted `.dbr` records.

### DBR format

Extracted DBRs are line-oriented records resembling:

```text
templateName,database/templates/lootrandomizer.tpl,
Class,LootRandomizer,
lootRandomizerName,tagPrefixAO007,
levelRequirement,50,
lootRandomizerJitter,10.000000,
offensiveLightningMin,6.000000,
offensiveLightningMax,42.000000,
```

Treat the format as comma-delimited key/value data, but preserve:

* original strings;
* ordering;
* duplicate fields, should they occur;
* negative numbers;
* nonempty string fields;
* referenced record paths.

Do not assume every meaningful property is a single nonzero numeric field.

### Affix localization tags

Affix records contain an exact localization key in `lootRandomizerName`.

Example:

```text
lootRandomizerName,tagPrefixAO007,
```

Rainbow Filter localization contains the corresponding entry:

```text
tagPrefixAO007={^Y}Charged
```

This is a direct key-based relationship. Do not use fuzzy name matching.

### Rainbow Filter output

Rainbow Filter does not need to be treated as a runtime software dependency. Its effective output consists of localization override files, generally under a folder such as:

```text
Grim Dawn/settings/text_en/
```

The files contain entries such as:

```text
tagPrefixAO007={^Y}Charged
```

A special-highlighting configuration may produce:

```text
tagPrefixAO007=X{^O}Charged
```

Color codes use syntax such as:

```text
{^Y}
{^O}
```

The application should post-process these localization files while preserving existing formatting.

A preferred generated form is:

```text
tagPrefixAO007={^O}[B2] {^Y}Charged
```

This explicitly colors the relevance marker while retaining Rainbow’s existing color for the affix name.

### Affix variants

Affix records commonly appear in groups such as:

```text
ao007a_lightning_01.dbr
ao007a_lightning_02.dbr
ao007b_lightning_01.dbr
ao007c_lightning_07.dbr
```

Working interpretation:

* letter variants often correspond to different equipment categories;
* trailing numbers generally correspond to level or power tiers;
* multiple records can share the same `lootRandomizerName`.

Do not select one arbitrary file as the canonical definition.

Parse every variant and group records by localization tag.

Compare each variant’s semantic property fingerprint. If all variants contain the same categories, they can share one relevance result. If categories differ, retain and expose that ambiguity.

### Jitter and value ranges

DBR stat values are generally central or base values. `lootRandomizerJitter` controls the generated range.

Example:

```text
lootRandomizerJitter,10.000000,
offensiveLightningMin,6.000000,
offensiveLightningMax,42.000000,
```

This yields approximately:

```text
Low roll:  5–38
High roll: 7–46
```

The relevance MVP does not need to reproduce exact generated roll ranges. Preserve base values and jitter for inspection, but do not use jitter in initial relevance scoring.

### Composite properties

Some player-visible properties are represented by multiple DBR fields.

Example:

```text
conversionInType,Physical,
conversionOutType,Lightning,
conversionPercentage,35.000000,
```

These fields jointly represent:

```text
Physical Damage converted to Lightning Damage
```

Similarly:

```text
offensiveLightningMin,6.000000,
offensiveLightningMax,42.000000,
```

jointly represent:

```text
Flat Lightning Damage
```

Raw fields must be normalized into semantic properties before scoring.

---

## Scope of the MVP

The MVP should answer:

> Which semantic stat categories does each affix contain, and how many of those categories matter to the selected build?

The MVP should include:

* extracted DBR parsing;
* affix-record discovery;
* localization-tag resolution;
* raw-field normalization;
* build profiles with weighted stat categories;
* affix relevance calculation;
* affix preview and inspection;
* Rainbow text annotation;
* safe output with backups;
* a basic PySide6 frontend.

The MVP should not include:

* determining whether an item is an upgrade;
* reading live dropped items;
* DLL injection or runtime hooking;
* DPYes integration;
* exact affix drop probabilities;
* legal prefix/suffix combinations;
* item-slot-specific filtering;
* Grim Tools build imports;
* exact rolled-value evaluation;
* base-item or Monster Infrequent scoring;
* automatic game launching;
* direct modification of `.arz` archives.

---

## Recommended technology

Use:

```text
Python 3.12+
PySide6
pytest
pathlib
dataclasses
json
subprocess
```

Use the standard library unless a dependency clearly reduces substantial complexity.

Do not begin with Electron, Tauri, C++, or a web server.

The application is primarily:

* file parsing;
* record normalization;
* deterministic scoring;
* text rewriting;
* a few tables and selection controls.

Develop the data pipeline and CLI before building the full GUI.

PyInstaller or Nuitka can be considered after the application works correctly.

---

## Proposed project structure

```text
gd-affix-relevance/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── src/
│   └── gd_affix_relevance/
│       ├── __init__.py
│       ├── cli.py
│       ├── domain/
│       │   ├── affix.py
│       │   ├── localization.py
│       │   ├── profile.py
│       │   └── score.py
│       ├── importers/
│       │   ├── archive_tool.py
│       │   ├── dbr_parser.py
│       │   ├── affix_discovery.py
│       │   └── localization_parser.py
│       ├── normalization/
│       │   ├── categories.json
│       │   ├── field_rules.py
│       │   └── normalizer.py
│       ├── scoring/
│       │   └── scorer.py
│       ├── output/
│       │   ├── rainbow_writer.py
│       │   └── backup.py
│       └── ui/
│           ├── main_window.py
│           ├── profile_page.py
│           ├── affix_page.py
│           └── generate_page.py
├── tests/
│   ├── fixtures/
│   │   ├── dbr/
│   │   └── localization/
│   ├── test_dbr_parser.py
│   ├── test_normalizer.py
│   ├── test_scorer.py
│   └── test_rainbow_writer.py
└── data/
    └── README.md
```

Do not commit extracted proprietary Grim Dawn databases or localization archives.

Small hand-created or reduced fixtures are acceptable.

---

## Domain models

Use explicit domain objects rather than passing unstructured dictionaries throughout the application.

A reasonable starting point:

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class RawDbrField:
    key: str
    value: str


@dataclass
class RawDbrRecord:
    source_path: Path
    fields: list[RawDbrField]

    def values_for(self, key: str) -> list[str]:
        return [
            field.value
            for field in self.fields
            if field.key == key
        ]


@dataclass(frozen=True)
class SemanticProperty:
    category: str
    label: str
    values: dict[str, Any] = field(default_factory=dict)
    source_fields: tuple[str, ...] = ()


@dataclass
class AffixVariant:
    source_path: Path
    localization_tag: str
    level_requirement: int | None
    classification: str | None
    jitter: float | None
    properties: list[SemanticProperty]


@dataclass
class Affix:
    localization_tag: str
    display_name: str | None
    variants: list[AffixVariant]


@dataclass
class BuildProfile:
    name: str
    weights: dict[str, int]
```

Keep raw records available for debugging and future normalization work.

---

## DBR parsing requirements

The parser must:

* tolerate blank lines;
* tolerate trailing commas;
* split each line only as much as necessary;
* preserve unknown fields;
* preserve nonnumeric values;
* preserve negative values;
* handle malformed lines without crashing the entire import;
* report warnings with file paths and line numbers;
* avoid silently discarding duplicate keys.

A basic DBR is not equivalent to a simple `dict[str, str]`.

Metadata fields should remain available even when ignored by the scoring layer.

Likely metadata includes:

```text
templateName
Class
itemClassification
levelRequirement
lootRandomizerCost
lootRandomizerJitter
lootRandomizerName
marketAdjustmentPercent
```

Do not globally discard every field with names such as `Chance`, `Global`, or `Modifier`. Some of those may represent meaningful properties in other records.

---

## Affix discovery

Initially, discover affix records by a combination of:

* file location under likely loot-affix directories;
* `Class,LootRandomizer`;
* presence of `lootRandomizerName`.

Do not rely solely on filename conventions.

The importer should produce a report containing:

* files scanned;
* affix variants found;
* records missing localization tags;
* duplicate localization tags;
* records with no recognized semantic properties;
* unknown nondefault fields;
* malformed records.

---

## Localization parsing

Scan all `.txt` files recursively under a user-selected localization directory.

Do not hardcode only `tags_items.txt`. Expansion content may live in separate files.

Represent each entry with:

```python
@dataclass
class LocalizationEntry:
    tag: str
    value: str
    source_path: Path
    line_number: int
```

Handle lines in the form:

```text
tag=value
```

Split only on the first `=`.

Preserve:

* existing color codes;
* prefixes and suffixes;
* spaces;
* line endings when practical;
* files unrelated to affixes;
* comments and unknown lines.

Detect duplicate tag definitions and report them.

The primary MVP input may be an installed Rainbow Filter folder. A later localization source may extract original `Text_EN.arc` files from the base game and expansions.

Keep localization loading behind an interface so additional sources can be added without changing the scoring engine.

Do not assume the FoA archive location until verified against an installed copy.

---

## Stat normalization

The normalization layer is the most important hand-maintained component.

Raw fields should map to semantic categories such as:

```text
flat_lightning_damage
lightning_damage_percent
electrocute_damage
physical_to_lightning_conversion
bleeding_damage
flat_bleeding_damage
attack_speed
casting_speed
total_speed
offensive_ability
defensive_ability
health
health_percent
health_regeneration
physical_resistance
fire_resistance
cold_resistance
lightning_resistance
pierce_resistance
poison_acid_resistance
bleeding_resistance
vitality_resistance
aether_resistance
chaos_resistance
armor
armor_absorption
movement_speed
cooldown_reduction
skill_bonus
mastery_bonus
pet_damage
retaliation_damage
```

Do not require complete category coverage before producing useful output.

Unknown nondefault fields should be:

1. retained;
2. shown in the affix inspector;
3. included in an “unclassified fields” report;
4. easy to add to normalization rules later.

Use configuration for simple one-field mappings.

Example:

```json
{
  "characterDefensiveAbility": {
    "category": "defensive_ability",
    "label": "Defensive Ability"
  },
  "characterLife": {
    "category": "health",
    "label": "Health"
  },
  "characterLifeModifier": {
    "category": "health",
    "label": "Health"
  }
}
```

Use Python rules for composite field families such as:

* minimum and maximum damage;
* conversion input/output/percentage;
* chance/duration/effect groups;
* skill references;
* mastery references.

Do not count `Min` and `Max` as separate stat categories.

---

## Variant grouping

Group variants by `lootRandomizerName`.

For each variant, calculate a semantic fingerprint:

```python
fingerprint = frozenset(
    property.category
    for property in variant.properties
)
```

Classify grouped affixes as:

* `consistent`: all variants share the same fingerprint;
* `subset_difference`: one variant adds or omits categories;
* `conflicting`: variants have materially different fingerprints;
* `unclassified`: no meaningful properties were recognized.

For consistent groups, score once.

For differing groups, retain:

* categories common to all variants;
* categories present in any variant;
* per-variant details.

The initial score should use categories common to all variants unless the user explicitly selects a more optimistic policy.

Never silently merge variant differences.

---

## Build profiles

A build profile should allow each category to be assigned an integer weight:

```text
0 = Ignore
1 = Useful
2 = Important
3 = Core
```

Profiles should be serializable as JSON.

Example:

```json
{
  "name": "Bleed Werewolf",
  "weights": {
    "bleeding_damage": 3,
    "flat_bleeding_damage": 3,
    "physical_resistance": 3,
    "health": 2,
    "defensive_ability": 2,
    "attack_speed": 2,
    "offensive_ability": 1,
    "movement_speed": 1
  }
}
```

Keep profile storage separate from imported game data.

---

## Relevance scoring

The score represents build correspondence, not upgrade likelihood.

For every affix, calculate and retain at least:

```text
matched categories
matched category count
total semantic category count
weighted matched value
coverage ratio
unclassified property count
variant consistency status
```

Suggested definitions:

```python
matched = {
    category
    for category in affix_categories
    if profile.weights.get(category, 0) > 0
}

matched_count = len(matched)
total_count = len(affix_categories)

weighted_match = sum(
    profile.weights[category]
    for category in matched
)

coverage_ratio = (
    matched_count / total_count
    if total_count
    else 0.0
)
```

Do not reduce the result to one opaque number internally.

The displayed grade may be derived from both:

* weighted breadth;
* affix coverage.

Keep grade thresholds configurable.

An initial marker format may be:

```text
[—] no selected categories
[C1] marginal match
[B2] useful match
[A3] strong match
[S4] exceptional match
```

The letter is the grade. The number is the matched-category count.

A percentage output may be offered, but it must be labeled as a relevance score rather than a probability.

The UI should explain why an affix received its grade.

---

## Rainbow output writer

The writer must be conservative and reversible.

It should:

1. Read the existing localization files.
2. Locate exact localization tags.
3. Add or replace this tool’s marker.
4. Preserve Rainbow’s existing affix coloring.
5. Write to a staging directory first.
6. Create timestamped backups before installation.
7. Avoid altering unrelated tags.
8. Report missing tags.
9. Support restoring the latest backup.

Preferred output:

```text
Before:
tagPrefixAO007={^Y}Charged

After:
tagPrefixAO007={^O}[A2] {^Y}Charged
```

Generated markers must be identifiable so rerunning the tool does not stack them:

```text
[A2] [A2] [A2] Charged
```

Use a deterministic marker parser and replacement rule.

Do not assume the existing value starts with a color code.

Do not normalize or reformat the rest of the localization file unnecessarily.

---

## User interface

Do not build the full UI until the parser, normalizer, scorer, and writer work through the CLI.

The eventual PySide6 interface should have three main areas.

### Build profile

* searchable stat-category list;
* weight selector;
* save profile;
* duplicate profile;
* rename profile;
* delete profile.

### Affix inspector

Columns should include:

```text
Grade
Affix name
Prefix/suffix
Matched categories
Matched count
Total categories
Variant status
Unclassified fields
Localization tag
```

Selecting a row should show:

* all semantic properties;
* matching profile weights;
* raw nondefault DBR fields;
* source variants;
* level requirements;
* source paths;
* ambiguity warnings.

### Generate output

Allow selection of:

* extracted database root;
* Rainbow localization root;
* build profile;
* marker format;
* marker color;
* output directory;
* backup directory.

Show a preview of changed lines before writing.

---

## Development order

Follow this sequence.

### Milestone 1: DBR parser

* Parse the supplied Charged fixture.
* Preserve all fields.
* Read `lootRandomizerName`.
* Read level, jitter, and classification.
* Add parser tests.

### Milestone 2: Charged normalization

Recognize:

```text
offensiveLightningMin
offensiveLightningMax
```

as:

```text
Flat Lightning Damage
```

Recognize:

```text
conversionInType
conversionOutType
conversionPercentage
```

as:

```text
Physical Damage converted to Lightning Damage
```

Add tests using the level-50 Charged record.

### Milestone 3: Localization parser and writer

Given:

```text
tagPrefixAO007={^Y}Charged
```

and marker:

```text
[A2]
```

produce:

```text
tagPrefixAO007={^O}[A2] {^Y}Charged
```

Verify idempotency and backup behavior.

### Milestone 4: Directory import

* recursively scan extracted DBRs;
* identify affix records;
* group by localization tag;
* report unknown fields and variant differences;
* export an inspectable JSON catalog.

### Milestone 5: Profiles and scoring

* load a profile;
* score grouped affixes;
* export a CSV or JSON preview;
* include detailed score explanations.

### Milestone 6: Minimal GUI

Build only after the full pipeline works from the command line.

---

## Testing priorities

Tests should emphasize correctness of transformation rather than UI appearance.

Required cases include:

* DBR lines with trailing commas;
* blank and malformed lines;
* negative numeric values;
* nonzero numeric properties;
* meaningful nonnumeric properties;
* duplicate keys;
* composite conversions;
* min/max property grouping;
* multiple variants sharing one tag;
* variants with different semantic fingerprints;
* duplicate localization tags;
* values containing additional `=` characters;
* Rainbow values with and without existing color codes;
* repeated generation without duplicate markers;
* missing localization tags;
* backup and restore behavior.

Use temporary directories for writer tests.

Never run tests against the user’s live Grim Dawn `settings` folder.

---

## Safety and file-handling rules

Never modify the user’s installed game files without:

* an explicit selected destination;
* a preview;
* a backup;
* clear error reporting.

Prefer generating output into a staging folder that the user can inspect.

Do not overwrite extracted database data.

Do not repack or modify `.arz` files.

Do not distribute Crate Entertainment’s extracted database or localization files.

Log paths and actions, but avoid collecting unrelated user data.

---

## Coding guidelines

* Prefer small, testable functions.
* Use type hints throughout.
* Use dataclasses for domain objects.
* Use `pathlib.Path` rather than raw path strings.
* Keep parsing, normalization, scoring, and output writing independent.
* Do not embed normalization rules in UI code.
* Do not embed UI concepts in the DBR parser.
* Do not hide unknown data.
* Report assumptions explicitly.
* Fail safely when input formats are unexpected.
* Keep the scoring model deterministic.
* Avoid premature performance optimization.
* Avoid premature packaging work.
* Do not introduce a database unless JSON becomes demonstrably inadequate.

Before implementing a large feature, first inspect the available fixtures and identify which assumptions are directly supported by the extracted records.

---

## Initial success criterion

The first useful vertical slice is complete when the tool can:

1. Read the extracted level-50 Charged DBR.
2. Identify its localization tag as `tagPrefixAO007`.
3. Normalize its properties to:

   * Flat Lightning Damage;
   * Physical Damage converted to Lightning Damage.
4. Load a build profile that values those categories.
5. Assign a deterministic marker such as `[A2]`.
6. Read:

   ```text
   tagPrefixAO007={^Y}Charged
   ```
7. Generate:

   ```text
   tagPrefixAO007={^O}[A2] {^Y}Charged
   ```
8. Preserve all unrelated localization lines.
9. Produce the same output when run repeatedly.
10. Restore the original file from backup.
