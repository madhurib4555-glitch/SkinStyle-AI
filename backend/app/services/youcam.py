"""Client for Perfect Corp / YouCam APIs, with a mock implementation.

The live client uses the current YouCam AI Clothes V3 API:

1. POST /s2s/v2.0/file/cloth-v3
2. PUT <presigned upload URL>
3. POST /s2s/v2.0/task/cloth-v3
4. GET /s2s/v2.0/task/cloth-v3/{task_id}

Authentication:
    Authorization: Bearer <YOUCAM_API_KEY>

The MockYouCamClient is kept so the frontend and routers do not need
to change when live credentials are unavailable.
"""

import asyncio
import base64
import hashlib
import io
import time
from typing import Protocol

import httpx
from PIL import Image

from app.config import settings


# Current YouCam API server.
_BASE_URL = "https://yce-api-01.makeupar.com"

# Current AI Clothes V3 endpoints.
_CLOTH_FILE_ENDPOINT = "/s2s/v2.0/file/cloth-v3"
_CLOTH_TASK_ENDPOINT = "/s2s/v2.0/task/cloth-v3"

# Default category for shirts, tops, jackets, etc.
#
# Change to:
#   "full_body"  -> dresses / full-body garments
#   "lower_body" -> pants / skirts
#   "shoes"      -> shoes
#   "auto"       -> let the API determine the category
#
# For your current SkinStyle-AI clothing try-on, upper_body is a
# sensible default.
_DEFAULT_GARMENT_CATEGORY = "upper_body"


class YouCamError(Exception):
    """Raised when the upstream YouCam API rejects a request or task fails."""


class YouCamClient(Protocol):
    async def analyze_skin_concerns(
        self, image_bytes: bytes
    ) -> dict[str, int]:
        """Return concern scores keyed by concern."""
        ...

    async def start_try_on(
        self, person_bytes: bytes, garment_bytes: bytes
    ) -> str:
        """Submit a clothing VTO task and return its task id."""
        ...

    async def poll_try_on(
        self, task_id: str
    ) -> tuple[str, str | None]:
        """Return (status, result_url)."""
        ...


class MockYouCamClient:
    """Deterministic stand-in used when live credentials are unavailable."""

    _CONCERNS = (
        "wrinkles",
        "spots",
        "texture",
        "acne",
        "dark_circles",
        "redness",
        "oiliness",
        "pores",
        "radiance",
        "firmness",
    )

    def __init__(self) -> None:
        # Maps task_id -> (created_at, composited image data URL)
        self._tasks: dict[str, tuple[float, str]] = {}

    async def analyze_skin_concerns(
        self, image_bytes: bytes
    ) -> dict[str, int]:
        await asyncio.sleep(0.4)

        digest = hashlib.sha256(image_bytes).digest()

        return {
            concern: 20 + (digest[i] % 51)
            for i, concern in enumerate(self._CONCERNS)
        }

    async def start_try_on(
        self,
        person_bytes: bytes,
        garment_bytes: bytes,
    ) -> str:
        task_id = (
            f"mock_{hashlib.sha1(person_bytes + garment_bytes).hexdigest()[:16]}"
        )

        self._tasks[task_id] = (
            time.monotonic(),
            self._composite(person_bytes, garment_bytes),
        )

        return task_id

    async def poll_try_on(
        self,
        task_id: str,
    ) -> tuple[str, str | None]:
        entry = self._tasks.get(task_id)

        if entry is None:
            raise YouCamError(f"Unknown task id: {task_id}")

        created, data_url = entry

        if time.monotonic() - created < settings.mock_vto_latency_seconds:
            return "running", None

        return "success", data_url

    def _composite(
        self,
        person_bytes: bytes,
        garment_bytes: bytes,
    ) -> str:
        """Create a simple placeholder preview for mock mode."""

        from PIL import ImageOps

        person = ImageOps.exif_transpose(
            Image.open(io.BytesIO(person_bytes))
        ).convert("RGBA")

        garment = Image.open(
            io.BytesIO(garment_bytes)
        ).convert("RGBA")

        target_w = int(person.width * 0.70)

        if garment.width > 0:
            ratio = target_w / garment.width
        else:
            ratio = 1.0

        garment = garment.resize(
            (
                target_w,
                int(garment.height * ratio),
            ),
            Image.LANCZOS,
        )

        offset = (
            (person.width - garment.width) // 2,
            int(person.height * 0.48),
        )

        canvas = person.copy()
        canvas.alpha_composite(garment, offset)

        buf = io.BytesIO()

        canvas.convert("RGB").save(
            buf,
            format="JPEG",
            quality=88,
        )

        return (
            "data:image/jpeg;base64,"
            + base64.b64encode(buf.getvalue()).decode()
        )


