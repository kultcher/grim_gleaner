"""Command-line entry points for data-pipeline development and inspection."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from gd_affix_relevance.catalog import CatalogBundle
from gd_affix_relevance.catalog.compiler import compile_catalog_bundle
from gd_affix_relevance.domain import LocalizationEntry, locale_for_code
from gd_affix_relevance.game_localization import prepare_game_item_tags
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
from gd_affix_relevance.release_assembly import assemble_release
from gd_affix_relevance.runtime_paths import resolve_runtime_paths
from gd_affix_relevance.scoring.magnitude import (
    MagnitudeModel,
    set_active_magnitude_model,
)
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


def _print_json_summary(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2))


def _write_report(report: str, output: Path | None) -> None:
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    sys.stdout.write(report)


def _run_inventory(args: argparse.Namespace) -> int:
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
    _print_json_summary(
        {
            "records_scanned": result.records_scanned,
            "supported_records": result.supported_records,
            "parse_warning_count": result.parse_warning_count,
            "unresolved_localization_tags": result.unresolved_localization_tags,
            "active_raw_fields": len(result.fields),
            "affix_reference_statuses": len(reference_statuses),
            "output_dir": str(args.output_dir),
        }
    )
    return 0


def _run_sample(args: argparse.Namespace) -> int:
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
    _write_report(report, args.output)
    return 0


def _run_rank(args: argparse.Namespace) -> int:
    bundle = CatalogBundle.load(args.catalog_root)
    set_active_magnitude_model(MagnitudeModel.from_bundle(bundle))
    profile = load_profile(args.profile_file)
    matches = rank_affix_catalog(bundle.affixes, profile, limit=args.limit)
    candidate_pool_size = sum(
        len(affix.variants) for affix in bundle.affixes.affixes
    )
    report = format_ranked_catalog_report(
        matches,
        profile=profile,
        candidate_pool_size=candidate_pool_size,
    )
    _write_report(report, args.output)
    return 0


def _run_compile_catalog(args: argparse.Namespace) -> int:
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
    _print_json_summary(
        {
            "affixes": result.affix_count,
            "affix_variants": result.affix_variant_count,
            "skills": result.skill_count,
            "strings": result.string_count,
            "unresolved_skill_names": result.unresolved_skill_name_count,
            "unresolved_affix_records": result.unresolved_affix_record_count,
            "items": result.item_counts,
            "item_variants": result.item_variant_count,
            "magnitude_entries": result.magnitude_entry_count,
            "magnitude_properties": result.magnitude_property_count,
            "skipped_unresolved_item_records": result.unresolved_item_record_count,
            "output_dir": str(result.output_dir),
        }
    )
    return 0


def _run_generate_output(args: argparse.Namespace) -> int:
    bundle = CatalogBundle.load(args.catalog_root)
    profile = load_profile(args.profile_file)
    result = generate_rainbow_output(
        args.source_root,
        args.output_dir,
        bundle.affixes,
        profile,
        items=bundle.items,
        fallback_source_root=args.fallback_source_root,
        locale=locale_for_code(args.locale),
    )
    _print_json_summary(
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
        }
    )
    return 0


def _run_audit_items(args: argparse.Namespace) -> int:
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
    _write_report(format_item_audit_report(result), args.output)
    return 0


def _run_audit_item_tags(args: argparse.Namespace) -> int:
    result = build_item_tag_audit(
        args.data_root,
        definition_sources=tuple(args.definition_source),
        scan_sources=tuple(
            args.scan_source or ("base", "gdx1", "gdx2", "gdx3")
        ),
        comparison_root=args.comparison_root,
    )
    write_item_tag_audit(result, args.output_dir)
    _print_json_summary(
        {
            "localization_definitions": len(result.entries),
            "unique_tags": len(result.unique_tags),
            "dbr_referenced_unique_tags": len(result.referenced_unique_tags),
            "unreferenced_unique_tags": len(
                result.unique_tags - result.referenced_unique_tags
            ),
            "dbr_files_scanned": result.dbr_files_scanned,
            "output_dir": str(args.output_dir),
        }
    )
    return 0


def _run_show_runtime_paths(args: argparse.Namespace) -> int:
    locale = locale_for_code(args.locale)
    runtime_paths = resolve_runtime_paths(
        application_root=args.application_root,
        locale=locale,
    )
    _print_json_summary(runtime_paths.as_dict())
    return 0


def _run_prepare_game_localization(args: argparse.Namespace) -> int:
    locale = locale_for_code(args.locale)
    destination = args.output_dir
    if destination is None:
        destination = resolve_runtime_paths(locale=locale).tags_root
    try:
        result = prepare_game_item_tags(
            args.game_folder,
            destination,
            locale=locale,
        )
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    _print_json_summary(
        {
            "locale": result.locale.code,
            "archive_paths": [str(path) for path in result.archive_paths],
            "output_root": str(result.output_root),
            "files_written": result.files_written,
        }
    )
    return 0


def _run_assemble_release(args: argparse.Namespace) -> int:
    result = assemble_release(
        args.project_root,
        output_root=args.output_dir,
        catalog_root=args.catalog_root,
        data_root=args.data_root,
        profiles_root=args.profiles_root,
    )
    _print_json_summary(result.as_dict())
    return 0


def _run_live_check(args: argparse.Namespace) -> int:
    from gd_affix_relevance.live.compatibility import check_game_dll, find_game_dll

    game_dll = args.game_dll or find_game_dll(args.game_folder)
    report = check_game_dll(game_dll)
    print(f"Game.dll: {report.game_dll}")
    if not report.is_64_bit:
        print("  This is the 32-bit Game.dll; the hook needs the 64-bit one (x64 folder).")
    for requirement, symbol in report.matched.items():
        print(f"  ok       {requirement}  ({symbol})")
    for requirement in report.missing:
        print(f"  MISSING  {requirement}")
    print("Compatible." if report.compatible else "NOT compatible: do not inject.")
    return 0 if report.compatible else 1


def _run_live_inject(args: argparse.Namespace) -> int:
    from gd_affix_relevance.live.compatibility import check_game_dll, find_game_dll
    from gd_affix_relevance.live.injector import (
        InjectionError,
        default_hook_dll,
        find_game_processes,
        inject,
        loaded_hook_modules,
    )

    try:
        processes = find_game_processes()
        if not processes:
            print("Grim Dawn is not running.")
            return 1
        if len(processes) > 1:
            print("More than one Grim Dawn process is running; close the extras.")
            return 1
        game = processes[0]
        if not args.skip_check:
            report = check_game_dll(find_game_dll(game.executable.parent))
            if not report.compatible:
                print(
                    "Refusing to inject: Game.dll is missing "
                    + ", ".join(report.missing)
                    + ". This game version needs a hook update."
                )
                return 1
        already = loaded_hook_modules(game.pid)
        if already:
            print(
                f"A hook is already loaded ({', '.join(already)}). "
                "Restart Grim Dawn to load a new build."
            )
            return 1
        staged = inject(game.pid, args.dll or default_hook_dll())
    except InjectionError as error:
        print(f"Injection failed: {error}")
        return 1
    print(f"Injected {staged.name} into Grim Dawn (pid {game.pid}).")
    print("Run `grim-gleaner live-listen` to see what it reports.")
    return 0


def _run_live_listen(args: argparse.Namespace) -> int:
    from gd_affix_relevance.live.listener import RecordNames, listen

    names = None
    if not args.no_names:
        catalog_root = args.catalog_root or resolve_runtime_paths().catalog_root
        names = RecordNames.from_catalog(CatalogBundle.load(catalog_root))
    print(f"Listening on 127.0.0.1:{args.port}. Hover items in Grim Dawn; Ctrl+C to stop.")
    try:
        listen(lambda line: print(line, flush=True), port=args.port, names=names)
    except KeyboardInterrupt:
        pass
    return 0


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
    inventory.set_defaults(handler=_run_inventory)

    sample = subparsers.add_parser(
        "sample",
        help="generate a human-readable random sample of reachable affix variants",
    )
    sample.add_argument("--data-root", type=Path, required=True)
    _add_localization_arguments(sample)
    sample.add_argument("--count", type=int, choices=range(1, 11), default=5)
    sample.add_argument("--seed", type=int)
    sample.add_argument("--output", type=Path)
    sample.set_defaults(handler=_run_sample)

    rank = subparsers.add_parser(
        "rank",
        help="rank compiled affix variants against a saved build profile",
    )
    rank.add_argument("--catalog-root", type=Path, required=True)
    rank.add_argument("--profile-file", type=Path, required=True)
    rank.add_argument("--limit", type=_positive_int, default=20)
    rank.add_argument("--output", type=Path)
    rank.set_defaults(handler=_run_rank)

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
    catalog.add_argument(
        "--game-version",
        required=True,
        help="Grim Dawn version the extracted data came from, e.g. 1.3.1.0",
    )
    catalog.add_argument(
        "--mastery-tree-root",
        type=Path,
        help="optional curated Markdown parent/child relationship directory",
    )
    catalog.set_defaults(handler=_run_compile_catalog)

    generate = subparsers.add_parser(
        "generate-output",
        help="clone item text files and add profile-grade affix and unique markers",
    )
    generate.add_argument("--catalog-root", type=Path, required=True)
    generate.add_argument("--profile-file", type=Path, required=True)
    generate.add_argument("--source-root", type=Path, required=True)
    generate.add_argument(
        "--fallback-source-root",
        type=Path,
        help="optional bundled source used for files absent from source-root",
    )
    generate.add_argument("--output-dir", type=Path, required=True)
    generate.add_argument("--locale", choices=("en", "ru"), default="en")
    generate.set_defaults(handler=_run_generate_output)

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
    item_audit.set_defaults(handler=_run_audit_items)

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
    item_tags.set_defaults(handler=_run_audit_item_tags)

    paths = subparsers.add_parser(
        "show-runtime-paths",
        help="show the resource paths used in development or a staged release",
    )
    paths.add_argument(
        "--application-root",
        type=Path,
        help="use the packaged layout rooted at this directory",
    )
    paths.add_argument("--locale", choices=("en", "ru"), default="en")
    paths.set_defaults(handler=_run_show_runtime_paths)

    prepare_localization = subparsers.add_parser(
        "prepare-game-localization",
        help="extract required item-tag files from an installed Grim Dawn locale",
    )
    prepare_localization.add_argument("--game-folder", type=Path, required=True)
    prepare_localization.add_argument(
        "--locale",
        choices=("en", "ru"),
        default="ru",
    )
    prepare_localization.add_argument("--output-dir", type=Path)
    prepare_localization.set_defaults(handler=_run_prepare_game_localization)

    release = subparsers.add_parser(
        "assemble-release",
        help="validate and copy runtime resources into a release directory",
    )
    release.add_argument("--project-root", type=Path, default=Path.cwd())
    release.add_argument("--output-dir", type=Path)
    release.add_argument("--catalog-root", type=Path)
    release.add_argument("--data-root", type=Path)
    release.add_argument("--profiles-root", type=Path)
    release.set_defaults(handler=_run_assemble_release)

    live_check = subparsers.add_parser(
        "live-check",
        help="check that an installed Game.dll exports what the in-game hook needs",
    )
    live_source = live_check.add_mutually_exclusive_group(required=True)
    live_source.add_argument("--game-folder", type=Path)
    live_source.add_argument("--game-dll", type=Path)
    live_check.set_defaults(handler=_run_live_check)

    live_inject = subparsers.add_parser(
        "live-inject",
        help="load the gg_hook DLL into the running Grim Dawn (Windows only)",
    )
    live_inject.add_argument(
        "--dll",
        type=Path,
        help="hook DLL to load (default: build/gg_hook/Release/gg_hook.dll in the project)",
    )
    live_inject.add_argument(
        "--skip-check",
        action="store_true",
        help="inject even if Game.dll lacks the expected exports (unsafe)",
    )
    live_inject.set_defaults(handler=_run_live_inject)

    live_listen = subparsers.add_parser(
        "live-listen",
        help="print the items whose tooltips the in-game hook reports",
    )
    live_listen.add_argument("--port", type=int, default=47817)
    live_listen.add_argument("--catalog-root", type=Path)
    live_listen.add_argument(
        "--no-names",
        action="store_true",
        help="print raw record paths instead of loading the catalog",
    )
    live_listen.set_defaults(handler=_run_live_listen)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
