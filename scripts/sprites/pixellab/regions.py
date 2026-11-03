"""Say which part of the uniform each pixel of every frame belongs to, so real uniforms can be painted on.

The owner's art shares classes between helmet and pants, and between jersey and socks, because every
team on the original sheet wore one color on both. Real uniforms don't (OWN-028), so each pixel is
assigned to the nearest bone of the skeleton the frame was drawn from, choosing only among the parts
its class can be. Writes assets/sprites/regions/<group>.txt. Run from data/sprites/pixellab-test.

Letters: H helmet, M facemask, J jersey, P pants, K cleats, 0-9 socks from top (0) to bottom (9),
. anything else (skin, outline, ball, empty).
Usage: regions.py [check]   (check prints a contact sheet path instead of writing)
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path.cwd()
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/sprites"))
sys.path.insert(0, str(Path(__file__).parent))
import frames as F  # noqa: E402
from assemble import FALL_NAMES  # noqa: E402
from poses2 import HAND  # noqa: E402

HELMET_PANTS, JERSEY_SOCKS, TRIM, MASK = set("jnba"), set("echf"), set("kmioq"), set("lp")
# Frames whose batch was redrawn: the installed one came from the later batch.
SOURCE = {"arms_up": "redo_stand", "tackle_dive": "redo_run"}


def skeletons():
    """Joints for every frame that has them, in the frame's own pixel coordinates."""
    anchors = F.anchors()
    raw = {name: dict(joints) for name, joints in HAND.items()}
    for path in sorted((HERE / "batches").glob("*.json")):
        spec = json.loads(path.read_text())
        for label, kps in spec["frames"]:
            if SOURCE.get(label, path.stem) == path.stem:
                raw.setdefault(label, {k["label"]: (k["x"] * spec["size"], k["y"] * spec["size"]) for k in kps})
    falls = json.loads((Path(__file__).parent / "fall-poses.json").read_text())[1:]
    for label, kps in zip(FALL_NAMES, falls, strict=True):
        raw[label] = {k["label"]: (k["x"] * 48, k["y"] * 48) for k in kps}
    out = {}
    for name, joints in raw.items():
        if name in anchors:
            hx, hy = anchors[name]["near_hand"]
            ox, oy = joints["RIGHT ARM"][0] - hx, joints["RIGHT ARM"][1] - hy
            out[name] = {k: np.array([x - ox, y - oy]) for k, (x, y) in joints.items()}
    return out


def seg_distance(p, a, b):
    ab = b - a
    t = np.clip(np.dot(p - a, ab) / max(np.dot(ab, ab), 1e-9), 0, 1)
    return float(np.linalg.norm(p - (a + t * ab))), float(t)


def parts(j):
    mid_hip = (j["RIGHT HIP"] + j["LEFT HIP"]) / 2
    head = np.mean([j[k] for k in ("NOSE", "RIGHT EYE", "LEFT EYE", "RIGHT EAR", "LEFT EAR")], axis=0)
    return {
        "head": [(j["NECK"], head), (head, j["NOSE"])],
        "torso": [(j["NECK"], mid_hip), (j["RIGHT SHOULDER"], j["RIGHT HIP"]), (j["LEFT SHOULDER"], j["LEFT HIP"]),
                  (j["RIGHT SHOULDER"], j["LEFT SHOULDER"]),
                  (j["RIGHT SHOULDER"], j["RIGHT ELBOW"]), (j["RIGHT ELBOW"], j["RIGHT ARM"]),
                  (j["LEFT SHOULDER"], j["LEFT ELBOW"]), (j["LEFT ELBOW"], j["LEFT ARM"])],
        "thighs": [(j["RIGHT HIP"], j["RIGHT KNEE"]), (j["LEFT HIP"], j["LEFT KNEE"]), (j["RIGHT HIP"], j["LEFT HIP"])],
        "shins": [(j["RIGHT KNEE"], j["RIGHT LEG"]), (j["LEFT KNEE"], j["LEFT LEG"])],
    }


def nearest(p, segments):
    return min(seg_distance(p, a, b)[0] for a, b in segments)


