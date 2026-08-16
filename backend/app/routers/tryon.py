"""Virtual try-on endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Response

from app.models import TryOnRequest, TryOnResponse
from app.services.garments import CATALOG, CATALOG_BY_ID, render_garment
from app.services.image_store import store
from app.services.youcam import YouCamError, get_client

logger = logging.getLogger(__name__)
router = APIRouter(tags=["try-on"])


@router.get("/garments")
async def list_garments() -> dict[str, list[dict[str, str]]]:
    return {
        "garments": [
            {
                "id": g.id,
                "name": g.name,
                "category": g.category,
            }
            for g in CATALOG
        ]
    }


@router.get("/garments/{garment_id}/preview")
async def garment_preview(
    garment_id: str,
    color: str,
) -> Response:
    """Tinted garment PNG, used for catalogue thumbnails in the UI."""

    if not (len(color) == 7 and color[0] == "#"):
        raise HTTPException(
            status_code=400,
            detail="color must be a #rrggbb hex value.",
        )

    try:
        png = render_garment(
            garment_id,
            color,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid colour value.",
        ) from exc

    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.post(
    "/try-on",
    response_model=TryOnResponse,
)
async def start_try_on(
    request: TryOnRequest,
) -> TryOnResponse:

    # ---------------------------------------------------------
    # Get user's uploaded photo
    # ---------------------------------------------------------

    person_bytes = store.get(
        request.image_id
    )

    if person_bytes is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "That photo is no longer available. "
                "Please upload it again."
            ),
        )

    # ---------------------------------------------------------
    # Validate garment
    # ---------------------------------------------------------

    garment = CATALOG_BY_ID.get(
        request.garment_id
    )

    if garment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown garment: {request.garment_id}",
        )

    # ---------------------------------------------------------
    # Render garment image
    # ---------------------------------------------------------

    try:
        garment_bytes = render_garment(
            request.garment_id,
            request.color_hex,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid colour value.",
        ) from exc

    # ---------------------------------------------------------
    # Determine YouCam garment category
    # ---------------------------------------------------------
    #
    # Our catalogue categories:
    #
    # T-Shirts / Shirts / Hoodies / Jackets / Tops
    #     -> upper_body
    #
    # Jeans / Pants / Trousers / Skirts
    #     -> lower_body
    #
    # Dresses
    #     -> full_body
    #
    # YouCam categories:
    #
    # upper_body
    # lower_body
    # full_body
    # shoes
    # ---------------------------------------------------------

    upper_body_categories = {
        "T-Shirts",
        "Shirts",
        "Hoodies",
        "Jackets",
        "Tops",
    }

    lower_body_categories = {
        "Jeans",
        "Pants",
        "Trousers",
        "Skirts",
    }

    full_body_categories = {
        "Dresses",
    }

    if garment.category in upper_body_categories:
        youcam_category = "upper_body"

    elif garment.category in lower_body_categories:
        youcam_category = "lower_body"

    elif garment.category in full_body_categories:
        youcam_category = "full_body"

    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported garment category: "
                f"{garment.category}"
            ),
        )

    logger.info(
        "Starting YouCam try-on: garment=%s category=%s YouCamCategory=%s",
        garment.id,
        garment.category,
        youcam_category,
    )

    # ---------------------------------------------------------
    # Submit to YouCam
    # ---------------------------------------------------------

    try:
        task_id = await get_client().start_try_on(
            person_bytes,
            garment_bytes,
            garment_category=youcam_category,
        )

    except YouCamError as exc:
        logger.error(
            "Try-on submission failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "The try-on service rejected this request."
            ),
        ) from exc

    return TryOnResponse(
        task_id=task_id,
        status="running",
    )


@router.get(
    "/try-on/{task_id}",
    response_model=TryOnResponse,
)
async def poll(
    task_id: str,
) -> TryOnResponse:

    try:
        status, result_url = await get_client().poll_try_on(
            task_id
        )

    except YouCamError as exc:
        logger.error(
            "Try-on polling failed for %s: %s",
            task_id,
            exc,
        )

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    return TryOnResponse(
        task_id=task_id,
        status=status,
        result_url=result_url,
    )