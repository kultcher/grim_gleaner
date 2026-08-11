# Grim Gleaner Tweak Guide

This is a quick map for small presentation and behavior changes. It is organized
by what you might want to change, rather than by the program's architecture.

## Fast lookup

| I want to change... | Start here | Useful landmark |
| --- | --- | --- |
| General colors, borders, spacing, fonts | `src/gd_affix_relevance/ui/style.py` | `APP_STYLESHEET` |
| Matches stat colors or row highlights | `src/gd_affix_relevance/ui/top_matches.py` | `STAT_CATEGORY_COLORS`, `DETAIL_TITLE_COLORS`, `_semantic_stat_color()` |
| Detail-view content or line ordering | `src/gd_affix_relevance/ui/top_matches.py` | `_show_match()`, `_show_unique()`, `_show_addon()` |
| Affix, unique, or add-on table columns | `src/gd_affix_relevance/ui/top_matches.py` | `AffixSlotTable`, `UniqueSlotTable`, `AddonSlotTable` |
| Gear-slot labels, grouping, or filter rules | `src/gd_affix_relevance/slots.py` | `SLOT_LABELS`, `SLOT_GROUPS`, `SLOT_FILTERS`, `FILTER_LABELS` |
| Profile tabs, packages, stat labels, scoring eligibility, or ordering | `src/gd_affix_relevance/stats/registry.py` | `DAMAGE_TAB`, `DEFENSES_TAB`, `CORE_TAB`, `ADVANCED_TAB`, `PETS_TAB`, `NON_SCOREABLE_STAT_DEFINITIONS` |
| Stars, arrows, stat rows, or accordion headers | `src/gd_affix_relevance/ui/widgets.py` | `WeightControl`, `StatRow`, `PackageAccordion` |
| Skills page layout or mastery-change warning | `src/gd_affix_relevance/ui/skills_editor.py` | `MasteryPanel`, `SkillsEditor` |
| Profile toolbar, Save/Load/New, or page hints | `src/gd_affix_relevance/ui/profile_editor.py` | `ProfileEditor` |
| Main left navigation or page ordering | `src/gd_affix_relevance/ui/main_window.py` | `MainWindow.__init__()`, `_add_navigation_item()` |
| In-app usage or limitations copy | `src/gd_affix_relevance/ui/guide.py` | `GuidePage` |
| Export Grades screen text or confirmations | `src/gd_affix_relevance/ui/generate_output.py` | `GenerateOutputPage.generate()`, `restore_backup()` |
| Export installation, backup, or restore behavior | `src/gd_affix_relevance/grade_export.py` | `export_grades_to_game()`, `restore_game_backup()` |
| Settings fields and persistence | `src/gd_affix_relevance/ui/settings.py` | `SettingsPage`, `GAME_FOLDER_SETTING` |
| Actual `tags*_items.txt` annotation behavior | `src/gd_affix_relevance/output/rainbow_writer.py` | `generate_rainbow_output()` |
| Grades, coverage, and weight math | `src/gd_affix_relevance/scoring/catalog_scorer.py` | `GRADE_THRESHOLDS`, `score_semantic_stat_ids()`, `_points_for_weight()` |
| Which fixed items enter the Uniques results | `src/gd_affix_relevance/scoring/item_scorer.py` | `unique_item_type()`, `rank_unique_items_for_slot()` |
| Which components or augments enter Add-ons | `src/gd_affix_relevance/scoring/item_scorer.py` | `rank_addons_for_slot()` |
| Resistance Cap Mode UI or amplification | `src/gd_affix_relevance/ui/top_matches.py` and `src/gd_affix_relevance/scoring/item_scorer.py` | `_build_addon_tab()`, `_resistance_cap_toggled()`, `rank_addons_for_slot()` |
| Saved-profile JSON fields | `src/gd_affix_relevance/domain/profile.py` and `src/gd_affix_relevance/profile_store.py` | `BuildProfile`, `PROFILE_FILE_SCHEMA_VERSION` |

