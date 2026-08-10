"""Command-line entry points for data-pipeline development and inspection."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from gd_affix_relevance.catalog import CatalogBundle
from gd_affix_relevance.catalog.compiler import compile_catalog_bundle
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
from gd_affix_relevance.normalization.item_audit import (
    build_item_audit,
    format_item_audit_report,
)
from gd_affix_relevance.normalization.item_tag_audit import (
    build_item_tag_audit,
    write_item_tag_audit,
)
from gd_affix_relevance.normalization.affix_reachability import (
    build_affix_reference_statuses,
    write_affix_reference_report,
)
from gd_affix_relevance.profile_store import load_profile
from gd_affix_relevance.output import generate_rainbow_output
from gd_affix_relevance.scoring import (
    format_ranked_catalog_report,
    rank_affix_catalog,
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
        help="rank compiled affix variants against a saved build profile",
    )
    rank.add_argument("--catalog-root", type=Path, required=True)
    rank.add_argument("--profile-file", type=Path, required=True)
    rank.add_argument("--limit", type=_positive_int, default=20)
    rank.add_argument("--output", type=Path)

    catalog = subparsers.add_parser(
        "compile-catalog",
        help="compile extracted data into the versioned runtime catalog",
    )
    catalog.add_argument("--data-root", type=Path, required=True)
    catalog.add_argument(
        "--localization-root",
        type=Path,
        action="append",
        required=True,
        help=(
            "official Text_EN directory; repeat from newest expansion to "
            "base game"
        ),
    )
    catalog.add_argument("--output-dir", type=Path, required=True)
    catalog.add_argument("--game-version", default="unknown")
    catalog.add_argument(
        "--mastery-tree-root",
        type=Path,
        help="optional curated Markdown parent/child relationship directory",
    )

    generate = subparsers.add_parser(
        "generate-output",
        help="clone item text files and add profile-grade affix and unique markers",
    )
    generate.add_argument("--catalog-root", type=Path, required=True)
    generate.add_argument("--profile-file", type=Path, required=True)
    generate.add_argument("--source-root", type=Path, required=True)
    generate.add_argument("--output-dir", type=Path, required=True)

    item_audit = subparsers.add_parser(
        "audit-items",
        help="audit fixed item stats and MI skill modifiers in one gear directory",
    )
    item_audit.add_argument("--data-root", type=Path, required=True)
    item_audit.add_argument("--source", default="base")
    item_audit.add_argument("--item-directory", default="gearhead")
    item_audit.add_argument(
        "--localization-root",
        type=Path,
        action="append",
        default=[],
        help="localization directory; repeat in preferred resolution order",
    )
    item_audit.add_argument(
        "--catalog-root",
        type=Path,
        help="optional compiled affix catalog used to identify new property IDs",
    )
    item_audit.add_argument("--output", type=Path)

    item_tags = subparsers.add_parser(
        "audit-item-tags",
        help="classify complete item-localization files and trace DBR consumers",
    )
    item_tags.add_argument("--data-root", type=Path, required=True)
    item_tags.add_argument(
        "--definition-source",
        action="append",
        choices=("base", "gdx1", "gdx2", "gdx3"),
        required=True,
    )
    item_tags.add_argument(
        "--scan-source",
        action="append",
        choices=("base", "gdx1", "gdx2", "gdx3"),
        help="DBR source to scan; defaults to all available sources",
    )
    item_tags.add_argument(
        "--comparison-root",
        type=Path,
        help="optional directory containing complete files to compare by tag key",
    )
    item_tags.add_argument("--output-dir", type=Path, required=True)
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
        bundle = CatalogBundle.load(args.catalog_root)
        profile = load_profile(args.profile_file)
        matches = rank_affix_catalog(
            bundle.affixes,
            profile,
            limit=args.limit,
        )
        candidate_pool_size = sum(
            len(affix.variants) for affix in bundle.affixes.affixes
        )
        report = format_ranked_catalog_report(
            matches,
            profile=profile,
            candidate_pool_size=candidate_pool_size,
        )
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
        sys.stdout.write(report)
        return 0
    if args.command == "compile-catalog":
        localization_entries: tuple[LocalizationEntry, ...] = ()
        for localization_root in args.localization_root:
            localization_entries += load_localization_directory(localization_root)
        result = compile_catalog_bundle(
            args.data_root,
            localization_entries,
            args.output_dir,
            game_version=args.game_version,
            mastery_tree_root=args.mastery_tree_root,
        )
        print(
            json.dumps(
                {
                    "affixes": result.affix_count,
                    "affix_variants": result.affix_variant_count,
                    "skills": result.skill_count,
                    "strings": result.string_count,
                    "unresolved_skill_names": result.unresolved_skill_name_count,
                    "unresolved_affix_records": (
                        result.unresolved_affix_record_count
                    ),
                    "items": result.item_counts,
                    "item_variants": result.item_variant_count,
                    "skipped_unresolved_item_records": (
                        result.unresolved_item_record_count
                    ),
                    "output_dir": str(result.output_dir),
                },
                indent=2,
            )
        )
        return 0
    if args.command == "generate-output":
        bundle = CatalogBundle.load(args.catalog_root)
        profile = load_profile(args.profile_file)
        result = generate_rainbow_output(
            args.source_root,
            args.output_dir,
            bundle.affixes,
            profile,
            items=bundle.items,
        )
        print(
            json.dumps(
                {
                    "profile": profile.name,
                    "files_written": result.files_written,
                    "affix_tags_scored": result.affix_tags_scored,
                    "affix_tags_found": result.affix_tags_found,
                    "unique_tags_scored": result.unique_tags_scored,
                    "unique_tags_found": result.unique_tags_found,
                    "annotated_lines": result.annotated_lines,
                    "missing_affix_tag_count": len(result.missing_affix_tags),
                    "missing_affix_tags": result.missing_affix_tags,
                    "missing_unique_tag_count": len(result.missing_unique_tags),
                    "missing_unique_tags": result.missing_unique_tags,
                    "output_dir": str(result.output_root),
                },
                indent=2,
            )
        )
        return 0
    if args.command == "audit-items":
        localization_entries: tuple[LocalizationEntry, ...] = ()
        for localization_root in args.localization_root:
            localization_entries += load_localization_directory(localization_root)
        affix_property_ids: set[str] = set()
        if args.catalog_root is not None:
            bundle = CatalogBundle.load(args.catalog_root)
            affix_property_ids = {
                property_.property_id
                for affix in bundle.affixes.affixes
                for variant in affix.variants
                for property_ in variant.properties
            }
        result = build_item_audit(
            args.data_root,
            localization_entries,
            source_name=args.source,
            item_directory=args.item_directory,
            affix_property_ids=affix_property_ids,
        )
        report = format_item_audit_report(result)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
        sys.stdout.write(report)
        return 0
    if args.command == "audit-item-tags":
        result = build_item_tag_audit(
            args.data_root,
            definition_sources=tuple(args.definition_source),
            scan_sources=tuple(
                args.scan_source or ("base", "gdx1", "gdx2", "gdx3")
            ),
            comparison_root=args.comparison_root,
        )
        write_item_tag_audit(result, args.output_dir)
        print(
            json.dumps(
                {
                    "localization_definitions": len(result.entries),
                    "unique_tags": len(result.unique_tags),
                    "dbr_referenced_unique_tags": len(
                        result.referenced_unique_tags
                    ),
                    "unreferenced_unique_tags": len(
                        result.unique_tags - result.referenced_unique_tags
                    ),
                    "dbr_files_scanned": result.dbr_files_scanned,
                    "output_dir": str(args.output_dir),
                },
                indent=2,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
