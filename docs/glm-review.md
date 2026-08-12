I have enough to compile the review. Here it is.

# Code Review: Grim Gleaner

Pre-release cleanup pass. Findings are grouped by theme, with `file:line` references. I flagged real problems only — no stylistic nitpicks.

---

## A. High-value cleanups (do these before release)

### A1. `cli.py:210-413` — 200-line command dispatch chain
`main()` is a 200-line ladder of `if args.command == "...":` blocks, each duplicating the same `args.output.parent.mkdir(...); args.output.write_text(...); sys.stdout.write(...)` pattern (`cli.py:256-259`, `277-280`, `367-369`). Subparsers already support `set_defaults(func=handler)` — convert each branch to a small `_run_*` function and end `main()` with `return args.func(args)`. Eliminates ~50 lines and the trailing `return 2` dead branch.

### A2. `cli.py:226-239, 293-313, 326-344, 382-398` — duplicated `json.dumps(..., indent=2)` summary printing
Four near-identical "print a stats dict" blocks. Extract `_print_json_summary(payload: dict)`.

### A3. `ui/widgets.py:448-450` — bulk-edit emits a misleading signal
`_apply_bulk` only emits `weight_changed` for the *first* `stat_id`, even though many stats changed. Any subscriber that re-derives state from one stat will be stale. Add a `bulk_changed` signal (or emit per changed stat).

---

## B. Redundancy / copy-paste

### B1. `scoring/item_scorer.py:137-203` vs `206-289` — `rank_unique_items_for_slot` and `rank_addons_for_slot`
~150 lines of structural duplication: slot filtering, `max()` candidate selection by `(level, rank_key, record_path)`, re-scoring, skill-modifier flag, identical 6-tuple sort key, `tuple(ranked[:limit])`. Extract a private `_rank_variants_for_slot(variants, slot_id, *, minimum_score, limit)` helper parameterized by the catalog family.

### B2. `scoring/catalog_scorer.py:311-321` vs `375-386` — duplicated sort-key tuple
The leading 5 elements of the sort key `(effective_score, relevance_points, weighted_match, matched_count, coverage_ratio, ...)` are copy-pasted between `rank_affix_catalog` and `rank_affixes_for_slot`. Put the common prefix on `RelevanceScore` as a `rank_key` property.

### B3. `output/rainbow_writer.py:75-103` vs `118-158` — `_build_affix_instructions` / `_build_unique_instructions`
Same skeleton: build `selected_skills`, iterate catalog, pick `max()` candidate, score, build flag string, emit `_MarkerInstruction`. Parameterize by catalog iterator + flag logic.

### B4. `output/rainbow_writer.py:366-374` vs `profile_store.py:28-37` — atomic-write pattern duplicated
Write-to-`.tmp` → `replace()` → cleanup-on-exception is copied verbatim. Extract to a shared `io_utils.atomic_write_text(path, text)` helper.

### B5. `catalog/compiler.py:554-558` and `catalog/item_compiler.py:660-665` — duplicated `_integer_value`/`_integer_field`
Identical `int(float(...))` with `try/except ValueError: return 0`. One helper in a shared module.

### B6. `catalog/item_compiler.py:398-406` vs `532-550` — duplicated blueprint-target resolution
Same 9-line block (resolve blueprint → `artifactName`/`forcedRandomArtifactName` → `.strip().lower().replace("\\","/")` → `startswith("records/items/") and endswith(".dbr")`). Extract `_resolve_blueprint_target`.

### B7. `catalog/models.py:72-75` vs `108-112` — `AffixProperty` and `ItemProperty` are byte-identical dataclasses
Same fields (`property_id`, `property_key`, `attributes`). Collapse to one `Property` class.

### B8. `ui/main_window.py:143-211` — page-creation copied 5×
Each page: instantiate → add to stacked widget → create nav item. Drive from a `(PageClass, title, tooltip, kwargs)` tuple list in a loop.

### B9. `ui/profile_editor.py:211-247` vs `249-279` — `load_from_path` / `new_profile` re-clear all fields by hand
Add a `BuildProfile.replace_with(source)` (or `_reset_profile_to(self, source)`) and call it from both.

### B10. `ui/profile_editor.py:293-313` — two near-identical unsaved-prompt dialogs
`_prompt_unsaved_action` / `_prompt_exit_unsaved_action` differ only by message. One `_prompt_unsaved(message)`.

