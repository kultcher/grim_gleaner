# gg_hook: Grim Gleaner's in-game hook (phase 1)

Injected into a running Grim Dawn. When the game builds an equipment tooltip,
the DLL reads that item's records and seed and sends them over loopback UDP
(127.0.0.1:47817) to `grim-gleaner live-listen`, which prints
`Got the info: <item> (seed …)`. Nothing is graded yet, and nothing in the
game is changed except that one function being observed.

Approach and type layouts follow GrimDawnItemAssistant's hook DLL (MIT,
marius00): exported, name-mangled Game.dll functions are hooked with
Microsoft Detours, so no signature scanning is involved.

## Build (Windows, MSVC)

Requires Visual Studio 2022 or later with the C++ workload, CMake 3.24+, and
git (CMake fetches Detours v4.0.1).

```powershell
cmake -S native/gg_hook -B build/gg_hook -A x64
cmake --build build/gg_hook --config Release
```

Output: `build/gg_hook/Release/gg_hook.dll`.

The DLL **must** be an MSVC x64 build. The game hands it Microsoft C++
`std::string`s, so the CMake file pins the shared runtime (`/MD`) and turns
iterator debugging off in every configuration. MinGW/clang builds are not
layout-compatible.

## Test

1. Start Grim Dawn and load a character.
2. Check the installed game is compatible (reads Game.dll's export table; no
   injection):
   ```powershell
   grim-gleaner live-check --game-folder "C:\Program Files (x86)\Steam\steamapps\common\Grim Dawn"
   ```
   The 64-bit Game.dll in the `x64` subfolder is used automatically.
   ```
   ```
3. In one terminal: `grim-gleaner live-listen`
4. In another: `grim-gleaner live-inject`. With no `--dll` it loads
   `build\gg_hook\Release\gg_hook.dll` from the project folder, whatever
   folder you run the command from. It refuses if Game.dll lacks the
   expected exports or a hook is already loaded.
5. Hover items. Expected listener output:
   ```
   Hook connected (Grim Dawn pid 12345): hooked ItemEquipment::GetUIDisplayText (4-argument)
   Got the info: Abyssal Mask [Epic] (seed 1234567)  [tooltip builds so far: 3]
   Got the info: Leggings [Rare] (seed 1760317122) with Runecarved + of Blood  [tooltip builds so far: 4]
   ```

The DLL logs to `%LOCALAPPDATA%\GrimGleaner\gg_hook.log`.

## Behaviour and limits

- **Reloading:** the DLL pins itself and cannot be unloaded; restart the game
  to load a new build. The injector copies each build to
  `%LOCALAPPDATA%\GrimGleaner\hook\gg_hook-<hash>.dll`, so rebuilding is never
  blocked by the copy the game has open.
- **Repeat reports:** one message per item, repeated only after 2 s without
  hovering it. `tooltip builds so far` is the raw call count. In testing it
  rises by about one per hover: the game builds a tooltip once when it opens,
  not every frame.
- **Safety:** if a game patch changes `ItemReplicaInfo` (the game writes past
  the guard area) or reading an item faults, the hook logs it, sends an
  error message and stops reporting, while the game carries on normally.
- **Not covered yet:** relics/charms (`ItemArtifact`), components and other
  non-equipment items. Comparison tooltips may report the equipped item too.
  If Item Assistant is running, its own stat requests also pass through this
  function and will be reported.
