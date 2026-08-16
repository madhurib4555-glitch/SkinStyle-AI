"""Clothing colour recommendation engine.

Scores a fixed palette against a skin analysis and returns the best matches with
a rationale written for that specific user. Scoring is deliberately rule-based
and inspectable: every point is traceable to a colour property, which matters
because the app's whole claim is that it explains *why* a colour works.
"""

from dataclasses import dataclass

from app.models import (
    ColorRecommendation,
    ColorToAvoid,
    Season,
    SkinAnalysis,
    ToneDepth,
    Undertone,
)


@dataclass(frozen=True)
class Swatch:
    name: str
    hex: str
    # Warm (+1) through cool (-1). Where the colour sits on the temperature axis.
    temperature: float
    # Perceptual lightness 0-1, eyeballed against the rendered swatch.
    value: float
    # Chroma 0-1: 0 is a neutral grey, 1 is fully saturated.
    chroma: float
    seasons: frozenset[Season]


# A compact wearable palette. Every entry is a colour that actually shows up in
# apparel, which keeps recommendations shoppable rather than theoretical.
PALETTE: tuple[Swatch, ...] = (
    Swatch("Emerald Green", "#0f7b6c", -0.15, 0.42, 0.75, frozenset({Season.WINTER, Season.SPRING})),
    Swatch("Olive Green", "#6b7042", 0.65, 0.44, 0.45, frozenset({Season.AUTUMN, Season.SPRING})),
    Swatch("Navy Blue", "#1f2a52", -0.45, 0.20, 0.50, frozenset({Season.WINTER, Season.SUMMER})),
    Swatch("Cobalt Blue", "#2f5fd0", -0.35, 0.45, 0.80, frozenset({Season.WINTER, Season.SPRING})),
    Swatch("Dusty Teal", "#4a8a92", -0.10, 0.52, 0.40, frozenset({Season.SUMMER, Season.AUTUMN})),
    Swatch("Burgundy", "#6d2233", 0.30, 0.24, 0.55, frozenset({Season.AUTUMN, Season.WINTER})),
    Swatch("Rust", "#a9542a", 0.85, 0.45, 0.65, frozenset({Season.AUTUMN})),
    Swatch("Terracotta", "#c1694f", 0.80, 0.55, 0.55, frozenset({Season.AUTUMN, Season.SPRING})),
    Swatch("Coral", "#f2795f", 0.70, 0.65, 0.75, frozenset({Season.SPRING})),
    Swatch("Blush Pink", "#e6a9ab", 0.15, 0.72, 0.35, frozenset({Season.SUMMER, Season.SPRING})),
    Swatch("Fuchsia", "#b5237c", -0.25, 0.40, 0.85, frozenset({Season.WINTER})),
    Swatch("Lavender", "#a89ccc", -0.30, 0.66, 0.35, frozenset({Season.SUMMER})),
    Swatch("Soft Grey", "#9aa0a6", -0.05, 0.63, 0.05, frozenset({Season.SUMMER, Season.WINTER})),
    Swatch("Charcoal", "#36393d", -0.05, 0.24, 0.06, frozenset({Season.WINTER, Season.SUMMER})),
    Swatch("Cream", "#f0e4cd", 0.55, 0.90, 0.20, frozenset({Season.AUTUMN, Season.SPRING})),
    Swatch("Camel", "#b8925f", 0.75, 0.60, 0.45, frozenset({Season.AUTUMN, Season.SPRING})),
    Swatch("Mustard", "#c8a02c", 0.85, 0.65, 0.70, frozenset({Season.AUTUMN, Season.SPRING})),
    Swatch("Crisp White", "#f8f9fa", 0.00, 0.97, 0.02, frozenset({Season.WINTER, Season.SUMMER})),
    Swatch("Icy Blue", "#bcd6e8", -0.40, 0.84, 0.20, frozenset({Season.WINTER, Season.SUMMER})),
    Swatch("Plum", "#5b2c5e", -0.20, 0.28, 0.50, frozenset({Season.WINTER, Season.AUTUMN})),
)

# Depth buckets mapped to the garment lightness that best preserves separation
# between face and clothing. Fair skin needs mid/deep garments to avoid washing
# out; deep skin has room for both extremes but gains most from luminous colour.
_IDEAL_VALUE: dict[ToneDepth, float] = {
    ToneDepth.FAIR: 0.42,
    ToneDepth.LIGHT: 0.48,
    ToneDepth.MEDIUM: 0.55,
    ToneDepth.TAN: 0.58,
    ToneDepth.DEEP: 0.62,
}

_UNDERTONE_TARGET: dict[Undertone, float] = {
    Undertone.WARM: 0.65,
    Undertone.COOL: -0.40,
    Undertone.NEUTRAL: 0.10,
}

_SEASON_LABEL: dict[Season, str] = {
    Season.SPRING: "bright and warm",
    Season.SUMMER: "soft and cool",
    Season.AUTUMN: "rich and warm",
    Season.WINTER: "bold and cool",
}


