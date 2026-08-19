"""Shared parsing helpers for scalar catalog fields."""

from __future__ import annotations


def integer_value(value: str | None) -> int:
    """Parse a DBR numeric scalar represented as an integer or float string."""

    try:
        return int(float(value or "0"))
    except ValueError:
        return 0


def optional_float_value(value: str | None) -> float | None:
    """Parse an optional DBR scalar without conflating absence with zero."""

    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None
