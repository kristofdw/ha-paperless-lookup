"""Render the Paperless Lookup brand icon (original design) with Pillow.

A green document with text lines and a folded corner, and a blue magnifying glass with a small
house in the lens: looking up documents from home. Drawn at 4x and downscaled for smooth edges,
then trimmed and centered. Home Assistant shows ``brand/icon.png`` of a custom integration.

Usage (Pillow is part of the test environment):
    bash script/uv run python dev/make_icon.py custom_components/paperless_lookup/brand
"""

from pathlib import Path
import sys

from PIL import Image, ImageDraw

S = 4  # supersampling
W = 512 * S

GREEN = (46, 125, 50, 255)
FOLD = (129, 199, 132, 255)
WHITE = (255, 255, 255, 255)
BLUE = (3, 169, 244, 255)
BLUE_DARK = (1, 87, 155, 255)
LENS = (255, 255, 255, 255)


def p(*xy: float) -> list[float]:
    """Scale 512-pixel coordinates to the supersampled canvas."""
    return [v * S for v in xy]


def draw() -> Image.Image:
    """Draw the icon on a transparent, supersampled canvas."""
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Document with a cut top-right corner.
    left, top, right, bottom, fold = 72, 32, 352, 412, 72
    page = Image.new("L", (W, W), 0)
    pd = ImageDraw.Draw(page)
    pd.rounded_rectangle(p(left, top, right, bottom), radius=32 * S, fill=255)
    pd.polygon(p(right - fold, top - 2, right + 2, top - 2, right + 2, top + fold + 2), fill=0)
    img.paste(GREEN, (0, 0), page)
    # Folded corner: exactly the cut-off triangle, mirrored onto the page.
    d.polygon(p(right - fold, top, right - fold, top + fold, right, top + fold), fill=FOLD)

    # Text lines.
    for y, length in ((130, 170), (186, 200), (242, 120)):
        d.rounded_rectangle(p(left + 44, y, left + 44 + length, y + 26), radius=13 * S, fill=WHITE)

    # Magnifying glass: handle, ring, lens.
    cx, cy, r, ring = 318, 318, 112, 30
    d.line(p(cx + 70, cy + 70, 470, 470), fill=BLUE_DARK, width=50 * S)
    d.ellipse(p(470 - 25, 470 - 25, 470 + 25, 470 + 25), fill=BLUE_DARK)
    d.ellipse(p(cx - r, cy - r, cx + r, cy + r), fill=BLUE)
    d.ellipse(p(cx - r + ring, cy - r + ring, cx + r - ring, cy + r - ring), fill=LENS)

    # House in the lens.
    d.polygon(p(cx, cy - 52, cx + 52, cy - 6, cx - 52, cy - 6), fill=BLUE)
    d.rectangle(p(cx - 38, cy - 10, cx + 38, cy + 46), fill=BLUE)
    d.rectangle(p(cx - 11, cy + 12, cx + 11, cy + 46), fill=LENS)
    return img


def square(img: Image.Image, margin: float = 0.02) -> Image.Image:
    """Trim transparent borders and center on a square canvas with a small margin."""
    bbox = img.getbbox()
    if bbox is None:
        raise ValueError("Empty icon")
    cropped = img.crop(bbox)
    side = int(max(cropped.size) * (1 + 2 * margin))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2))
    return canvas


def main() -> None:
    """Write icon.png and icon@2x.png (and optionally a light/dark preview)."""
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    icon = square(draw())
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        icon.resize((size, size), Image.Resampling.LANCZOS).save(out / name, optimize=True)
    if len(sys.argv) > 2:
        preview = Image.new("RGBA", (1100, 560), (255, 255, 255, 255))
        dark = Image.new("RGBA", (530, 560), (17, 17, 17, 255))
        preview.paste(dark, (570, 0))
        big = icon.resize((512, 512), Image.Resampling.LANCZOS)
        preview.alpha_composite(big, (24, 24))
        preview.alpha_composite(big, (570 + 9, 24))
        preview.save(sys.argv[2])


if __name__ == "__main__":
    main()
