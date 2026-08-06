# Compiled catalog

The runtime catalog separates maintenance-time extraction from normal
application use. Its current files are:

```text
catalog/
|-- manifest.json
|-- strings.en.json
|-- skills.json
`-- affixes.json
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

## Skill catalog

`skills.json` contains expansion-overlaid, named records from the
`playerclass*` and `itemskills*` branches. This covers mastery/player skills,
their explicit pet subskills, and item-granted skills even when no current
affix refers to them. Named monster, quest, devotion, default, template, and
other internal branches are excluded. Each entry retains its logical record
path, winning source, broad category, name tag, display name, name-resolution
status, and optional description tag.

The resolution statuses are:

- `localized`: the name tag resolved through official English text;
- `literal`: the DBR field already contained a literal name;
- `unresolved`: the DBR supplied a tag absent from the extracted English text.

Affix skill properties also carry their resolved display name. This matters for
intermediary records such as a mastery node whose own DBR has no display tag but
references the named effect record.

## Affix catalog

`affixes.json` includes structurally reachable magic and rare prefixes and
suffixes. It does not include unique affixes or base-item/Monster Infrequent
records. Affixes group by kind and localization tag, while each distinct gear
slot and semantic layout remains a separate variant. A variant preserves:

- all level requirements observed for that exact layout;
- semantic property IDs and distinguishing attributes;
- number-free player-facing stat lines;
- representative source path and source-record count;
- the count of layouts observed for the same affix and gear slot.

## Future item data

Base items and Monster Infrequents can be added as a sibling `items.json`
catalog without changing affix, skill, string, profile, or scoring concepts.
Monster Infrequent should be an item classification inside that catalog rather
than a separate storage system. Adding the file will require a deliberate
schema revision and an optional `ItemCatalog` member on `CatalogBundle`; it does
not require changing existing catalog IDs.

## Distribution boundary

Extracted DBRs and localization archives remain development inputs under the
ignored `game_data/` tree. Generated bundles currently remain under ignored
`artifacts/` as well. A release may package the derived bundle after the project
settles the relevant redistribution policy; end-user archive extraction is not
part of the intended runtime design.