## Colors and appearance

Most ordinary UI appearance is in the single stylesheet string
`APP_STYLESHEET` in `ui/style.py`. Qt widgets are targeted by type and
`objectName`, for example:

```css
QLabel#pageTitle { ... }
QFrame#slotFilterBar { ... }
QTextEdit#matchDetails { ... }
```

The corresponding Python usually contains a line such as:

```python
widget.setObjectName("matchDetails")
```

Search the object name to find both halves of the styling. Changes to
backgrounds, borders, padding, font size, hover states, and selected tabs
usually belong in `style.py`.

### Matches-view color exception

Colors that depend on what a result contains cannot be expressed in the static
stylesheet. They live near the top of `ui/top_matches.py`:

- `SKILL_RANK_HIGHLIGHT` and `SKILL_MODIFIER_HIGHLIGHT`: table-row highlights.
- `DETAIL_TITLE_COLORS`: affix/MI/epic/legendary detail-title backgrounds.
- `STAT_CATEGORY_COLORS`: Rainbow-style semantic stat colors.
- `MATCHED_STAT_COLOR` and `UNMATCHED_STAT_COLOR`: fallback colors for stats
  without a special category.
- `_semantic_stat_color()`: decides which category a semantic stat ID belongs
  to. Its test order matters when names overlap, as with `burn` and
  `frostburn`.

If you only change a hex value, no catalog rebuild is needed.

## Matches page

Nearly all of this page is in `ui/top_matches.py`.

### Detail title and body

`MatchDetailPane` creates the fixed title label and independently scrolling
body. `set_title()` applies the selected title color.

The detail-body order is deliberately explicit:

- `_show_match()` constructs an affix's detail body.
- `_show_unique()` constructs an MI/epic/legendary detail body.
- `_show_addon()` constructs a component/augment detail body.

Each method builds an `html` list from top to bottom and finally passes it to
`setHtml()`. Move the relevant `_html_line()` or `_stat_html()` calls to reorder
sections. `_html_line("")` supplies a visible blank line between sections.

`_stat_html()` handles an individual semantic stat line. Skill-modifier text is
added separately inside `_show_unique()` because modifier effects are not yet
ordinary scored semantic stats.

The title format is also set in these two methods. Affixes currently use a
neutral title because `AffixCatalog` does not carry reliable rarity metadata.

### Tables and result limits

- `AffixSlotTable.set_matches()` defines affix table values and columns.
- `UniqueSlotTable.set_matches()` defines unique-item table values and columns.
- `AddonSlotTable.set_matches()` defines component/augment values and columns.
- `_build_addon_tab()` constructs the fold-down Resistance Cap Mode controls.
- `RESULTS_PER_AFFIX_TABLE` controls the five-result affix limit.
- The Uniques minimum-grade dropdown is constructed in `_build_unique_tab()`.
- `_update_status()` produces the summary sentence above the filters.
- `_weapon_filter_warning()` contains the invalid-filter helper text.

If you add or remove a column, update both the table's header labels and the
`values` tuple used to populate each row. The associated UI tests assert the
current column names.

### Gear sections and filters

The reusable gear vocabulary lives in `slots.py`, not in the page itself:

- `SLOT_LABELS` controls displayed names such as `Helm` and `2H Ranged`.
- `SLOT_GROUPS` controls section order: Weapons, Off-hands, Accessories, Armor.
- The order inside each group's tuple controls row order.
- `SLOT_FILTERS` determines which checkboxes must be enabled for a row.
- `FILTER_LABELS` controls checkbox order and text.

These definitions are shared by Affixes, Uniques, and Add-ons, so changing them
normally keeps all three tabs aligned.

## Build Profile page

### Tabs, packages, and stat order

`stats/registry.py` is the shared semantic and presentation catalog for profile
weights. `ui/catalog.py` only preserves the older import path for UI callers.
Neither file contains extracted game records.

Each `TabDefinition` contains ordered `PackageDefinition` objects, and each
package contains ordered `StatDefinition` objects. Therefore:

