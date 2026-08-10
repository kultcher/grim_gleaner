# Profile editor UI notes

## Weight control

Each stat uses a four-star, five-state control representing weights 0 through 4.

```text
All Damage     ◀  ★ ★ ★ ☆  ▶
```

- `0`: ☆ ☆ ☆ ☆ — Ignored
- `1`: ★ ☆ ☆ ☆ — Incidental
- `2`: ★ ★ ☆ ☆ — Useful
- `3`: ★ ★ ★ ☆ — Emphasized
- `4`: ★ ★ ★ ★ — Core

The left and right buttons decrement and increment the weight. Stars should also
be directly clickable for faster entry. The control exposes an accessible value
such as `Weight 3 of 4: Emphasized`; filled state must not depend on color alone.
The decrement button is disabled at 0 and the increment button is disabled at 4.

## Package accordions

All package names remain visible in their assigned tab. Optional packages start
collapsed instead of being hidden behind an add-package menu.

- Default packages are always expanded and cannot be collapsed.
- Optional packages with all weights at 0 can be expanded or collapsed.
- Changing any stat in an optional package above 0 expands and pins that package.
- A pinned package cannot be collapsed while it contains a nonzero weight.
- Returning every stat in the package to 0 makes it collapsible again.
- An optional package header shows its nonzero-stat count, for example
  `Fire (3 weighted)`.
- An expanded package header shows a `Modify All` star control. Its arrows
  increment or decrement every row independently by one, respecting the 0–4
  limits; selecting a star assigns that exact weight to every package row.
  Mixed packages show unfilled summary stars until all rows share one value.

Accordion expansion is presentation state, not scoring state. A package does not
need a separate enabled flag: only its stat weights affect relevance. Expanded
package IDs may be saved as a user-interface convenience, independently of the
profile's semantic weights.

## Profile files

The editor provides `New Profile`, `Load...`, and `Save...` actions beside the
profile name. New Profile prompts to Save, Discard, or Cancel when the current
profile is dirty. Continuing resets the profile in place to its baseline name,
zero weights, empty mastery slots, and no build-relevant skills. A View Matches
button above the weighting tabs navigates directly to Top Matches.

The application remembers the path most recently saved or loaded and restores
that profile in the next session. The path is persisted immediately rather
than only during a graceful close. If the file is missing or invalid, the stale
setting is removed and the editor starts with a blank profile plus a status
message.

The user chooses the file location and filename; `.json` is added when a save
path has no extension. Files contain a schema version, profile name, two mastery
IDs, selected-skill weights, and the nonzero semantic-stat weights. Weight
values are validated as integers from 0 through 4 when loading. Version-1
profiles remain loadable and receive empty mastery and skill selections.

Saving writes a temporary sibling file and replaces the selected destination
only after serialization succeeds. Profile files are user data and remain
separate from generated game catalogs. Loading updates the active profile in
place, refreshes every star control, and expands packages containing loaded
weights.

## Confirmed placement details

- Generic flat and percentage target resistance reduction appear once in the
  Damage tab's default Base package.
- Damage-type packages expose directional conversion into their selected damage
  type rather than duplicating one generic conversion weight.
- Each conversion destination has a nested source filter. Its incoming damage
  types and a future-facing `Specific Skill` option are enabled by default;
  unchecked global sources are omitted from affix, unique-item, and
  generated-marker scoring and all selections persist with the profile. The
  source-type itself is excluded when it matches the destination. These menus
  show the complete set of other damage families; they are not narrowed to
  source/destination pairs observed in the current catalog.
- Direct damage packages expose `Base Weapon Damage as <type>`. Item base-damage
  DBR bundles map to this category instead of ordinary flat damage; weapons
  without an explicit nonphysical override are treated as physical-base
  weapons. DoT-only Bleeding does not expose a misleading base-weapon option.
- The Pierce package exposes the normalized weapon implicit as `100% Armor
  Piercing`. Its existing `armor_piercing_percent` property uses the same
  user-weighted scoring path as other profile stats.
- Granted item skills remain separate from the mastery-skill selector. Their
  eventual weighting and scoring behavior is still deferred.

## Skills tab

