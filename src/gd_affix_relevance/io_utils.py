"""Small shared helpers for durable local file writes."""

from __future__ import annotations

from pathlib import Path
import shutil


def atomic_replace_directory(target: Path, incoming: Path) -> None:
    """Replace an owned directory, restoring the previous tree on failure."""
    target.parent.mkdir(parents=True, exist_ok=True)
    previous = target.parent / f".{target.name}-grim-gleaner-previous"
    if previous.exists():
        raise ValueError(f"unfinished prior replacement exists: {previous}")
    moved_previous = False
    try:
        if target.exists():
            target.replace(previous)
            moved_previous = True
        incoming.replace(target)
    except Exception:
        if moved_previous and not target.exists():
            previous.replace(target)
        raise
    else:
        if moved_previous:
            shutil.rmtree(previous)


def atomic_write_text(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
) -> None:
    """Write text beside its destination and atomically replace the target."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        temporary.write_text(text, encoding=encoding)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Write bytes beside their destination and atomically replace the target."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
