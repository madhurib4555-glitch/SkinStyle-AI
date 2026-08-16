"""Generate /tmp/fixture.json for the frontend visual-render harness.

Runs the real analyse and try-on flow in-process (no server needed) and dumps
the responses, the selfie, garment previews and the try-on composite as inlined
data URLs.

Usage:
    cd backend && uv run python ../scripts/fixture.py
"""

import base64
import json
import sys
import time
from pathlib import Path

# Import the app package from backend/ regardless of where this is invoked from.
BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.garments import CATALOG, render_garment  # noqa: E402
from tests.test_skin_tone import synthetic_face  # noqa: E402

OUT = Path("/tmp/fixture.json")


def main() -> None:
    client = TestClient(app)

    # A warm/golden synthetic face, so the fixture exercises the Autumn palette.
    selfie = synthetic_face((214, 172, 120))
    analyze = client.post(
        "/api/analyze", files={"file": ("selfie.jpg", selfie, "image/jpeg")}
    ).json()

    top_hex = analyze["recommendations"][0]["hex"]

    task = client.post(
        "/api/try-on",
        json={
            "image_id": analyze["image_id"],
            "garment_id": "hoodie",
            "color_hex": top_hex,
        },
    ).json()

    # Wait out the mock's simulated render latency before polling for the result.
    time.sleep(3.0)
    result = client.get(f"/api/try-on/{task['task_id']}").json()
    if result.get("status") != "success":
        raise SystemExit(f"try-on did not complete: {result}")

    fixture = {
        # image_id is per-run and unused by the harness.
        "analyze": {k: v for k, v in analyze.items() if k != "image_id"},
        "selfie": "data:image/jpeg;base64," + base64.b64encode(selfie).decode(),
        "garments": [
            {"id": g.id, "name": g.name, "category": g.category} for g in CATALOG
        ],
        "previews": {
            g.id: "data:image/png;base64,"
            + base64.b64encode(render_garment(g.id, top_hex)).decode()
            for g in CATALOG
        },
        "tryon": result["result_url"],
    }

    OUT.write_text(json.dumps(fixture))
    print(f"wrote {OUT} (top colour: {analyze['recommendations'][0]['name']})")


if __name__ == "__main__":
    main()
