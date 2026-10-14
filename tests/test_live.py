from __future__ import annotations

import socket
import threading
from pathlib import Path

import pytest

from gd_affix_relevance.live.compatibility import REQUIRED_EXPORTS, check_game_dll
from gd_affix_relevance.live.injector import staged_dll_path
from gd_affix_relevance.live.listener import (
    ListenerState,
    RecordNames,
    describe_item,
    listen,
)
from gd_affix_relevance.live.pe_exports import PeFormatError, read_export_names
from gd_affix_relevance.live.protocol import (
    DEFAULT_PORT,
    HookError,
    HookStatus,
    HoveredItem,
    ProtocolError,
    parse_message,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DLL = Path(__file__).parent / "fixtures" / "pe" / "exports_sample.dll"


def _item_line(**overrides: str) -> bytes:
    fields = {
        "calls": "42",
        "seed": "123456",
        "base": "records/items/gearhead/d004_head.dbr",
        "prefix": "records/items/lootaffixes/prefix/b_ar001.dbr",
        "suffix": "",
    }
    fields.update(overrides)
    values = [fields["calls"], fields["seed"], fields["base"], fields["prefix"], fields["suffix"]]
    values += [""] * 7
    return ("GG1\titem\t" + "\t".join(values) + "\n").encode()


def test_protocol_port_matches_native_reporter() -> None:
    header = (PROJECT_ROOT / "native" / "gg_hook" / "src" / "reporter.h").read_text()
    assert f"kReporterPort = {DEFAULT_PORT};" in header


def test_parse_item_message() -> None:
    message = parse_message(_item_line())
    assert isinstance(message, HoveredItem)
    assert message.calls == 42
    assert message.seed == 123456
    assert message.base_record == "records/items/gearhead/d004_head.dbr"
    assert message.suffix_record == ""


def test_parse_status_and_error_messages() -> None:
    assert parse_message(b"GG1\thello\t9000\tok\thooked it") == HookStatus(
        "hello", 9000, True, "hooked it"
    )
    assert parse_message(b"GG1\terror\tlayout changed") == HookError("layout changed")


@pytest.mark.parametrize(
    "payload",
    [b"nope", b"GG1", b"GG1\titem\t1\t2", b"GG1\thello\tx\tok\td", b"GG1\tmystery", b"\xff"],
)
def test_parse_rejects_malformed_messages(payload: bytes) -> None:
    with pytest.raises(ProtocolError):
        parse_message(payload)


def test_describe_item_resolves_names_from_catalog() -> None:
    names = RecordNames(
        items={"records/items/gearhead/d004_head.dbr": ("Abyssal Mask", "Epic")},
        affixes={"records/items/lootaffixes/prefix/b_ar001.dbr": "Stalwart"},
    )
    text = describe_item(parse_message(_item_line()), names)  # type: ignore[arg-type]
    assert text.startswith("Got the info: Abyssal Mask [Epic] (seed 123456) with Stalwart")
    assert "Got the info: records/items/gearhead/d004_head.dbr" in describe_item(
        parse_message(_item_line())  # type: ignore[arg-type]
    )


def test_record_names_from_real_catalog() -> None:
    from gd_affix_relevance.catalog import CatalogBundle

    names = RecordNames.from_catalog(CatalogBundle.load(PROJECT_ROOT / "artifacts" / "catalog"))
    assert names.item("RECORDS\\ITEMS\\GEARHEAD\\D004_HEAD.DBR") is not None
    assert names.affixes


def test_listener_state_reports_connection_once() -> None:
    state = ListenerState()
    assert "connected" in state.handle(HookStatus("heartbeat", 7, True, "12"))
    assert state.handle(HookStatus("heartbeat", 7, True, "13")) is None
    assert "NOT hooked" in state.handle(HookStatus("hello", 7, False, "no export"))


def test_listen_receives_udp_datagrams() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    lines: list[str] = []
    stop = threading.Event()
    worker = threading.Thread(
        target=listen,
        kwargs={"on_line": lines.append, "port": port, "should_stop": stop.is_set},
    )
    worker.start()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            for _ in range(50):
                sender.sendto(_item_line(), ("127.0.0.1", port))
                if lines:
                    break
                stop.wait(0.05)
    finally:
        stop.set()
        worker.join(timeout=5)
    assert lines and lines[0].startswith("Got the info:")


def test_read_export_names_from_a_real_dll() -> None:
    assert "GgHookVersion" in read_export_names(SAMPLE_DLL)


def test_read_export_names_rejects_non_pe(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.dll"
    bogus.write_bytes(b"not a dll")
    with pytest.raises(PeFormatError):
        read_export_names(bogus)


def test_compatibility_check_reports_missing_exports() -> None:
    report = check_game_dll(SAMPLE_DLL)
    assert not report.compatible
    assert set(report.missing) == set(REQUIRED_EXPORTS)


def test_required_exports_match_native_symbols() -> None:
    header = (PROJECT_ROOT / "native" / "gg_hook" / "src" / "game_types.h").read_text()
    for candidates in REQUIRED_EXPORTS.values():
        for symbol in candidates:
            assert f'"{symbol}"' in header


def test_staged_dll_path_changes_with_content(tmp_path: Path) -> None:
    dll = tmp_path / "gg_hook.dll"
    dll.write_bytes(b"build one")
    first = staged_dll_path(dll, tmp_path / "stage")
    dll.write_bytes(b"build two")
    second = staged_dll_path(dll, tmp_path / "stage")
    assert first != second
    assert first.name.startswith("gg_hook-") and first.suffix == ".dll"
