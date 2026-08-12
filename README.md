# Grim Gleaner v.0.9.0-beta

Grim Gleaner is a utility to help Grim Dawn players quickly and conveniently
identify and evaluate affixes and items that are most relevant to their build.

It has two layers:
- a standalone UI where users can assign weights to relevant stats and see detailed
reports on best-fit affixes, items and components/augments with grades from F-S++
- and an in-game notation system that adds the grades for affixes, epics, legendaries
and MI items directly to the item's tooltip

## Use Cases
- Better loot filtering: In Grim Dawn's loot filter, if you click "Health" it will show you every item with health, even if Health is tied to an affix that has 5-6 other stats you don't care about. With Grim Gleaner, an item like that will still be shown, but will have a very low grade, quickly letting you know that it's not worth your time.
- Checking build support: Before you commit to a build, you can use this tool to identify the key epics, legendaries, MIs and affixes that will be build-defining... or expose the lack of support so you can reconsider or restructure your build.
- Component/Augment Guidance: With all of the random drop and reputation-gated blueprints, it's easy to forget which enhancers are good for your build and where in the world to find them. Grim Gleaner gives you a quick breakdown, slot-by-slot of the best options and which faction they are tied to.

**NOTE:** Grading only assesses *relevance* of stats of an item, not their values. A high grade means "this item's synergizes well with your build" but it may still be a poorly rolled item, or include stats you have already capped, etc. (Sadly, Grim Dawn doesn't expose live values of gear modifiers by default, and digging them up is a much more difficult and invasive process).

## Disclaimer
AI (Codex) was used for data analysis data and coding to build this program.

## Installation and Setup

1. Download the latest .zip file from the releases section
2. Unzip the files to their own folder
3. Run grim_gleaner.exe to launch the utility
4. Open the "Settings" section from the sidebar and set your Grim Dawn game location
(Steam default: C:\Program Files (x86)\Steam\steamapps\common\Grim Dawn)

**NOTE**: This utility has only been tested using English localization. No promises that it will work for other languages!

### Usage

1. Create a build profile
On the "Build Profile" screen, click "New Profile" and enter a name in the textbox.
Starter builds are included under `Profiles/examples` and can be opened with
"Load Profile" as examples to customize.
2. Apply weights to stats
In the tabbed section, you can find almost any individual stat that an item or affix can have.
These are divided into "packages" so you can more easily ignore stats that are irrelevant to your build.
Click the arrows or click directly on the stars to assign a weight (from 0-4) to each stat.
A higher weight will contribute to a higher grade for any item with that stat. Stats with a 0 weight are ignored in this calculation.
3. Check the results
Once you're done setting the weights, click on the "Gear Grades" section from the sidebar or "View Matches" from the Build Profile screen.
There are three tabbed subsections:
- Affixes will show you the 5 highest-graded prefixes and suffixes for each item slot.
- Uniques will do the same for Epics, Uniques and Monster Infrequents. You can set a minimum grade you want to appear in each list.
- Add-ons will show your the 5 highest-graded Components and Augments for each item slot and their sources. It also has an optional "Resistance Cap Mode" that lets you easily target specific resistances that you need to cap.
4. Export to in-game tags
Click over to the "Export Grades" sections from the sidebar, then click "Export Grades." This will automatically backup the files in your /Grim Dawn/settings/text_en folder, if they are there. (These files are used for things like Rainbow Filters). Grim Gleaner *should* be fully compatible and add it's tags while preserving any color/text changes from Rainbow Filters and similar mods. (**Note**: Since Grim Gleaner uses "S" in it's grading and Rainbow uses "S" for set items, Grim Gleaner will replace Rainbow's set notation with "$" for clarity.)

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
- Grading is currently based on the max level of an item/affix. Higher-level versions of many affixes gain new stats in addition to increasing the roll ranges for existing stats. Prior to level 80, this may mean an item's grade my be artificially inflated by it's higher level version.
- Set Bonuses and Granted Skills are currently not graded at all, so items with these features may be graded slightly lower than you might expect. Items with granted skills are marked with an * so you can identify them easily.
- Similarly, Skill Modifiers are graded only based on their existence, not their actual modifications. In other words, if you set the weight on Flame Strike to 4, items with Flame Strike modifiers will get higher grades, but it doesn't account for things like converting your damage to a different type that you aren't using, so use with caution.
Items with modifiers to your chosen skills are marked with ! in the grade.