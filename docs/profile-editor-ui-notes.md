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
path has no extension. Files contain a schema version, profile name, and the
nonzero semantic-stat weights. Weight values are validated as integers from 0
through 4 when loading.

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
- Granted item skills remain in the dedicated Skills tab and are deferred until
  specific skill selection and scoring behavior are designed.

## Top Matches testing view

The top-level Top Matches page uses the compiled `AffixCatalog` and the active
`BuildProfile`. During development it looks for `artifacts/catalog`; the scorer
itself receives an `AffixCatalog` directly and does not depend on that path.

Each compiled gear-slot/stat-layout variant is scored independently. The table
shows its grade marker, affix name and type, slot, matched profile stats,
weighted match, and category coverage. Selecting a row shows the full number-
free stat list, level-layout information, localization tag, and representative
record. Changing a profile weight or loading a profile reranks the table.

## Generate Output staging view

The Generate Output page accepts a complete Rainbow `text_en` source folder and
a separate staging destination. It clones all files because partial
`tags_items` overrides make unmapped game tags display as `Tag not found`. Only
exact affix localization tags from the compiled catalog are modified; base-item
names and every unrelated line remain byte-for-byte equivalent apart from a
file's edited affix lines.

The generated marker is inserted immediately before the first Rainbow color
code. Its form is `(S6)`: grade plus matched stat count. If semantic properties
differ between the localization tag's compiled variants, the writer scores the
intersection and marks that conservative result as `(S*5)`. The writer detects
and replaces its own existing marker, making generation idempotent.

The page shows a changed-line preview and reports catalog tags missing from the
Rainbow source. Installation and backup/restore are deliberately not automated
yet; the user manually copies the inspected staging folder into the game.