### B11. `ui/profile_editor.py:315-361` — three blocks of `try: save/load; except (OSError, ValueError, TypeError): QMessageBox.critical`
Extract `_with_profile_io(description, fn)`.

### B12. `ui/top_matches.py:1197-1288, 1290-1417, 1419-1522` — `_show_match`/`_show_unique`/`_show_addon`
~80% shared HTML scaffolding (score header, matched/unmatched sections, footer). Extract `_build_detail_html(base_parts, extra_parts)`.

### B13. `ui/top_matches.py:1162-1195` — three near-identical `_select_first_visible_*` methods
Same `SLOT_GROUPS` nested loop differing only by row/table map and pane cleared. Parameterize.

### B14. `ui/top_matches.py:1048-1084` — `_refresh_uniques` / `_refresh_addons` structurally identical
Extract `_refresh_tables(tables, rank_fn, **kwargs)`.

### B15. `ui/generate_output.py:117-171` vs `173-209` — `generate` / `restore_backup` skeleton
Both: validate folder → `QMessageBox.question` → call backend → status update. Extract `_run_confirmed_action(title, message, fn, on_success)`.

### B16. `ui/settings.py:134-163` — `has_valid_game_folder` and `_refresh_game_folder_status` duplicate validation
Both call `validate_grim_dawn_folder(Path(value))` and catch `(OSError, ValueError)`. Have one call the other.

### B17. `ui/widgets.py:44-69` vs `265-290` — `WeightControl` and `PackageModifyControl` duplicate star/arrow layout
Extract a `StarControl` base or factory.

### B18. `ui/skills_editor.py:117-133` — `_root_skill_sort_key` / `_child_skill_sort_key` differ only in tuple order
Combine into `_skill_sort_key(skill, tier_first: bool)`.

### B19. `scoring/catalog_scorer.py:105-107, 145-147` — inline damage-type alias dict
`{"life": "vitality", "poison": "acid"}` is inlined in two functions while `canonical_damage_type` (which uses the same map in `conversions.py`) is *already imported* in this file. Use it.

### B20. `stats/registry.py:727, 738-739` — prefix tuple `("skill_bonus:", "skill_modifier:", "mastery_bonus:")` repeated
Extract `DYNAMIC_STAT_PREFIXES` constant.

### B21. `stats/registry.py:8-25` — parallel `RACE_STAT_SUFFIXES` / `RACE_DISPLAY_NAMES` must stay in lockstep
Collapse to a single `RACES = (("aether", "Aether"), ...)` tuple.

---

## C. Overengineering / defensive-where-not-needed

### C1. `domain/profile.py:43-71` — `__post_init__` round-trips every field through its setter
For each of `weights`, `skill_weights`, `resistance_cap_weights`, `excluded_conversion_sources`, it copies out, clears, and re-applies via the validating setters — including re-validating types that `from_dict` already validated. Fine for `from_dict`, but this also runs on every direct construction (e.g. tests, `new_profile`). Consider a `_validate()` method instead of copy/clear/re-apply.

### C2. `ui/main_window.py:261, 265` — `isinstance(page_index, int)` / `isinstance(tab_index, int)`
These guard ints that `_add_navigation_item` stored two lines earlier. Internal contract — drop the checks.

### C3. `profile_store.py:22` — `_with_json_suffix(Path(path))` wraps an already-`Path` arg
Remove the redundant `Path()`.

### C4. `catalog/compiler.py:69-71`, `catalog/item_compiler.py:132` — redundant `Path()` wrapping and `resolver = repository` alias
Parameters are already typed `Path`; `resolver` is just `repository` renamed and passed around.

### C5. `catalog/item_compiler.py:692` — `dict` used as a set
`property_ids[property_id] = property_id` — value never read. Use `set[str]`.

### C6. `ui/generate_output.py:211-216` — unused `_game_folder` parameter
`refresh_game_location(self, _game_folder="", ...)` never uses the arg; always re-derives via `_configured_game_folder()`. Drop the parameter or honor it.

### C7. `ui/generate_output.py:121-125` — side-effect-only call
`grim_dawn_text_root(game_folder)` is called only to raise on invalid folders; return discarded. Replace with `validate_grim_dawn_folder(game_folder)` for intent clarity.

