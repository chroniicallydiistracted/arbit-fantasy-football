"""Turn the official's PixelLab frames into frames in the repository's format (OWN-037).

The official was drawn by PixelLab from the owner's standing player (gen/official/1.png), then
posed with the skeleton animator (batch "official" in poses2.py). Officials never take team
colors, so their frames get a small fixed palette of their own, in assets/sprites/officials. The
shirt uses the jersey letters, so a renderer centers the body the same way as a player's. The
model painted a yellow flag and a motion streak into some frames; the flag is drawn on its own
as it flies (a script prop), so yellow pixels and anything not attached to the body are removed.
Run from data/sprites/pixellab-test. Usage: officials.py
"""

import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "assets/sprites/officials"
# The official's colors, by letter. e and h are the jersey letters, so the body centers on them.
PALETTE = {
    "#": (12, 12, 12),  # outline and shoes
    "a": (36, 36, 36),  # pants
    "h": (30, 30, 30),  # dark stripes
    "e": (250, 250, 250),  # white stripes
    "j": (245, 245, 245),  # cap
    "b": (128, 126, 124),  # grey shading
    "l": (200, 199, 199),  # light grey shading
    "d": (115, 64, 17),  # skin, shadow
    "g": (168, 98, 38),  # skin
}


def flag_or_streak(px: np.ndarray) -> np.ndarray:
    r, g, b = px[..., 0].astype(int), px[..., 1].astype(int), px[..., 2].astype(int)
    return (r > 170) & (g > 130) & (b < 110) & (r - b > 80)


def largest(mask: np.ndarray) -> np.ndarray:
    """Only the biggest 8-connected piece: the body, without streaks or a stray flag."""
    seen = np.zeros_like(mask)
    best: list[tuple[int, int]] = []
    for y, x in zip(*np.nonzero(mask), strict=True):
        if seen[y, x]:
            continue
        stack, piece = [(y, x)], []
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            piece.append((cy, cx))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        if len(piece) > len(best):
            best = piece
    keep = np.zeros_like(mask)
    for y, x in best:
        keep[y, x] = True
    return keep


def classify(path: Path, kps: list[dict], size: int) -> list[str]:
    px = np.array(Image.open(path).convert("RGBA"))
    solid = (px[..., 3] > 128) & ~flag_or_streak(px)
    solid = largest(solid)
    pt = {k["label"]: (k["x"] * size, k["y"] * size) for k in kps}
    neck = pt["NECK"][1]
    hip = (pt["RIGHT HIP"][1] + pt["LEFT HIP"][1]) / 2
    names = list(PALETTE)
    colors = np.array([PALETTE[n] for n in names], float)
    grid = np.full(solid.shape, ".", dtype="<U1")
    for y, x in zip(*np.nonzero(solid), strict=True):
        rgb = px[y, x, :3].astype(float)
        name = names[int(np.argmin(((colors - rgb) ** 2).sum(1)))]
        if name in ("a", "h", "#") and rgb.max() > 20:  # a dark cloth pixel: shirt or pants?
            name = "h" if neck - 1 <= y <= hip + 1 else "a"
        if name in ("e", "j"):  # white: the cap above the neck, the shirt's stripes below
            name = "j" if y < neck - 1 else "e"
        grid[y, x] = name
    ys, xs = np.nonzero(grid != ".")
    box = grid[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    return ["".join(row) for row in box]


def main() -> None:
    spec = json.load(open("batches/official.json"))
    lines = []
    for index, (label, kps) in enumerate(spec["frames"]):
        rows = classify(Path(f"gen/official-poses/{index + 1}.png"), kps, spec["size"])
        lines += [f"== {label}", *rows]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "official.txt").write_text("\n".join(lines) + "\n")
    (OUT / "palette.json").write_text(json.dumps({k: list(v) for k, v in PALETTE.items()}, indent=1) + "\n")
    print("wrote", len(spec["frames"]), "official frames to", OUT)


if __name__ == "__main__":
    main()
