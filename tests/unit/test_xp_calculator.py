"""Unit tests for XP calculator — pure math, no DB needed."""

import pytest

from platform.experience.calculator import (
    BASE_XP,
    XPSource,
    calculate_xp,
    evaluate_tier,
    level_from_xp,
    quality_multiplier,
    xp_for_level,
)


class TestQualityMultiplier:
    def test_exceptional(self):
        assert quality_multiplier(0.95) == 1.5
        assert quality_multiplier(0.99) == 1.5

    def test_strong(self):
        assert quality_multiplier(0.85) == 1.2
        assert quality_multiplier(0.94) == 1.2

    def test_standard(self):
        assert quality_multiplier(0.70) == 1.0
        assert quality_multiplier(0.84) == 1.0

    def test_marginal(self):
        assert quality_multiplier(0.69) == 0.8
        assert quality_multiplier(0.0) == 0.8


class TestXPForLevel:
    def test_level_1_is_zero(self):
        assert xp_for_level(1) == 0

    def test_level_0_is_zero(self):
        assert xp_for_level(0) == 0

    def test_monotonically_increasing(self):
        prev = 0
        for level in range(2, 100):
            current = xp_for_level(level)
            assert current > prev, f"Level {level} ({current}) not > Level {level-1} ({prev})"
            prev = current

    def test_level_10_approximate(self):
        xp = xp_for_level(10)
        assert 5_000 <= xp <= 15_000

    def test_level_50_approximate(self):
        xp = xp_for_level(50)
        assert 100_000 <= xp <= 500_000


class TestLevelFromXP:
    def test_zero_xp_is_level_1(self):
        assert level_from_xp(0) == 1

    def test_exact_threshold(self):
        xp_at_10 = xp_for_level(10)
        assert level_from_xp(xp_at_10) == 10

    def test_just_below_threshold(self):
        xp_at_10 = xp_for_level(10)
        assert level_from_xp(xp_at_10 - 1) == 9

    def test_roundtrip(self):
        for level in [1, 5, 10, 20, 50]:
            xp = xp_for_level(level)
            assert level_from_xp(xp) == level

    def test_large_xp(self):
        level = level_from_xp(10_000_000)
        assert level > 50


class TestCalculateXP:
    def test_basic_claim_verified(self):
        award = calculate_xp(
            source=XPSource.CLAIM_VERIFIED,
            domain="mathematics",
            verification_score=0.90,
            prestige_bonus=1.0,
            role_category="theory",
        )
        assert award.base == 100
        assert award.quality_mult == 1.2
        assert award.domain_mult == 1.3
        assert award.prestige_mult == 1.0
        assert award.total == int(100 * 1.2 * 1.3 * 1.0)  # 156

    def test_prestige_bonus_increases_total(self):
        normal = calculate_xp(
            source=XPSource.CLAIM_VERIFIED,
            domain="ml_ai",
            verification_score=0.80,
            prestige_bonus=1.0,
            role_category="execution",
        )
        prestiged = calculate_xp(
            source=XPSource.CLAIM_VERIFIED,
            domain="ml_ai",
            verification_score=0.80,
            prestige_bonus=1.15,
            role_category="execution",
        )
        assert prestiged.total > normal.total

    def test_no_domain(self):
        award = calculate_xp(
            source=XPSource.REVIEW_ACCEPTED,
            domain=None,
            verification_score=0.0,
            prestige_bonus=1.0,
            role_category="review",
        )
        assert award.domain_mult == 1.0
        assert award.total == 40

    def test_challenge_won_high_xp(self):
        award = calculate_xp(
            source=XPSource.CHALLENGE_WON,
            domain="computational_biology",
            verification_score=0.0,
            prestige_bonus=1.0,
            role_category="execution",
        )
        assert award.total == int(500 * 1.0 * 1.2 * 1.0)  # 600

    def test_frozen_dataclass(self):
        award = calculate_xp(
            source=XPSource.CLAIM_CITED,
            domain="ml_ai",
            verification_score=0.0,
            prestige_bonus=1.0,
            role_category="theory",
        )
        with pytest.raises(AttributeError):
            award.total = 999


class TestEvaluateTier:
    def test_novice(self):
        tier = evaluate_tier(
            max_domain_level=0,
            second_domain_level=0,
            claims_verified=0,
            challenge_medals=0,
            gold_medals=0,
            solo_golds=0,
            success_rate=0.0,
            max_citation_count=0,
        )
        assert tier == "novice"

    def test_contributor(self):
        tier = evaluate_tier(
            max_domain_level=5,
            second_domain_level=0,
            claims_verified=1,
            challenge_medals=0,
            gold_medals=0,
            solo_golds=0,
            success_rate=0.8,
            max_citation_count=0,
        )
        assert tier == "contributor"

    def test_specialist(self):
        tier = evaluate_tier(
            max_domain_level=15,
            second_domain_level=0,
            claims_verified=10,
            challenge_medals=0,
            gold_medals=0,
            solo_golds=0,
            success_rate=0.8,
            max_citation_count=0,
        )
        assert tier == "specialist"

    def test_expert_single_domain(self):
        tier = evaluate_tier(
            max_domain_level=25,
            second_domain_level=0,
            claims_verified=50,
            challenge_medals=1,
            gold_medals=0,
            solo_golds=0,
            success_rate=0.8,
            max_citation_count=0,
        )
        assert tier == "expert"

    def test_expert_dual_domain(self):
        tier = evaluate_tier(
            max_domain_level=15,
            second_domain_level=15,
            claims_verified=50,
            challenge_medals=1,
            gold_medals=0,
            solo_golds=0,
            success_rate=0.8,
            max_citation_count=0,
        )
        assert tier == "expert"

    def test_master(self):
        tier = evaluate_tier(
            max_domain_level=35,
            second_domain_level=0,
            claims_verified=100,
            challenge_medals=3,
            gold_medals=1,
            solo_golds=0,
            success_rate=0.85,
            max_citation_count=0,
        )
        assert tier == "master"

    def test_grandmaster(self):
        tier = evaluate_tier(
            max_domain_level=50,
            second_domain_level=0,
            claims_verified=200,
            challenge_medals=10,
            gold_medals=5,
            solo_golds=1,
            success_rate=0.90,
            max_citation_count=10,
        )
        assert tier == "grandmaster"

    def test_grandmaster_missing_citations(self):
        """Should fall to master if citation requirement not met."""
        tier = evaluate_tier(
            max_domain_level=50,
            second_domain_level=0,
            claims_verified=200,
            challenge_medals=10,
            gold_medals=5,
            solo_golds=1,
            success_rate=0.90,
            max_citation_count=5,  # needs 10
        )
        assert tier == "master"
