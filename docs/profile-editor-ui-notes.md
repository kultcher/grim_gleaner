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

Accordion expansion is presentation state, not scoring state. A package does not
need a separate enabled flag: only its stat weights affect relevance. Expanded
package IDs may be saved as a user-interface convenience, independently of the
profile's semantic weights.

## Profile files

The editor provides `Load...` and `Save...` actions beside the profile name.
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
- Granted item skills remain separate from the mastery-skill selector. Their
  eventual weighting and scoring behavior is still deferred.

## Skills tab

The Skills tab contains two mastery panels. Each panel has a mastery selector,
a `Mastery Skills` list, and a dynamic `Build-Relevant Skills` section. A skill
can be added with the Add button or by double-clicking it, then assigned the
same 0-through-4 weight used by ordinary stats. Removing a skill removes its
stored weight.

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
affixes may correctly appear in several slot rows.

The shared, default-on filters for 1H, 2H, melee, caster, ranged, shield, and
off-hand rows apply to both the Affixes and Uniques tabs. They are presentation
filters rather than saved profile choices. A later `Weapon Type(s)` profile
setting can reuse the same stable slot IDs when loadout choice needs to affect
Add-ons and Build Support globally.

Within each affix/type/slot combination, the highest-level stat layout is shown
and lower tiers are deduplicated. This max-level assumption is stated once in
the page and detail views rather than marked on nearly every result. It remains
separate from `*`, which is the conservative multi-layout marker used by
generated in-game annotations. Selecting a row shows matched stats, the full
number-free stat list, level information, localization tag, and representative
record. Changing a profile weight or loading a profile reranks every table.

The Uniques tab contains one variable-length table per slot. Its minimum-grade
dropdown supports S, A, or B and defaults to A; C and D are intentionally not
presentation cutoffs. A second, default-on filter row controls Monster
Infrequent, epic, and legendary types. The Type and Source columns
distinguish item rarity from the current basic acquisition classification:
Crafted, Purchased, Random Drop, or Specific Monster Drop. Source inference is
deliberately broad for this first pass: faction records are purchased, direct
blueprint outputs are crafted, Monster Infrequents are specific-monster drops,
and remaining epics or legendaries are random drops.

Fixed item stats, selected-mastery bonuses, and ordinary selected-skill rank
bonuses participate in grading. `†` flags an item that modifies a skill in the
build-relevant skill list. Skill-modifier mechanics, including conversions, are
not yet included in the numeric grade and are called out in the detail pane.

Affixes and unique items share the same nonlinear relevance formula. Weight
`w` contributes `w² / 4` points, and the sum is multiplied by
`0.70 + 0.30 × coverage`, where coverage is matched categories divided by all
gradeable categories on that affix or item. Grade floors are S 10, A 6.5, B 4,
C 1, and D above zero. A one-stat affix therefore receives full coverage: a
core match is B, a useful or emphasized match is C, and an incidental match is
D. The detail pane retains the raw linear weight total for diagnosis.

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
code. Its form is `(S6)`: grade plus matched stat count. If semantic properties
differ between the localization tag's compiled variants, the writer scores the
intersection and marks that conservative result as `(S*5)`. The writer detects
and replaces its own existing marker, making generation idempotent.

The page shows a changed-line preview and reports catalog tags missing from the
Rainbow source. Installation and backup/restore are deliberately not automated
yet; the user manually copies the inspected staging folder into the game.
