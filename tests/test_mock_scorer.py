from gd_affix_relevance.scoring.mock_scorer import (
    MOCK_BUILD_PROFILES,
    score_semantic_properties,
)


def test_mock_scorer_collapses_related_properties_and_explains_score() -> None:
    profile = MOCK_BUILD_PROFILES["bleed-melee"]
    score = score_semantic_properties(
        (
            "flat_bleeding_damage",
            "bleeding_damage_percent",
            "health",
            "health_percent",
            "attack_speed",
            "fire_resistance",
        ),
        profile,
    )

    assert score.weighted_match == 8
    assert score.matched_count == 3
    assert score.total_category_count == 4
    assert score.coverage_ratio == 0.75
    assert score.grade == "A"
    assert score.marker == "[A3]"


def test_mock_scorer_uses_weight_then_breadth_then_coverage_for_ranking() -> None:
    profile = MOCK_BUILD_PROFILES["bleed-melee"]
    focused = score_semantic_properties(("flat_bleeding_damage",), profile)
    diluted = score_semantic_properties(
        ("flat_bleeding_damage", "fire_resistance"), profile
    )
    health = score_semantic_properties(("health",), profile)

    assert focused.rank_key > diluted.rank_key > health.rank_key


def test_mock_scorer_uses_f_for_no_relevance() -> None:
    score = score_semantic_properties(
        ("fire_resistance",), MOCK_BUILD_PROFILES["bleed-melee"]
    )

    assert score.grade == "F"
    assert score.marker == "[F0]"
