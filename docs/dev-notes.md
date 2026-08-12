TO DO:
- add links to grimtools for everything
- surface any error logs
- show list of leveled affixes
- maybe just bundle rarity colors anyway
- coverage should probably exclude 1-rated items
- use tags_uimain to modify tagRDifficultyTitles to maybe display current profile info
- check idempotence protections
- maybe some kind of notifier if files changed externally?
- finalize recommendation text for weights
- somehow track unwanted negative conversions?

STRETCH:
- stretch: properly evaluated skill modifiers weight assignments (currently naive)
- stretch: semi-smart granted skill evaluation (damage type based?)
- stretch: add bonus weight to skill rank bonuses higher than 1 (and weighting for # of active skills on +allskills)
- stretch: implement build support calculations (remember: important to also classify slot diversity)
- stretch: Add drop locations* of MIs/Epics/Legendaries (maybe just redirect to Grim Tools?)
- stretch: "resistance hunt" mode
- stretch: add system tailoring affixes to given level, including numbers
- stretch: per-slot filtering for profiles
- add monster names and locations for drops
- some kind of character import?

LOW PRIORITY:
- save item slot visibility prefs with profile save
- re-evaluate approach to Rainbow's (S)
- app-level: include an "Ungrade" standalone script instead of just backup?
- If no actual changes, skip "Exported grades to..."
- maintainability organization and planning

NOTES/EXPLORATIONS: 
- change to "commit changes" type of flow vs. automatic updates (add warning to matches screens if unsaved changes)
- apply affix colors to profile view, maybe?
- outport sorting: currently by weight. Alt: flat damage, % damage, damage conversion, core stats, health/energy mod, OA/DA, speed, damage resistances, other resistances, skill bonuses, misc, granted skills...
- dig into _html_line stuff in scoring

POSSIBLE USER SETTINGS:
- whether or not to include relevance number
- minimum stars for relevance
- some value to change grading strictness
- allow customizing elements of grading display, maybe grade-tag colors?


______
Important pre-release checks
- Code signing would reduce Windows SmartScreen friction, but it is not required for an initial release.
- CI is absent. Useful, but not a blocker if we retain a documented local release checklist.

py -3.13 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -e ".[test,release]"
.\scripts\package-release.ps1