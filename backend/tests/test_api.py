"""End-to-end API tests against the mock YouCam client."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import app
from tests.test_skin_tone import synthetic_face


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def fast_mock_vto(monkeypatch):
    """Collapse the mock's simulated latency so polling tests stay quick."""
    monkeypatch.setattr(settings, "mock_vto_latency_seconds", 0.0)


_UNSET = object()


def upload(client, image_bytes=_UNSET, content_type="image/jpeg"):
    """POST a selfie to /analyze.

    Uses a sentinel rather than `or` for the default: b"" is falsy, and an `or`
    default would silently swap the empty-upload case for a valid face.
    """
    payload = synthetic_face((205, 160, 125)) if image_bytes is _UNSET else image_bytes
    return client.post(
        "/api/analyze", files={"file": ("selfie.jpg", payload, content_type)}
    )


class TestHealth:
    def test_reports_mock_mode_without_credentials(self, client):
        body = client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["youcam_mode"] == "mock"


class TestAnalyzeEndpoint:
    def test_happy_path_returns_full_payload(self, client):
        resp = upload(client)
        assert resp.status_code == 200, resp.text

        body = resp.json()
        assert body["image_id"]
        assert body["summary"]
        assert body["analysis"]["undertone"] in ("warm", "cool", "neutral")
        assert len(body["recommendations"]) == 6
        assert len(body["avoid"]) == 3
        # Mock client always succeeds, so enrichment must be present.
        assert body["skin_concerns"]

    def test_rejects_unsupported_content_type(self, client):
        resp = client.post(
            "/api/analyze", files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")}
        )
        assert resp.status_code == 415

    def test_rejects_empty_upload(self, client):
        resp = upload(client, image_bytes=b"")
        assert resp.status_code == 400

    def test_rejects_oversized_upload(self, client, monkeypatch):
        monkeypatch.setattr(settings, "max_upload_bytes", 100)
        assert upload(client).status_code == 413

    def test_faceless_image_returns_actionable_422(self, client):
        blank = Image.new("RGB", (400, 400), (120, 120, 120))
        buf = io.BytesIO()
        blank.save(buf, format="JPEG")
        resp = upload(client, image_bytes=buf.getvalue())
        assert resp.status_code == 422
        # The message must tell the user what to do differently.
        assert "face" in resp.json()["detail"].lower()

    def test_corrupt_image_bytes_return_400_not_500(self, client):
        resp = upload(client, image_bytes=b"not a real jpeg at all")
        assert resp.status_code == 400

    def test_analysis_survives_skin_ai_outage(self, client, monkeypatch):
        """Colour advice must still be returned when enrichment fails."""
        from app.services import youcam

        async def boom(_self, _bytes):
            raise youcam.YouCamError("upstream down")

        monkeypatch.setattr(youcam.MockYouCamClient, "analyze_skin_concerns", boom)

        body = upload(client).json()
        assert len(body["recommendations"]) == 6
        assert body["skin_concerns"] is None


class TestGarmentEndpoints:
    def test_lists_catalogue(self, client):
        garments = client.get("/api/garments").json()["garments"]
        assert len(garments) >= 4
        assert {"id", "name", "category"} <= garments[0].keys()

    def test_preview_returns_png(self, client):
        resp = client.get("/api/garments/tshirt/preview", params={"color": "#0f7b6c"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        # Verify it decodes and carries transparency.
        img = Image.open(io.BytesIO(resp.content))
        assert img.mode == "RGBA"

    def test_preview_reflects_requested_colour(self, client):
        """Two colours must not render identical pixels."""
        teal = client.get("/api/garments/tshirt/preview", params={"color": "#0f7b6c"})
        rust = client.get("/api/garments/tshirt/preview", params={"color": "#a9542a"})
        assert teal.content != rust.content

    def test_preview_rejects_unknown_garment(self, client):
        resp = client.get("/api/garments/sombrero/preview", params={"color": "#0f7b6c"})
        assert resp.status_code == 404

    def test_preview_rejects_malformed_colour(self, client):
        resp = client.get("/api/garments/tshirt/preview", params={"color": "teal"})
        assert resp.status_code == 400


class TestTryOnFlow:
    def test_full_try_on_round_trip(self, client):
        image_id = upload(client).json()["image_id"]

        start = client.post(
            "/api/try-on",
            json={"image_id": image_id, "garment_id": "hoodie", "color_hex": "#1f2a52"},
        )
        assert start.status_code == 200, start.text
        task_id = start.json()["task_id"]

        poll = client.get(f"/api/try-on/{task_id}")
        assert poll.status_code == 200
        body = poll.json()
        assert body["status"] == "success"
        # Mock returns an inline composite.
        assert body["result_url"].startswith("data:image/jpeg;base64,")

    def test_reports_running_before_latency_elapses(self, client, monkeypatch):
        monkeypatch.setattr(settings, "mock_vto_latency_seconds", 30.0)
        image_id = upload(client).json()["image_id"]
        task_id = client.post(
            "/api/try-on",
            json={"image_id": image_id, "garment_id": "tshirt", "color_hex": "#1f2a52"},
        ).json()["task_id"]

        body = client.get(f"/api/try-on/{task_id}").json()
        assert body["status"] == "running"
        assert body["result_url"] is None

    def test_expired_image_id_returns_404(self, client):
        resp = client.post(
            "/api/try-on",
            json={"image_id": "nope", "garment_id": "tshirt", "color_hex": "#1f2a52"},
        )
        assert resp.status_code == 404

    def test_unknown_garment_returns_404(self, client):
        image_id = upload(client).json()["image_id"]
        resp = client.post(
            "/api/try-on",
            json={"image_id": image_id, "garment_id": "kilt", "color_hex": "#1f2a52"},
        )
        assert resp.status_code == 404

    def test_malformed_hex_is_rejected_by_validation(self, client):
        image_id = upload(client).json()["image_id"]
        resp = client.post(
            "/api/try-on",
            json={"image_id": image_id, "garment_id": "tshirt", "color_hex": "navy"},
        )
        assert resp.status_code == 422

    def test_unknown_task_id_returns_502(self, client):
        # The mock raises YouCamError for unknown tasks; router maps upstream
        # failures to 502.
        assert client.get("/api/try-on/mock_doesnotexist").status_code == 502
