"""Skin analysis and colour recommendation endpoints."""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.models import AnalyzeResponse
from app.services import recommender
from app.services.image_store import store
from app.services.skin_tone import NoFaceDetectedError, analyze_skin
from app.services.youcam import get_client

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analysis"])

_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)) -> AnalyzeResponse:
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=415, detail="Unsupported image type. Use JPEG, PNG or WebP."
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(image_bytes) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=413, detail=f"Image exceeds the {limit_mb}MB limit."
        )

    try:
        analysis = analyze_skin(image_bytes)
    except NoFaceDetectedError as exc:
        # User-actionable message; pass the guidance through verbatim.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Skin tone analysis failed")
        raise HTTPException(
            status_code=400,
            detail="Could not process that image. Try a different photo.",
        ) from exc

    recommendations, avoid = recommender.recommend(analysis)

    # Skin AI concerns are supplementary: colour advice does not depend on them,
    # so an upstream failure degrades the response rather than failing it.
    skin_concerns: dict[str, int] | None = None
    try:
        skin_concerns = await get_client().analyze_skin_concerns(image_bytes)
    except Exception as exc:
        logger.warning("Skin concern enrichment unavailable: %s", exc)

    return AnalyzeResponse(
        image_id=store.put(image_bytes),
        summary=recommender.season_summary(analysis),
        analysis=analysis,
        recommendations=recommendations,
        avoid=avoid,
        skin_concerns=skin_concerns,
    )
