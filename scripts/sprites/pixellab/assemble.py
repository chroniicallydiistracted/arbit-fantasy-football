"""Turn generated batches into frame files in the repository's format, plus hand and lift anchors.

Each frame keeps the colour classes, so one drawing serves all 32 teams and both skin tones.
Usage: assemble.py OUTDIR batch [batch ...]   (the fall uses its hybrid grids)
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path.cwd()  # run from the work folder, data/sprites/pixellab-test
sys.path.insert(0, str(Path(__file__).parent))
import convert as V  # noqa: E402

REF_CLASSES = {"run1": "#abcdefghijklno", "stand": "#abcdefghijklmnopq", "kneel": "#abcdefghijklmnp"}
FALL_NAMES = ["hit", "stumble", "fall_30", "fall_60", "ground"]
# Frames left out after review: replaced by a redraw, or not good enough to ship.
SKIP = {("kick", "arms_up"), ("catch_tackle", "tackle_dive"), ("redo_run", "stiff_arm")}
# Hand fixes after review, on the generation canvas: (frame, classes to clear, rows, columns).
# Motion streaks and the drawn ball are removed; the renderer draws the ball.
MANUAL = [
    ("run_knee", "a", range(33, 37), range(9, 17)),
    ("run_knee", "a", range(36, 42), range(29, 36)),
    ("drop_b", "a", range(51, 54), range(17, 25)),
    ("throw_cock", "a", range(53, 54), range(18, 20)),
    ("kick_swing", "a", range(32, 35), range(33, 42)),
    ("kick_strike", "a", range(25, 30), range(39, 48)),
    ("kick_strike", "dgh", range(40, 48), range(40, 47)),
    ("kick_follow", "dghal", range(24, 29), range(41, 49)),
    ("kick_follow", "dhl", range(29, 30), range(44, 47)),
    ("punt_strike", "#abcdefghijklmnopq", range(41, 48), range(38, 44)),
    ("punt_strike", "dl", range(36, 38), range(44, 47)),
    ("punt_follow", "al", range(10, 22), range(41, 48)),
    ("punt_follow", "a", range(52, 53), range(29, 31)),
    ("catch_high", "fh", range(3, 7), range(25, 30)),
    ("catch_low", "dh", range(39, 44), range(19, 26)),
    ("catch_low", "a", range(41, 45), range(19, 26)),
    ("catch_low", "a", range(37, 42), range(8, 11)),
    ("dive_catch", "#abcdefghijklmnopq", range(23, 29), range(36, 40)),
    ("recover", "a", range(36, 40), range(11, 20)),
]


def manual(label, g):
    for frame, classes, ys, xs in MANUAL:
        if frame == label:
            for y in ys:
                for x in xs:
                    if g[y, x] in classes:
                        g[y, x] = "."
    return g


def grid_rows(g):
    ys, xs = np.nonzero(g != ".")
    box = g[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return ["".join(r) for r in box], (int(xs.min()), int(ys.min()), int(ys.max()))


def anchors(kps, size, origin, bottom):
    pt = {k["label"]: (k["x"] * size, k["y"] * size) for k in kps}
    ox, oy = origin
    hand = lambda label: [round(pt[label][0] - ox, 1), round(pt[label][1] - oy, 1)]
    sx, sy = pt["RIGHT SHOULDER"]; hx, hy = pt["RIGHT HIP"]
    chest = [round(sx + (hx - sx) * 0.4 + 1.5 - ox, 1), round(sy + (hy - sy) * 0.4 - oy, 1)]
    return {"near_hand": hand("RIGHT ARM"), "far_hand": hand("LEFT ARM"), "chest": chest, "lift": max(0, (size - 5) - bottom)}


def batch_frames(name):
    if name == "fall":
        poses = json.load(open(Path(__file__).resolve().parent / "fall-poses.json"))[1:]
        for i, label in enumerate(FALL_NAMES):
            yield label, np.load(HERE / f"gen/fall-hybrid-{i + 1}.npy"), poses[i], 48
        return
    jobs = json.load(open(HERE / "gen/jobs.json"))[name]
    spec = json.load(open(HERE / f"batches/{name}.json"))
    allowed = set(REF_CLASSES[jobs["ref"]])
    for i, (label, kps) in enumerate(spec["frames"]):
        if label.endswith("_g") or (name, label) in SKIP:  # _g: comparison redraws of an original
            continue
        size = spec["size"]
        hands = [(k["x"] * size, k["y"] * size) for k in kps if k["label"] in ("RIGHT ARM", "LEFT ARM")]
        g, dist = V.to_grid_with_ball(HERE / f"gen/{name}/{i + 1}.png", allowed, hands, size)
        yield label, V.clean(V.strip_ball(manual(label, V.clean(g, dist))), dist), kps, spec["size"]


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    meta_path = out / "anchors.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    for name in sys.argv[2:]:
        lines = []
        for label, g, kps, size in batch_frames(name):
            rows, (x0, y0, y1) = grid_rows(g)
            lines += [f"== {label}", *rows]
            meta[label] = anchors(kps, size, (x0, y0), y1)
        (out / f"{name}.txt").write_text("\n".join(lines) + "\n")
        print(name, "->", out / f"{name}.txt")
    meta_path.write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n")
