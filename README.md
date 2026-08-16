# SkinStyle AI

Find the clothing colours that complement your skin tone, then preview them
with virtual try-on.

Upload a selfie → the app detects your skin depth, undertone and seasonal
palette → it recommends colours **with a written reason for each** → pick one
and see it on a garment → download the result.

## Read this first: what the YouCam APIs actually do

The original proposal assumed YouCam Skin AI returns skin tone and undertone.
**It does not.** Perfect Corp's Skin AI returns *dermatological concern scores*
— wrinkles, spots, redness, acne, texture, pores and so on. There is no tone or
undertone field.

So the work is split:

| Capability | Provided by |
|---|---|
| Skin tone, undertone, season, contrast | **This repo**, locally (`backend/app/services/skin_tone.py`) |
| Colour recommendations + rationales | **This repo** (`backend/app/services/recommender.py`) |
| Skin concern scores (optional enrichment) | YouCam Skin AI |
| Apparel virtual try-on | YouCam Apparel VTO |

This is still a genuine two-API integration. Just describe it accurately: **do
not claim the tone analysis comes from YouCam Skin AI.** If a judge asks how
undertone is detected, the answer is CIE L\*a\*b\* analysis of sampled cheek and
forehead pixels — see below.

## Running it

Two terminals. The app works fully without any API credentials.

```bash
# Terminal 1 — backend on :8000
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend on :3000
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>.

Without credentials the backend uses `MockYouCamClient`, and the UI shows a
"Placeholder preview" notice on every try-on result so a mock is never mistaken
for real VTO.

### Enabling the real YouCam APIs

```bash
cd backend
cp .env.example .env
# then set:
#   YOUCAM_API_KEY=...
#   YOUCAM_SECRET_KEY=...
```

`get_client()` in `app/services/youcam.py` switches to `LiveYouCamClient` when
both are present. Nothing else changes — the mock and live clients implement the
same `YouCamClient` protocol.

> **Not yet verified against the live service.** `LiveYouCamClient` is written
> from Perfect Corp's documented S2S contract (RSA-OAEP auth → presigned upload
> → task submit → poll) but has never run against real credentials. Expect to
> adjust response field paths on first contact. That seam is deliberately one
> file.

## How the colour analysis works

**Tone detection.** The face is located with a Haar cascade, then skin pixels are
sampled from both cheeks and the forehead — regions chosen to avoid eyes, brows
and lips. A YCrCb chroma mask rejects non-skin pixels, and luma bounds discard
crushed shadows and specular highlights (a shiny nose would otherwise read as
much fairer skin). The per-channel **median** of what survives becomes the skin
colour; median rather than mean, so stray hair strands and blemishes don't shift
it.

**Depth** is CIE L\*, bucketed into five bands. Cutoffs are calibrated against
measured L\* for real skin, which spans roughly 20–90.

**Undertone** is the **b\*/a\* ratio**, not absolute b\*. This matters: all human
skin sits in the positive a\*/positive b\* quadrant, so absolute yellow cannot
separate warm from cool. What distinguishes them is how much yellow there is
*relative to red* — golden skin skews b\*, rosy skin skews a\*. This is why the
same code separates warm from cool at both fair and deep depths.

**Season** combines undertone (warm/cool axis) with facial contrast — the L\*
gap between hair and skin — for the bright/muted axis.

**Scoring** is rule-based and inspectable, out of 100: undertone agreement (40),
depth contrast (25), seasonal palette membership (20), and chroma against facial
contrast (15). Every point traces to a colour property, which is what makes the
per-colour explanations honest rather than decorative.

## Tests

```bash
cd backend  && uv run pytest      # 57 tests
cd frontend && npm test           # 60 tests
```

The backend suite builds synthetic faces of known colour, so tone classification
is asserted against **known inputs** rather than just checked for absence of
crashes. Depth buckets are pinned to nine reference skin colours — that test is
what caught a miscalibration where everything from very-fair to light-medium
collapsed into `fair`.

### Visual check without a dev server

To eyeball the UI without running `next dev`, render the real components to a
standalone HTML file with real backend data:

```bash
# 1. generate a fixture from the backend (writes /tmp/fixture.json)
cd backend && uv run python ../scripts/fixture.py

# 2. render the components with real Tailwind CSS (writes /tmp/render.html)
cd ../frontend && npx vitest run --config vitest.render.mts

# 3. open it
open /tmp/render.html
```

Everything is inlined, so the file works offline with no server.

## Notable constraints

- **Uploads are never written to disk.** A selfie is biometric data, so it is
  held in an in-memory store with a 30-minute TTL (`services/image_store.py`).
  The trade-off is that this is **single-process only** — running multiple
  workers means a try-on can hit a process without the image. For multi-instance
  deployment, back that store with Redis; the `put`/`get` interface is unchanged.
- **`opencv-python-headless` is pinned to `<5`.** OpenCV 5.0 dropped
  `CascadeClassifier` from the headless wheel.
- **Garments are procedurally rendered**, not photos: greyscale shape templates
  tinted on demand, so any of the 20 palette colours works without shipping
  4 × 20 image assets. They are placeholders for the mock composite; live VTO
  replaces them.
- **Two palette colours cannot meet WCAG AA as text backgrounds** — Dusty Teal
  and Terracotta are mid-tones where neither black nor white clears 4.5:1. The UI
  works around this by keeping swatches text-free and putting the fit score on
  the card background. A test pins the known set so a new swatch below AA fails
  loudly.
- Single light theme by design: the colour swatches *are* the product, and
  predictable contrast against them beats honouring a dark-mode preference.

## Layout

```
backend/
  app/
    services/skin_tone.py    tone + undertone detection (the local analysis)
    services/recommender.py  palette scoring and rationales
    services/youcam.py       mock + live YouCam clients behind one protocol
    services/garments.py     procedural garment rendering
    services/image_store.py  in-memory selfie store with TTL
    routers/                 /analyze, /try-on, /garments
frontend/
  app/page.tsx               the upload → analyse → try-on flow
  components/                uploader, analysis card, colour list, picker, result
  lib/api.ts                 typed API client
  lib/color.ts               WCAG contrast helpers
```

## Not built

Everything under "Future Enhancements" in the proposal: occasion-based outfits,
seasonal suggestions, wardrobe management, full outfit generation, e-commerce
integration, accessory recommendations.
