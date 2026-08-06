"""Command-line entry points for data-pipeline development and inspection."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from gd_affix_relevance.domain import LocalizationEntry
from gd_affix_relevance.importers.localization_parser import (
    load_localization_directory,
)
from gd_affix_relevance.normalization.field_inventory import (
    build_field_inventory,
    write_inventory_reports,
)
from gd_affix_relevance.normalization.sample_report import (
    build_sample_candidates,
    format_sample_report,
)
from gd_affix_relevance.normalization.affix_reachability import (
    build_affix_reference_statuses,
    write_affix_reference_report,
)
from gd_affix_relevance.scoring.mock_scorer import (
    MOCK_BUILD_PROFILES,
    format_ranked_affix_report,
    rank_key_for_profile,
)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _add_localization_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--localization-root", type=Path, required=True)
    parser.add_argument(
        "--game-localization-root",
        type=Path,
        action="append",
        help=(
            "optional official localization root used to resolve skill-name "
            "and expansion tags; repeat from newest expansion to base game"
        ),
    )


def _load_all_localization_entries(
    args: argparse.Namespace,
) -> tuple[LocalizationEntry, ...]:
    localization_entries = load_localization_directory(args.localization_root)
    for game_localization_root in args.game_localization_root or ():
        localization_entries += load_localization_directory(game_localization_root)
    return localization_entries


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="grim-gleaner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser(
        "inventory",
        help="inventory active affix fields and propose normalization mappings",
    )
    inventory.add_argument("--data-root", type=Path, required=True)
    inventory.add_argument("--localization-root", type=Path)
    inventory.add_argument("--output-dir", type=Path, required=True)

    sample = subparsers.add_parser(
        "sample",
        help="generate a human-readable random sample of reachable affix variants",
    )
    sample.add_argument("--data-root", type=Path, required=True)
    _add_localization_arguments(sample)
    sample.add_argument("--count", type=int, choices=range(1, 11), default=5)
    sample.add_argument("--seed", type=int)
    sample.add_argument("--output", type=Path)

    rank = subparsers.add_parser(
        "rank",
        help="grade all reachable affix variants and show the top matches",
    )
    rank.add_argument("--data-root", type=Path, required=True)
    _add_localization_arguments(rank)
    rank.add_argument(
        "--profile",
        choices=tuple(MOCK_BUILD_PROFILES),
        default="bleed-melee",
    )
    rank.add_argument("--limit", type=_positive_int, default=20)
    rank.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "inventory":
        localization_entries = (
            load_localization_directory(args.localization_root)
            if args.localization_root is not None
            else ()
        )
        result = build_field_inventory(args.data_root, localization_entries)
        write_inventory_reports(result, args.output_dir)
        reference_statuses = build_affix_reference_statuses(
            args.data_root, localization_entries
        )
        write_affix_reference_report(
            reference_statuses, args.output_dir / "affix_reference_status.csv"
        )
        print(
            json.dumps(
                {
                    "records_scanned": result.records_scanned,
                    "supported_records": result.supported_records,
                    "parse_warning_count": result.parse_warning_count,
                    "unresolved_localization_tags": result.unresolved_localization_tags,
                    "active_raw_fields": len(result.fields),
                    "affix_reference_statuses": len(reference_statuses),
                    "output_dir": str(args.output_dir),
                },
                indent=2,
            )
        )
        return 0
    if args.command == "sample":
        localization_entries = _load_all_localization_entries(args)
        result = build_sample_candidates(
            args.data_root,
            localization_entries,
            count=args.count,
            seed=args.seed,
        )
        report = format_sample_report(
            result.candidates,
            seed=result.seed,
            candidate_pool_size=result.candidate_pool_size,
            unresolved_name_records_skipped=result.unresolved_name_records_skipped,
            unknown_slot_records_skipped=result.unknown_slot_records_skipped,
        )
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
        sys.stdout.write(report)
        return 0
    if args.command == "rank":
        localization_entries = _load_all_localization_entries(args)
        profile = MOCK_BUILD_PROFILES[args.profile]
        result = build_sample_candidates(
            args.data_root,
            localization_entries,
            count=args.limit,
            rank_key=rank_key_for_profile(profile),
        )
        report = format_ranked_affix_report(
            result.candidates,
            profile=profile,
            candidate_pool_size=result.candidate_pool_size,
        )
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
        sys.stdout.write(report)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
