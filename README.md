# Grim Gleaner v.0.9.2-beta

Recent Changes:
v0.9.2-beta (08/19/26):
- updated catalog for Grim Dawn 1.3.0.7
- added English and Russian interface and item-name export support
- added profile level-awareness:\
Items that are above your selected level band are excluded from the display view\
Item grading and stat displays reflect the version of that affix/item that is appropriate to your level range
- Various UI readability and organization tweaks

_____

Grim Gleaner is a utility to help Grim Dawn players quickly and conveniently
identify and evaluate affixes and items that are most relevant to their build.

It has two layers:
- a standalone UI where users can assign weights to relevant stats and see detailed
reports on best-fit affixes, items and components/augments with grades from F-S++
- and an in-game notation system that adds the grades for affixes, epics, legendaries
and MI items directly to the item's tooltip

**UPDATE: 08/13/26**: The previous release was being flagged as a trojan due to a known issue the Nuitka Python Compiler in --onefile mode. It now builds in --standalone mode and should no longer cause issues with virus protection.

## Use Cases
- **Better loot filtering**: In Grim Dawn's loot filter, if you click "Health" it will show you every item with health, even if Health is tied to an affix that has 5-6 other stats you don't care about. With Grim Gleaner, an item like that will still be shown, but will have a very low grade, quickly letting you know that it's not worth your time.
- **Checking build support**: Before you commit to a build, you can use this tool to identify the key epics, legendaries, MIs and affixes that will be build-defining... or expose the lack of support so you can reconsider or restructure your build.
- **Component/Augment Guidance**: With all of the random drop and reputation-gated blueprints, it's easy to forget which enhancers are good for your build and where in the world to find them. Grim Gleaner gives you a quick breakdown, slot-by-slot of the best options and which faction they are tied to.

