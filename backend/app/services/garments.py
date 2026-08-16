"""Garment catalogue and colour-accurate garment rendering.

Garments are stored as greyscale alpha-masked shape templates and tinted
on demand. Each garment has its own silhouette and detailing so the preview
looks visually different rather than being the same shape with a different
colour.
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
    Garment("fitted_top", "Fitted Top", "Tops"),

    # Jeans / lower-body garments
    Garment("skinny_jeans", "Skinny Jeans", "Jeans"),
    Garment("straight_jeans", "Straight-Leg Jeans", "Jeans"),
    Garment("wide_leg_jeans", "Wide-Leg Jeans", "Jeans"),
    Garment("mom_jeans", "Mom Jeans", "Jeans"),
    Garment("frock", "Frock Dress", "Dresses"),
Garment("gown", "Evening Gown", "Dresses"),
Garment("anarkali", "Anarkali Dress", "Dresses"),
Garment("maxi_dress", "Maxi Dress", "Dresses"),
Garment("a_line_dress", "A-Line Dress", "Dresses"),
Garment("party_dress", "Party Dress", "Dresses"),
)

CATALOG_BY_ID = {g.id: g for g in CATALOG}

_W, _H = 600, 640


# ---------------------------------------------------------------------------
# Standard garment shapes
# ---------------------------------------------------------------------------

def _body_polygon(
    shoulder_drop: int,
    hem_flare: int,
) -> list[tuple[int, int]]:
    """Standard relaxed torso silhouette."""

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
    """Standard T-shirt / long-sleeve shapes."""

    if long:
        return [
            [
                (168, 106),
                (138, 200),
                (108, 330),
                (92, 424),
                (156, 438),
                (176, 330),
                (192, 224),
                (206, 140),
            ],
            [
                (432, 106),
                (462, 200),
                (492, 330),
                (508, 424),
                (444, 438),
                (424, 330),
                (408, 224),
                (394, 140),
            ],
        ]

    return [
        [
            (168, 106),
            (138, 200),
            (112, 286),
            (176, 302),
            (192, 220),
            (206, 140),
        ],
        [
            (432, 106),
            (462, 200),
            (488, 286),
            (424, 302),
            (408, 220),
            (394, 140),
        ],
    ]


# ---------------------------------------------------------------------------
# Fitted women's top shape
# ---------------------------------------------------------------------------

def _fitted_top_body() -> list[tuple[int, int]]:
    """Clearly fitted torso with narrower waist and shorter length."""

    return [
        # Left shoulder
        (182, 108),

        # Neck / shoulder transition
        (238, 78),
        (300, 72),
        (362, 78),

        # Right shoulder
        (418, 108),

        # Upper arm / chest
        (430, 190),

        # Narrow waist
        (412, 300),
        (398, 410),

        # Slightly flared bottom
        (410, 500),
        (404, 548),

        # Bottom
        (300, 556),
        (196, 548),

        # Left side
        (190, 500),
        (202, 410),
        (188, 300),

        # Upper left
        (170, 190),
    ]


def _fitted_top_sleeves() -> list[list[tuple[int, int]]]:
    """Short, fitted sleeves clearly different from the T-shirt sleeves."""

    return [
        [
            (182, 108),
            (150, 152),
            (132, 218),
            (184, 232),
            (206, 178),
            (218, 130),
        ],
        [
            (418, 108),
            (450, 152),
            (468, 218),
            (416, 232),
            (394, 178),
            (382, 130),
        ],
    ]


# ---------------------------------------------------------------------------
# Template renderer
# ---------------------------------------------------------------------------

def _template(garment_id: str) -> Image.Image:
    """Create the greyscale alpha-masked template for a garment."""

    scale = 2

    img = Image.new(
        "LA",
        (_W * scale, _H * scale),
        (0, 0),
    )

    draw = ImageDraw.Draw(img)

    def s(points):
        return [(x * scale, y * scale) for x, y in points]

    def sbox(box):
        return tuple(v * scale for v in box)

    # -----------------------------------------------------------------------
    # FITTED TOP
    # -----------------------------------------------------------------------

    if garment_id == "fitted_top":

        # Short sleeves
        for poly in _fitted_top_sleeves():
            draw.polygon(
                s(poly),
                fill=(184, 255),
            )

        # Fitted body
        draw.polygon(
            s(_fitted_top_body()),
            fill=(204, 255),
        )

        # Scoop neckline - deeper and wider than the crew neck
        draw.ellipse(
            sbox((238, 68, 362, 150)),
            fill=(150, 0),
        )

        # Neckline trim
        draw.arc(
            sbox((236, 66, 364, 154)),
            start=5,
            end=175,
            fill=(170, 255),
            width=7 * scale,
        )

        # Waist shaping shadows
        draw.polygon(
            s(
                [
                    (202, 300),
                    (222, 300),
                    (234, 430),
                    (226, 510),
                    (196, 548),
                    (205, 470),
                    (212, 390),
                ]
            ),
            fill=(180, 255),
        )

        draw.polygon(
            s(
                [
                    (398, 300),
                    (378, 300),
                    (366, 430),
                    (374, 510),
                    (404, 548),
                    (395, 470),
                    (388, 390),
                ]
            ),
            fill=(180, 255),
        )

        # Bottom hem
        draw.rectangle(
            sbox((196, 530, 404, 556)),
            fill=(178, 255),
        )

        # Small decorative seam under bust
        draw.arc(
            sbox((222, 220, 378, 330)),
            start=15,
            end=165,
            fill=(188, 255),
            width=4 * scale,
        )

    # -----------------------------------------------------------------------
    # HOODIE
    # -----------------------------------------------------------------------

    elif garment_id == "hoodie":

        draw.ellipse(
            sbox((214, 30, 386, 168)),
            fill=(168, 255),
        )

        for poly in _sleeve_polygons(True):
            draw.polygon(
                s(poly),
                fill=(186, 255),
            )

        draw.polygon(
            s(_body_polygon(12, 22)),
            fill=(202, 255),
        )

        # Hood opening
        draw.ellipse(
            sbox((243, 74, 357, 150)),
            fill=(150, 0),
        )

        draw.chord(
            sbox((236, 60, 364, 158)),
            start=200,
            end=340,
            fill=(120, 255),
        )

        # Pocket
        draw.rounded_rectangle(
            sbox((198, 412, 402, 524)),
            radius=16 * scale,
            fill=(184, 255),
        )

        # Drawstrings
        draw.line(
            sbox((272, 148, 268, 258)),
            fill=(148, 255),
            width=7 * scale,
        )

        draw.line(
            sbox((328, 148, 332, 258)),
            fill=(148, 255),
            width=7 * scale,
        )

        draw.ellipse(
            sbox((263, 254, 275, 268)),
            fill=(130, 255),
        )

        draw.ellipse(
            sbox((327, 254, 339, 268)),
            fill=(130, 255),
        )

        # Waist band
        draw.rectangle(
            sbox((150, 560, 450, 592)),
            fill=(188, 255),
        )

    # -----------------------------------------------------------------------
    # JACKET
    # -----------------------------------------------------------------------

    elif garment_id == "jacket":

        for poly in _sleeve_polygons(True):
            draw.polygon(
                s(poly),
                fill=(186, 255),
            )

        draw.polygon(
            s(_body_polygon(0, 22)),
            fill=(202, 255),
        )

        # V opening
        draw.polygon(
            s(
                [
                    (258, 72),
                    (342, 72),
                    (318, 168),
                    (282, 168),
                ]
            ),
            fill=(150, 0),
        )

        # Lapels
        draw.polygon(
            s(
                [
                    (258, 72),
                    (300, 120),
                    (272, 176),
                    (250, 100),
                ]
            ),
            fill=(176, 255),
        )

        draw.polygon(
            s(
                [
                    (342, 72),
                    (300, 120),
                    (328, 176),
                    (350, 100),
                ]
            ),
            fill=(176, 255),
        )

        # Zipper
        draw.rectangle(
            sbox((294, 158, 306, 592)),
            fill=(140, 255),
        )

        for y in range(166, 590, 16):
            draw.line(
                sbox((295, y, 305, y)),
                fill=(112, 255),
                width=2 * scale,
            )

        # Hem
        draw.rectangle(
            sbox((150, 556, 450, 592)),
            fill=(188, 255),
        )

    # -----------------------------------------------------------------------
    # BUTTON-DOWN SHIRT
    # -----------------------------------------------------------------------

    elif garment_id == "shirt":

        for poly in _sleeve_polygons(True):
            draw.polygon(
                s(poly),
                fill=(186, 255),
            )

        draw.polygon(
            s(_body_polygon(0, 0)),
            fill=(202, 255),
        )

        # Collar opening
        draw.ellipse(
            sbox((252, 70, 348, 132)),
            fill=(150, 0),
        )

        # Centre placket
        draw.rectangle(
            sbox((288, 118, 312, 592)),
            fill=(170, 255),
        )

        # Collar
        draw.polygon(
            s(
                [
                    (252, 78),
                    (300, 126),
                    (264, 140),
                    (244, 96),
                ]
            ),
            fill=(180, 255),
        )

        draw.polygon(
            s(
                [
                    (348, 78),
                    (300, 126),
                    (336, 140),
                    (356, 96),
                ]
            ),
            fill=(180, 255),
        )

        # Buttons
        for y in range(170, 570, 68):
            draw.ellipse(
                sbox((295, y, 305, y + 10)),
                fill=(124, 255),
            )

        # Cuffs
        draw.polygon(
            s(
                [
                    (92, 424),
                    (156, 438),
                    (150, 462),
                    (86, 448),
                ]
            ),
            fill=(174, 255),
        )

        draw.polygon(
            s(
                [
                    (508, 424),
                    (444, 438),
                    (450, 462),
                    (514, 448),
                ]
            ),
            fill=(174, 255),
        )


            # -----------------------------------------------------------------------
    # JEANS / LOWER-BODY GARMENTS
    # -----------------------------------------------------------------------

    elif garment_id in {
        "skinny_jeans",
        "straight_jeans",
        "wide_leg_jeans",
        "mom_jeans",
    }:
        # Waistband
        draw.rectangle(
            sbox((190, 80, 410, 130)),
            fill=(190, 255),
        )

        # Choose leg width based on the jeans style.
        if garment_id == "skinny_jeans":
            left_outer = 222
            left_inner = 278
            right_inner = 322
            right_outer = 378

        elif garment_id == "straight_jeans":
            left_outer = 190
            left_inner = 278
            right_inner = 322
            right_outer = 410

        elif garment_id == "wide_leg_jeans":
            left_outer = 145
            left_inner = 270
            right_inner = 330
            right_outer = 455

        else:  # mom_jeans
            left_outer = 178
            left_inner = 274
            right_inner = 326
            right_outer = 422

        # Left leg
        draw.polygon(
            s(
                [
                    (190, 120),
                    (left_inner, 120),
                    (left_inner, 300),
                    (left_inner - 8, 580),
                    (left_outer, 580),
                    (left_outer, 300),
                ]
            ),
            fill=(202, 255),
        )

        # Right leg
        draw.polygon(
            s(
                [
                    (right_inner, 120),
                    (410, 120),
                    (right_outer, 300),
                    (right_outer, 580),
                    (right_inner + 8, 580),
                    (right_inner, 300),
                ]
            ),
            fill=(202, 255),
        )

        # Centre seam / zipper
        draw.rectangle(
            sbox((294, 125, 306, 300)),
            fill=(150, 255),
        )

        # Jeans pockets
        draw.line(
            sbox((205, 145, 270, 205)),
            fill=(145, 255),
            width=5 * scale,
        )

        draw.line(
            sbox((395, 145, 330, 205)),
            fill=(145, 255),
            width=5 * scale,
        )

        # Knee / leg shading
        draw.rectangle(
            sbox((left_outer, 300, left_inner, 330)),
            fill=(175, 255),
        )

        draw.rectangle(
            sbox((right_inner, 300, right_outer, 330)),
            fill=(175, 255),
        )

        # Bottom hems
        draw.rectangle(
            sbox((left_outer, 560, left_inner, 590)),
            fill=(180, 255),
        )

        draw.rectangle(
            sbox((right_inner, 560, right_outer, 590)),
            fill=(180, 255),
        )


            # -----------------------------------------------------------------------
    # WOMEN'S DRESSES / FULL-BODY GARMENTS
    # -----------------------------------------------------------------------

    elif garment_id in {
        "frock",
        "gown",
        "anarkali",
        "maxi_dress",
        "a_line_dress",
        "party_dress",
    }:

        # ---------------------------------------------------------------
        # Bodice / upper body
        # ---------------------------------------------------------------

        draw.polygon(
            s(
                [
                    (190, 108),
                    (240, 78),
                    (300, 72),
                    (360, 78),
                    (410, 108),
                    (430, 190),
                    (410, 285),
                    (190, 285),
                    (170, 190),
                ]
            ),
            fill=(202, 255),
        )

        # Neck opening
        draw.ellipse(
            sbox((252, 70, 348, 132)),
            fill=(150, 0),
        )

        # ---------------------------------------------------------------
        # Dress silhouette
        # ---------------------------------------------------------------

        if garment_id == "frock":
            # Short, playful flare
            skirt = [
                (190, 250),
                (410, 250),
                (445, 540),
                (155, 540),
            ]

        elif garment_id == "gown":
            # Long flowing evening gown
            skirt = [
                (205, 245),
                (395, 245),
                (470, 595),
                (130, 595),
            ]

        elif garment_id == "anarkali":
            # Narrow upper body with strong flare from the waist
            skirt = [
                (205, 245),
                (395, 245),
                (500, 595),
                (100, 595),
            ]

        elif garment_id == "maxi_dress":
            # Long, relatively straight silhouette
            skirt = [
                (200, 245),
                (400, 245),
                (430, 595),
                (170, 595),
            ]

        elif garment_id == "a_line_dress":
            # Gradually widening A-line silhouette
            skirt = [
                (210, 245),
                (390, 245),
                (455, 595),
                (145, 595),
            ]

        else:
            # Party dress - shorter and wider flare
            skirt = [
                (195, 245),
                (405, 245),
                (455, 485),
                (145, 485),
            ]

        draw.polygon(
            s(skirt),
            fill=(202, 255),
        )

        # ---------------------------------------------------------------
        # Waist seam
        # ---------------------------------------------------------------

        draw.rectangle(
            sbox((190, 245, 410, 270)),
            fill=(180, 255),
        )

        # ---------------------------------------------------------------
        # Centre dress seam / detail
        # ---------------------------------------------------------------

        draw.line(
            sbox((300, 270, 300, 575)),
            fill=(170, 255),
            width=3 * scale,
        )

        # ---------------------------------------------------------------
        # Soft skirt folds
        # ---------------------------------------------------------------

        draw.line(
            sbox((235, 275, 210, 560)),
            fill=(175, 255),
            width=4 * scale,
        )

        draw.line(
            sbox((365, 275, 390, 560)),
            fill=(175, 255),
            width=4 * scale,
        )

        # ---------------------------------------------------------------
        # Hem
        # ---------------------------------------------------------------

        hem_y = 575 if garment_id != "party_dress" else 465

        draw.rectangle(
            sbox(
                (
                    145 if garment_id != "party_dress" else 150,
                    hem_y,
                    455 if garment_id != "party_dress" else 450,
                    hem_y + 25,
                )
            ),
            fill=(180, 255),
        )





    # -----------------------------------------------------------------------
    # CREW NECK T-SHIRT
    # -----------------------------------------------------------------------

    else:

        for poly in _sleeve_polygons(False):
            draw.polygon(
                s(poly),
                fill=(186, 255),
            )

        draw.polygon(
            s(_body_polygon(0, 0)),
            fill=(202, 255),
        )

        # Crew neckline
        draw.ellipse(
            sbox((252, 70, 348, 132)),
            fill=(150, 0),
        )

        # Ribbed collar
        draw.arc(
            sbox((250, 68, 350, 136)),
            start=8,
            end=172,
            fill=(172, 255),
            width=7 * scale,
        )

    # -----------------------------------------------------------------------
    # Final shading
    # -----------------------------------------------------------------------

    img = img.resize(
        (_W, _H),
        Image.LANCZOS,
    )

    shading = np.asarray(
        img.getchannel("L"),
        dtype=np.float32,
    )

    gradient = np.linspace(
        1.07,
        0.87,
        _H,
        dtype=np.float32,
    )[:, None]

    shading = np.clip(
        shading * gradient,
        0,
        255,
    ).astype(np.uint8)

    out = Image.merge(
        "LA",
        (
            Image.fromarray(
                shading,
                mode="L",
            ),
            img.getchannel("A"),
        ),
    )

    return out.filter(
        ImageFilter.GaussianBlur(0.8)
    )


# ---------------------------------------------------------------------------
# Template cache
# ---------------------------------------------------------------------------

_TEMPLATE_CACHE: dict[str, Image.Image] = {}


def _cached_template(garment_id: str) -> Image.Image:
    if garment_id not in _TEMPLATE_CACHE:
        _TEMPLATE_CACHE[garment_id] = _template(garment_id)

    return _TEMPLATE_CACHE[garment_id]


# ---------------------------------------------------------------------------
# Colour rendering
# ---------------------------------------------------------------------------

def render_garment(
    garment_id: str,
    color_hex: str,
) -> bytes:
    """Return a transparent PNG of the selected garment in the requested colour."""

    if garment_id not in CATALOG_BY_ID:
        raise KeyError(
            f"Unknown garment: {garment_id}"
        )

    template = _cached_template(
        garment_id
    )

    shading = (
        np.asarray(
            template.getchannel("L"),
            dtype=np.float32,
        )
        / 255.0
    )

    alpha = template.getchannel("A")

    target = np.array(
        [
            int(color_hex[i : i + 2], 16)
            for i in (1, 3, 5)
        ],
        dtype=np.float32,
    )

    tinted = np.clip(
        target[None, None, :]
        * (shading[:, :, None] / 0.78),
        0,
        255,
    ).astype(np.uint8)

    rgba = Image.fromarray(
        tinted,
        mode="RGB",
    ).convert("RGBA")

    rgba.putalpha(alpha)

    buf = io.BytesIO()

    rgba.save(
        buf,
        format="PNG",
    )

    return buf.getvalue()