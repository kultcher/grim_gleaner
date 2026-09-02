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
SUPPORTED_UI_LOCALES = (ENGLISH_LOCALE, RUSSIAN_LOCALE)
SUPPORTED_GAME_LOCALES = (ENGLISH_LOCALE, RUSSIAN_LOCALE)
# Backwards-compatible union for callers that only need locale lookup. Keeping
# the two capability lists separate lets a future game-language export ship
# without implying that Grim Gleaner's entire interface is translated too.
SUPPORTED_LOCALES = tuple(
    dict.fromkeys((*SUPPORTED_UI_LOCALES, *SUPPORTED_GAME_LOCALES))
)


def _locale_for_code(
    code: str,
    supported: tuple[LocaleSpec, ...],
    *,
    capability: str,
) -> LocaleSpec:
    normalized = str(code).strip().casefold()
    locales_by_code = {locale.code: locale for locale in supported}
    if normalized in locales_by_code:
        return locales_by_code[normalized]
    choices = ", ".join(locale.code for locale in supported)
    raise ValueError(
        f"Unsupported locale {code!r} for {capability}; expected one of: {choices}"
    )


def locale_for_code(code: str) -> LocaleSpec:
    """Return any supported locale after normalizing a user-supplied code."""

    return _locale_for_code(code, SUPPORTED_LOCALES, capability="application")


def ui_locale_for_code(code: str) -> LocaleSpec:
    """Return a locale with translated Grim Gleaner interface resources."""

    return _locale_for_code(code, SUPPORTED_UI_LOCALES, capability="interface")


def game_locale_for_code(code: str) -> LocaleSpec:
    """Return a locale supported by game-data extraction and grade export."""

    return _locale_for_code(code, SUPPORTED_GAME_LOCALES, capability="game")
