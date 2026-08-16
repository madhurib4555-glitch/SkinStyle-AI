"""Garment catalogue and colour-accurate garment rendering.

The VTO step needs a garment image in the colour the user tapped. Rather than
shipping a fixed photo per colour (which would mean 4 garment types x 20 colours
of assets), garments are stored as greyscale alpha-masked shape templates and
tinted on demand. The template keeps fabric shading, so the tinted output still
reads as cloth rather than a flat silhouette.
"""

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


@dataclass(frozen=True)
class Garment:
    id: str
    name: str
    category: str


CATALOG: tuple[Garment, ...] = (
    Garment("tshirt", "Crew-Neck T-Shirt", "T-Shirts"),
    Garment("shirt", "Button-Down Shirt", "Shirts"),
    Garment("hoodie", "Pullover Hoodie", "Hoodies"),
    Garment("jacket", "Zip Jacket", "Jackets"),
)

CATALOG_BY_ID = {g.id: g for g in CATALOG}

_W, _H = 600, 640


def _body_polygon(shoulder_drop: int, hem_flare: int) -> list[tuple[int, int]]:
    """Torso outline shared by every garment, parameterised by cut.

    Traced with a slight waist taper and a wider hem so it reads as a hanging
    garment rather than a rectangle.
    """
    return [
        (168, 104 + shoulder_drop),
        (232, 74),
        (300, 68),
        (368, 74),
        (432, 104 + shoulder_drop),
        (462 + hem_flare, 196),
        (440, 224),
        (446, 380),
        (452, 592),
        (300, 602),
        (148, 592),
        (154, 380),
        (160, 224),
        (138 - hem_flare, 196),
    ]


def _sleeve_polygons(long: bool) -> list[list[tuple[int, int]]]:
    """Sleeves as separate shapes so they can shade slightly darker than the body."""
    if long:
        return [
            [(168, 106), (138, 200), (108, 330), (92, 424), (156, 438), (176, 330), (192, 224), (206, 140)],
            [(432, 106), (462, 200), (492, 330), (508, 424), (444, 438), (424, 330), (408, 224), (394, 140)],
        ]
    return [
        [(168, 106), (138, 200), (112, 286), (176, 302), (192, 220), (206, 140)],
        [(432, 106), (462, 200), (488, 286), (424, 302), (408, 220), (394, 140)],
    ]


