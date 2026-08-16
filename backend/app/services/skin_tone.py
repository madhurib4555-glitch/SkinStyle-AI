"""Skin tone and undertone detection from a selfie.

Perfect Corp's Skin AI returns dermatological concern scores (wrinkles, spots,
redness, acne, texture...) and does *not* classify tone or undertone. This module
supplies that missing piece locally: it locates the face, samples skin pixels
while rejecting non-skin ones (eyes, brows, lips, shadow, specular highlights),
and converts the mean colour into a depth bucket plus a warm/cool/neutral
undertone.

Everything here runs on CPU in well under a second per image, so it stays on the
request path rather than going through the task queue.
"""

import io
import math

import cv2
import numpy as np
from PIL import Image

from app.models import Season, SkinAnalysis, ToneDepth, Undertone

# Haar cascade ships with opencv-python; no model download needed at deploy time.
_FACE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# Skin pixels in YCrCb fall in a tight, illumination-tolerant band. These bounds
# are the widely used Chai & Ngan values, which hold across the full tonal range
# because Cr/Cb encode chroma independently of luma.
_CR_RANGE = (133, 173)
_CB_RANGE = (77, 127)


class NoFaceDetectedError(Exception):
    """Raised when no usable face region can be sampled from the upload."""


def _decode(image_bytes: bytes) -> np.ndarray:
    """Decode to an RGB ndarray, honouring EXIF rotation from phone cameras."""
    pil = Image.open(io.BytesIO(image_bytes))
    # Phone selfies are near-always EXIF-rotated; without this the cascade misses.
    from PIL import ImageOps

    pil = ImageOps.exif_transpose(pil).convert("RGB")

    # Cap the long edge: detection accuracy plateaus well before full sensor res,
    # and this keeps peak memory bounded for large uploads.
    long_edge = max(pil.size)
    if long_edge > 1024:
        scale = 1024 / long_edge
        pil = pil.resize(
            (round(pil.width * scale), round(pil.height * scale)), Image.LANCZOS
        )

    return np.asarray(pil)


def _largest_face(rgb: np.ndarray) -> tuple[int, int, int, int]:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    # equalizeHist markedly improves recall on under- and over-exposed selfies.
    equalized = cv2.equalizeHist(gray)

    # A single (scaleFactor, image) pass misses faces whose size falls between
    # the pyramid's discrete steps, so retry with a finer pyramid and with the
    # un-equalized image before giving up. Ordered cheapest-first; most real
    # selfies hit on the first attempt.
    attempts = (
        (equalized, 1.1),
        (equalized, 1.05),
        (gray, 1.05),
        (equalized, 1.02),
    )

    for image, scale_factor in attempts:
        faces = _FACE_CASCADE.detectMultiScale(
            image, scaleFactor=scale_factor, minNeighbors=5, minSize=(80, 80)
        )
        if len(faces) > 0:
            # Assume the subject is the most prominent face if several appear.
            return max(faces, key=lambda f: f[2] * f[3])

    raise NoFaceDetectedError(
        "No face found in the uploaded image. Use a clear, front-facing photo."
    )


def _skin_mask(patch_rgb: np.ndarray) -> np.ndarray:
    """Boolean mask of pixels that are plausibly well-lit skin."""
    ycrcb = cv2.cvtColor(patch_rgb, cv2.COLOR_RGB2YCrCb)
    cr, cb = ycrcb[:, :, 1], ycrcb[:, :, 2]
    mask = (
        (cr >= _CR_RANGE[0])
        & (cr <= _CR_RANGE[1])
        & (cb >= _CB_RANGE[0])
        & (cb <= _CB_RANGE[1])
    )

    # Drop crushed shadows and blown highlights: both destroy chroma, and a
    # specular highlight on the nose would otherwise read as a much fairer tone.
    luma = ycrcb[:, :, 0]
    return mask & (luma > 40) & (luma < 245)


def _cheek_regions(x: int, y: int, w: int, h: int) -> list[tuple[int, int, int, int]]:
    """Boxes over both cheeks and the forehead.

    These avoid the eyes, brows and lips, which are the main sources of
    non-skin contamination inside a face bounding box.
    """
    return [
        # Left cheek, right cheek: below the eye line, outboard of the nose.
        (x + int(0.12 * w), y + int(0.55 * h), int(0.22 * w), int(0.20 * h)),
        (x + int(0.66 * w), y + int(0.55 * h), int(0.22 * w), int(0.20 * h)),
        # Forehead: above the brows, inboard to dodge hairline and temples.
        (x + int(0.30 * w), y + int(0.15 * h), int(0.40 * w), int(0.12 * h)),
    ]


def _srgb_to_lab(rgb: np.ndarray) -> tuple[float, float, float]:
    """Convert a single mean RGB triple to CIE L*a*b* under D65."""
    arr = np.asarray(rgb, dtype=np.float32).reshape(1, 1, 3) / 255.0
    lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB).reshape(3)
    # OpenCV's float LAB is already in the natural ranges: L 0-100, a/b -127..127.
    return float(lab[0]), float(lab[1]), float(lab[2])


