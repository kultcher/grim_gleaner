"""Legacy pre-catalog scorer retained for historical comparison tests."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from gd_affix_relevance.normalization.sample_report import AffixSampleCandidate


@dataclass(frozen=True, slots=True)
class MockBuildProfile:
    profile_id: str
    display_name: str
    weights: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class MockRelevanceScore:
    grade: str
    weighted_match: int
    matched_count: int
    total_category_count: int
    coverage_ratio: float
    matched_categories: tuple[str, ...]

    @property
    def marker(self) -> str:
        return f"[{self.grade}{self.matched_count}]"

    @property
    def rank_key(self) -> tuple[float, ...]:
        return (
            float(self.weighted_match),
            float(self.matched_count),
            self.coverage_ratio,
        )


PROPERTY_CATEGORY_ALIASES = {
    "attack_speed": "attack_speed",
    "bleeding_damage_percent": "bleeding_damage",
    "defensive_ability": "defensive_ability",
    "defensive_ability_percent": "defensive_ability",
    "flat_bleeding_damage": "bleeding_damage",
    "health": "health",
    "health_percent": "health",
    "movement_speed": "movement_speed",
    "offensive_ability": "offensive_ability",
    "offensive_ability_percent": "offensive_ability",
    "physical_resistance": "physical_resistance",
}

CATEGORY_LABELS = {
    "attack_speed": "Attack Speed",
    "bleeding_damage": "Bleeding Damage",
    "defensive_ability": "Defensive Ability",
    "health": "Health",
    "movement_speed": "Movement Speed",
    "offensive_ability": "Offensive Ability",
    "physical_resistance": "Physical Resistance",
}

MOCK_BUILD_PROFILES = {
    "bleed-melee": MockBuildProfile(
        profile_id="bleed-melee",
        display_name="Bleed Melee (mock)",
        weights={
            "bleeding_damage": 4,
            "physical_resistance": 4,
            "health": 2,
            "defensive_ability": 2,
            "attack_speed": 2,
            "offensive_ability": 1,
            "movement_speed": 1,
        },
    )
}


def score_semantic_properties(
    semantic_properties: tuple[str, ...], profile: MockBuildProfile
) -> MockRelevanceScore:
    """Score category presence only; numeric roll magnitude is intentionally ignored."""

    normalized_categories = {
        PROPERTY_CATEGORY_ALIASES.get(property_id, property_id)
        for property_id in semantic_properties
    }
    matched_categories = tuple(
        sorted(
            (
                category
                for category in normalized_categories
                if profile.weights.get(category, 0) > 0
            ),
            key=lambda category: (-profile.weights[category], category),
        )
    )
    weighted_match = sum(profile.weights[category] for category in matched_categories)
    matched_count = len(matched_categories)
    total_category_count = len(normalized_categories)
    coverage_ratio = (
        matched_count / total_category_count if total_category_count else 0.0
    )
    return MockRelevanceScore(
        grade=_grade_for_weighted_match(weighted_match),
        weighted_match=weighted_match,
        matched_count=matched_count,
        total_category_count=total_category_count,
        coverage_ratio=coverage_ratio,
        matched_categories=matched_categories,
    )


def rank_key_for_profile(
    profile: MockBuildProfile,
) -> Callable[[tuple[str, ...]], tuple[float, ...]]:
    """Return the lightweight key used before humanizing only the winners."""

    def rank_key(semantic_properties: tuple[str, ...]) -> tuple[float, ...]:
        return score_semantic_properties(semantic_properties, profile).rank_key

    return rank_key


def format_ranked_affix_report(
    candidates: tuple[AffixSampleCandidate, ...],
    *,
    profile: MockBuildProfile,
    candidate_pool_size: int,
) -> str:
    """Render top-ranked variants with the facts behind every grade."""

    lines = [
        f"Grim Gleaner ranked affixes — {profile.display_name}",
        f"Candidate variants graded: {candidate_pool_size}",
        f"Top variants shown: {len(candidates)}",
        "Weights: "
        + "; ".join(
            f"{CATEGORY_LABELS.get(category, category)}={weight}"
            for category, weight in sorted(
                profile.weights.items(), key=lambda item: (-item[1], item[0])
            )
        ),
    ]

    for index, candidate in enumerate(candidates, start=1):
        score = score_semantic_properties(candidate.semantic_properties, profile)
        matched = "; ".join(
            f"{CATEGORY_LABELS.get(category, category)} ({profile.weights[category]})"
            for category in score.matched_categories
        )
        lines.extend(
            [
                "",
                f"{index}. {score.marker} {candidate.display_name}",
                f"   Type: {candidate.affix_kind.title()}",
                f"   Gear slot: {candidate.gear_slot}",
                f"   Weighted match: {score.weighted_match}",
                "   Coverage: "
                f"{score.matched_count}/{score.total_category_count} "
                f"({score.coverage_ratio:.0%})",
                f"   Matched: {matched or 'None'}",
            ]
        )
        if candidate.level_requirements:
            lines.append(
                "   Level requirement(s) for this stat layout: "
                + ", ".join(map(str, candidate.level_requirements))
            )
        if candidate.stat_layout_count > 1:
            lines.append(
                "   Distinct stat layouts for this affix/slot: "
                f"{candidate.stat_layout_count}"
            )
        lines.append("   All stats:")
        lines.extend(f"   - {stat_line}" for stat_line in candidate.stat_lines)
        lines.extend(
            [
                f"   Localization: {candidate.localization_tag}",
                f"   Representative: {candidate.representative_source}",
            ]
        )
    return "\n".join(lines) + "\n"


def _grade_for_weighted_match(weighted_match: int) -> str:
    if weighted_match >= 10:
        return "S"
    if weighted_match >= 7:
        return "A"
    if weighted_match >= 4:
        return "B"
    if weighted_match >= 2:
        return "C"
    if weighted_match >= 1:
        return "D"
    return "—"