def by_skeleton(rows, joints):
    width = max(map(len, rows))
    grid = [row.ljust(width, ".") for row in rows]
    out = [["."] * width for _ in grid]
    bones = parts(joints)
    legs = [(joints["RIGHT KNEE"], joints["RIGHT LEG"]), (joints["LEFT KNEE"], joints["LEFT LEG"])]
    socks = {0: [], 1: []}
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            p = np.array([x + 0.5, y + 0.5])
            d = {name: nearest(p, segs) for name, segs in bones.items()}
            if cell in HELMET_PANTS:
                out[y][x] = "H" if d["head"] < d["thighs"] else "P"
            elif cell in JERSEY_SOCKS:
                out[y][x] = "S" if d["shins"] < d["torso"] else "J"
            elif cell in TRIM:
                out[y][x] = {"head": "H", "torso": "J", "thighs": "P", "shins": "S"}[min(d, key=d.get)]
            elif cell in MASK:
                out[y][x] = "M" if d["head"] < 4.5 and d["head"] <= min(d.values()) + 0.01 else "."
            elif cell == "#":
                for knee, ankle in legs:
                    dist, t = seg_distance(p, knee, ankle)
                    if np.linalg.norm(p - ankle) < 3.2 and t > 0.8 and dist < 3.2:
                        out[y][x] = "K"
            if out[y][x] == "S":
                leg = min((0, 1), key=lambda i: seg_distance(p, *legs[i])[0])
                socks[leg].append((y, x, seg_distance(p, *legs[leg])[1]))
    for cells in socks.values():
        if cells:
            ts = [t for _, _, t in cells]
            lo, hi = min(ts), max(ts)
            for y, x, t in cells:
                out[y][x] = str(min(9, round(9 * (t - lo) / max(hi - lo, 1e-9))))
    return ["".join(r) for r in keep_cleats_on_socks(out)]


def keep_cleats_on_socks(out):
    """A cleat pixel must join a sock through other cleat pixels, so stray outline near an ankle stays outline."""
    height, width = len(out), len(out[0])
    seen, stack = set(), [(y, x) for y in range(height) for x in range(width) if out[y][x].isdigit()]
    while stack:
        y, x = stack.pop()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width and out[ny][nx] == "K" and (ny, nx) not in seen:
                    seen.add((ny, nx))
                    stack.append((ny, nx))
    return [[c if c != "K" or (y, x) in seen else "." for x, c in enumerate(row)] for y, row in enumerate(out)]


def by_rows(rows):
    """For the one original with no skeleton (arm, standing upright): parts by height on the body."""
    width = max(map(len, rows))
    grid = [row.ljust(width, ".") for row in rows]
    jersey_rows = [y for y, row in enumerate(grid) if sum(c in JERSEY_SOCKS for c in row) >= 3]
    top = jersey_rows[0]
    pants_rows = [y for y, row in enumerate(grid) if y > top and sum(c in HELMET_PANTS for c in row) >= 3]
    waist = pants_rows[0] if pants_rows else len(grid)
    knee = pants_rows[-1] if pants_rows else len(grid)
    sock_rows = [y for y in range(knee + 1, len(grid)) if any(c in JERSEY_SOCKS for c in grid[y])]
    out = []
    for y, row in enumerate(grid):
        line = []
        for c in row:
            if c in HELMET_PANTS:
                line.append("H" if y < top + 2 else "P")
            elif c in JERSEY_SOCKS:
                line.append(str(round(9 * (y - sock_rows[0]) / max(1, sock_rows[-1] - sock_rows[0]))) if y > knee else "J")
            elif c in TRIM:
                line.append("H" if y < top else "J" if y < waist else "P")
            elif c in MASK:
                line.append("M" if y < top + 2 else ".")
            elif c == "#" and sock_rows and y > sock_rows[-1]:
                line.append("K")
            else:
                line.append(".")
        out.append("".join(line))
    return out


def build():
    joints = skeletons()
    groups = {}
    for group, frames in F.load_groups().items():
        groups[group] = {name: by_skeleton(rows, joints[name]) if name in joints else by_rows(rows) for name, rows in frames.items()}
    return groups


if __name__ == "__main__":
    groups = build()
    if sys.argv[1:] == ["check"]:
        from PIL import Image
        colors = {"H": (230, 60, 60), "M": (250, 250, 120), "J": (60, 120, 240), "P": (60, 200, 90), "K": (250, 160, 0)}
        frames = F.all_frames()
        cells = [(name, rows) for g in groups.values() for name, rows in g.items()]
        columns = 8
        sheet = Image.new("RGB", (columns * 100, -(-len(cells) // columns) * 56), (40, 40, 40))
        for i, (name, rows) in enumerate(cells):
            left, top = (i % columns) * 100, (i // columns) * 56 + 2
            for y, row in enumerate(rows):
                for x, c in enumerate(row):
                    f = frames[name][y][x] if x < len(frames[name][y]) else "."
                    if f != ".":
                        base = (90, 70, 60) if f in "gdBC" else (0, 0, 0) if f == "#" else (150, 150, 150)
                        col = colors.get(c, (110 + int(c) * 16, 0, 250 - int(c) * 16) if c.isdigit() else base)
                        sheet.putpixel((left + x, top + y), col)
        out = HERE / "regions-check.png"
        sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST).save(out)
        print(out)
    else:
        target = ROOT / "assets/sprites/regions"
        target.mkdir(exist_ok=True)
        for group, frames in groups.items():
            (target / f"{group}.txt").write_text("".join(f"== {n}\n" + "\n".join(r) + "\n" for n, r in frames.items()))
        print("wrote", sum(map(len, groups.values())), "region maps to", target)
