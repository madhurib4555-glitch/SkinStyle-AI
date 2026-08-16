"""SkinStyle AI backend entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import analysis, tryon

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.using_mock:
        logger.warning(
            "YOUCAM_API_KEY/YOUCAM_SECRET_KEY not set - using the mock YouCam client. "
            "Try-on results are placeholder composites, not real virtual try-on."
        )
    yield


app = FastAPI(
    title="SkinStyle AI",
    description="Skin-tone-aware clothing colour recommendations with virtual try-on.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(analysis.router, prefix="/api")
app.include_router(tryon.router, prefix="/api")


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "youcam_mode": "mock" if settings.using_mock else "live"}
