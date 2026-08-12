from __future__ import annotations

from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_release_dependencies_and_python_range_are_pinned() -> None:
    payload = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

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
    assert "__PYTHON_PATH__" in template
    assert "__NUITKA_VERSION__" in template
    assert "mode = onefile" in template
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
    assert "assemble-release" in script
    assert "release-manifest.json" in script
    assert "Compress-Archive" in script
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
