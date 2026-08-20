"""Restart-friendly UI translation layer keyed by stable message IDs.

Grim Gleaner's interface language is chosen once per process (see
``ui.settings.UI_LOCALE_SETTING``) and does not change without a restart.
The active locale is therefore process-global state, configured once at
startup via :func:`configure` before any widget is constructed, and read
everywhere else through the module-level :func:`t`.

Every translatable string is looked up by a stable, namespaced key such as
``"nav.build_profile"`` or ``"stat.flat_fire_damage"`` — never by its
English source text — so the English and Russian resource files can drift
independently and a missing key degrades safely instead of silently
mistranslating one language.
"""

from __future__ import annotations

import json
from pathlib import Path

from gd_affix_relevance.domain import ENGLISH_LOCALE, LocaleSpec

STAT_LABEL_PREFIX = "stat."


def load_translations(resources_root: Path, locale: LocaleSpec) -> dict[str, str]:
    """Read one locale's flat ``{key: text}`` resource file, if present."""

    path = Path(resources_root) / f"{locale.code}.json"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object of key -> text")
    return {str(key): str(value) for key, value in payload.items()}


class Translator:
    """Resolve message keys for one active locale, falling back to English."""

    def __init__(self, resources_root: Path, locale: LocaleSpec) -> None:
        self.locale = locale
        self.resources_root = Path(resources_root)
        self._english = load_translations(self.resources_root, ENGLISH_LOCALE)
        self._active = (
            self._english
            if locale.code == ENGLISH_LOCALE.code
            else load_translations(self.resources_root, locale)
        )
        self.missing_keys: set[str] = set()

    def t(
        self,
        key: str,
        *,
        default: str | None = None,
        **kwargs: object,
    ) -> str:
        """Resolve *key* in the active locale, then English, then *default*.

        When *default* is omitted, an unresolved key falls back to the key
        itself, so a missing translation is visibly obvious rather than
        silently blank.
        """

        template = self._active.get(key)
        if template is None:
            template = self._english.get(key)
            if template is None:
                self.missing_keys.add(key)
                template = default if default is not None else key
        return template.format(**kwargs) if kwargs else template

    def stat_label(self, stat_id: str, fallback: str) -> str:
        """Resolve a stat's presentation label, defaulting to its catalog label.

        Stat labels are keyed by the already-stable ``stat_id`` (never by the
        English label text) under the ``stat.`` namespace.
        """

        return self.t(f"{STAT_LABEL_PREFIX}{stat_id}", default=fallback)


_translator: Translator | None = None


def configure(resources_root: Path, locale: LocaleSpec) -> Translator:
    """Set the process-wide active translator. Call once, before UI startup."""

    global _translator
    _translator = Translator(resources_root, locale)
    return _translator


def active_translator() -> Translator | None:
    return _translator


def active_locale() -> LocaleSpec:
    return _translator.locale if _translator is not None else ENGLISH_LOCALE


def t(key: str, *, default: str | None = None, **kwargs: object) -> str:
    """Translate *key* using the configured translator, or return it as-is."""

    if _translator is None:
        base = default if default is not None else key
        return base.format(**kwargs) if kwargs else base
    return _translator.t(key, default=default, **kwargs)


def stat_label(stat_id: str, fallback: str) -> str:
    if _translator is None:
        return fallback
    return _translator.stat_label(stat_id, fallback)