class LiveYouCamClient:
    """Live Perfect Corp / YouCam client using the current V2 authentication.

    The current YouCam APIs use:

        Authorization: Bearer <API_KEY>

    No RSA encryption or /client/auth call is required.
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str | None = None,
    ) -> None:
        self._api_key = api_key

        # Kept for backwards compatibility with the existing config.
        # The current V2 API does not require the secret key.
        self._secret_key = secret_key

    def _headers(self) -> dict[str, str]:
        """Return headers for the current YouCam V2 API."""

        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _upload(
        self,
        client: httpx.AsyncClient,
        image_bytes: bytes,
        file_name: str,
    ) -> str:
        """Create an upload request, upload the bytes, and return file_id."""

        # The current YouCam File API expects image/jpg or image/jpeg.
        content_type = "image/jpeg"

        response = await client.post(
            f"{_BASE_URL}{_CLOTH_FILE_ENDPOINT}",
            headers=self._headers(),
            json={
                "files": [
                    {
                        "content_type": content_type,
                        "file_name": file_name,
                        "file_size": len(image_bytes),
                    }
                ]
            },
        )

        if response.status_code != 200:
            raise YouCamError(
                "YouCam file upload initialization failed "
                f"({response.status_code}): {response.text}"
            )

        try:
            body = response.json()
            files = body["data"]["files"]
            entry = files[0]
            file_id = entry["file_id"]
            upload_request = entry["requests"][0]
            upload_url = upload_request["url"]
            upload_headers = upload_request.get("headers", {})
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise YouCamError(
                f"Unexpected YouCam upload response: {response.text}"
            ) from exc

        # Upload the actual image bytes to the presigned S3 URL.
        put_response = await client.put(
            upload_url,
            content=image_bytes,
            headers=upload_headers,
        )

        if put_response.status_code not in (200, 201, 204):
            raise YouCamError(
                "YouCam image upload failed "
                f"({put_response.status_code}): {put_response.text}"
            )

        return file_id

    async def analyze_skin_concerns(
        self,
        image_bytes: bytes,
    ) -> dict[str, int]:
        """Run the current V2 skin-analysis API.

        This keeps the existing method signature used by the application.
        """

        skin_file_endpoint = "/s2s/v2.0/file/skin-analysis"
        skin_task_endpoint = "/s2s/v2.0/task/skin-analysis"

        async with httpx.AsyncClient(timeout=60) as client:
            # Step 1: request upload URL.
            response = await client.post(
                f"{_BASE_URL}{skin_file_endpoint}",
                headers=self._headers(),
                json={
                    "files": [
                        {
                            "content_type": "image/jpeg",
                            "file_name": "skin-analysis.jpg",
                            "file_size": len(image_bytes),
                        }
                    ]
                },
            )

            if response.status_code != 200:
                raise YouCamError(
                    "Skin-analysis upload initialization failed "
                    f"({response.status_code}): {response.text}"
                )

            try:
                body = response.json()
                entry = body["data"]["files"][0]
                file_id = entry["file_id"]
                upload_url = entry["requests"][0]["url"]
                upload_headers = entry["requests"][0].get(
                    "headers",
                    {},
                )
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise YouCamError(
                    f"Unexpected skin-analysis upload response: "
                    f"{response.text}"
                ) from exc

            # Step 2: upload image.
            put_response = await client.put(
                upload_url,
                content=image_bytes,
                headers=upload_headers,
            )

            if put_response.status_code not in (200, 201, 204):
                raise YouCamError(
                    "Skin-analysis image upload failed "
                    f"({put_response.status_code}): "
                    f"{put_response.text}"
                )

            # Step 3: create skin-analysis task.
            task_response = await client.post(
                f"{_BASE_URL}{skin_task_endpoint}",
                headers=self._headers(),
                json={
                    "src_file_id": file_id,
                    "dst_actions": [
                        "wrinkle",
                        "pore",
                        "texture",
                        "acne",
                    ],
                    "format": "json",
                },
            )

            if task_response.status_code != 200:
                raise YouCamError(
                    "Skin-analysis task failed "
                    f"({task_response.status_code}): "
                    f"{task_response.text}"
                )

            try:
                task_body = task_response.json()
                task_id = task_body["data"]["task_id"]
            except (KeyError, TypeError, ValueError) as exc:
                raise YouCamError(
                    f"Unexpected skin-analysis task response: "
                    f"{task_response.text}"
                ) from exc

            # Step 4: poll.
            for _ in range(30):
                await asyncio.sleep(2)

                poll_response = await client.get(
                    f"{_BASE_URL}{skin_task_endpoint}/{task_id}",
                    headers=self._headers(),
                )

                if poll_response.status_code != 200:
                    raise YouCamError(
                        "Skin-analysis polling failed "
                        f"({poll_response.status_code}): "
                        f"{poll_response.text}"
                    )

                try:
                    poll_body = poll_response.json()
                    data = poll_body.get("data", {})
                    status = data.get("task_status")
                except (TypeError, ValueError) as exc:
                    raise YouCamError(
                        f"Invalid skin-analysis polling response: "
                        f"{poll_response.text}"
                    ) from exc

                if status == "success":
                    results = data.get("results") or {}

                    # Keep the existing dictionary-style interface.
                    if isinstance(results, dict):
                        output: dict[str, int] = {}

                        for key, value in results.items():
                            if isinstance(value, dict):
                                score = (
                                    value.get("ui_score")
                                    or value.get("score")
                                    or value.get("raw_score")
                                )
                            else:
                                score = value

                            try:
                                output[key] = int(score)
                            except (TypeError, ValueError):
                                continue

                        return output

                    return {}

                if status == "error":
                    raise YouCamError(
                        "Skin analysis errored: "
                        f"{data}"
                    )

            raise YouCamError(
                "Skin analysis timed out"
            )

    async def start_try_on(
        self,
        person_bytes: bytes,
        garment_bytes: bytes,
    ) -> str:
        """Upload person + garment and create a YouCam cloth-v3 task."""

        async with httpx.AsyncClient(timeout=60) as client:
            # ---------------------------------------------------------
            # Step 1: upload the person's image.
            # ---------------------------------------------------------
            person_id = await self._upload(
                client,
                person_bytes,
                "person.jpg",
            )

            # ---------------------------------------------------------
            # Step 2: upload the garment/reference image.
            # ---------------------------------------------------------
            garment_id = await self._upload(
                client,
                garment_bytes,
                "garment.jpg",
            )

            # ---------------------------------------------------------
            # Step 3: create the AI Clothes V3 task.
            # ---------------------------------------------------------
            task_response = await client.post(
                f"{_BASE_URL}{_CLOTH_TASK_ENDPOINT}",
                headers=self._headers(),
                json={
                    "src_file_id": person_id,
                    "ref_file_id": garment_id,
                    "garment_category": _DEFAULT_GARMENT_CATEGORY,
                },
            )

            if task_response.status_code != 200:
                raise YouCamError(
                    "YouCam try-on task failed "
                    f"({task_response.status_code}): "
                    f"{task_response.text}"
                )

            try:
                body = task_response.json()
                task_id = body["data"]["task_id"]
            except (KeyError, TypeError, ValueError) as exc:
                raise YouCamError(
                    f"Unexpected YouCam task response: "
                    f"{task_response.text}"
                ) from exc

            return task_id

    async def poll_try_on(
        self,
        task_id: str,
    ) -> tuple[str, str | None]:
        """Poll a YouCam cloth-v3 task until completion."""

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{_BASE_URL}{_CLOTH_TASK_ENDPOINT}/{task_id}",
                headers=self._headers(),
            )

            if response.status_code != 200:
                raise YouCamError(
                    "YouCam try-on polling failed "
                    f"({response.status_code}): "
                    f"{response.text}"
                )

            try:
                body = response.json()
                data = body.get("data", {})
                status = data.get("task_status", "running")
            except (TypeError, ValueError) as exc:
                raise YouCamError(
                    f"Invalid YouCam polling response: "
                    f"{response.text}"
                ) from exc

            if status == "success":
                results = data.get("results") or {}

                if isinstance(results, dict):
                    result_url = results.get("url")
                else:
                    result_url = None

                return "success", result_url

            if status == "error":
                error_message = (
                    data.get("error_message")
                    or data.get("error")
                    or "Unknown YouCam error"
                )

                raise YouCamError(
                    f"Try-on errored: {error_message}"
                )

            return "running", None


_client: YouCamClient | None = None


def get_client() -> YouCamClient:
    """Return the live client when YouCam credentials exist."""

    global _client

    if _client is None:
        if settings.youcam_api_key:
            _client = LiveYouCamClient(
                settings.youcam_api_key,
                settings.youcam_secret_key,
            )
        else:
            _client = MockYouCamClient()

    return _client