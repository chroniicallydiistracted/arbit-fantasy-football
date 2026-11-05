"""Preview name tags without a background box, in team colors, for the owner to choose (OWN-037).

For each of the 32 teams, the two colors that best represent it without being black-like, taken
from the colors nflverse lists, first to fourth: the one that stands out most against the turf
fills the letters, the other outlines them. Each tag is drawn on the two turf shades of the review
renders, in three outline styles, beside today's boxed tag. The turf is a flat color sampled from
the renders, not the Gridiron field. Writes data/sprites/review/name-tags-preview.png.

Usage: uv run --with pillow python scripts/sprites/name_tag_preview.py
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/live"))
import positions as depth  # noqa: E402

TURF = ((87, 112, 72), (80, 105, 64))  # the light and dark stripes in the review renders
BLACKISH = 0.04  # relative luminance under this reads as black on the field
SIZE = 16  # the review renders' tag size
OUT = ROOT / "data/sprites/review/name-tags-preview.png"
SAMPLE = {"ARI": "K.Murray", "SEA": "J.Smith-Njigba", "CHI": "C.Williams", "PIT": "T.Watt"}
GONE = {"OAK", "SD", "STL", "LAR"}  # old abbreviations nflverse keeps


def rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(color: tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def pair(colors: list[str]) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    """The fill, the outline and the team's darkest color."""
    seen = list(dict.fromkeys(rgb(c) for c in colors))
    usable = [c for c in seen if luminance(c) >= BLACKISH] or [(255, 255, 255)]
    fill = max(usable, key=lambda c: min(contrast(c, turf) for turf in TURF))
    rest = [c for c in usable if c != fill]
    outline = max(rest, key=lambda c: contrast(c, fill)) if rest else (255, 255, 255)
    return fill, outline, min(seen, key=luminance)


def text(draw, x, y, words, font, fill, stroke=None, width=0) -> None:
    draw.text((x, y), words, font=font, fill=fill, stroke_width=width, stroke_fill=stroke)


def main() -> None:
    colors = {team: found for team, found in depth.team_colors().items() if team not in GONE}
    font = ImageFont.load_default(size=SIZE)
    small = ImageFont.load_default(size=13)
    columns = ("Today: boxed", "A: fill, outline in the 2nd color", "B: fill, thin dark outline", "C: fill, 2nd-color shadow")
    cell, row_h = 250, 30
    image = Image.new("RGB", (90 + cell * len(columns), 40 + row_h * len(colors) * 2), TURF[0])
    draw = ImageDraw.Draw(image)
    for index, title in enumerate(columns):
        text(draw, 90 + cell * index + 6, 10, title, small, (240, 240, 235))
    for row, (team, listed) in enumerate(sorted(colors.items())):
        fill, outline, dark = pair(listed)
        words = SAMPLE.get(team, f"{team[0]}.{team}")
        for stripe, turf in enumerate(TURF):
            y = 40 + (row * 2 + stripe) * row_h
            draw.rectangle((0, y, image.width, y + row_h), fill=turf)
            text(draw, 8, y + 7, team, small, (240, 240, 235))
            x = 90
            width = draw.textlength(words, font=font)
            draw.rectangle((x + 6, y + 4, x + 14 + width, y + 4 + SIZE + 4), fill=(10, 12, 14, 170))
            text(draw, x + 10, y + 5, words, font, (240, 240, 235))
            text(draw, x + cell + 10, y + 5, words, font, fill, outline, 2)
            text(draw, x + 2 * cell + 10, y + 5, words, font, fill, dark, 1)
            text(draw, x + 3 * cell + 11, y + 6, words, font, outline)
            text(draw, x + 3 * cell + 10, y + 5, words, font, fill)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT)
    print(f"Wrote {OUT.relative_to(ROOT)} for {len(colors)} teams")


if __name__ == "__main__":
    main()