def _classify_depth(lightness: float) -> ToneDepth:
    """Bucket CIE L* into five depth bands.

    Cutoffs are calibrated against measured L* for real skin, which spans
    roughly 20 (very deep) to 90 (very fair). Earlier values clustered too high
    and collapsed everything above light-medium into `fair`.
    """
    if lightness >= 80:
        return ToneDepth.FAIR
    if lightness >= 69:
        return ToneDepth.LIGHT
    if lightness >= 56:
        return ToneDepth.MEDIUM
    if lightness >= 43:
        return ToneDepth.TAN
    return ToneDepth.DEEP


def _classify_undertone(a: float, b: float) -> Undertone:
    """Warm/cool/neutral from the a*/b* ratio.

    All human skin sits in the positive a*/positive b* quadrant, so absolute b*
    cannot separate undertones. What distinguishes them is how much yellow (b*)
    there is *relative* to red (a*): golden skin skews b*, rosy skin skews a*.
    """
    if a <= 0:
        # Degenerate sample (e.g. heavy colour cast); refuse to guess a bias.
        return Undertone.NEUTRAL

    ratio = b / a
    if ratio >= 1.55:
        return Undertone.WARM
    if ratio <= 1.15:
        return Undertone.COOL
    return Undertone.NEUTRAL


def _hair_lightness(rgb: np.ndarray, face: tuple[int, int, int, int]) -> float:
    """Mean L* of the band just above the face box, as a hair proxy.

    Used only for the contrast figure that splits bright (Winter/Spring) from
    muted (Summer/Autumn) seasons. Falls back to the skin value when the crop
    runs off the top of the frame, which makes contrast 0 and biases toward the
    muted seasons rather than inventing a value.
    """
    x, y, w, h = face
    top = max(0, y - int(0.30 * h))
    if y - top < 10:
        return -1.0

    band = rgb[top:y, x : x + w]
    if band.size == 0:
        return -1.0

    mean_rgb = band.reshape(-1, 3).mean(axis=0)
    return _srgb_to_lab(mean_rgb)[0]


def _classify_season(
    depth: ToneDepth, undertone: Undertone, contrast: float
) -> Season:
    """Map depth + undertone + contrast onto a seasonal archetype.

    Undertone picks the warm/cool axis; contrast picks the bright/muted axis.
    """
    high_contrast = contrast >= 22

    if undertone is Undertone.WARM:
        return Season.SPRING if high_contrast else Season.AUTUMN
    if undertone is Undertone.COOL:
        return Season.WINTER if high_contrast else Season.SUMMER

    # Neutral undertone: let depth break the tie, since deeper neutral skin
    # carries saturated colour better than fair neutral skin does.
    if depth in (ToneDepth.TAN, ToneDepth.DEEP):
        return Season.WINTER if high_contrast else Season.AUTUMN
    return Season.SPRING if high_contrast else Season.SUMMER


def analyze_skin(image_bytes: bytes) -> SkinAnalysis:
    """Detect tone depth, undertone and season from selfie bytes.

    Raises NoFaceDetectedError when no face is found or the sampled region holds
    too few skin pixels to be trustworthy.
    """
    rgb = _decode(image_bytes)
    x, y, w, h = _largest_face(rgb)

    samples: list[np.ndarray] = []
    for rx, ry, rw, rh in _cheek_regions(x, y, w, h):
        # Clamp: the cascade box can extend past the frame on edge-cropped shots.
        patch = rgb[
            max(0, ry) : min(rgb.shape[0], ry + rh),
            max(0, rx) : min(rgb.shape[1], rx + rw),
        ]
        if patch.size == 0:
            continue
        mask = _skin_mask(patch)
        if mask.any():
            samples.append(patch[mask])

    if not samples:
        raise NoFaceDetectedError(
            "Found a face but could not sample clean skin pixels. "
            "Try even lighting and a photo without heavy filters."
        )

    pixels = np.concatenate(samples, axis=0)

    # Per-channel median, not mean: robust to the stray hair strands, blemishes
    # and shadow edges that survive the chroma mask.
    skin_rgb = np.median(pixels, axis=0)
    lightness, a_star, b_star = _srgb_to_lab(skin_rgb)

    hair_l = _hair_lightness(rgb, (x, y, w, h))
    contrast = abs(lightness - hair_l) if hair_l >= 0 else 0.0

    depth = _classify_depth(lightness)
    undertone = _classify_undertone(a_star, b_star)

    # Confidence tracks how much clean skin we actually measured. A face box of
    # w*h pixels yields ~0.54*w*h sampled pixels when the mask passes everything,
    # so scale against that ceiling and treat a third of it as fully confident.
    ceiling = 0.54 * w * h
    coverage = len(pixels) / ceiling if ceiling > 0 else 0.0
    confidence = max(0.35, min(1.0, coverage / 0.33))

    r, g, bl = (int(round(c)) for c in skin_rgb)

    return SkinAnalysis(
        tone_depth=depth,
        undertone=undertone,
        season=_classify_season(depth, undertone, contrast),
        skin_hex=f"#{r:02x}{g:02x}{bl:02x}",
        lightness=round(lightness, 1),
        contrast=round(min(contrast, 100.0), 1),
        confidence=round(confidence, 2),
    )
