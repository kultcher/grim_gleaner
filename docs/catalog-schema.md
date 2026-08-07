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
mastery-level requirement, maximum level, and whether the record is the mastery
header itself.

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
records. Affixes group by kind and localization tag, while each distinct gear
slot and semantic layout remains a separate variant. A variant preserves:

- all level requirements observed for that exact layout;
- structured atomic applicability, including melee, caster, and ranged weapon
  families rather than a display string alone;
- semantic property IDs and distinguishing attributes;
- number-free player-facing stat lines;
- representative source path and source-record count;
- the count of layouts observed for the same affix and gear slot.

## Item catalog

Schema version 2 added one logical `ItemCatalog` stored in six files. Schema
version 3 adds structured atomic applicability to affix variants. Splitting
the files keeps large equipment data separate from smaller attachment and
consumable families without forcing callers to manage six unrelated models:

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
number-free stat lines, set membership, granted skills, consumable effect
skills, component completion-table references, and MI/rune skill modifiers.
Fixed property attributes retain their raw DBR role values even though current
scoring remains category-presence based.

Equipment variants also retain a broad acquisition-source classification for
recommendation display. Faction equipment is `Purchased`, equipment referenced
directly by a blueprint is `Crafted`, Monster Infrequents are `Specific Monster
Drop`, and other equipment defaults to `Random Drop`. Referenced pet-bonus
records are expanded into individual `pet_*` properties so unique-equipment
scoring can reuse the same pet weights as affix scoring.

Set names and player, pet, item-granted, and modifier skill names resolve during
compilation. Records whose name tags are absent from official localization are
reported and skipped; the current extracted data identifies these as blank or
retired templates rather than releasable items. `enemygear`, transmute proxies,
and decorative equipment-class records are outside the item scope.

The `records/items` and `records/skills` DBR branches are sufficient for the item and scoring
catalogs. They are not a complete inventory of every consumer of an item
localization tag: chests and corpses are usually under `records/items`, while
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