The Skills tab contains two mastery panels. Each panel has a mastery selector,
a `Mastery Skills` list, and a dynamic `Build-Relevant Skills` section. A skill
can be added with the Add button or by double-clicking it, then assigned the
same 0-through-4 weight used by ordinary stats. Removing a skill removes its
stored weight.

After a skill is added, it remains in the Mastery Skills list in its original
tree position but is disabled and visually muted. This preserves the visible
parent/child structure while preventing duplicate selections.

The available list uses compiled mastery-tree metadata rather than raw skill
record paths. Parent and standalone skills are ordered primarily by mastery
tier. Rankable child nodes remain visible at all times, appear immediately
below their parent, and use a `└` marker. Single-rank transmuters and internal
helper records are omitted because item bonuses cannot add ranks to them.

The same mastery cannot be selected in both panels. Changing either selected
mastery while the build-relevant list is nonempty displays:
`Changing masteries will erase the build-relevant skills list and all weights.`
Confirm clears every selected skill and weight belonging to the mastery being
replaced; Cancel restores the prior mastery selection. Skills and weights from
the other mastery are preserved. If the changed mastery has no selected skills,
no warning is necessary.

Profiles store mastery IDs and exact skill record paths rather than display
names. This keeps saved builds stable across presentation changes and lets
direct `+X to Skill` affix properties use the chosen skill weight immediately.
Skill modifiers and granted-skill evaluation remain later work.

Closing the application with unsaved profile changes offers Save, Discard, and
Cancel. Cancel leaves the application open; Save uses the active profile path
or opens the normal save-file chooser for a new profile.

## Pets tab

The Pets tab exposes every pet stat currently found on reachable magic and rare
affixes. Damage, Defenses, and Utility / Other are all default packages, so they
remain expanded without requiring a separate pet-build toggle. The referenced
pet-bonus DBRs are expanded during catalog compilation; each row therefore
weights an individual pet stat rather than one opaque `Pet Bonus` category.

## Top Matches testing view

The top-level Top Matches page uses the compiled affix and item catalogs with
the active `BuildProfile`. During development it looks for `artifacts/catalog`;
the scorers themselves receive catalog objects directly and do not depend on
that path.

Affixes are grouped by atomic gear slot. Each slot row contains an independent
top-five prefix table and top-five suffix table; matched profile stats remain in
the shared detail pane instead of consuming table width. Broadly applicable
affixes may correctly appear in several slot rows. Rows with bonus ranks to a
build-relevant skill are highlighted pale turquoise. Rows with modifiers for a
build-relevant skill are highlighted aquamarine and take precedence when both
are present.

The shared, default-on filters for 1H, 2H, melee, caster, ranged, shield, and
off-hand rows apply to the Affixes, Uniques, and Add-ons tabs. They are presentation
filters rather than saved profile choices. A later `Weapon Type(s)` profile
setting can reuse the same stable slot IDs when loadout choice needs to affect
Add-ons and Build Support globally.

A divider separates handedness from weapon style. If neither 1H nor 2H is
selected, or no melee/caster/ranged style is selected, the Weapons category
stays visible and explains which two filter groups require a selection.

Within each affix/type/slot combination, the highest-level stat layout is shown
and lower tiers are deduplicated. This max-level assumption is stated once in
the page and detail views rather than marked on nearly every result. It remains
separate from `*`, which is the conservative multi-layout marker used by
generated in-game annotations. Selecting a row partitions its semantic stats
into matched and remaining-unmatched lists, so matched entries are not repeated.
Unique skill-modifier lines remain in their own detail section. Level
information, localization tag, and representative record remain visible.
Changing a profile weight or loading a profile reranks every table.

The detail pane has a fixed title above its independently scrolling body. Unique
titles show grade, item, slot, and type, with green, blue, or purple title bars
for Monster Infrequent, Epic, or Legendary items. Affixes and add-ons use the
same title layout with their compiled rarity or family presentation colors.
Semantic stat colors follow the Rainbow-style damage and resistance families;
attributes, OA/DA, health, energy, skill ranks, and skill modifiers have their
own high-contrast colors. Vitality uses a distinct violet pending visual tuning.

