# Grim Gleaner

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

# Installation and Setup

1. Download the latest .zip file from the releases section
2. Unzip the files to their own folder
3. Run grim_gleaner.exe to launch the utility
4. Open the "Settings" section from the sidebar and set your Grim Dawn game location
(Steam default: C:\Program Files (x86)\Steam\steamapps\common\Grim Dawn)

# Usage

1. Create a build profile
On the "Build Profile" screen, click "New Profile" and enter a name in the textbox.
2. Apply weights to stats
In the tabbed section, you can find almost any individual stat that an item or affix can have.
These are divided into "packages" so you can more easily ignore stats that are irrelevant to your build.
Click the arrows or click directly on the stars to assign a weight (from 0-4) to each stat.
A higher weight will contribute to a higher grade for any item with that stat. Stats with a 0 weight are ignored in this calculation.
3. Check the results
Once you're done setting the weights, click on the "Gear Grades" section from the sidebar or "View Matches" from the Build Profile screen.
There are three tabbed subsections:
> Affixes will show you the 5 highest-graded prefixes and suffixes for each item slot.
> Uniques will do the same for Epics, Uniques and Monster Infrequents. You can set a minimum grade you want to appear in each list.
> Add-ons will show your the 5 highest-graded Components and Augments for each item slot and their sources. It also has an optional "Resistance Cap Mode" that lets you easily target specific resistances that you need to cap.
4. Export to in-game tags
Click over to the "Export Grades" sections from the sidebar, then click "Export Grades." This will automatically backup the files in your /Grim Dawn/settings/text_en folder, if they are there. (These files are used for things like Rainbow Filters). Grim Gleaner *should* be fully compatible and add it's tags while preserving any color/text changes from Rainbow Filters and similar mods.

**NOTE**: This has only been tested using English localization. No promises that it will work for other languages!

# How Weighting/Grading Works
