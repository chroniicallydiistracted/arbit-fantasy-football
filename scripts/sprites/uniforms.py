"""Real uniforms on the sprite frames (OWN-028).

Every color comes from the uniform sheet the team wore, measured at fixed places on Gridiron's sheet
template; nothing is chosen by hand. Shading follows the owner's original sheet, whose shades are
fixed multiples of a base color (`ramp`). Which part of the uniform a pixel shows comes from
assets/sprites/regions, made by scripts/sprites/pixellab/regions.py.

Gridiron sheets are licensed for personal use only (OWN-015): measured colors and anything painted
with them stay in ignored data/ folders. Painting and shading use the standard library only;
`measure_file` needs Pillow.
"""

import re
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "sprites"
RGB = tuple[int, int, int]

# Measured on the owner's sheet (assets/sprites/palette.json): every set follows these exactly.
# Each family has its highlight multiplier and its shades: a multiple of the base color, the
# highlight ("light"), or the highlight blended toward white ("lighter").
WHITE_BLEND = 0.31
SHADES: dict[str, tuple[float, dict[str, str | float]]] = {
    "helmet_pants": (1.234, {"j": "light", "n": "lighter", "b": 1.0, "a": 0.85}),
    "jersey_socks": (1.177, {"e": "light", "c": 1.0, "f": 0.622, "h": 0.41}),
    "trim": (1.234, {"k": "light", "m": "lighter", "i": 1.0, "o": 0.85, "q": 0.43}),
    "facemask": (217 / 115, {"p": "light", "l": 1.0}),
}
BASE_CLASS = {"helmet_pants": "b", "jersey_socks": "c", "trim": "i", "facemask": "l"}
FAMILY_OF = {cls: family for family, (_, shades) in SHADES.items() for cls in shades}

# Places on the 400x500 sheet template: (left, top, right, bottom).
TEMPLATE = {
    "helmet": (48, 15, 150, 111),
    "helmet_stripe": (188, 21, 213, 61),  # inside the swatch's frame
    "facemask": (140, 78, 152, 110),
    "jersey": (9, 117, 174, 250),
    "numbers": (64, 171, 112, 231),
    "pants": (36, 252, 148, 378),
    "pants_stripe": (184, 250, 216, 373),
    "socks": (40, 380, 66, 451),
    "cleats": (27, 453, 67, 490),
}
SHEET_SIZE = (400, 500)
OUTLINE: RGB = (149, 149, 149)
SAME = 28  # colors closer than this are one color: anti-aliasing and printed texture
DISTINCT = 36  # a trim must differ from the color under it by more than this
ACCENT_SHARE = 0.04  # and cover this much of its place, so edge blends never count as a trim
STRIPE_SHARE = 0.25  # a sock stripe survives shrinking to sprite size if it fills this much of a pixel


def distance(a: Sequence[float], b: Sequence[float]) -> float:
    return float(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) ** 0.5)


def ramp(color: Sequence[float], family: str) -> dict[str, RGB]:
    """Every shade of one family from a measured color, the way the owner's sheet shades its sets.
    A color is darkened only as far as needed for its highlight to fit, as the sheet does for white."""
    light, shades = SHADES[family]
    top = max(color)
    scale = min(1.0, 255 / (top * light)) if top else 1.0
    base = [c * scale for c in color]
    bright = [min(255.0, c * light) for c in base]
    values = {"light": bright, "lighter": [v + (255 - v) * WHITE_BLEND for v in bright]}
    out = {}
    for cls, shade in shades.items():
        rgb = values[shade] if isinstance(shade, str) else [c * shade for c in base]
        out[cls] = (round(rgb[0]), round(rgb[1]), round(rgb[2]))
    return out


def groups(colors: list[RGB]) -> list[tuple[RGB, int]]:
    """Colors merged with near neighbours, most common first; each group named by its commonest color."""
    merged: list[list] = []
    for color, n in Counter(colors).most_common():
        for group in merged:
            if distance(group[0], color) < SAME:
                group[1] += n
                break
        else:
            merged.append([color, n])
    return [(tuple(g[0]), g[1]) for g in sorted(merged, key=lambda g: -g[1])]