Item `base_attack_speed` is structural weapon metadata rather than a weighted
build stat, so it is excluded from both item coverage and unmatched details.
Mastery-wide bonuses resolve through the compiled mastery display name. Named
skill `_buff` DBRs are treated as aliases of their base skill record, allowing
items such as Ugdenbog Sparkthrower to match and highlight a selected Storm Box
of Elgoloth even though the profile and modifier reference different DBRs.

The Uniques tab contains one variable-length table per slot. Its minimum-grade
dropdown supports S, A, or B and defaults to A; C and D are intentionally not
presentation cutoffs. A second, default-on filter row controls Monster
Infrequent, epic, and legendary types. The Type and Source columns
distinguish item rarity from the current basic acquisition classification:
Crafted, Purchased, Random Drop, or Specific Monster Drop. Source inference is
deliberately broad for this first pass: faction records are purchased, direct
blueprint outputs are crafted, Monster Infrequents are specific-monster drops,
and remaining epics or legendaries are random drops.

The Add-ons tab mirrors the compact Affixes layout: every slot row has a
top-five Components table and a top-five Augments table. Components show the
catalog's broad Crafted or Random Drop source. Augments show the officially
localized faction resolved from their DBR `factionSource`; their acquisition
source is Purchased. Selecting either family opens the same matched versus
remaining-unmatched detail structure used elsewhere. Component faction-vendor
availability and reputation tier are added when the corresponding merchant
tables are present in the compiler inputs; otherwise the broad source label
remains available.

Add-ons also provide a centered, collapsed Resistance Cap Mode section. Its
enable checkbox and local copy of the primary Resistances package are temporary
view state rather than saved profile data. While enabled, all local resistance
weights replace the main profile's resistance weights for component and augment
ranking only; Affixes and Uniques continue to use the profile. Non-resistance
profile weights continue contributing to Add-ons. Cap-mode weights are treated
as double their displayed value before the ordinary quadratic scoring curve, so
two cap stars equal an ordinary four-star contribution and four cap stars
contribute 16 relevance points before coverage. The header changes color while
the mode is active. Wheel input over the expanded controls is forwarded to the
Add-ons results scroller so the table list remains navigable without first
collapsing the section.

Fixed item stats, selected-mastery bonuses, and ordinary selected-skill rank
bonuses participate in grading. `†` flags an item that modifies a skill in the
build-relevant skill list. Skill-modifier mechanics, including conversions, are
not yet included in the numeric grade and are called out in the detail pane.

Affixes, unique items, components, and augments share the same nonlinear
relevance formula. Weight
`w` contributes `w² / 4` points, and the sum is multiplied by
`0.70 + 0.30 × coverage`, where coverage is matched categories divided by all
gradeable categories on that affix or item. The base score then receives a
profile-style adjustment based on the average quadratic contribution of all
nonzero ordinary-stat and selected-skill weights. The square-root correction is
bounded to 0.80-1.25 and blended toward 1.0 until the profile has eight nonzero
ratings. Grade floors are S++ 24, S+ 18, S 14, A 10, B 6, C 3, and D 1. The
detail pane shows the adjusted effective score, base score, adjustment factor,
raw linear weight total, and coverage.

## Generate Output staging view

The Generate Output page accepts a complete `text_en` source folder and a
separate staging destination. The source may be Grim Gleaner's complete
official-English baseline or a complete Rainbow folder whose existing colors
the user wants to retain. It clones all files because partial `tags_items`
overrides make unmapped game tags display as `Tag not found`. Only exact
localization tags from compiled scoring catalogs are modified; base-item names,
containers, doors, and every unrelated line remain byte-for-byte equivalent
apart from deliberately edited lines.

The generated marker is inserted immediately before the first Rainbow color
code. Its form is `(S++6)`: grade plus matched stat count. If semantic properties
differ between the localization tag's compiled variants, the writer scores the
intersection and marks that conservative result as `(S++*5)`. The writer detects
and replaces its own existing marker, making generation idempotent.

The page shows a changed-line preview and reports catalog tags missing from the
Rainbow source. Installation and backup/restore are deliberately not automated
yet; the user manually copies the inspected staging folder into the game.
