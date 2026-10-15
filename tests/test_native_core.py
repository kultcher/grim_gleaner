"""C++ live core (native/gg_hook/src/stat_core.cpp) must match the Python
reference exactly. Compiled with the host C++ compiler; skipped without one."""

from __future__ import annotations

import random
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from gd_affix_relevance.catalog import CatalogBundle
from gd_affix_relevance.live.grade_table import build_grade_table
from gd_affix_relevance.live.scoring import (
    LiveCatalog,
    LootFilterSettings,
    roll_quality,
    score_live_item,
    tooltip_label,
)
from gd_affix_relevance.live.stat_lines import StatLineIndex, line_key, read_templates
from gd_affix_relevance.profile_store import load_profile
from gd_affix_relevance.scoring.magnitude import MagnitudeModel, set_active_magnitude_model

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NATIVE = PROJECT_ROOT / "native" / "gg_hook"
TEMPLATES = Path(__file__).parent / "fixtures" / "live" / "tags_ui_sample.txt"
COMPILER = shutil.which("g++") or shutil.which("clang++")

pytestmark = pytest.mark.skipif(COMPILER is None, reason="no host C++ compiler")


@pytest.fixture(scope="module")
def harness(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("native") / "core_harness"
    subprocess.run(
        [COMPILER, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
         str(NATIVE / "src" / "stat_core.cpp"), str(NATIVE / "tests" / "core_harness.cpp"),
         "-o", str(output)],
        check=True,
    )
    return output


def _fill(template: str, rng: random.Random) -> str:
    """Render a template roughly the way the game does."""

    def value(match: re.Match[str]) -> str:
        spec = match.group(0)
        number = rng.choice([1, 3, 7, 12, 25, 39, 61, 128, 911])
        if "t0" in spec or "t1" in spec:
            return rng.choice([str(number), f"{number}-{number * 2}"])
        if "+" in spec:
            return f"+{number}"
        return str(number)

    return re.sub(r"\{%[^}]*\}", value, template)


def _cases(bundle: CatalogBundle, rng: random.Random, templates: dict[str, str]) -> list[dict]:
    bases = [v.record_path for i in bundle.items.equipment for v in i.variants]
    affixes = {"prefix": [], "suffix": []}
    for affix in bundle.affixes.affixes:
        affixes[affix.kind].extend(tier.record_path for tier in affix.tiers)
    stat_templates = [t for tag, t in templates.items() if "Range" not in tag]
    cases = []
    for index in range(300):
        lines = [(5, "Some Item Name"), (66, "Rare Pants")]
        if index % 7 == 0:
            lines += [(70, "Bonus to All Pets:"), (71, _fill(rng.choice(stat_templates), rng))]
        for _ in range(rng.randint(0, 8)):
            text = _fill(rng.choice(stat_templates), rng)
            if rng.random() < 0.7:
                low = rng.randint(1, 50)
                text += f" ^H[{low}-{low + rng.randint(0, 30)}]"
            lines.append((rng.choice([18, 19, 19, 19, 71]), text))
        lines.append((20, "Required Player Level: 70"))
        cases.append(
            {
                "records": (
                    rng.choice(bases).upper() if index % 11 == 0 else rng.choice(bases),
                    rng.choice(affixes["prefix"]) if rng.random() < 0.6 else "",
                    rng.choice(affixes["suffix"]) if rng.random() < 0.6 else "",
                ),
                "lines": lines,
            }
        )
    cases.append({"records": ("records/not/in/catalog.dbr", "", ""), "lines": []})
    return cases


def test_native_core_matches_python(harness: Path, tmp_path: Path) -> None:
    bundle = CatalogBundle.load(PROJECT_ROOT / "artifacts" / "catalog")
    profile = load_profile(PROJECT_ROOT / "artifacts" / "profiles" / "examples" / "Fire_Burn_Shieldbreaker.json")
    profile.set_magnitude_influence("normal")
    set_active_magnitude_model(MagnitudeModel.from_bundle(bundle))
    try:
        index = StatLineIndex.from_tags_file(TEMPLATES)
        catalog = LiveCatalog.build(bundle, profile)
        filter_settings = LootFilterSettings(True, {"magic": "B", "rare": "C", "common": "A"})
        table = build_grade_table(catalog, profile, index, filter_settings)
        (tmp_path / "table.txt").write_text(table.text, encoding="utf-8")

        rng = random.Random(1234)
        templates = read_templates(TEMPLATES)
        cases = _cases(bundle, rng, templates)
        key_samples = [_fill(t, rng) + rng.choice(["", " [3-9]", " ^H[12]"]) for t in templates.values()]
        key_samples += ["+39% ^EElemental Damage [29-40]", "45 ^EBleeding Damage over 3 Seconds",
                        "{^E}+12% {^Y}Fire{^E} Damage ", "20% Chance of 30-50 Fire Damage",
                        "Bonus to All Pets:", "  (+5)  to   X  "]
        rows = [f"key\t{text}" for text in key_samples]
        for case in cases:
            rows.append("case\t" + "\t".join(case["records"]))
            rows.extend(f"l\t{cls}\t{text}" for cls, text in case["lines"])
            rows.append("end")
        (tmp_path / "cases.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")

        output = subprocess.run(
            [str(harness), str(tmp_path / "table.txt"), str(tmp_path / "cases.txt")],
            check=True, capture_output=True, text=True, encoding="utf-8",
        ).stdout.splitlines()
        assert output[0] == f"table\t{table.table_id}"
        keys = [line.split("\t", 1)[1] for line in output if line.startswith("key\t")]
        assert keys == [line_key(text) for text in key_samples]

        items = [line.split("\t")[1:] for line in output if line.startswith("item\t")]
        assert len(items) == len(cases)
        for case, native in zip(cases, items):
            relevance = score_live_item(catalog, profile, *case["records"])
            quality = roll_quality(index, profile, case["lines"])
            grade, score, matched, total, rarity, rq, label, hide = native
            context = f"{case['records']} {case['lines']}"
            assert grade == relevance.score.grade, context
            assert float(score) == pytest.approx(relevance.score.effective_score, abs=1e-6), context
            assert (int(matched), int(total)) == (
                relevance.score.matched_count, relevance.score.total_category_count), context
            assert rarity == relevance.rarity_class, context
            if quality.value is None:
                assert rq == "-", context
            else:
                assert float(rq) == pytest.approx(quality.value, abs=1e-9), context
            assert label == tooltip_label(relevance.score.grade, quality.value), context
            assert (hide == "1") == filter_settings.should_hide(grade, relevance.rarity_class), context
        assert sum(1 for item in items if item[5] != "-") > 50  # roll quality exercised
        assert sum(1 for item in items if item[7] == "1") > 0  # filter exercised
    finally:
        set_active_magnitude_model(None)