### C8. `ui/generate_output.py:127-128` — build full marker lists only to `len()` them
`build_affix_markers(...)` and `build_unique_item_markers(...)` construct the full lists and discard them, then `export_grades_to_game` rebuilds them internally. Add `count_affix_markers`/`count_unique_item_markers` (or build once and reuse).

### C9. `ui/profile_editor.py:49-54` — eager `Path.cwd().mkdir(...)` on startup when `profiles_root is None`
Creates a directory at CWD even if the user never saves there. Defer to first save.

### C10. `ui/profile_editor.py:236` — `del blocker` on a `QSignalBlocker`
Unnecessary; scoping already releases it.

### C11. `catalog/models.py:290-301` — `validate()` re-checks aggregate counts already guaranteed by per-family checks
`len(self.items.all_items())`, `item_variant_count`, `affix_variant_count` are pure sums of already-validated parts. Remove the three aggregate checks.

### C12. `catalog/models.py:223-226` — dead backward-compat defaults in `CatalogBundle.load`
`skill_scope`/`item_scope` defaults are unreachable because `compiler.py:164-165` always writes both fields.

### C13. `ui/settings.py:131-132` — one-line `_browse_game_folder` wrapper
Connect the button directly to `prompt_for_game_folder`.

### C14. `catalog/item_compiler.py:696-701` — `chance_damage_bundle_keys` built eagerly, used once, never stored
Inline into `contextualize_damage_chance` or accept a generator.

### C15. `catalog/item_compiler.py:410-441` — `_acquisition_source` takes 4 booleans + category branching
Combinatorial flag matrix. Replace with an `AcquisitionContext` dataclass or a lookup keyed on `(family, source_kind)`.

### C16. `ui/top_matches.py:973` — `refresh(self, _value=False)` unused param tied to a non-checkable button
Connect with `lambda _: self.refresh()` and drop the param.

---

## D. Vibe-code red flags / bugs

