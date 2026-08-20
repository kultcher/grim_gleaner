"""Supported application and Grim Dawn localization definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LocaleSpec:
    """All stable names needed to resolve resources for one locale."""

    code: str
    display_name: str
    game_text_directory: str
    catalog_filename: str
    game_archive_filename: str
    encoding: str = "utf-8-sig"


ENGLISH_LOCALE = LocaleSpec(
    code="en",
    display_name="English",
    game_text_directory="text_en",
    catalog_filename="strings.en.json",
    game_archive_filename="Text_EN.arc",
)
RUSSIAN_LOCALE = LocaleSpec(
    code="ru",
    display_name="Русский",
    game_text_directory="text_ru",
    catalog_filename="strings.ru.json",
    game_archive_filename="Text_RU.arc",
)
SUPPORTED_LOCALES = (ENGLISH_LOCALE, RUSSIAN_LOCALE)
_LOCALES_BY_CODE = {locale.code: locale for locale in SUPPORTED_LOCALES}


def locale_for_code(code: str) -> LocaleSpec:
    """Return a supported locale after normalizing a user-supplied code."""

    normalized = str(code).strip().casefold()
    try:
        return _LOCALES_BY_CODE[normalized]
    except KeyError as error:
        supported = ", ".join(locale.code for locale in SUPPORTED_LOCALES)
        raise ValueError(
            f"Unsupported locale {code!r}; expected one of: {supported}"
        ) from error
