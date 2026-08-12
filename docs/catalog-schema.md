# Compiled catalog

The runtime catalog separates maintenance-time extraction from normal
application use. Its current files are:

```text
catalog/
|-- manifest.json
|-- strings.en.json
|-- skills.json
|-- affixes.json
|-- equipment.json
|-- components.json
|-- augments.json
|-- relics.json
|-- runes.json
`-- consumables.json
```

`manifest.json` declares the schema version, game-data version label, locale,
DBR overlay order, file list, counts, and the affix reachability scope. Builds
do not include timestamps, and arrays and object keys use stable ordering, so
two compiles from the same inputs produce byte-identical files.

## String catalog

`strings.en.json` is the English name lookup used by the compiled records. It
currently contains referenced affix and skill name tags rather than the full
game localization archive. Official `Text_EN` data is authoritative during
compilation; Rainbow Filter text is not a catalog-build dependency.

The runtime JSON and the optional in-game localization output have different
coverage requirements. The JSON catalog only needs strings referenced by its
compiled records. A generated `tags*_items.txt` override must instead retain
every definition from the corresponding official English file because Grim
Dawn does not fall back to the archives for omitted tags once an override file
is present. Generation therefore starts with a complete official file and
changes only tags that Grim Gleaner intentionally annotates. Rainbow files may
be used as an alternate, already-colored source, but are not required.

## Skill catalog

`skills.json` contains expansion-overlaid, named records from the
`playerclass*` and `itemskills*` branches. This covers mastery/player skills,
their explicit pet subskills, and item-granted skills even when no current
affix refers to them. Named monster, quest, devotion, default, template, and
other internal branches are excluded. Each entry retains its logical record
path, winning source, broad category, name tag, display name, name-resolution
status, optional description tag, mastery ID and localized mastery name,
maximum level, DBR `skillTier`, class-tree order, curated parent skill ID, and
whether the record is the mastery header itself. The legacy
`mastery_level_required` value remains temporarily for runtime compatibility but
is not useful for sorting the current extracted mastery records.

Class-tree order is derived from each `_classtree_classXX.dbr`, following
unnamed `buffSkillName` and `petSkillName` proxies to their named backing skill.
An order of 0 means the named record is not a selectable mastery-tree node.
Curated parent/child display-name relationships come from the optional
`artifacts/mastery-trees` Markdown source and compile to stable skill IDs.
Unlisted nodes remain valid roots or unlinked skills.

The resolution statuses are:

- `localized`: the name tag resolved through official English text;
- `literal`: the DBR field already contained a literal name;
- `unresolved`: the DBR supplied a tag absent from the extracted English text.

Affix skill properties also carry their resolved display name. This matters for
intermediary records such as a mastery node whose own DBR has no display tag but
references the named effect record.

Affix `petBonusName` references are followed during compilation. The referenced
pet package is expanded into individual `pet_*` properties such as pet total
damage, health, offensive ability, speed, and resistances. This makes each pet
stat independently weightable while retaining the source pet-bonus record on
the compiled property's attributes.

## Affix catalog

`affixes.json` includes structurally reachable magic and rare prefixes and
suffixes. It does not include unique affixes or base-item/Monster Infrequent
records. Affixes group by kind and localization tag and retain their consistent
Magical or Rare classification, while each distinct gear slot and semantic
layout remains a separate variant. A variant preserves:

- all level requirements observed for that exact layout;
- structured atomic applicability, including melee, caster, and ranged weapon
  families rather than a display string alone;
- semantic property IDs and distinguishing attributes;
- player-facing stat lines with abstract roll values but concrete discrete
  skill-rank bonuses;
- representative source path and source-record count;
- the count of layouts observed for the same affix and gear slot.

Discrete `skill_level` values are retained on skill-rank properties rather than
being reduced to mere stat presence. When otherwise-identical leveled records
contain different rank values, `skill_level` follows the catalog's current
max-level assumption and `skill_level_min` / `skill_level_max` preserve the
observed range for later level-aware scoring.

Flat damage wrapped in an explicit proc-chance field is compiled under a
separate `chance_flat_<type>_damage` property instead of being conflated with
always-on flat damage. The current reachable affix data uses this form for
Fire, Burn, Physical, and Pierce damage.

## Item catalog

Schema version 2 added one logical `ItemCatalog` stored in six files. Schema
version 3 added structured atomic applicability to affix variants. Schema
version 4 adds affix rarity and skill-rank magnitudes plus mastery tier, order,
and curated parent links. Schema version 5 adds attachment acquisition and
localized faction metadata. Schema version 6 adds reverse-resolved, localized
monster drop sources. Schema version 7 adds reverse-resolved loot-container
sources. Splitting the files keeps large equipment data
separate from smaller attachment and consumable families without forcing
callers to manage six unrelated models:

- `equipment.json`: common and magical bases, Monster Infrequents, ordinary
  rares, crafted and faction equipment, epics, legendaries, awakened variants,
  and equippable quest-record exceptions;
- `components.json`: attachable component records;
- `augments.json`: non-rune enchantments;
- `relics.json`: equipped relic/artifact records;
- `runes.json`: medal movement runes and their skill modifiers;
- `consumables.json`: potions, oils, tinctures, reset/unlock items, and faction
  boosters or warrants.

Items group by family and localization tag. Each definition contains one or
more concrete variants so shared names can retain level tiers, expansion
overlays, and upgraded records. Variants preserve rarity, item class, gear or
applicable slots, item and required level, fixed normalized properties,
stat lines with concrete discrete skill-rank bonuses, set membership, granted
skills, consumable effect skills, component completion-table references, and
MI/rune skill modifiers.
Fixed property attributes retain their raw DBR role values even though current
scoring remains category-presence based.

Equipment variants also retain a broad acquisition-source classification for
recommendation display. Faction equipment is `Purchased`, equipment referenced
directly by a blueprint is `Crafted`, Monster Infrequents are `Specific Monster
Drop`, and other equipment defaults to `Random Drop`. A bounded reverse loot
graph can additionally classify epics and legendaries reached only through
specific enemy loot tables. Each retained `monster_sources` entry contains the
localized enemy name, localization tag, and monster classification. Physical
enemy records sharing the same localized name are collapsed. Loot pools that
fan out to more than 50 distinct localized enemy names are treated as global
random pools and omitted from this metadata. Referenced pet-bonus
records are expanded into individual `pet_*` properties so unique-equipment
scoring can reuse the same pet weights as affix scoring.

Localized records under `records/items/lootchests` are also traced through
their chest loot tables. Concrete items reached through a bounded container
source retain `container_sources` entries containing the localized container
name and tag. A container-only specific item is classified as `Lootable
Container`; the UI renders this as `Lootable Container: <name>`. Container
pools exceeding 10 distinct localized names are treated as global loot rather
than a useful specific source.

Component recipes distinguish `Default Recipe`, `Random Blueprint`, `Special
Vendor Blueprint`, and faction-vendor blueprint availability. This requires
checking where each recipe blueprint is referenced: blueprint-record existence
alone is insufficient because recipes known by default also use blueprint
records. When faction merchant tables are present, direct component offers and
offered blueprints compile to structured faction and reputation sources.
Augments retain their raw DBR
`factionSource`, its official localized faction name, and `Purchased`
acquisition. This metadata is presentation-oriented and does not affect
relevance grades.

Set names and player, pet, item-granted, and modifier skill names resolve during
compilation. Records whose name tags are absent from official localization are
reported and skipped; the current extracted data identifies these as blank or
retired templates rather than releasable items. `enemygear`, transmute proxies,
and decorative equipment-class records are outside the item scope.

The `records/items` and `records/skills` DBR branches are sufficient for item
stats and scoring. Optional component faction-vendor attribution additionally
uses `records/creatures/npcs/merchants` and the referenced faction-controller
records. Optional monster-drop attribution uses `records/creatures/enemies`.
Map locations are not inferred because the extracted DBRs do not contain a
reliable enemy-to-map relationship. These branches are not a complete inventory
of every consumer of an item localization tag: chests and corpses are usually
under `records/items`, while
some doors, map interactables, and quest assets live under `records/level art`,
`records/storyelements*`, or other world-data branches. Grim Gleaner does not
need those extra DBRs to produce a safe override as long as it preserves the
complete official localization file. They would only become required if the
application later needs to interpret or annotate those world objects.

## Distribution boundary

Extracted DBRs and localization archives remain development inputs under the
ignored `game_data/` tree. Normal application use is intended to consume
precompiled JSON catalogs and require no local ARZ extraction. A release may
also offer complete, generated English `tags*_items.txt` files for users who do
not already use Rainbow Filter; users who do use Rainbow can select its complete
files as the output source and retain its existing colors.

Generated bundles currently remain under ignored `artifacts/` until the project
settles the relevant redistribution and release-packaging policy. End-user
archive extraction is not part of the intended runtime design.
