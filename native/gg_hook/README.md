# gg_hook: Grim Gleaner's in-game hook

Injected into a running 64-bit Grim Dawn. For every equipment tooltip the
game builds, the hook:

1. reads the item's records and seed (`Item::GetItemReplicaInfo`);
2. optionally asks the game for the detailed (Ctrl) version of the tooltip
   into a private list, to get each stat's roll range;
3. grades the item with the **grade table** Grim Gleaner wrote for the
   active profile: whole-item relevance (base + prefix + suffix stats),
   roll quality, rarity class;
4. optionally adds a short line such as `A 87%` to the tooltip;
5. reports everything to Grim Gleaner over loopback UDP (127.0.0.1:47817),
   where the app grades the same item itself and flags any disagreement.

It also hooks `Item::PassLootFilter` so items graded below their rarity's
threshold fail the game's own loot filter.

Approach and type layouts follow GrimDawnItemAssistant's hook DLL (MIT,
marius00): exported, name-mangled Game.dll functions hooked with Microsoft
Detours, so no signature scanning.

## Layout

| File | Role |
|---|---|
| `src/stat_core.*` | Game-independent grading: line keys, grade table, relevance, roll quality, label, filter decision. Port of `gd_affix_relevance/live/*.py`; `tests/test_native_core.py` checks they agree. |
| `src/game_access.*` | Guarded game reads, the detailed tooltip pass, the injected line. |
| `src/live_table.*` | Polls and hot-swaps `%LOCALAPPDATA%\GrimGleaner\live\grade_table.txt`. |
| `src/tooltip_hook.*` | `ItemEquipment::GetUIDisplayText` hook. |
| `src/loot_filter_hook.*` | `Item::PassLootFilter` hook. |
| `src/reporter.*`, `hook_log.*`, `hook_util.*`, `dllmain.cpp` | Messaging, logging, Detours attach, start-up. |

## Build (Windows, MSVC)

Visual Studio 2022+ with the C++ workload, CMake 3.24+, git (CMake fetches
Detours v4.0.1). From the project folder:

```powershell
cmake -S native/gg_hook -B build/gg_hook -A x64
cmake --build build/gg_hook --config Release
```

Must be an MSVC x64 build with the shared runtime (the CMake file enforces
`/MD` and no iterator debugging): the game hands the DLL Microsoft C++
`std::string`s and `std::wstring`s.

## Test plan (phase 2)

Commands below run from `.venv-build\Scripts`. The DLL cannot be unloaded:
restart Grim Dawn to load a new build.

1. **Compatibility.** With the game closed or running:
   ```powershell
   .\grim-gleaner live-check --game-folder "D:\SteamLibrary\steamapps\common\Grim Dawn"
   ```
   `Item::PassLootFilter` is optional; if missing, only the loot filter is off.
2. **Console listener with grading.** Writes the grade table and grades every
   item in the app too:
   ```powershell
   .\grim-gleaner live-listen --profile-file "C:\...\MyBuild.json" --record "C:\...\live.jsonl"
   ```
   In development it reads `game_data\base\text_en\tags_ui.txt`; otherwise
   add `--game-folder` once to extract it from the game.
3. **Inject:** `.\grim-gleaner live-inject` (in a second terminal).
4. **Hover items.** Each item prints the app's verdict and whether the hook
   agrees, e.g.
   ```
   Got the info: Leggings [Rare] (seed 1760317122) with Runecarved + of Blood  [...]
       app: B (7.40, 5/9) rare, roll 79%, label 'B 79%' | dll agrees (ranges read, label injected)
            bonuses | +39% Elemental Damage [29-40]
   ```
   Check: `dll agrees` on every item; `ranges read` without holding Ctrl
   (proves the detailed pass); the `B 79%` line in the in-game tooltip
   (proves injection); no "unmatched rolled lines".
5. **Loot filter.** Restart the listener with thresholds, e.g.
   `--hide magic=B --hide common=A`. Ground items below them should lose
   their labels the way the game's own filter hides items, and the listener
   prints `Loot filter hid: ...`.
6. **Switches.** `--no-inject` and `--no-detail` turn those behaviours off
   through the grade table, without rebuilding or restarting.
7. **Live tab.** Close the console listener (it holds the port), open the
   app's **Live** page and click **Start listening**. Same information, with
   the filter and tooltip options in the UI.

Everything the hook does is logged to `%LOCALAPPDATA%\GrimGleaner\gg_hook.log`.

## Safety design

- **Reading:** every game read runs under structured exception handling and
  is checked against the layouts confirmed in testing (ItemReplicaInfo guard
  area, 64-byte GameTextLine, sane text classes and lengths).
- **Writing:** the only write into game memory is the optional label line. It
  is placed only into spare capacity the game's list already has (never
  growing or reallocating it), and its text is at most 7 characters, which
  `std::wstring` stores inline, so nothing is allocated. If there is no spare
  slot, that tooltip simply has no label.
- **Detailed pass:** uses a private scratch list whose storage the game
  allocates once and which is reused; its strings are destroyed the same way
  the item records already are.
- **Loot filter:** only turns a pass into a fail, never the reverse; items
  not in the grade table (potions, components, unknown records) are never
  hidden; decisions are cached per item for at most a second.
- **Independent off-switches:** reporting, tooltip text, the detailed pass
  and the filter each disable themselves on the first fault and report why,
  leaving the game untouched. `inject`, `detail` and `filter` are also grade
  table switches the app controls.
- **Unload:** the DLL pins itself so it can never be unloaded while hooked.

## Known assumptions to confirm in game

- The `bool` argument of `ItemEquipment::GetUIDisplayText` selects the
  detailed (Ctrl) tooltip. If it does not, the listener will show no
  `ranges read` and roll quality only appears while Ctrl is held.
- `Item::PassLootFilter` returning false hides an item the way the built-in
  filter does. Its `ItemIgnore` argument is passed through untouched.
- The injected line uses text class 0x13 (item bonus lines in 1.3.1).
- English stat lines are matched against `tags_ui.txt`; Russian would use
  the Russian `tags_ui.txt` once extracted (same keys), not yet tested.