def measure_pixels(pixel: Callable[[int, int], RGB], width: int, height: int) -> dict:
    """Measure one sheet given its pixels. Background is the white reachable from the edges."""
    if (width, height) != SHEET_SIZE:
        raise ValueError(f"sheet is {width}x{height}, template is {SHEET_SIZE}")
    background = set()
    stack = [(x, y) for x in range(width) for y in (0, height - 1)] + [(x, y) for y in range(height) for x in (0, width - 1)]
    while stack:
        x, y = stack.pop()
        if 0 <= x < width and 0 <= y < height and (x, y) not in background and min(pixel(x, y)) >= 245:
            background.add((x, y))
            stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    def inside_an_area(x: int, y: int) -> bool:
        """Outlines and edge blends are a pixel or two wide; a filled area has like neighbours."""
        here = pixel(x, y)
        return all(
            0 <= nx < width and 0 <= ny < height and (nx, ny) not in background and distance(pixel(nx, ny), here) < SAME
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
        )

    def colors(box: tuple[int, int, int, int], rows: range | None = None, areas: bool = True) -> list[RGB]:
        """Drawn colors in a place. Thin parts like facemask bars pass areas=False."""
        left, top, right, bottom = box
        ys = rows if rows is not None else range(top, bottom)
        return [
            pixel(x, y)
            for y in ys
            for x in range(left, right)
            if (x, y) not in background
            and distance(pixel(x, y), OUTLINE) > 6
            and (not areas or inside_an_area(x, y))
        ]

    def main(box: tuple[int, int, int, int], areas: bool = True) -> RGB:
        found = groups(colors(box, areas=areas))
        if not found:
            raise ValueError(f"nothing drawn at {box}")
        return found[0][0]

    def accent(box: tuple[int, int, int, int], under: RGB) -> RGB | None:
        drawn = colors(box)
        for color, count in groups(drawn):
            if distance(color, under) > DISTINCT and count >= ACCENT_SHARE * len(drawn):
                return color
        return None

    helmet, jersey, pants = main(TEMPLATE["helmet"]), main(TEMPLATE["jersey"]), main(TEMPLATE["pants"])
    stripe_box = TEMPLATE["helmet_stripe"]
    has_stripe_view = len(colors(stripe_box)) > 100
    _, top, _, bottom = TEMPLATE["socks"]
    sock_rows = [groups(colors(TEMPLATE["socks"], range(y, y + 1))) for y in range(top, bottom)]
    return {
        "helmet": helmet,
        "helmet_stripe": accent(stripe_box, helmet) if has_stripe_view else None,
        "facemask": main(TEMPLATE["facemask"], areas=False),
        "jersey": jersey,
        "numbers": accent(TEMPLATE["numbers"], jersey),
        "pants": pants,
        "pants_stripe": accent(TEMPLATE["pants_stripe"], pants),
        "socks": [row[0][0] if row else None for row in sock_rows],
        "cleats": main(TEMPLATE["cleats"], areas=False),
    }


def measure_file(path: Path, version: int | None = None) -> dict:
    """Measure a sheet file. A few sheets are animated GIFs that alternate between two versions of
    the uniform (different socks, say); the site doesn't say which was worn, so one must be named."""
    from PIL import Image

    image = Image.open(path)
    versions = getattr(image, "n_frames", 1)
    if versions > 1 and version is None:
        raise ValueError(f"{path.name} shows {versions} versions of the uniform; name the one worn")
    image.seek(version or 0)
    image = image.convert("RGB")
    if image.size != SHEET_SIZE:  # the large sheets are the same drawing at 3.2 times the size
        image = image.resize(SHEET_SIZE, Image.NEAREST)
    data = image.load()
    assert data is not None
    measured = measure_pixels(lambda x, y: data[x, y], *image.size)
    measured["sheet"] = path.name if versions == 1 else f"{path.name} version {version}"
    return measured


def sock_color(socks: list[RGB | None], t: float, window: float = 0.1) -> RGB:
    """The sock at a point from its top (0) to its bottom (1). A stripe that fills enough of the
    stretch one sprite pixel covers wins over the sock's main color, so stripes don't vanish."""
    rows = [c for c in socks if c is not None]
    main = groups(rows)[0][0]
    n = len(socks)
    lo, hi = max(0, round((t - window) * (n - 1))), min(n - 1, round((t + window) * (n - 1)))
    here = [c for c in socks[lo : hi + 1] if c is not None]
    if not here:
        return main
    for color, count in groups(here):
        if distance(color, main) > DISTINCT and count >= STRIPE_SHARE * len(here):
            return color
    return groups(here)[0][0]


def load_regions() -> dict[str, list[str]]:
    regions: dict[str, list[str]] = {}
    for path in sorted((ASSETS / "regions").glob("*.txt")):
        for chunk in re.split(r"(?m)^== ", path.read_text()):
            if chunk.strip():
                name, *rows = chunk.strip("\n").split("\n")
                regions[name] = rows
    return regions


def paint(rows: list[str], regions: list[str], uniform: dict, skin: dict[str, Sequence[int]]) -> list[list[RGB | None]]:
    """Colors for one frame: uniform parts from the measured sheet, everything else (skin, outline,
    ball) from the owner's palette set `skin`, which maps a class to its color."""
    trims = {
        "H": uniform["helmet_stripe"] or uniform["helmet"],
        "J": uniform["numbers"] or uniform["jersey"],
        "P": uniform["pants_stripe"] or uniform["pants"],
    }
    bases = {"H": uniform["helmet"], "J": uniform["jersey"], "P": uniform["pants"]}
    out: list[list[RGB | None]] = []
    for row, part_row in zip(rows, regions, strict=True):
        line: list[RGB | None] = []
        for x, cls in enumerate(row):
            part = part_row[x] if x < len(part_row) else "."
            family = FAMILY_OF.get(cls)
            if cls == ".":
                line.append(None)
            elif part == "K":
                line.append(ramp(uniform["cleats"], "helmet_pants")["b"])
            elif part == "M" and family == "facemask":
                line.append(ramp(uniform["facemask"], "facemask")[cls])
            elif part.isdigit() and family in ("jersey_socks", "trim"):
                line.append(ramp(sock_color(uniform["socks"], int(part) / 9), family)[cls])
            elif part in bases and family == "trim":
                line.append(ramp(trims[part], "trim")[cls])
            elif part in bases and family in ("helmet_pants", "jersey_socks"):
                line.append(ramp(bases[part], family)[cls])
            else:
                color = skin[cls]
                line.append((color[0], color[1], color[2]))
        out.append(line)
    return out
