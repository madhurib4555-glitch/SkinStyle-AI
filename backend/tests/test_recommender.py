"""Tests for the colour recommendation engine."""

import pytest

from app.models import Season, SkinAnalysis, ToneDepth, Undertone
from app.services.recommender import PALETTE, recommend, season_summary


def analysis(
    depth=ToneDepth.MEDIUM,
    undertone=Undertone.WARM,
    season=Season.AUTUMN,
    contrast=25.0,
) -> SkinAnalysis:
    return SkinAnalysis(
        tone_depth=depth,
        undertone=undertone,
        season=season,
        skin_hex="#c8a080",
        lightness=58.0,
        contrast=contrast,
        confidence=0.9,
    )


class TestRecommend:
    def test_returns_requested_counts(self):
        best, avoid = recommend(analysis(), top_n=6, avoid_n=3)
        assert len(best) == 6
        assert len(avoid) == 3

    def test_results_are_ordered_by_descending_score(self):
        best, _ = recommend(analysis())
        scores = [r.score for r in best]
        assert scores == sorted(scores, reverse=True)

    def test_recommended_and_avoided_sets_do_not_overlap(self):
        best, avoid = recommend(analysis())
        assert not {r.name for r in best} & {a.name for a in avoid}

    def test_warm_undertone_favours_warm_colours(self):
        best, _ = recommend(analysis(undertone=Undertone.WARM, season=Season.AUTUMN))
        names = {r.name for r in best}
        # At least one unmistakably warm colour should surface.
        assert names & {"Rust", "Camel", "Terracotta", "Mustard", "Olive Green", "Cream"}

    def test_cool_undertone_favours_cool_colours(self):
        best, _ = recommend(analysis(undertone=Undertone.COOL, season=Season.WINTER))
        names = {r.name for r in best}
        assert names & {"Navy Blue", "Cobalt Blue", "Icy Blue", "Fuchsia", "Plum", "Charcoal"}

    def test_warm_and_cool_produce_different_advice(self):
        warm, _ = recommend(analysis(undertone=Undertone.WARM, season=Season.AUTUMN))
        cool, _ = recommend(analysis(undertone=Undertone.COOL, season=Season.WINTER))
        # The engine must actually discriminate, not return one fixed list.
        assert {r.name for r in warm} != {r.name for r in cool}

    def test_scores_stay_in_range_across_every_profile(self):
        """Exhaustive sweep: no profile may produce an out-of-band score."""
        for depth in ToneDepth:
            for undertone in Undertone:
                for season in Season:
                    for contrast in (5.0, 25.0, 60.0):
                        best, avoid = recommend(
                            analysis(depth, undertone, season, contrast)
                        )
                        assert all(0 <= r.score <= 100 for r in best)
                        assert len(best) == 6 and len(avoid) == 3

    def test_every_recommendation_has_a_nonempty_rationale(self):
        best, avoid = recommend(analysis())
        assert all(len(r.rationale) > 20 for r in best)
        assert all(len(a.reason) > 20 for a in avoid)

    def test_rationale_references_the_colour_name(self):
        best, _ = recommend(analysis())
        assert all(r.name in r.rationale for r in best)

    def test_palette_hexes_are_wellformed(self):
        for swatch in PALETTE:
            assert len(swatch.hex) == 7 and swatch.hex[0] == "#"
            int(swatch.hex[1:], 16)  # Raises if not valid hex.

    def test_palette_properties_are_in_range(self):
        for s in PALETTE:
            assert -1.0 <= s.temperature <= 1.0
            assert 0.0 <= s.value <= 1.0
            assert 0.0 <= s.chroma <= 1.0
            assert s.seasons, f"{s.name} must belong to at least one season"


class TestSeasonSummary:
    def test_mentions_season_depth_and_undertone(self):
        text = season_summary(analysis(undertone=Undertone.WARM, season=Season.AUTUMN))
        assert "Autumn" in text
        assert "warm" in text
        assert "medium" in text
