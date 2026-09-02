from __future__ import annotations

from pathlib import Path
import tomllib

from gd_affix_relevance import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_release_dependencies_and_python_range_are_pinned() -> None:
    payload = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert payload["project"]["version"] == "0.9.2-beta"
    assert __version__ == payload["project"]["version"]
    assert payload["project"]["requires-python"] == ">=3.13,<3.15"
    assert "PySide6==6.11.1" in payload["project"]["dependencies"]
    assert "Nuitka==4.1.3" in payload["project"]["optional-dependencies"][
        "release"
    ]


def test_deployment_template_is_portable_and_complete() -> None:
    template = (
        PROJECT_ROOT / "packaging" / "pysidedeploy.spec.template"
    ).read_text(encoding="utf-8")

    assert "__PROJECT_ROOT__" in template
    assert "__DEPLOY_OUTPUT__" in template
    assert "__ICON_PATH__" in template
    assert "__PYTHON_PATH__" in template
    assert "__NUITKA_VERSION__" in template
    assert "mode = standalone" in template
    assert "--output-filename=grim_gleaner.exe" in template
    assert "mode = onefile" not in template
    assert "C:\\Users\\" not in template


def test_packaging_script_validates_release_before_archiving() -> None:
    script = (PROJECT_ROOT / "scripts" / "package-release.ps1").read_text(
        encoding="utf-8"
    )

    assert "Release builds require Python 3.13" in script
    assert "--basetemp" in script
    assert "cache_dir=" in script
    assert "grim-gleaner-package-tests-" in script
    assert "pyside6-deploy.exe" in script
    assert '"packaging\\gg_icon.ico"' in script
    assert 'Replace("__ICON_PATH__", $iconPath)' in script
    assert "Application icon is not a valid ICO container" in script
    assert '"grim_gleaner.dist"' in script
    assert "Grim-Gleaner-0.9.2-beta-win64.zip" in script
    assert "Standalone distribution does not contain its required dependencies" in script
    assert "Copy-Item -LiteralPath $standaloneOutput" in script
    assert "assemble-release" in script
    assert '"tags\\tagsgdx2_endlessdungeon.txt"' in script
    assert "release-manifest.json" in script
    assert "resources\\i18n\\en.json" in script
    assert "resources\\i18n\\ru.json" in script
    assert "Compress-Archive -LiteralPath $releaseRoot" in script
    assert 'Join-Path $releaseRoot "*"' not in script
    assert "C:\\Users\\" not in script


def test_release_legal_documents_are_populated() -> None:
    license_text = (PROJECT_ROOT / "LICENSE.TXT").read_text(encoding="utf-8")
    notices = (PROJECT_ROOT / "THIRD_PARTY_NOTICES.txt").read_text(
        encoding="utf-8"
    )

    assert "MIT License" in license_text
    assert "Grim Gleaner contributors" in license_text
    assert "PySide6" in notices
    assert "Python Software Foundation" in notices
    assert "Nuitka" in notices
    assert "Crate Entertainment" in notices


def test_release_icon_is_a_multiresolution_windows_icon() -> None:
    icon = (PROJECT_ROOT / "packaging" / "gg_icon.ico").read_bytes()

    assert int.from_bytes(icon[0:2], "little") == 0
    assert int.from_bytes(icon[2:4], "little") == 1
    image_count = int.from_bytes(icon[4:6], "little")
    assert image_count >= 1

    sizes = set()
    for index in range(image_count):
        offset = 6 + (16 * index)
        width = icon[offset] or 256
        height = icon[offset + 1] or 256
        sizes.add((width, height))

    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes
