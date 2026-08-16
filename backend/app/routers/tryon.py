"""Virtual try-on endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Response

from app.models import TryOnRequest, TryOnResponse
from app.services.garments import CATALOG, render_garment
from app.services.image_store import store
from app.services.youcam import YouCamError, get_client

logger = logging.getLogger(__name__)
router = APIRouter(tags=["try-on"])


@router.get("/garments")
async def list_garments() -> dict[str, list[dict[str, str]]]:
    return {
        "garments": [
            {"id": g.id, "name": g.name, "category": g.category} for g in CATALOG
        ]
    }


@router.get("/garments/{garment_id}/preview")
async def garment_preview(garment_id: str, color: str) -> Response:
    """Tinted garment PNG, used for catalogue thumbnails in the UI."""
    if not (len(color) == 7 and color[0] == "#"):
        raise HTTPException(status_code=400, detail="color must be a #rrggbb hex value.")
    try:
        png = render_garment(garment_id, color)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid colour value.") from exc

    # Deterministic for a given (garment, colour), so let the browser cache it.
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.post("/try-on", response_model=TryOnResponse)
async def start_try_on(request: TryOnRequest) -> TryOnResponse:
    person_bytes = store.get(request.image_id)
    if person_bytes is None:
        # Expired or unknown: the client must re-run /analyze.
        raise HTTPException(
            status_code=404,
            detail="That photo is no longer available. Please upload it again.",
        )

    try:
        garment_bytes = render_garment(request.garment_id, request.color_hex)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        task_id = await get_client().start_try_on(person_bytes, garment_bytes)
    except YouCamError as exc:
        logger.error("Try-on submission failed: %s", exc)
        raise HTTPException(
            status_code=502, detail="The try-on service rejected this request."
        ) from exc

    return TryOnResponse(task_id=task_id, status="running")


@router.get("/try-on/{task_id}", response_model=TryOnResponse)
async def poll(task_id: str) -> TryOnResponse:
    try:
        status, result_url = await get_client().poll_try_on(task_id)
    except YouCamError as exc:
        logger.error("Try-on polling failed for %s: %s", task_id, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return TryOnResponse(task_id=task_id, status=status, result_url=result_url)
