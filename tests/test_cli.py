from gd_affix_relevance.cli import build_parser


def test_every_cli_command_has_a_dispatch_handler() -> None:
    parser = build_parser()
    command_arguments = (
        ("inventory", "--data-root", "data", "--output-dir", "out"),
        (
            "sample",
            "--data-root",
            "data",
            "--localization-root",
            "text",
        ),
        ("rank", "--catalog-root", "catalog", "--profile-file", "profile.json"),
        (
            "compile-catalog",
            "--data-root",
            "data",
            "--localization-root",
            "text",
            "--output-dir",
            "out",
        ),
        (
            "generate-output",
            "--catalog-root",
            "catalog",
            "--profile-file",
            "profile.json",
            "--source-root",
            "text",
            "--output-dir",
            "out",
            "--locale",
            "ru",
        ),
        ("audit-items", "--data-root", "data"),
        (
            "audit-item-tags",
            "--data-root",
            "data",
            "--definition-source",
            "base",
            "--output-dir",
            "out",
        ),
        ("show-runtime-paths",),
        (
            "prepare-game-localization",
            "--game-folder",
            "game",
            "--locale",
            "ru",
        ),
        ("assemble-release",),
    )

    for arguments in command_arguments:
        parsed = parser.parse_args(arguments)
        assert callable(parsed.handler)
