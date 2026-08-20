from __future__ import annotations

from pathlib import Path

import pytest

from gd_affix_relevance.domain import ENGLISH_LOCALE
from gd_affix_relevance.ui import i18n

PROJECT_ROOT = Path(__file__).resolve().parents[1]
I18N_RESOURCES_ROOT = PROJECT_ROOT / "resources" / "i18n"


@pytest.fixture(autouse=True)
def _default_ui_locale():
    """Mirror the application's startup behavior: English until configured.

    ``ui.i18n`` holds process-global state because locale changes require a
    restart. Resetting it before and after every test keeps tests that
    exercise the Russian UI from leaking that choice into unrelated tests.
    """

    i18n.configure(I18N_RESOURCES_ROOT, ENGLISH_LOCALE)
    yield
    i18n.configure(I18N_RESOURCES_ROOT, ENGLISH_LOCALE)
