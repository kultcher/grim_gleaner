"""Shared parsing helpers for scalar catalog fields."""

from __future__ import annotations


def integer_value(value: str | None) -> int:
    """Parse a DBR numeric scalar represented as an integer or float string."""

    try:
        return int(float(value or "0"))
    except ValueError:
        return 0