### D1. `catalog/compiler.py:554-558` / `item_compiler.py:660-665` — silent `ValueError → 0`
`_integer_value` swallows parse failures and returns `0`, masking malformed game-data fields. At minimum log a warning; prefer letting it propagate during catalog compilation (it's a build-time tool, not runtime).

### D2. `catalog/compiler.py:224` — unresolved skill tags pollute `strings`
When `display_name` is unresolved (starts with `tag`/`xtag`) it's set to `""`, but `strings[name_tag] = display_name` still inserts the empty string into the catalog. Only insert when truthy.

### D3. `catalog/item_compiler.py:481-490` — side effect inside a list comprehension
`_vendor_source_payloads` comprehension calls `_localized_faction_name`, which mutates the caller's `strings` dict. Rewrite as an explicit loop.

### D4. `output/rainbow_writer.py:203` — `ItemCatalog((), (), (), (), (), ())`
Six positional empty tuples hardcode the constructor signature. Add `ItemCatalog.empty()` classmethod.

### D5. `scoring/item_scorer.py:126-134` — string literals instead of module constants
`unique_item_type()` uses `"monster_infrequent"`, `"epic"`, `"legendary"` while `TYPE_*` constants exist 10 lines above.

### D6. `scoring/item_scorer.py:142` — `frozenset(UNIQUE_ITEM_TYPES)` rebuilt per call
Make `UNIQUE_ITEM_TYPES` a `frozenset` at module level.

### D7. `profile_store.py:11-12` — schema version tracked in two places
`PROFILE_FILE_SCHEMA_VERSION = 4` and `SUPPORTED_PROFILE_FILE_SCHEMA_VERSIONS = frozenset({1,2,3,4})` drift independently. Derive: `SUPPORTED = frozenset(range(1, PROFILE_FILE_SCHEMA_VERSION + 1))`.

### D8. `ui/style.py:208-213` — dead CSS selectors
`QSpinBox#matchLimit`, `QLineEdit#outputPath`, `QPlainTextEdit#outputPreview` reference object names not present in any reviewed UI file. Delete or wire up.

### D9. `ui/top_matches.py:537-594` — `TopMatchesPage` god-class
~15 parallel collections (`tables`, `unique_tables`, `addon_tables`, matching `*_slot_rows`, matching `*_category_widgets`, `weapon_filter_warnings`, three `_*_selected_table`, `resistance_cap_rows`). Split into `AffixTabPage` / `UniqueTabPage` / `AddonTabPage`, each owning its tables/rows/state; parent becomes a coordinator. This is the single largest maintainability risk in the UI.

### D10. `ui/top_matches.py:59-97` — color tokens hardcoded in Python
`STAT_CATEGORY_COLORS` / `DETAIL_TITLE_COLORS` duplicate the project's color system outside `style.py`. Move there.

---

## E. Minor / optional

- `catalog/__init__.py:26-45`, `stats/__init__.py:23-41`, `ui/catalog.py:22-39`, `records/__init__.py`, `importers/__init__.py`, `normalization/__init__.py` — `__all__` mirrors the import list verbatim. Either drop it (Python exposes non-underscored names) or accept the maintenance cost; right now every new export needs two edits.
- `catalog/models.py:181-193` — `ItemCatalog.all_items()` rebuilds a 6-family tuple on every call; `validate()` calls it 4×. `@cached_property` (class is frozen).
- `catalog/compiler.py:213, 217` — `name_tag.casefold()` computed twice. Hoist to `tag_folded`.
- `catalog/item_compiler.py:291-294` — `family == "components"` repeated 3× in one call. Compute `is_component` once.
- `stats/registry.py:8-16` — `RACE_STAT_SUFFIXES` appears unused outside the module (suffix already encoded in `stat_id` strings); confirm and remove if so.
- `scoring/catalog_scorer.py:170-197` — `unregistered_catalog_stat_ids` has two near-identical nested loops differing only by skip-set. Extract inner loop.

---

## Release recommendation

The app is functional. Before release I'd prioritize, in order:
1. **A1–A3** (CLI dispatch, summary-print duplication, guide typo, dead method, misleading bulk signal) — quick, user-facing or structural.
2. **D1, D2, D3, D5, D6, D7** (silent error swallowing, string-literal/constant mismatches, schema-version drift) — correctness/drift hazards.
3. **B1–B3, B12, B15** (the big copy-paste blocks in scoring/output/UI) — these are where future bugs will hide.
4. **D9** (split `TopMatchesPage`) — biggest UI maintainability risk, but can ship without if time-boxed; just file it as the first post-release refactor.

Everything in **C** and **E** is optional polish.

---

## Grim Gleaner follow-up (2026-08-12)

The review was checked against the current working tree. The following agreed,
low-risk items were resolved in the pre-release cleanup:

- **A1 / A2:** CLI subparsers now register dedicated command handlers. `main()`
  only parses and dispatches, while shared helpers handle JSON summaries and
  optional report-file output. A regression test verifies that every command
  has a callable handler.
- **A3:** package-wide weight changes now emit `weight_changed` once for every
  stat that actually changed, with its real stat ID and value. The widget test
  now verifies the complete signal sequence.
- **B2:** the existing `RelevanceScore.rank_key` is now used by both affix sort
  paths instead of repeating its five fields.
- **B4:** profile JSON and Rainbow byte output now use shared atomic-write
  helpers. Catalog JSON output uses the same text helper as well.
- **B5:** DBR integer scalar parsing is centralized in
  `catalog/value_parsing.py`.
- **B6:** blueprint output resolution is centralized in
  `_resolve_blueprint_target` and shared by blueprint-distribution and faction
  vendor discovery.
- **B10:** the two unsaved-profile dialogs now share one message-parameterized
  helper.
- **B16:** Settings now has one game-folder validation path used by both the
  boolean check and visible status message.
- **B18:** root and child skill ordering now share `_skill_sort_key`.
- **B19:** conversion scoring now uses the already-centralized
  `canonical_damage_type` aliases.
- **B20 / B21:** dynamic stat prefixes and race metadata now each have a single
  source of truth.

The larger B1, B3, B7-B9, B11-B15, and B17 refactors are directionally
reasonable, but are deferred because they touch broader scoring, output, model,
or UI ownership boundaries and are not suitable for a low-risk release patch.

Two review details were not current:

- **D2** is already handled correctly: unresolved skill display names are only
  added to `strings` when the resolved display name is truthy.
- The release recommendation mentions a "guide typo" and a "dead method" under
  A1-A3, but no corresponding findings appear in sections A1-A3.
