"""Tests for skin tone detection.

Real selfies cannot be committed, so these build synthetic faces: an ellipse of a
known skin colour on a contrasting background, with dark ovals for eyes and brows
so the cascade has features to latch onto. The point is not photorealism but
checking that a face of a *known* tone classifies into the expected bucket.
"""

import io

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter

from app.services.skin_tone import (
    NoFaceDetectedError,
    _classify_depth,
    _classify_undertone,
    _srgb_to_lab,
    analyze_skin,
)
from app.models import ToneDepth, Undertone


def synthetic_face(skin_rgb: tuple[int, int, int], hair_rgb=(30, 25, 20)) -> bytes:
    """Render a crude frontal face that Haar detection reliably finds."""
    w, h = 500, 600
    img = Image.new("RGB", (w, h), (235, 235, 240))
    draw = ImageDraw.Draw(img)

    # Hair mass above and around the head, so contrast has something to measure.
    draw.ellipse((120, 60, 380, 400), fill=hair_rgb)
    # Face oval.
    draw.ellipse((150, 130, 350, 430), fill=skin_rgb)

    # Eyes, brows and mouth: Haar cascades key off these dark/light transitions.
    for cx in (205, 295):
        draw.ellipse((cx - 26, 235, cx + 26, 262), fill=(250, 250, 250))
        draw.ellipse((cx - 11, 240, cx + 11, 258), fill=(45, 35, 30))
        draw.rectangle((cx - 30, 212, cx + 30, 221), fill=hair_rgb)

    draw.ellipse((228, 330, 272, 348), fill=(150, 90, 90))

    # Slight blur: sharp synthetic edges otherwise suppress cascade detection.
    img = img.filter(ImageFilter.GaussianBlur(1.5))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


class TestClassifiers:
    """Unit tests for the pure classification helpers."""

    @pytest.mark.parametrize(
        "lightness,expected",
        [
            (90.0, ToneDepth.FAIR),
            (80.0, ToneDepth.FAIR),
            (72.0, ToneDepth.LIGHT),
            (65.0, ToneDepth.MEDIUM),
            (50.0, ToneDepth.TAN),
            (30.0, ToneDepth.DEEP),
        ],
    )
    def test_depth_buckets(self, lightness, expected):
        assert _classify_depth(lightness) == expected

    @pytest.mark.parametrize(
        "rgb,expected",
        [
            # Reference skin colours across the tonal range. These guard against
            # cutoffs drifting away from real skin, where L* spans ~20-90 and a
            # too-high threshold silently collapses several bands into "fair".
            ((246, 224, 210), ToneDepth.FAIR),
            ((240, 206, 190), ToneDepth.FAIR),
            ((228, 185, 160), ToneDepth.LIGHT),
            ((214, 172, 120), ToneDepth.LIGHT),
            ((198, 150, 110), ToneDepth.MEDIUM),
            ((176, 132, 96), ToneDepth.MEDIUM),
            ((150, 108, 76), ToneDepth.TAN),
            ((120, 84, 60), ToneDepth.DEEP),
            ((92, 62, 48), ToneDepth.DEEP),
        ],
    )
    def test_depth_calibrated_against_reference_skin(self, rgb, expected):
        lightness, _, _ = _srgb_to_lab(np.array(rgb, dtype=np.float32))
        assert _classify_depth(lightness) == expected

    def test_depth_buckets_are_all_reachable(self):
        """Every bucket must be produced by some real skin colour."""
        reference = [
            (246, 224, 210), (240, 206, 190), (228, 185, 160), (214, 172, 120),
            (198, 150, 110), (176, 132, 96), (150, 108, 76), (120, 84, 60),
            (92, 62, 48), (66, 44, 34),
        ]
        produced = {
            _classify_depth(_srgb_to_lab(np.array(rgb, dtype=np.float32))[0])
            for rgb in reference
        }
        assert produced == set(ToneDepth)

    @pytest.mark.parametrize(
        "a,b,expected",
        [
            # High yellow relative to red -> golden/warm.
            (10.0, 20.0, Undertone.WARM),
            # Red and yellow near parity -> rosy/cool.
            (18.0, 18.0, Undertone.COOL),
            (12.0, 16.0, Undertone.NEUTRAL),
        ],
    )
    def test_undertone_from_ratio(self, a, b, expected):
        assert _classify_undertone(a, b) == expected

    def test_undertone_refuses_to_guess_on_degenerate_sample(self):
        # Non-positive a* is not real skin; must not claim a temperature bias.
        assert _classify_undertone(-3.0, 20.0) == Undertone.NEUTRAL


class TestAnalyzeSkin:
    def test_rejects_image_with_no_face(self):
        blank = Image.new("RGB", (400, 400), (120, 120, 120))
        buf = io.BytesIO()
        blank.save(buf, format="JPEG")
        with pytest.raises(NoFaceDetectedError):
            analyze_skin(buf.getvalue())

    def test_fair_skin_classifies_lighter_than_deep_skin(self):
        """Ordering is the real invariant: relative depth must be monotonic."""
        fair = analyze_skin(synthetic_face((242, 214, 196)))
        deep = analyze_skin(synthetic_face((92, 62, 48)))
        assert fair.lightness > deep.lightness
        # Compare via the ordered bucket list rather than the enum values.
        order = list(ToneDepth)
        assert order.index(fair.tone_depth) < order.index(deep.tone_depth)

    def test_golden_skin_reads_warm_and_rosy_skin_reads_cool(self):
        # Strongly golden: much more yellow than red.
        warm = analyze_skin(synthetic_face((226, 186, 130)))
        # Strongly rosy: red and yellow close together.
        cool = analyze_skin(synthetic_face((222, 178, 176)))
        assert warm.undertone == Undertone.WARM
        assert cool.undertone == Undertone.COOL

    def test_returns_wellformed_analysis(self):
        result = analyze_skin(synthetic_face((205, 160, 125)))
        assert result.skin_hex.startswith("#") and len(result.skin_hex) == 7
        assert 0 <= result.lightness <= 100
        assert 0 <= result.confidence <= 1
        assert result.season is not None

    def test_dark_hair_on_fair_skin_yields_high_contrast(self):
        high = analyze_skin(synthetic_face((240, 212, 194), hair_rgb=(25, 20, 18)))
        low = analyze_skin(synthetic_face((240, 212, 194), hair_rgb=(215, 195, 175)))
        assert high.contrast > low.contrast

    def test_handles_png_and_rgba_input(self):
        rgba = Image.open(io.BytesIO(synthetic_face((205, 160, 125)))).convert("RGBA")
        buf = io.BytesIO()
        rgba.save(buf, format="PNG")
        # Must not raise on an alpha channel.
        assert analyze_skin(buf.getvalue()).confidence > 0