- Move a package definition to reorder packages.
- Move a `stat(...)` line to reorder stats inside a package.
- Change the second argument to alter a displayed label.
- Change `default_expanded=True` to alter the initial accordion state.
- Change `PROFILE_TABS` to alter the main tab order.

Be cautious with the first `stat_id` argument. It is the stable key used by
profiles and scoring. Changing only the label is cosmetic; changing the ID can
break existing profile weights unless a migration is added.

`NON_SCOREABLE_STAT_DEFINITIONS` lists recognized properties that should appear
in compiled details but must not affect coverage, such as base shield values and
unresolved placeholders. The compiler validates that every other static
semantic ID has an explicit registry entry.

`ui/widgets.py` owns the reusable visual controls. Look there for star glyphs,
arrow behavior, `Modify All`, nonzero summaries, and accordion header text.

### Skills

`ui/skills_editor.py` owns mastery selection, available-skill lists,
build-relevant skill rows, and the confirmation dialog. `build_mastery_skills()`
transforms the compiled `SkillCatalog` into the per-mastery list shown by the
page.

Skill display names themselves come from the compiled catalog; they are not a
hard-coded UI list.

## Helper text and labels

Most helper text is intentionally kept next to the widget or behavior it
describes. The quickest way to locate a sentence is a repository search:

```powershell
rg -n "part of the visible sentence" src\gd_affix_relevance
```

Common locations:

- `profile_editor.py`: Build Profile hints, file status, and New Profile text.
- `skills_editor.py`: skill-page hint and mastery-change warning.
- `top_matches.py`: page status, legends, filters, and detail text.
- `generate_output.py`: output instructions, path labels, and preview wording.
- `main_window.py`: navigation titles and tooltips.

Dynamic text is often in a method named `_update_status()`, `refresh()`, or the
event handler for the action it follows.

## Scoring and output behavior

Presentation changes usually stop at the UI files. These files change actual
results:

- `scoring/catalog_scorer.py`: semantic-property translation, profile-weight
  lookup, nonlinear points, coverage multiplier, grade thresholds, and affix
  ranking.
- `scoring/item_scorer.py`: fixed-item semantic stats, physical base-weapon
  inference, item type classification, and per-slot unique ranking.
- `output/rainbow_writer.py`: conservative shared-layout grading, marker format,
  placement before Rainbow color codes, source cloning, and idempotent marker
  replacement.
- `ui/generate_output.py`: only the screen and human-readable preview around
  that writer.

Changing grade math should be accompanied by scorer tests. Changing only the
order of detail-view lines does not alter grades or generated game files.

## Profiles, catalogs, and data extraction

- `domain/profile.py` defines the in-memory `BuildProfile`.
- `profile_store.py` translates profiles to and from versioned JSON.
- `catalog/models.py` defines the compiled runtime catalogs and JSON loading.
- `catalog/compiler.py` coordinates a full catalog build.
- `catalog/item_compiler.py` discovers and compiles fixed items and skills.
- `normalization/mapping_proposals.py` maps raw DBR fields into semantic
  properties.
- `normalization/field_policy.py` records ignored/non-gameplay raw fields.

If a change only affects layout, wording, or colors, do not rebuild the catalog.
Rebuild `artifacts/catalog` when extracted data, localization resolution,
normalization rules, or compiled catalog structure changes.

## Quick verification

Run the focused test for the area you changed, then the full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_top_matches_ui.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

Other useful focused tests are:

- `tests/test_profile_editor.py`
- `tests/test_skills_editor.py`
- `tests/test_ui_widgets.py`
- `tests/test_generate_output_ui.py`
- `tests/test_catalog_scorer.py`
- `tests/test_item_scorer.py`
- `tests/test_rainbow_writer.py`

Run the application with:

```powershell
.\.venv\Scripts\grim-gleaner-ui.exe
```

For visual tweaks, the focused automated test catches structural regressions,
but the running application is still the best check for contrast, clipping,
scrolling, and spacing.