def _template(garment_id: str) -> Image.Image:
    """Greyscale garment template with alpha. L channel carries fabric shading."""
    # Build at 2x then downsample, so polygon edges come out anti-aliased.
    scale = 2
    # 'LA': L is the shading multiplier, A is the garment silhouette.
    img = Image.new("LA", (_W * scale, _H * scale), (0, 0))
    draw = ImageDraw.Draw(img)

    def s(points):
        return [(x * scale, y * scale) for x, y in points]

    def sbox(box):
        return tuple(v * scale for v in box)

    long_sleeve = garment_id in ("hoodie", "jacket", "shirt")
    flare = 22 if garment_id in ("hoodie", "jacket") else 0
    drop = 12 if garment_id == "hoodie" else 0

    # Hood sits behind the shoulders, so it is drawn before the body.
    if garment_id == "hoodie":
        draw.ellipse(sbox((214, 30, 386, 168)), fill=(168, 255))

    # Sleeves slightly darker than the body: they catch less light head-on.
    for poly in _sleeve_polygons(long_sleeve):
        draw.polygon(s(poly), fill=(186, 255))
    draw.polygon(s(_body_polygon(drop, flare)), fill=(202, 255))

    # Neckline: cut out of the alpha so skin shows through.
    if garment_id == "hoodie":
        draw.ellipse(sbox((243, 74, 357, 150)), fill=(150, 0))
        # Inner hood opening, shaded dark to imply depth.
        draw.chord(sbox((236, 60, 364, 158)), start=200, end=340, fill=(120, 255))
    elif garment_id == "jacket":
        # V opening formed by the two lapels.
        draw.polygon(s([(258, 72), (342, 72), (318, 168), (282, 168)]), fill=(150, 0))
        draw.polygon(s([(258, 72), (300, 120), (272, 176), (250, 100)]), fill=(176, 255))
        draw.polygon(s([(342, 72), (300, 120), (328, 176), (350, 100)]), fill=(176, 255))
    else:
        draw.ellipse(sbox((252, 70, 348, 132)), fill=(150, 0))
        # Ribbed collar band around the neckline.
        draw.arc(sbox((250, 68, 350, 136)), start=8, end=172, fill=(172, 255), width=7 * scale)

    # Garment-specific detailing, drawn as shading only (alpha untouched).
    if garment_id == "shirt":
        draw.rectangle(sbox((288, 118, 312, 592)), fill=(170, 255))
        # Collar points folding outward from the neckline.
        draw.polygon(s([(252, 78), (300, 126), (264, 140), (244, 96)]), fill=(180, 255))
        draw.polygon(s([(348, 78), (300, 126), (336, 140), (356, 96)]), fill=(180, 255))
        for y in range(170, 570, 68):
            draw.ellipse(sbox((295, y, 305, y + 10)), fill=(124, 255))
        # Cuffs.
        draw.polygon(s([(92, 424), (156, 438), (150, 462), (86, 448)]), fill=(174, 255))
        draw.polygon(s([(508, 424), (444, 438), (450, 462), (514, 448)]), fill=(174, 255))
    elif garment_id == "jacket":
        draw.rectangle(sbox((294, 158, 306, 592)), fill=(140, 255))
        for y in range(166, 590, 16):
            draw.line(sbox((295, y, 305, y)), fill=(112, 255), width=2 * scale)
        # Hem band.
        draw.rectangle(sbox((150, 556, 450, 592)), fill=(188, 255))
    elif garment_id == "hoodie":
        draw.rounded_rectangle(sbox((198, 412, 402, 524)), radius=16 * scale, fill=(184, 255))
        # Drawstrings.
        draw.line(sbox((272, 148, 268, 258)), fill=(148, 255), width=7 * scale)
        draw.line(sbox((328, 148, 332, 258)), fill=(148, 255), width=7 * scale)
        draw.ellipse(sbox((263, 254, 275, 268)), fill=(130, 255))
        draw.ellipse(sbox((327, 254, 339, 268)), fill=(130, 255))
        # Waist band.
        draw.rectangle(sbox((150, 560, 450, 592)), fill=(188, 255))

    img = img.resize((_W, _H), Image.LANCZOS)

    # Soft vertical falloff plus blur reads as cloth drape rather than flat fill.
    shading = np.asarray(img.getchannel("L"), dtype=np.float32)
    gradient = np.linspace(1.07, 0.87, _H, dtype=np.float32)[:, None]
    shading = np.clip(shading * gradient, 0, 255).astype(np.uint8)

    out = Image.merge("LA", (Image.fromarray(shading, mode="L"), img.getchannel("A")))
    return out.filter(ImageFilter.GaussianBlur(0.8))


# Templates are deterministic and reused across requests, so build each once.
_TEMPLATE_CACHE: dict[str, Image.Image] = {}


def _cached_template(garment_id: str) -> Image.Image:
    if garment_id not in _TEMPLATE_CACHE:
        _TEMPLATE_CACHE[garment_id] = _template(garment_id)
    return _TEMPLATE_CACHE[garment_id]


def render_garment(garment_id: str, color_hex: str) -> bytes:
    """Return a PNG of the garment tinted to color_hex, with transparency."""
    if garment_id not in CATALOG_BY_ID:
        raise KeyError(f"Unknown garment: {garment_id}")

    template = _cached_template(garment_id)
    shading = np.asarray(template.getchannel("L"), dtype=np.float32) / 255.0
    alpha = template.getchannel("A")

    target = np.array(
        [int(color_hex[i : i + 2], 16) for i in (1, 3, 5)], dtype=np.float32
    )

    # Multiply the target colour by the shading map, normalised so mid-grey maps
    # to the exact requested colour. Folds and details then read as relative
    # light and shade around it instead of shifting the hue.
    tinted = np.clip(
        target[None, None, :] * (shading[:, :, None] / 0.78), 0, 255
    ).astype(np.uint8)

    rgba = Image.fromarray(tinted, mode="RGB").convert("RGBA")
    rgba.putalpha(alpha)

    buf = io.BytesIO()
    rgba.save(buf, format="PNG")
    return buf.getvalue()
