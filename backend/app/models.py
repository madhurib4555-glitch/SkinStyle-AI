"""Pydantic schemas shared across routers and services."""

from enum import Enum

from pydantic import BaseModel, Field


class Undertone(str, Enum):
    WARM = "warm"
    COOL = "cool"
    NEUTRAL = "neutral"


class ToneDepth(str, Enum):
    """Fitzpatrick-inspired depth buckets, collapsed to five for styling purposes."""

    FAIR = "fair"
    LIGHT = "light"
    MEDIUM = "medium"
    TAN = "tan"
    DEEP = "deep"


class Season(str, Enum):
    """Seasonal colour analysis archetype derived from depth + undertone + contrast."""

    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class SkinAnalysis(BaseModel):
    tone_depth: ToneDepth
    undertone: Undertone
    season: Season
    # Mean skin colour sampled from the face region, as hex. Useful for the UI swatch.
    skin_hex: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    # Perceptual lightness (CIE L*) of the sampled skin, 0-100.
    lightness: float = Field(ge=0, le=100)
    # Difference in L* between hair/brow region and skin. Drives warm/cool season split.
    contrast: float = Field(ge=0, le=100)
    # 0-1 confidence that a usable face was found and sampled.
    confidence: float = Field(ge=0, le=1)


class ColorRecommendation(BaseModel):
    name: str
    hex: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    # Why this colour suits this specific analysis, in one sentence.
    rationale: str
    # 0-100 fit score, used to order and to render a strength bar.
    score: int = Field(ge=0, le=100)


class ColorToAvoid(BaseModel):
    name: str
    hex: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    reason: str


class AnalyzeResponse(BaseModel):
    # Handle for the cached upload; pass to /try-on to avoid re-uploading.
    image_id: str
    # Headline sentence describing the user's palette.
    summary: str
    analysis: SkinAnalysis
    recommendations: list[ColorRecommendation]
    avoid: list[ColorToAvoid]
    # Present only when the optional YouCam Skin AI enrichment succeeded.
    skin_concerns: dict[str, int] | None = None


class TryOnRequest(BaseModel):
    # Identifier returned by /analyze; points at the cached upload.
    image_id: str
    garment_id: str
    # Hex of the recommended colour the user tapped, for recolouring the garment.
    color_hex: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class TryOnResponse(BaseModel):
    task_id: str
    status: str
    result_url: str | None = None