def _score(swatch: Swatch, analysis: SkinAnalysis) -> int:
    """Fit score 0-100, summed from four independent colour-theory factors."""

    # 1. Undertone agreement, 0-40. The dominant factor: a warm colour on cool
    #    skin is the single most visible mismatch.
    target = _UNDERTONE_TARGET[analysis.undertone]
    # Max distance on a -1..1 axis is 2.0, so normalise against that.
    temp_fit = 1.0 - abs(swatch.temperature - target) / 2.0
    score = 40.0 * temp_fit

    # 2. Depth contrast, 0-25. Rewards garments that sit near the ideal
    #    lightness for this skin depth.
    ideal = _IDEAL_VALUE[analysis.tone_depth]
    score += 25.0 * (1.0 - min(abs(swatch.value - ideal) / 0.6, 1.0))

    # 3. Season membership, 0-20. Encodes the classic palettes directly.
    if analysis.season in swatch.seasons:
        score += 20.0
    else:
        # Adjacent seasons share a temperature axis, so a near miss still reads
        # better than an opposite-axis colour.
        adjacent = {
            Season.SPRING: {Season.AUTUMN, Season.WINTER},
            Season.AUTUMN: {Season.SPRING, Season.WINTER},
            Season.SUMMER: {Season.WINTER, Season.AUTUMN},
            Season.WINTER: {Season.SUMMER, Season.SPRING},
        }[analysis.season]
        if swatch.seasons & adjacent:
            score += 8.0

    # 4. Chroma against facial contrast, 0-15. High-contrast faces carry
    #    saturated colour; low-contrast faces are overwhelmed by it.
    contrast_norm = min(analysis.contrast / 40.0, 1.0)
    score += 15.0 * (1.0 - abs(swatch.chroma - contrast_norm))

    return max(0, min(100, round(score)))


def _rationale(swatch: Swatch, analysis: SkinAnalysis) -> str:
    """One sentence tying this colour to this user's measured attributes."""
    undertone = analysis.undertone.value
    depth = analysis.tone_depth.value

    if swatch.chroma < 0.12:
        # Neutrals work structurally rather than by temperature agreement.
        anchor = (
            f"{swatch.name} is a clean neutral that frames your {depth} complexion "
            f"without competing with it"
        )
    elif abs(swatch.temperature - _UNDERTONE_TARGET[analysis.undertone]) < 0.35:
        anchor = (
            f"{swatch.name} shares the {undertone} cast of your skin, so it reads as "
            f"an extension of your natural colouring"
        )
    else:
        anchor = (
            f"{swatch.name} sits just off your {undertone} undertone, which lifts your "
            f"complexion by contrast rather than by matching it"
        )

    ideal = _IDEAL_VALUE[analysis.tone_depth]
    if swatch.value < ideal - 0.15:
        depth_note = "and its depth gives your face clear separation from the garment"
    elif swatch.value > ideal + 0.15:
        depth_note = "and its lightness keeps the overall look open and fresh"
    else:
        depth_note = f"and its mid-depth balances your {depth} skin evenly"

    if analysis.contrast >= 22 and swatch.chroma >= 0.6:
        contrast_note = ". Your naturally high contrast carries this saturation well."
    elif analysis.contrast < 22 and swatch.chroma <= 0.4:
        contrast_note = ". The muted saturation suits your softer natural contrast."
    else:
        contrast_note = "."

    return f"{anchor}, {depth_note}{contrast_note}"


def _avoid_reason(swatch: Swatch, analysis: SkinAnalysis) -> str:
    undertone = analysis.undertone.value
    opposite = "cool" if analysis.undertone is Undertone.WARM else "warm"

    if abs(swatch.temperature - _UNDERTONE_TARGET[analysis.undertone]) > 0.7:
        return (
            f"Leans {opposite} against your {undertone} undertone, which tends to "
            f"flatten your complexion and emphasise shadow around the jaw."
        )
    ideal = _IDEAL_VALUE[analysis.tone_depth]
    if abs(swatch.value - ideal) > 0.3:
        direction = "close to" if swatch.value > ideal else "far below"
        return (
            f"Its lightness sits {direction} your own skin depth, so the garment and "
            f"your face blur together instead of framing each other."
        )
    return (
        f"Its saturation works against your natural contrast level, drawing the eye "
        f"to the fabric rather than your face."
    )


def recommend(
    analysis: SkinAnalysis, top_n: int = 6, avoid_n: int = 3
) -> tuple[list[ColorRecommendation], list[ColorToAvoid]]:
    """Rank the palette for this analysis and return best and worst matches."""
    ranked = sorted(
        PALETTE, key=lambda s: (_score(s, analysis), s.name), reverse=True
    )

    best = [
        ColorRecommendation(
            name=s.name,
            hex=s.hex,
            rationale=_rationale(s, analysis),
            score=_score(s, analysis),
        )
        for s in ranked[:top_n]
    ]

    worst = [
        ColorToAvoid(name=s.name, hex=s.hex, reason=_avoid_reason(s, analysis))
        for s in reversed(ranked[-avoid_n:])
    ]

    return best, worst


def season_summary(analysis: SkinAnalysis) -> str:
    """Headline sentence describing the user's palette, for the results header."""
    return (
        f"Your colouring reads as {_SEASON_LABEL[analysis.season]} "
        f"({analysis.season.value.title()}): {analysis.tone_depth.value} depth with a "
        f"{analysis.undertone.value} undertone."
    )
