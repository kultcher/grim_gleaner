# Release Build

Grim Gleaner's Windows release is built with Python 3.13, PySide6 6.11.1,
`pyside6-deploy`, and Nuitka 4.1.3. Python 3.14 remains supported for ordinary
development, but it is intentionally not used for the release compiler while
Nuitka reports its support as experimental.

## Prepare the build environment

From the project root:

```powershell
py -3.13 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -e ".[test,release]"
```

The build script does not install or upgrade dependencies automatically. This
keeps dependency downloads separate from packaging and makes failures easier to
diagnose.

## Build

```powershell
.\scripts\package-release.ps1
```

By default the script:

1. verifies that the build interpreter is Python 3.13;
2. runs the complete test suite;
3. materializes a machine-local `pysidedeploy.spec` under ignored `build/`;
4. creates a one-file `grim_gleaner.exe` with `pyside6-deploy`;
5. assembles the catalog, tags, README, license, notices, and Profiles folder;
6. validates the required release paths; and
7. creates `dist/Grim-Gleaner-0.1.0-win64.zip`.

It refuses to replace an existing release folder or archive unless explicitly
called with `-Overwrite`. That switch is intended only for the generated
`dist/Grim Gleaner` and ZIP paths.

Useful options:

```powershell
# Skip tests only after they have already passed in this exact build environment.
.\scripts\package-release.ps1 -SkipTests

# Rebuild the generated release outputs.
.\scripts\package-release.ps1 -Overwrite

# Select a non-default Python 3.13 environment.
.\scripts\package-release.ps1 `
  -BuildPython C:\path\to\venv\Scripts\python.exe
```

Do not run the packaging script as Administrator. Files created directly in the
release folder inherit the invoking user's normal access rules. The application
does not access or modify Grim Dawn during packaging.

## Smoke test

Extract the ZIP into a new writable folder and launch `grim_gleaner.exe` from
there. Do not test only from the project checkout. Confirm that:

- Gear Grades contains catalog results;
- the configured Grim Dawn folder is recognized by `Grim Dawn.exe`;
- saving and reopening a profile works;
- export creates an original-state backup;
- a second export preserves that backup; and
- Restore Backups returns `settings/text_en` to its original state.

For a clean-machine test, use a Windows account without Python or development
tools installed.
