"""Read exported symbol names from a Windows DLL (PE32+) without Windows.

Used to check, before injecting anything, that the installed Game.dll still
exports the functions gg_hook needs. A patch that changes one of their
signatures changes the mangled name, so this catches incompatible game
versions up front.
"""

from __future__ import annotations

import struct
from pathlib import Path


class PeFormatError(ValueError):
    pass


def is_64_bit(path: Path) -> bool:
    """Whether a PE file is a PE32+ (64-bit) image."""

    data = Path(path).read_bytes()[:4096]
    if data[:2] != b"MZ":
        raise PeFormatError(f"{path} is not a PE file")
    (pe_offset,) = struct.unpack_from("<I", data, 0x3C)
    (magic,) = struct.unpack_from("<H", data, pe_offset + 24)
    return magic == 0x20B


def read_export_names(path: Path) -> frozenset[str]:
    data = Path(path).read_bytes()
    if data[:2] != b"MZ":
        raise PeFormatError(f"{path} is not a PE file")
    (pe_offset,) = struct.unpack_from("<I", data, 0x3C)
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise PeFormatError(f"{path} has no PE signature")
    coff = pe_offset + 4
    section_count, optional_size = struct.unpack_from("<H12xH", data, coff + 2)
    optional = coff + 20
    (magic,) = struct.unpack_from("<H", data, optional)
    if magic == 0x20B:  # PE32+
        directories = optional + 112
    elif magic == 0x10B:  # PE32
        directories = optional + 96
    else:
        raise PeFormatError(f"{path} has an unknown optional header")
    export_rva, export_size = struct.unpack_from("<II", data, directories)
    if export_rva == 0 or export_size == 0:
        return frozenset()

    sections = []
    table = optional + optional_size
    for index in range(section_count):
        entry = table + index * 40
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
            "<IIII", data, entry + 8
        )
        sections.append(
            (virtual_address, max(virtual_size, raw_size), raw_pointer)
        )

    def offset(rva: int) -> int:
        for virtual_address, size, raw_pointer in sections:
            if virtual_address <= rva < virtual_address + size:
                return raw_pointer + (rva - virtual_address)
        raise PeFormatError(f"RVA {rva:#x} is outside every section")

    directory = offset(export_rva)
    # IMAGE_EXPORT_DIRECTORY: NumberOfNames at +24, AddressOfNames at +32.
    (name_count,) = struct.unpack_from("<I", data, directory + 24)
    (names_rva,) = struct.unpack_from("<I", data, directory + 32)
    names_table = offset(names_rva)
    names: set[str] = set()
    for index in range(name_count):
        (name_rva,) = struct.unpack_from("<I", data, names_table + index * 4)
        start = offset(name_rva)
        end = data.index(b"\0", start)
        names.add(data[start:end].decode("ascii", errors="replace"))
    return frozenset(names)
