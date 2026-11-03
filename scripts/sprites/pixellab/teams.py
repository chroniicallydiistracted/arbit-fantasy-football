"""Render staged frames in all 64 colour sets: checks every set renders and builds review sheets.
Usage: teams.py STAGING_DIR OUT_DIR"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import convert as V  # noqa: E402

TEAMS = ["ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
         "LAC", "LAR", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "LV", "PHI", "PIT", "SF", "SEA", "TB", "TEN", "WSH"]


def load(path):
    frames, name = {}, None
    for line in Path(path).read_text().splitlines():
        if line.startswith("== "):
            name = line[3:]; frames[name] = []
        elif name:
            frames[name].append(line)
    return frames


def grid(rows):
    w = max(map(len, rows))
    return np.array([list(r.ljust(w, ".")) for r in rows])


if __name__ == "__main__":
    staging, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    frames = {}
    for f in sorted(staging.glob("*.txt")):
        if f.name != "ball.txt":
            frames.update(load(f))
    names = list(frames)
    rendered = 0
    BG = (92, 104, 92, 255)
    cell = 52
    for skin in (0, 32):
        sheet = Image.new("RGBA", (cell * (len(names) + 1), cell * 32), BG)
        d = ImageDraw.Draw(sheet)
        for t in range(32):
            d.text((4, t * cell + 20), TEAMS[t], fill=(255, 255, 255))
            for i, n in enumerate(names):
                im = V.render(grid(frames[n]), t + skin)
                assert im.getbbox() is not None
                rendered += 1
                sheet.alpha_composite(im, (cell * (i + 1) + (cell - im.width) // 2, t * cell + cell - 2 - im.height))
        sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(out / f"all-teams-{'dark' if skin == 0 else 'light'}-skin.png")
    print(len(names), "frames x 64 colour sets =", rendered, "renders")