**NOTE:** Grading only assesses *relevance* of stats of an item, not their values. A high grade means "this item's synergizes well with your build" but it may still be a poorly rolled item, or include stats you have already capped, etc. (Sadly, Grim Dawn doesn't expose live values of gear modifiers by default, and digging them up is a much more difficult and invasive process).

### Disclaimer
AI (Codex) was used for data analysis data and coding to build this program.

## Installation and Setup

1. Download the latest .zip file from the [releases section](https://github.com/kultcher/grim_gleaner/releases)
2. Extract the `Grim Gleaner` folder from the archive and place it wherever you
   want.
3. Run `grim_gleaner.exe` to launch the utility.
4. Open the "Settings" section from the sidebar and set your Grim Dawn game location (you'll be prompted automatically the first time you open the program.)\
(Steam default location: C:\Program Files (x86)\Steam\steamapps\common\Grim Dawn)

**NOTE**: English and Russian localizations are supported on 64-bit Windows.
Other Grim Dawn languages and non-x64 Windows systems are not currently supported.

## Russian Localization / Русская локализация

Grim Gleaner can display its interface in Russian and export grades into Russian
Grim Dawn item names. The interface language and the item language are separate
settings, so either can remain in English if preferred.

1. Close Grim Dawn before preparing files or exporting grades.
2. In **Settings**, set **Interface language** to **Русский**. Restart Grim
   Gleaner to apply the translated interface.
3. Set **Grim Dawn item language** to **Русский**. Selecting Russian for the
   interface also selects Russian item names by default, but the item language
   can be changed independently.
4. Confirm that the selected game folder contains `Grim Dawn.exe`.
5. Create or load a profile, then open **Export Grades** and export it. Before
   the first Russian export, Grim Gleaner automatically reads the required item
   tags from `Text_RU.arc` in the selected Grim Dawn installation.
6. Start Grim Dawn with its language set to Russian. The generated files are
   written to the active `Documents\My Games\Grim Dawn\Settings\text_ru`
   folder when it exists, otherwise to the selected installation's
   `settings\text_ru` folder.

Use **Refresh game language files** only after a Grim Dawn update or when you
need to rebuild the prepared clean-language source. Restart Grim Gleaner after
refreshing so the catalog reloads the updated item names.

Rainbow Filter and gdse are optional. If matching localization files are
already installed, Grim Gleaner preserves their colors and text and adds grade
markers on top. Clean item tags extracted from the user's own Grim Dawn
installation fill any missing files. Grim Gleaner does not distribute extracted
game localization.

The first export for each language preserves its original state in the
`backups` folder beside the packaged application. Later exports do not overwrite
that snapshot. **Restore Backups** restores only the currently selected item
language, so English and Russian backups cannot be mixed accidentally.

### Краткая инструкция

1. Закройте Grim Dawn.
2. В разделе **Настройки** выберите **Русский** для языка интерфейса и языка
   предметов Grim Dawn, затем перезапустите Grim Gleaner.
3. Укажите папку игры, содержащую `Grim Dawn.exe`.
4. Создайте или загрузите профиль и нажмите **Экспортировать оценки**. При
   первом экспорте русские файлы будут подготовлены автоматически.
5. Запустите Grim Dawn на русском языке и проверьте оценки в названиях
   предметов. Для отмены изменений используйте **Восстановить резервную
   копию**.

Rainbow Filter устанавливать необязательно. Если он уже установлен, его цвета
и оформление сохраняются. Кнопка **Обновить файлы языка игры** нужна после
обновления Grim Dawn; после её использования перезапустите Grim Gleaner.

## Installing from Source

I don't recommend doing this right now as I need to clean up some things. You can try:
1. Clone the repo
2. python -m pip install -e .
3. run grim-gleaner-ui.exe

but no guarantees it'll work properly this way. It *definitely* won't work properly if you don't use the -e flag.

### Usage

1. **Create a build profile**\
On the "Build Profile" screen, click "New Profile" and enter a name in the textbox.
Starter builds are included under `Profiles/examples` and can be opened with
"Load Profile" as examples to customize.
2. **Apply weights to stats**\
In the tabbed section, you can find almost any individual stat that an item or affix can have.
These are divided into "packages" so you can more easily ignore stats that are irrelevant to your build.
Click the arrows or click directly on the stars to assign a weight (from 0-4) to each stat.
A higher weight will contribute to a higher grade for any item with that stat. Stats with a 0 weight are ignored in this calculation.
3. **Check the results**\
Once you're done setting the weights, click on the "Gear Grades" section from the sidebar or "View Matches" from the Build Profile screen.
There are three tabbed subsections:
- Affixes will show you the 5 highest-graded prefixes and suffixes for each item slot.
- Uniques will do the same for Epics, Uniques and Monster Infrequents. You can set a minimum grade you want to appear in each list.
- Add-ons will show your the 5 highest-graded Components and Augments for each item slot and their sources. It also has an optional "Resistance Cap Mode" that lets you easily target specific resistances that you need to cap.
4. **Export to in-game tags**\
**Important**: Any time you want to export grades, make sure the game is closed! Also, if you replace or remove the files in the selected `text_en` or `text_ru` folder, you need to run the export again.\
Choose the item language under "Settings," then open "Export Grades" from the sidebar and click "Export Grades." Missing clean-language files are prepared automatically from the selected Grim Dawn installation. The first export backs up the selected language folder if it already exists. These files may be used by Rainbow Filter or gdse; Grim Gleaner preserves their color/text changes while adding grades. (**Note**: Since Grim Gleaner uses "S" in its grading and Rainbow uses "S" for set items, Grim Gleaner replaces Rainbow's set notation with "$" for clarity.)

Rainbow Filter or gdse are recommended but not required. Find them below:\
[Rainbow Filter](https://forums.crateentertainment.com/t/tool-rainbow-filter-item-highlighting/42765)\
[gdse](https://forums.crateentertainment.com/t/tool-gdse-a-light-weight-fully-automated-alternative-to-rainbow-filter/156183)

See the "Guide" section in the UI for more information.

#### Weighting Tips

Assign stars to each stat modifier based on how important the stat is to your build. Use the following as a guideline:

0 stars: Stats that are totally irrelevant to your build.
> Examples: Vitality damage in a pure Fire build; flat +damage on a caster build, energy regen for a WPS build

1 star: Stats that have minimal or only occasional impact, such as damage types that you deal only incidentally.
> Examples: +% modifiers for things you aren't stacking, flat elemental damage in a mono-element build, Health Regen

2 stars: Baseline stats that are generally useful, but not core to your build.
> Health, Physique, OA/DA, skills bonuses to secondary skills

3 stars: Important stats you're always happy to have.
> Examples: OA and Crit Damage for crit builds, attack/cast/move speed

4 stars: Core stats that you want as much of as possible.
> Examples: Main damage type, resist reduction, skill bonuses to core skills

Don't be too conservative in rating things at 3/4 if they are important. The more strong signals you provide, the more the surfaced results will reflect your preferences.

#### Limitations
- Grading is currently based on the max level of an item/affix. Higher-level versions of many items and affixes gain new stats in addition to increasing the roll ranges for existing stats. Prior to level 80, this may mean an item's grade my be artificially inflated based on it's higher level version.\
> For example, Francis' Gun, which you find on a corpse in the opening area, has flat and fire damage at level 1, but gains Lightning Damage and Offensive Ability on the level 50 version, so profiles set up for Lightning Damage or OA may see a higher grade or "false positive."
- Set Bonuses and Granted Skills are currently not graded at all, so items with these features may be graded slightly lower than you might expect. Items with granted skills are marked with an * so you can identify them easily.
- Similarly, Skill Modifiers are graded only based on their existence, not their actual modifications. In other words, if you set the weight on Flame Strike to 4, items with Flame Strike modifiers will get higher grades, but it doesn't account for things like converting your damage to a different type that you aren't using, so use with caution.
Items with modifiers to your chosen skills are marked with ! in the grade.
- Magic affixes often have only one or two stat mods, which makes it unlikely for them to score above a C grade. However, since most "rare items" are technically ones with one rare and one magic affix, a C-grade magic affix may be stronger than that grade entails.
